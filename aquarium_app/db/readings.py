"""Операции с замерами воды."""
from __future__ import annotations
import sqlite3
import datetime as dt

from aquarium_app.config import TEST_PARAMS


_READING_PARAM_COLS = [p[0] for p in TEST_PARAMS]  # po4, no3, k, fe, mg, ca, gh, kh, ph


def get_readings(conn: sqlite3.Connection, aq_id: int):
    return conn.execute(
        "SELECT * FROM readings WHERE aquarium_id=? ORDER BY date DESC, id DESC",
        (aq_id,),
    ).fetchall()


def get_readings_by_date(conn: sqlite3.Connection, aq_id: int, date_iso: str):
    """Все записи показаний аквариума на конкретную дату."""
    return conn.execute(
        "SELECT * FROM readings WHERE aquarium_id=? AND date=?",
        (aq_id, date_iso),
    ).fetchall()


def get_parameter_history(conn: sqlite3.Connection, aq_id: int, param_key: str,
                          days: int = 14, since_iso: str = None) -> list:
    """История значений параметра за период.

    Возвращает список (date_iso, value), отсортированный по дате возрастания.
    """
    params = [aq_id]
    where_date = ""
    if since_iso:
        where_date = " AND date >= ?"
        params.append(since_iso)
    elif days is not None:
        since = (dt.date.today() - dt.timedelta(days=days)).isoformat()
        where_date = " AND date >= ?"
        params.append(since)
    rows = conn.execute(
        f"SELECT date, {param_key} AS val FROM readings "
        f"WHERE aquarium_id=?{where_date} AND {param_key} IS NOT NULL "
        f"ORDER BY date ASC, id ASC",
        params
    ).fetchall()
    return [(r["date"], r["val"]) for r in rows if r["val"] is not None]


def add_reading(conn: sqlite3.Connection, aq_id: int, date: str, values: dict,
                comment: str = "", water_change_pct=None, water_change_l=None):
    """values — dict {param_key: float, ...}, например {"no3": 15.0, "po4": 1.5}."""
    cols = ["aquarium_id", "date"]
    vals = [aq_id, date]
    for k in _READING_PARAM_COLS:
        cols.append(k)
        vals.append(values.get(k))
    cols.append("water_change_pct")
    vals.append(water_change_pct)
    cols.append("water_change_l")
    vals.append(water_change_l)
    cols.append("comment")
    vals.append(comment)
    placeholders = ",".join(["?"] * len(cols))
    col_names = ",".join(cols)
    cur = conn.execute(f"INSERT INTO readings ({col_names}) VALUES ({placeholders})", vals)
    conn.commit()
    return cur.lastrowid


def delete_reading(conn: sqlite3.Connection, reading_id: int):
    conn.execute("DELETE FROM readings WHERE id=?", (reading_id,))
    conn.commit()


def get_reading(conn: sqlite3.Connection, reading_id: int):
    return conn.execute("SELECT * FROM readings WHERE id=?", (reading_id,)).fetchone()


def update_reading(conn: sqlite3.Connection, reading_id: int, date: str,
                   values: dict, comment: str = "",
                   water_change_pct=None, water_change_l=None):
    """values — dict {param_key: float, ...}."""
    sets = ["date=?"]
    vals = [date]
    for k in _READING_PARAM_COLS:
        sets.append(f"{k}=?")
        vals.append(values.get(k))
    sets.append("water_change_pct=?")
    vals.append(water_change_pct)
    sets.append("water_change_l=?")
    vals.append(water_change_l)
    sets.append("comment=?")
    vals.append(comment)
    vals.append(reading_id)
    conn.execute(f"UPDATE readings SET {','.join(sets)} WHERE id=?", vals)
    conn.commit()


def get_water_change_stats(conn: sqlite3.Connection, aq_id: int, days: int = 30):
    """Возвращает статистику подмен воды: total_pct, total_l, count, last_date, last_pct, last_l.

    total_pct всегда включает пересчёт литров в проценты (если известен объём
    аквариума — передаётся через volume_l)."""
    since = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    rows = conn.execute("""
        SELECT water_change_pct, water_change_l, date
        FROM readings
        WHERE aquarium_id=? AND date>=? AND (water_change_pct IS NOT NULL OR water_change_l IS NOT NULL)
        ORDER BY date DESC
    """, (aq_id, since)).fetchall()

    # получаем объём для пересчёта литров → %
    aq = conn.execute("SELECT volume_l FROM aquariums WHERE id=?", (aq_id,)).fetchone()
    vol = aq["volume_l"] if aq and aq["volume_l"] else 0

    total_pct = 0.0
    total_l = 0.0
    count = 0
    last_date = None
    last_pct = None
    last_l = None

    for r in rows:
        pct = r["water_change_pct"]
        lit = r["water_change_l"]
        # пересчитываем литры в % если pct не указан
        if pct is None and lit is not None and vol > 0:
            pct = round(lit / vol * 100, 1)
        if pct is not None:
            total_pct += pct
        if lit is not None:
            total_l += lit
        if pct is not None or lit is not None:
            count += 1
        if last_date is None:
            last_date = r["date"]
            last_pct = pct
            last_l = lit

    return {
        "total_pct": total_pct,
        "total_l": total_l,
        "count": count,
        "last_date": last_date,
        "last_pct": last_pct,
        "last_l": last_l,
    }