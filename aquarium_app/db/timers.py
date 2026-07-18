"""Операции с таймерами (напоминаниями)."""
from __future__ import annotations
import sqlite3
import datetime as dt


def add_timer(conn: sqlite3.Connection, aquarium_id: int, kind: str,
              title: str, started_at: str, due_at: str,
              interval_days=None, note=None):
    cur = conn.execute(
        "INSERT INTO timers (aquarium_id, kind, title, started_at, due_at, "
        "interval_days, fired, note) VALUES (?,?,?,?,?,?,0,?)",
        (aquarium_id, kind, title, started_at, due_at, interval_days, note),
    )
    conn.commit()
    return cur.lastrowid


def get_active_timers(conn: sqlite3.Connection, aquarium_id: int):
    return conn.execute(
        "SELECT * FROM timers WHERE aquarium_id=? ORDER BY due_at DESC",
        (aquarium_id,),
    ).fetchall()


def get_latest_filter_clean(conn: sqlite3.Connection, aquarium_id: int):
    return conn.execute(
        "SELECT * FROM timers WHERE aquarium_id=? AND kind='filter_clean' "
        "ORDER BY due_at DESC LIMIT 1",
        (aquarium_id,),
    ).fetchone()


def get_due_timers(conn: sqlite3.Connection):
    """Unfired timers where due_at <= now, joined with aquariums for name."""
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return conn.execute("""
        SELECT t.*, a.name AS aquarium_name
        FROM timers t
        JOIN aquariums a ON t.aquarium_id = a.id
        WHERE t.fired = 0 AND t.due_at <= ?
        ORDER BY t.due_at ASC
    """, (now,)).fetchall()


def mark_timer_fired(conn: sqlite3.Connection, timer_id: int):
    conn.execute("UPDATE timers SET fired=1 WHERE id=?", (timer_id,))
    conn.commit()


def delete_timer(conn: sqlite3.Connection, timer_id: int):
    conn.execute("DELETE FROM timers WHERE id=?", (timer_id,))
    conn.commit()