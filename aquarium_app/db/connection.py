"""Управление подключением к SQLite."""
from __future__ import annotations

import sqlite3

from aquarium_app.config import DB_PATH


def get_connection() -> sqlite3.Connection:
    """Создаёт новое подключение к БД с Row-фабрикой и внешними ключами."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn