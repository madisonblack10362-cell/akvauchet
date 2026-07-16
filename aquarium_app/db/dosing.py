"""Операции с журналом дозировок."""
from __future__ import annotations
import sqlite3

from aquarium_app.config import TEST_PARAMS


def get_dosing(conn: sqlite3.Connection, aq_id: int):
    return conn.execute("""
        SELECT d.*, f.name AS fert_name, f.form AS fert_form,
               f.no3 AS f_no3, f.po4 AS f_po4, f.k AS f_k, f.fe AS f_fe,
               f.mg AS f_mg, f.ca AS f_ca, f.mn AS f_mn, f.b AS f_b,
               f.zn AS f_zn, f.cu AS f_cu, f.mo AS f_mo, f.co AS f_co
        FROM dosing d
        JOIN fertilizers f ON d.fert_id = f.id
        WHERE d.aquarium_id = ?
        ORDER BY d.date DESC, d.id DESC
    """, (aq_id,)).fetchall()


def get_dosing_filtered(conn: sqlite3.Connection, aq_id: int,
                        date_from=None, date_to=None):
    where = ["d.aquarium_id=?"]
    params: list = [aq_id]
    if date_from:
        where.append("d.date>=?")
        params.append(date_from)
    if date_to:
        where.append("d.date<=?")
        params.append(date_to)
    where_sql = " AND ".join(where)
    return conn.execute(f"""
        SELECT d.*, f.name AS fert_name, f.form AS fert_form,
               f.no3 AS f_no3, f.po4 AS f_po4, f.k AS f_k, f.fe AS f_fe,
               f.mg AS f_mg, f.ca AS f_ca, f.mn AS f_mn, f.b AS f_b,
               f.zn AS f_zn, f.cu AS f_cu, f.mo AS f_mo, f.co AS f_co
        FROM dosing d
        JOIN fertilizers f ON d.fert_id = f.id
        WHERE {where_sql}
        ORDER BY d.date DESC, d.id DESC
    """, params).fetchall()


def get_latest_dosing_date(conn: sqlite3.Connection, aq_id: int):
    row = conn.execute(
        "SELECT MAX(date) AS latest FROM dosing WHERE aquarium_id=?", (aq_id,)
    ).fetchone()
    return row["latest"] if row and row["latest"] else None


def get_journal_data(conn: sqlite3.Connection, aq_id: int,
                     date_from=None, date_to=None):
    """Сливает дозировки и замеры по дате. Возвращает список dicts:
       {"date": str, "dosing": list[dict], "readings": dict}
    """
    # --- дозировки ---
    where = ["d.aquarium_id=?"]
    params: list = [aq_id]
    if date_from:
        where.append("d.date>=?")
        params.append(date_from)
    if date_to:
        where.append("d.date<=?")
        params.append(date_to)
    where_sql = " AND ".join(where)

    dosing_rows = conn.execute(f"""
        SELECT d.id, d.date, d.fert_id, d.dose, d.comment,
               f.name AS fert_name
        FROM dosing d
        JOIN fertilizers f ON d.fert_id = f.id
        WHERE {where_sql}
        ORDER BY d.date DESC, d.id DESC
    """, params).fetchall()

    # --- замеры ---
    rwhere = ["aquarium_id=?"]
    rparams: list = [aq_id]
    if date_from:
        rwhere.append("date>=?")
        rparams.append(date_from)
    if date_to:
        rwhere.append("date<=?")
        rparams.append(date_to)
    rwhere_sql = " AND ".join(rwhere)

    reading_rows = conn.execute(f"""
        SELECT * FROM readings WHERE {rwhere_sql} ORDER BY date DESC
    """, rparams).fetchall()

    # Группируем
    from collections import defaultdict
    dosing_by_date: dict[str, list] = defaultdict(list)
    readings_by_date: dict[str, dict] = defaultdict(dict)
    all_dates: set[str] = set()

    for r in dosing_rows:
        all_dates.add(r["date"])
        dosing_by_date[r["date"]].append({
            "id": r["id"],
            "fert_id": r["fert_id"],
            "fert_name": r["fert_name"],
            "dose": r["dose"],
            "comment": r["comment"],
        })

    reading_keys = [p[0] for p in TEST_PARAMS]
    for r in reading_rows:
        all_dates.add(r["date"])
        vals = {}
        for k in reading_keys:
            vals[k] = r[k]
        vals["water_change_pct"] = r["water_change_pct"]
        vals["water_change_l"] = r["water_change_l"]
        vals["comment"] = r["comment"]
        vals["id"] = r["id"]
        readings_by_date[r["date"]] = vals

    result = []
    for date in sorted(all_dates, reverse=True):
        result.append({
            "date": date,
            "dosing": dosing_by_date.get(date, []),
            "readings": readings_by_date.get(date, {}),
        })
    return result


def add_dosing(conn: sqlite3.Connection, aq_id: int, date: str,
               fert_id: int, dose: float, comment: str = ""):
    cur = conn.execute(
        "INSERT INTO dosing (aquarium_id, fert_id, date, dose, comment) VALUES (?,?,?,?,?)",
        (aq_id, fert_id, date, dose, comment),
    )
    conn.commit()
    return cur.lastrowid


def delete_dosing(conn: sqlite3.Connection, dosing_id: int):
    conn.execute("DELETE FROM dosing WHERE id=?", (dosing_id,))
    conn.commit()


def get_dosing_entry(conn: sqlite3.Connection, dosing_id: int):
    return conn.execute("""
        SELECT d.*, f.name AS fert_name, f.form AS fert_form,
               f.no3 AS f_no3, f.po4 AS f_po4, f.k AS f_k, f.fe AS f_fe,
               f.mg AS f_mg, f.ca AS f_ca, f.mn AS f_mn, f.b AS f_b,
               f.zn AS f_zn, f.cu AS f_cu, f.mo AS f_mo, f.co AS f_co
        FROM dosing d
        JOIN fertilizers f ON d.fert_id = f.id
        WHERE d.id = ?
    """, (dosing_id,)).fetchone()


def update_dosing(conn: sqlite3.Connection, dosing_id: int,
                  date: str, fert_id: int, dose: float, comment: str = ""):
    conn.execute(
        "UPDATE dosing SET date=?, fert_id=?, dose=?, comment=? WHERE id=?",
        (date, fert_id, dose, comment, dosing_id),
    )
    conn.commit()