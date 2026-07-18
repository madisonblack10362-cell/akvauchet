"""CRUD-операции для таблицы targets (целевые значения параметров)."""
from __future__ import annotations
import sqlite3


def get_targets(conn: sqlite3.Connection, aq_id: int) -> dict:
    rows = conn.execute("SELECT * FROM targets WHERE aquarium_id=?", (aq_id,)).fetchall()
    return {r["param"]: (r["min_val"], r["max_val"]) for r in rows}


def update_target(conn: sqlite3.Connection, aq_id: int, param: str, mn, mx):
    exists = conn.execute("SELECT id FROM targets WHERE aquarium_id=? AND param=?",
                           (aq_id, param)).fetchone()
    if exists:
        conn.execute("UPDATE targets SET min_val=?, max_val=? WHERE id=?", (mn, mx, exists["id"]))
    else:
        conn.execute("INSERT INTO targets (aquarium_id, param, min_val, max_val) VALUES (?,?,?,?)",
                     (aq_id, param, mn, mx))
    conn.commit()