"""MSSQL → ntfy: powiadomienia o nowych i gotowych zamówieniach."""
from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys
import time
from types import SimpleNamespace

from config import ConfigError, load_config
from db import BUSY_QUERY_FILE, COURIER_QUERY_FILE, DbError, connect_db, fetch_busy_users, fetch_courier_rows, get_next_order, load_query
from ntfy import Ntfy, NtfyError
from state import courier_changed, open_state, save_finished_order, top_finished_users
from users import load_users

logger = logging.getLogger("bot")
RECONNECT_DELAY = 5
DEFAULT_NEW_TEXT = "{}"
DEFAULT_READY_TEXT = "{}"
ORDER_URL = "https://it.serwis-kop.pl/magazyn/pl/warehouse/collectingcustomerorders/view/{}"


async def _sleep_until(stop: asyncio.Event, seconds: float) -> None:
    try:
        await asyncio.wait_for(stop.wait(), timeout=seconds)
    except asyncio.TimeoutError:
        pass


async def _send_batch(ntfy: Ntfy, messages: list[tuple[str, str, str, str]], limit: int) -> None:
    semaphore = asyncio.Semaphore(limit)

    async def send(topic: str, text: str, title: str, priority: str) -> None:
        async with semaphore:
            await ntfy.publish_to(topic, text, title, priority)

    for start in range(0, len(messages), limit):
        results = await asyncio.gather(*(send(*item) for item in messages[start:start + limit]), return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                logger.error("Notification failed: %s", result)


async def run_service(cfg: SimpleNamespace, stop: asyncio.Event | None = None) -> int:
    stop = stop or asyncio.Event()
    query = load_query()
    busy_query = load_query(BUSY_QUERY_FILE)
    courier_query = load_query(COURIER_QUERY_FILE)
    users = load_users(cfg.users_file)
    state = open_state(cfg.state_file)
    ntfy = Ntfy(cfg)
    db = None
    next_poll = time.monotonic()
    last_new_order: tuple[int | None, str] | None = None
    last_new_announcement = 0.0
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            pass

    try:
        while not stop.is_set():
            try:
                now = time.monotonic()
                if now < next_poll:
                    await _sleep_until(stop, next_poll - now)
                    continue
                if db is None:
                    db = connect_db(cfg)
                with db.cursor() as cursor:
                    new_order = get_next_order(cursor, query)
                    busy7 = fetch_busy_users(cursor, busy_query)
                    courier_rows = fetch_courier_rows(cursor, courier_query)

                ready_users: set[str] = set()
                busy22: set[str] = set()
                messages: list[tuple[str, str, str, str]] = []
                # Najpierw zapisz wszystkie zakończone zamówienia typu 7 z tego pollingu.
                for row in courier_rows:
                    if row.document_type == "7" and row.status == "end" and row.doc_id is not None and row.user_name and row.packaged_position_count is not None:
                        save_finished_order(state, row.doc_id, row.user_name, row.packaged_position_count)
                for row in courier_rows:
                    if row.user_name:
                        if row.status == "in_progress":
                            busy22.add(row.user_name)
                    if row.doc_id is not None:
                        changed = courier_changed(state, row.doc_id, row.courier_id, row.status, row.user_name)
                        if changed and row.document_type == "22" and row.courier_id == str(cfg.courier_id) and row.status != "end":
                            ready_users = top_finished_users(state)
                            for login in ready_users:
                                messages.append((login, DEFAULT_READY_TEXT.format(row.number), "Gotowe do wydania", "max"))
                            messages.append((cfg.supervisor_topic, DEFAULT_READY_TEXT.format(row.number), "Gotowe do wydania", "max"))
                            logger.info("Ready order %s; recipients: %s", row.number, ", ".join(sorted(ready_users)) or "none")

                # Gotowe do wydania i typ 22 in_progress mają pierwszeństwo nad nowymi.
                busy = busy7 | busy22 | ready_users
                if new_order:
                    _order_id, number = new_order
                    if messages:
                        logger.info("New order %s skipped because a ready-order notification has priority", number)
                    else:
                        new_order_text = ORDER_URL.format(_order_id) if _order_id is not None else number
                        order_key = (_order_id, number)
                        announce = (
                            order_key != last_new_order
                            or cfg.announce_interval == 0
                            or now - last_new_announcement >= cfg.announce_interval
                        )
                        if announce:
                            last_new_order = order_key
                            last_new_announcement = now
                            messages.append((cfg.supervisor_topic, DEFAULT_NEW_TEXT.format(new_order_text), "Nowe zamówienie", "default"))
                            for login in users:
                                if login not in busy:
                                    messages.append((login, DEFAULT_NEW_TEXT.format(new_order_text), "Nowe zamówienie", "default"))
                            logger.info("New order %s; free recipients: %d plus supervisor", number, sum(login not in busy for login in users))
                        else:
                            logger.info("New order %s; notification skipped (announce interval)", number)
                else:
                    last_new_order = None
                    logger.info("Query OK — no new orders")
                if cfg.send_text and messages:
                    await _send_batch(ntfy, messages, cfg.max_notifications_per_batch)
                next_poll = now + cfg.poll_interval
            except DbError as exc:
                logger.error("MSSQL error: %s", exc)
                if db is not None:
                    db.close()
                db = None
                await _sleep_until(stop, RECONNECT_DELAY)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Error in main loop")
                await _sleep_until(stop, RECONNECT_DELAY)
    finally:
        if db is not None:
            db.close()
        state.close()
        await ntfy.close()
    logger.info("Stopped")
    return 0


def test_db(cfg: SimpleNamespace) -> int:
    try:
        db = connect_db(cfg)
        with db.cursor() as cursor:
            cursor.execute("SELECT 1")
            assert cursor.fetchone()[0] == 1
        db.close()
        load_query()
        load_query(BUSY_QUERY_FILE)
        load_query(COURIER_QUERY_FILE)
        load_users(cfg.users_file)
    except Exception as exc:
        logger.error("DB test FAILED: %s", exc)
        return 1
    logger.info("DB test OK")
    return 0


async def test_ntfy(cfg: SimpleNamespace) -> int:
    try:
        await Ntfy(cfg).publish_to(cfg.ntfy_topic, "Test wiadomości z bota MSSQL")
    except NtfyError as exc:
        logger.error("ntfy test FAILED: %s", exc)
        return 1
    return 0


async def test_new_notification(cfg: SimpleNamespace) -> int:
    topic = cfg.test_topic or cfg.supervisor_topic
    ntfy = Ntfy(cfg)
    try:
        await ntfy.publish_to(
            topic,
            ORDER_URL.format("TEST-7"),
            "Nowe zamówienie",
            "default",
        )
    except NtfyError as exc:
        logger.error("New notification test FAILED: %s", exc)
        return 1
    finally:
        await ntfy.close()
    logger.info("New notification test OK: sent to %s", topic)
    return 0


async def test_ready_notification(cfg: SimpleNamespace) -> int:
    topic = cfg.test_topic or cfg.supervisor_topic
    ntfy = Ntfy(cfg)
    try:
        await ntfy.publish_to(topic, "TEST-22", "Gotowe do wydania", "max")
    except NtfyError as exc:
        logger.error("Ready notification test FAILED: %s", exc)
        return 1
    finally:
        await ntfy.close()
    logger.info("Ready notification test OK: sent to %s", topic)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="MSSQL -> ntfy")
    parser.add_argument("--test-db", action="store_true")
    parser.add_argument("--test-ntfy", "--test-text", dest="test_ntfy", action="store_true")
    parser.add_argument("--test-new", action="store_true")
    parser.add_argument("--test-ready", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        cfg = load_config()
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    if args.test_db:
        return test_db(cfg)
    if args.test_ntfy:
        return asyncio.run(test_ntfy(cfg))
    if args.test_new:
        return asyncio.run(test_new_notification(cfg))
    if args.test_ready:
        return asyncio.run(test_ready_notification(cfg))
    try:
        return asyncio.run(run_service(cfg))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
