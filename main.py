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
from state import courier_changed, open_state
from users import load_mapping

logger = logging.getLogger("bot")
RECONNECT_DELAY = 5
DEFAULT_NEW_TEXT = "🔔 Nowe zamówienie: {}"
DEFAULT_READY_TEXT = "📦 Zamówienie gotowe do wydania: {}"


async def _sleep_until(stop: asyncio.Event, seconds: float) -> None:
    try:
        await asyncio.wait_for(stop.wait(), timeout=seconds)
    except asyncio.TimeoutError:
        pass


async def _send_batch(ntfy: Ntfy, messages: list[tuple[str, str, str]], limit: int) -> None:
    semaphore = asyncio.Semaphore(limit)

    async def send(topic: str, text: str, title: str) -> None:
        async with semaphore:
            await ntfy.publish_to(topic, text, title)

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
    mapping = load_mapping(cfg.mapping_file)
    state = open_state()
    ntfy = Ntfy(cfg)
    db = None
    next_poll = time.monotonic()
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
                messages: list[tuple[str, str, str]] = []
                for row in courier_rows:
                    if row.user_name:
                        if row.status == "in_progress":
                            busy22.add(row.user_name)
                        if row.courier_id == str(cfg.courier_id) and row.status == "new":
                            ready_users.add(row.user_name)
                    if row.doc_id is not None:
                        changed = courier_changed(state, row.doc_id, row.courier_id, row.status, row.user_name)
                        # Typ 22 in_progress jest wyłącznie blokadą — nigdy nie wysyła alertu.
                        if changed and row.courier_id == str(cfg.courier_id) and row.status == "new":
                            topics = mapping.get(row.user_name)
                            if topics:
                                messages.append((topics["ready_order_topic"], DEFAULT_READY_TEXT.format(row.number), "Gotowe do wydania"))

                # Gotowe do wydania i typ 22 in_progress mają pierwszeństwo nad nowymi.
                busy = busy7 | busy22 | ready_users
                if new_order:
                    _order_id, number = new_order
                    for login, topics in mapping.items():
                        if login not in busy:
                            messages.append((topics["new_order_topic"], DEFAULT_NEW_TEXT.format(number), "Nowe zamówienie"))
                    logger.info("New order %s; free recipients: %d", number, sum(login not in busy for login in mapping))
                else:
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
        load_mapping(cfg.mapping_file)
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


def main() -> int:
    parser = argparse.ArgumentParser(description="MSSQL -> ntfy")
    parser.add_argument("--test-db", action="store_true")
    parser.add_argument("--test-ntfy", "--test-text", dest="test_ntfy", action="store_true")
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
    try:
        return asyncio.run(run_service(cfg))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
