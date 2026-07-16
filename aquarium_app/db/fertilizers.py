"""CRUD-операции для таблицы fertilizers (удобрения)."""
from __future__ import annotations
import sqlite3

from aquarium_app.config import ELEMENT_KEYS


_FERT_COLS = ["name", "form", "no3", "po4", "k", "fe", "mg", "ca",
              "mn", "b", "zn", "cu", "mo", "co", "note"]


def get_fertilizers(conn: sqlite3.Connection):
    return conn.execute("SELECT * FROM fertilizers ORDER BY id").fetchall()


def get_fertilizer(conn: sqlite3.Connection, fid: int):
    return conn.execute("SELECT * FROM fertilizers WHERE id=?", (fid,)).fetchone()


def add_fertilizer(conn: sqlite3.Connection, data: dict):
    cols = []
    vals = []
    for col in _FERT_COLS:
        if col in data and data[col] is not None:
            cols.append(col)
            vals.append(data[col])
    placeholders = ",".join(["?"] * len(cols))
    col_names = ",".join(cols)
    cur = conn.execute(f"INSERT INTO fertilizers ({col_names}) VALUES ({placeholders})", vals)
    conn.commit()
    return cur.lastrowid


def update_fertilizer(conn: sqlite3.Connection, fid: int, data: dict):
    sets = []
    vals = []
    for col in _FERT_COLS:
        if col in data:
            sets.append(f"{col}=?")
            vals.append(data[col])
    if not sets:
        return
    vals.append(fid)
    conn.execute(f"UPDATE fertilizers SET {','.join(sets)} WHERE id=?", vals)
    conn.commit()


def delete_fertilizer(conn: sqlite3.Connection, fid: int):
    conn.execute("DELETE FROM fertilizers WHERE id=?", (fid,))
    conn.commit()