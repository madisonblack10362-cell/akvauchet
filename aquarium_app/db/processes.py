"""Операции с процессами."""
from __future__ import annotations

import datetime as dt
import sqlite3


def add_process(conn: sqlite3.Connection, aquarium_id: int, title: str,
                started_at: str, expected_days: float = None,
                note: str = None) -> None:
    created_at = dt.datetime.now().isoformat()
    conn.execute("""
        INSERT INTO processes (aquarium_id, title, started_at, expected_days, note, created_at)
        VALUES (?,?,?,?,?,?)
    """, (aquarium_id, title, started_at, expected_days, note, created_at))
    conn.commit()


def get_active_processes(conn: sqlite3.Connection, aquarium_id: int) -> list:
    return conn.execute("""
        SELECT * FROM processes
        WHERE aquarium_id=? AND archived=0
        ORDER BY started_at DESC, id DESC
    """, (aquarium_id,)).fetchall()


def get_process(conn: sqlite3.Connection, process_id: int):
    return conn.execute("SELECT * FROM processes WHERE id=?", (process_id,)).fetchone()


def update_process(conn: sqlite3.Connection, process_id: int, title: str,
                   started_at: str, expected_days: float = None,
                   note: str = None) -> None:
    conn.execute("""
        UPDATE processes SET title=?, started_at=?, expected_days=?, note=?
        WHERE id=?
    """, (title, started_at, expected_days, note, process_id))
    conn.commit()


def archive_process(conn: sqlite3.Connection, process_id: int) -> None:
    conn.execute("UPDATE processes SET archived=1 WHERE id=?", (process_id,))
    conn.commit()


def restart_process(conn: sqlite3.Connection, process_id: int,
                     new_started_at: str = None) -> None:
    if new_started_at is None:
        new_started_at = dt.datetime.now().isoformat()
    conn.execute("UPDATE processes SET started_at=? WHERE id=?", (new_started_at, process_id))
    conn.commit()


def delete_process(conn: sqlite3.Connection, process_id: int) -> None:
    conn.execute("DELETE FROM processes WHERE id=?", (process_id,))
    conn.commit()