"""Управление подключением к SQLite."""
from __future__ import annotations

import sqlite3

from aquarium_app.config import DB_PATH


def _dict_factory(cursor, row):
    """Конвертирует строки БД в dict (поддерживает .get())."""
    return {col[0]: val for col, val in zip(cursor.description, row)}


def get_connection() -> sqlite3.Connection:
    """Создаёт новое подключение к БД с dict-фабрикой и внешними ключами."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = _dict_factory
    conn.execute("PRAGMA foreign_keys = ON")
    return conn