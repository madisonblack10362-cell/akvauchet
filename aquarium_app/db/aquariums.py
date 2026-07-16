"""CRUD-операции для таблицы aquariums."""
from __future__ import annotations
import sqlite3


def get_aquariums(conn: sqlite3.Connection):
    return conn.execute("SELECT * FROM aquariums ORDER BY id").fetchall()


def get_aquarium(conn: sqlite3.Connection, aq_id: int):
    return conn.execute("SELECT * FROM aquariums WHERE id=?", (aq_id,)).fetchone()


def update_aquarium(conn: sqlite3.Connection, aq_id: int, name: str, volume: float, co2: str, light: str):
    conn.execute("UPDATE aquariums SET name=?, volume_l=?, co2=?, light=? WHERE id=?",
                 (name, volume, co2, light, aq_id))
    conn.commit()