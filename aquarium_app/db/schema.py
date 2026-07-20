"""Схема БД, миграции и начальное заполнение."""
from __future__ import annotations

import sqlite3

from aquarium_app.config import ELEMENT_KEYS, TEST_PARAMS
from .connection import get_connection


def init_db(conn: sqlite3.Connection) -> None:
    """Создаёт все таблицы, индексы, выполняет миграции и заполняет дефолтные данные."""
    cur = conn.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS aquariums (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        volume_l REAL NOT NULL,
        co2 TEXT,
        light TEXT
    );

    CREATE TABLE IF NOT EXISTS targets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        aquarium_id INTEGER NOT NULL REFERENCES aquariums(id) ON DELETE CASCADE,
        param TEXT NOT NULL,
        min_val REAL,
        max_val REAL
    );

    CREATE TABLE IF NOT EXISTS fertilizers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        form TEXT,
        no3 REAL DEFAULT 0, po4 REAL DEFAULT 0, k REAL DEFAULT 0, fe REAL DEFAULT 0,
        mg REAL DEFAULT 0, ca REAL DEFAULT 0, mn REAL DEFAULT 0, b REAL DEFAULT 0,
        zn REAL DEFAULT 0, cu REAL DEFAULT 0, mo REAL DEFAULT 0, co REAL DEFAULT 0,
        note TEXT
    );

    CREATE TABLE IF NOT EXISTS dosing (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        aquarium_id INTEGER NOT NULL REFERENCES aquariums(id) ON DELETE CASCADE,
        fert_id INTEGER NOT NULL REFERENCES fertilizers(id) ON DELETE CASCADE,
        date TEXT NOT NULL,
        dose REAL NOT NULL,
        comment TEXT
    );

    CREATE TABLE IF NOT EXISTS readings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        aquarium_id INTEGER NOT NULL REFERENCES aquariums(id) ON DELETE CASCADE,
        date TEXT NOT NULL,
        no3 REAL, po4 REAL, k REAL, fe REAL, mg REAL, ca REAL,
        gh REAL, kh REAL, ph REAL,
        water_change_pct REAL,
        water_change_l REAL,
        comment TEXT
    );

    CREATE TABLE IF NOT EXISTS timers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        aquarium_id INTEGER REFERENCES aquariums(id) ON DELETE CASCADE,
        kind TEXT NOT NULL,
        title TEXT NOT NULL,
        started_at TEXT NOT NULL,
        due_at TEXT NOT NULL,
        interval_days REAL,
        fired INTEGER DEFAULT 0,
        note TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_timers_due ON timers(due_at);
    CREATE INDEX IF NOT EXISTS idx_timers_aq ON timers(aquarium_id);

    CREATE TABLE IF NOT EXISTS processes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        aquarium_id INTEGER REFERENCES aquariums(id) ON DELETE CASCADE,
        title TEXT NOT NULL,
        started_at TEXT NOT NULL,
        expected_days REAL,
        note TEXT,
        archived INTEGER DEFAULT 0,
        created_at TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_processes_aq ON processes(aquarium_id);
    """)
    conn.commit()

    # миграция: добавляем колонки water_change_pct и water_change_l
    cols = {row["name"] for row in cur.execute("PRAGMA table_info(readings)").fetchall()}
    if "water_change_pct" not in cols:
        cur.execute("ALTER TABLE readings ADD COLUMN water_change_pct REAL")
    if "water_change_l" not in cols:
        cur.execute("ALTER TABLE readings ADD COLUMN water_change_l REAL")
    conn.commit()

    # миграция: wc_week_goal — целевая подмена % в неделю для аквариума
    aq_cols = {row["name"] for row in cur.execute("PRAGMA table_info(aquariums)").fetchall()}
    if "wc_week_goal" not in aq_cols:
        cur.execute("ALTER TABLE aquariums ADD COLUMN wc_week_goal REAL DEFAULT 30")
        conn.commit()

    cur.execute("SELECT COUNT(*) AS c FROM aquariums")
    if cur.fetchone()["c"] == 0:
        seed_defaults(conn)
    else:
        migrate_fertilizer_names(conn)


def migrate_fertilizer_names(conn: sqlite3.Connection) -> None:
    """Переименовывает удобрения из старых версий."""
    renames = {
        "Раствор KNO3 (10 г/100 мл)": "Нитрат",
        "Раствор KH2PO4 (10 г/100 мл)": "Фосфат",
        "Раствор K2SO4 (10 г/100 мл)": "Калий",
        "WaterSci Micro XL": "Микро (WaterSci Micro XL)",
    }
    cur = conn.cursor()
    for old_name, new_name in renames.items():
        cur.execute("UPDATE fertilizers SET name=? WHERE name=?", (new_name, old_name))
    conn.commit()
    migrate_fertilizer_concentrations(conn)


def migrate_fertilizer_concentrations(conn: sqlite3.Connection) -> None:
    """Корректирует концентрации удобрений по этикетке."""
    corrections = [
        ("Нитрат", "no3", 61.33, 59.76),
        ("Нитрат", "k", 38.67, 38.02),
        ("Фосфат", "po4", 69.79, 66.91),
        ("Фосфат", "k", 28.73, 27.40),
        ("Калий", "k", 44.88, 43.17),
    ]
    cur = conn.cursor()
    for name, field, old_val, new_val in corrections:
        row = cur.execute(f"SELECT id, {field} FROM fertilizers WHERE name=?", (name,)).fetchone()
        if row is not None and row[field] is not None and abs(row[field] - old_val) < 0.01:
            cur.execute(f"UPDATE fertilizers SET {field}=? WHERE id=?", (new_val, row["id"]))
    conn.commit()


def seed_defaults(conn: sqlite3.Connection) -> None:
    """Заполняет начальные данные для двух аквариумов."""
    cur = conn.cursor()
    cur.execute("INSERT INTO aquariums (name, volume_l, co2, light) VALUES (?,?,?,?)",
                ("Аквариум 1 (CO2)", 60, "Да", "Средний, ~0.5 Вт/л"))
    aq1 = cur.lastrowid
    cur.execute("INSERT INTO aquariums (name, volume_l, co2, light) VALUES (?,?,?,?)",
                ("Аквариум 2 (без CO2)", 40, "Нет", "Средний"))
    aq2 = cur.lastrowid

    targets1 = [("no3", 10, 20), ("po4", 0.5, 2), ("k", 10, 25), ("fe", 0.1, 0.3),
                ("mg", 5, 15), ("ca", 10, 30), ("gh", 4, 8), ("kh", 3, 6), ("ph", 6.5, 7.5)]
    targets2 = [("no3", 2, 10), ("po4", 0.1, 0.5), ("k", 5, 15), ("fe", 0.05, 0.1),
                ("mg", 5, 15), ("ca", 10, 30), ("gh", 4, 8), ("kh", 3, 6), ("ph", 6.5, 7.5)]
    for p, mn, mx in targets1:
        cur.execute("INSERT INTO targets (aquarium_id, param, min_val, max_val) VALUES (?,?,?,?)",
                    (aq1, p, mn, mx))
    for p, mn, mx in targets2:
        cur.execute("INSERT INTO targets (aquarium_id, param, min_val, max_val) VALUES (?,?,?,?)",
                    (aq2, p, mn, mx))

    ferts = [
        ("Нитрат", "Жидкое (мг/мл)",
         59.76, 0, 38.02, 0, 0, 0, 0, 0, 0, 0, 0, 0,
         "Домашний раствор «Селитра калиевая с микроэлементами» (N-13.5%, K2O-45.8% на этикетке), "
         "10 г на 100 мл воды. Азот в форме NO3 (как меряет тест) + калий."),
        ("Фосфат", "Жидкое (мг/мл)",
         0, 66.91, 27.40, 0, 0, 0, 0, 0, 0, 0, 0, 0,
         "Домашний раствор «Монокалийфосфат» (P2O5-50%, K2O-33% на этикетке), 10 г на 100 мл воды. "
         "Фосфор в форме PO4 (как меряет тест) + калий."),
        ("Калий", "Жидкое (мг/мл)",
         0, 0, 43.17, 0, 0, 0, 0, 0, 0, 0, 0, 0,
         "Домашний раствор «Сульфат калия» (K2O-52%, K2SO4 99.3% на этикетке), 10 г на 100 мл воды. "
         "Почти чистый калий, азота и фосфора нет."),
        ("Микро (WaterSci Micro XL)", "Жидкое (мг/мл)",
         0, 0, 10.48, 2.00, 5.55, 0, 0.52, 0.09, 0.05, 0.03, 0.04, 0.01,
         "С этикетки. Калий (K) в составе учтён. Также содержит S 6.56 г/л, Na 0.37 г/л "
         "(не отслеживаются отдельно). Реком. произв.: 1 мл/100л через день; "
         "1 нажатие дозатора ≈ 1.7 мл."),
    ]
    for f in ferts:
        cur.execute("""INSERT INTO fertilizers
            (name, form, no3, po4, k, fe, mg, ca, mn, b, zn, cu, mo, co, note)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", f)
    conn.commit()