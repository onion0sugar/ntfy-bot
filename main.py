"""MSSQL → ntfy: powiadomienia o nowych i gotowych zamówieniach."""
from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys
import time
from collections import Counter
from types import SimpleNamespace

from config import ConfigError, load_config
from db import COURIER_QUERY_FILE, READY_USERS_QUERY_FILE, WORK_TODAY_USERS_QUERY_FILE, DbError, connect_db, fetch_courier_rows, fetch_top_ready_user, fetch_work_today_users, load_query
from ntfy import Ntfy, NtfyError
from state import courier_changed, open_state
from users import load_users

logger = logging.getLogger("bot")
RECONNECT_DELAY = 5
DEFAULT_NEW_TEXT = "{}"
ORDER_URL = "https://it.serwis-kop.pl/magazyn/pl/warehouse/collectingcustomerorders/view/{}"


def build_new_order_messages(
    orders: list[tuple[int | None, str, int | None]],
    users: set[str],
    work_today: dict[str, int],
    busy: set[str],
    supervisor_topic: str,
) -> list[tuple[str, str, str, str, str | None]]:
    """Zbuduj osobne powiadomienie dla każdego zamówienia i odbiorcy."""
    messages: list[tuple[str, str, str, str, str | None]] = []
    notified_groups: set[int | None] = set()
    for order_id, order_number, zone_group_id in orders:
        # `orders` są posortowane od najstarszego. Dla jednej grupy
        # powiadamiamy tylko o pierwszym (najstarszym) zamówieniu.
        if zone_group_id in notified_groups:
            continue
        notified_groups.add(zone_group_id)
        click_url = ORDER_URL.format(order_id) if order_id is not None else None
        displayed_number = f"{order_number} (grupa: {zone_group_id if zone_group_id is not None else 'brak'})"
        text = DEFAULT_NEW_TEXT.format(displayed_number)
        messages.append((supervisor_topic, text, "Nowe zamówienie", "default", click_url))
        if zone_group_id is None:
            continue
        messages.extend(
            (login, text, "Nowe zamówienie", "default", click_url)
            for login in users
            if login in work_today and login not in busy and zone_group_id <= work_today[login]
        )
    return messages


async def _sleep_until(stop: asyncio.Event, seconds: float) -> None:
    try:
        await asyncio.wait_for(stop.wait(), timeout=seconds)
    except asyncio.TimeoutError:
        pass


async def _send_batch(ntfy: Ntfy, messages: list[tuple[str, str, str, str, str | None]], limit: int) -> None:
    semaphore = asyncio.Semaphore(limit)

    async def send(topic: str, text: str, title: str, priority: str, click: str | None) -> None:
        async with semaphore:
            await ntfy.publish_to(topic, text, title, priority, click)

    for start in range(0, len(messages), limit):
        results = await asyncio.gather(*(send(*item) for item in messages[start:start + limit]), return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                logger.error("Notification failed: %s", result)


async def run_service(cfg: SimpleNamespace, stop: asyncio.Event | None = None) -> int:
    stop = stop or asyncio.Event()
    courier_query = load_query(COURIER_QUERY_FILE)
    ready_users_query = load_query(READY_USERS_QUERY_FILE)
    work_today_users_query = load_query(WORK_TODAY_USERS_QUERY_FILE)
    users = load_users(cfg.users_file)
    state = open_state(cfg.state_file)
    ntfy = Ntfy(cfg)
    db = None
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            pass

    latest_orders: list[tuple[int | None, str, int | None]] = []
    latest_busy: set[str] = set()
    latest_work_today: dict[str, int] = {}
    latest_ready_messages: list[tuple[str, str, str, str, str | None]] = []
    poll_finished = asyncio.Event()

    async def poll_loop() -> None:
        nonlocal db, latest_orders, latest_busy, latest_ready_messages, latest_work_today
        while not stop.is_set():
            try:
                if db is None:
                    db = connect_db(cfg)
                with db.cursor() as cursor:
                    courier_rows = fetch_courier_rows(cursor, courier_query)
                    latest_work_today = fetch_work_today_users(cursor, work_today_users_query, users)
                    ready_messages: list[tuple[str, str, str, str, str | None]] = []
                    ready_users: set[str] = set()
                    for row in courier_rows:
                        if row.doc_id is not None:
                            courier_changed(state, row.doc_id, row.courier_id, row.status, row.user_name)
                        if row.document_type == "22" and row.courier_id == str(cfg.courier_id) and row.status in {"new", "in_progress"} and row.item_count == 0 and row.number:
                            top_users = fetch_top_ready_user(cursor, ready_users_query, row.number)
                            top_user = top_users[0] if top_users else None
                            ready_text = row.number
                            click_url = ORDER_URL.format(top_user[2]) if top_user else None
                            if top_user:
                                ready_users.add(top_user[0])
                                ready_text += "\n" + "\n".join(f"{login} ({count})" for login, count, _document_id in top_users)
                                if top_user[0] in users:
                                    ready_messages.append((top_user[0], ready_text, "Gotowe do wydania", "max", click_url))
                            ready_messages.append((cfg.supervisor_topic, ready_text, "Gotowe do wydania", "max", click_url))
                    latest_orders = sorted(
                        [(row.doc_id, row.number, row.zone_group_id) for row in courier_rows if row.document_type == "7" and row.status == "new" and row.number],
                        key=lambda order: (order[0] is None, order[0] if order[0] is not None else 0, order[1]),
                    )
                    latest_busy = {
                        row.user_name for row in courier_rows
                        if row.user_name and row.status == "in_progress"
                        and (row.document_type == "7" or (row.document_type == "22" and row.item_count > 0))
                    } | ready_users
                    latest_ready_messages = ready_messages
                free_recipients = sum(
                    login in latest_work_today and login not in latest_busy
                    for login in users
                )
                working_by_group = Counter(latest_work_today.values())
                working_groups = ", ".join(
                    f"{group}:{working_by_group[group]}"
                    for group in sorted(working_by_group)
                ) or "brak"
                logger.info(
                    "Poll OK; new orders: %d, busy: %d, working: %s, free: %d",
                    len(latest_orders),
                    len(latest_busy),
                    working_groups,
                    free_recipients,
                )
                poll_finished.set()
                await _sleep_until(stop, cfg.poll_interval)
            except DbError as exc:
                logger.error("MSSQL error: %s", exc)
                if db is not None:
                    db.close()
                db = None
                await _sleep_until(stop, RECONNECT_DELAY)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Error in poll loop")
                await _sleep_until(stop, RECONNECT_DELAY)

    async def announce_loop() -> None:
        while not stop.is_set():
            if cfg.announce_interval == 0:
                await poll_finished.wait()
                poll_finished.clear()
            else:
                await _sleep_until(stop, cfg.announce_interval)
            if stop.is_set():
                break
            messages = list(latest_ready_messages)
            if latest_orders:
                # Każde zamówienie wysyłamy osobno. Dzięki temu przy kilku
                # zamówieniach w różnych grupach odbiorca dostaje tylko te,
                # które może obsłużyć (np. grupa 1 nie dostanie grupy 2).
                order_messages = build_new_order_messages(
                    latest_orders, users, latest_work_today, latest_busy, cfg.supervisor_topic
                )
                messages.extend(order_messages)
                for _topic, text, _title, _priority, _click_url in order_messages:
                    logger.info("%s", text)
            if cfg.send_text and messages:
                await _send_batch(ntfy, messages, cfg.max_notifications_per_batch)

    poll_task = asyncio.create_task(poll_loop())
    announce_task = asyncio.create_task(announce_loop())
    try:
        await stop.wait()
    finally:
        poll_task.cancel()
        announce_task.cancel()
        await asyncio.gather(poll_task, announce_task, return_exceptions=True)
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
        load_query(COURIER_QUERY_FILE)
        load_query(READY_USERS_QUERY_FILE)
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
            "TEST-7",
            "Nowe zamówienie",
            "default",
            ORDER_URL.format("TEST-7"),
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
