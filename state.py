"""Mały lokalny stan, aby nie ponawiać tego samego przypisania kuriera."""

from __future__ import annotations

import sqlite3


def open_state(path: str = "state.db") -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE IF NOT EXISTS courier_seen (doc_id INTEGER PRIMARY KEY, courier_id TEXT, status TEXT, user_name TEXT, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)")
    conn.execute("CREATE TABLE IF NOT EXISTS finished_orders (doc_id INTEGER PRIMARY KEY, user_name TEXT NOT NULL, packaged_position_count INTEGER NOT NULL, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)")
    conn.commit()
    return conn


def save_finished_order(conn: sqlite3.Connection, doc_id: int, user_name: str, packaged_position_count: int) -> None:
    conn.execute(
        "INSERT INTO finished_orders(doc_id, user_name, packaged_position_count) VALUES(?,?,?) "
        "ON CONFLICT(doc_id) DO UPDATE SET user_name=excluded.user_name, "
        "packaged_position_count=excluded.packaged_position_count, updated_at=CURRENT_TIMESTAMP",
        (doc_id, user_name, packaged_position_count),
    )
    conn.commit()


def top_finished_users(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT user_name FROM finished_orders "
        "WHERE packaged_position_count = (SELECT MAX(packaged_position_count) FROM finished_orders)"
    ).fetchall()
    return {str(row[0]).strip() for row in rows if row[0]}


def courier_changed(conn, doc_id: int, courier_id: str, status: str, user_name: str) -> bool:
    row = conn.execute("SELECT courier_id, status, user_name FROM courier_seen WHERE doc_id=?", (doc_id,)).fetchone()
    changed = row is None or tuple(row) != (courier_id, status, user_name)
    conn.execute(
        "INSERT INTO courier_seen(doc_id,courier_id,status,user_name) VALUES(?,?,?,?) "
        "ON CONFLICT(doc_id) DO UPDATE SET courier_id=excluded.courier_id,status=excluded.status,user_name=excluded.user_name,updated_at=CURRENT_TIMESTAMP",
        (doc_id, courier_id, status, user_name),
    )
    conn.commit()
    return changed
