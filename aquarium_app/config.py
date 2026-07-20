"""Конфигурация приложения АкваУчёт — все константы в одном месте."""
from __future__ import annotations

import os
import sys
import sqlite3

# ---------------------------------------------------------------------------
# Пути (с поддержкой PyInstaller frozen-режима)
# ---------------------------------------------------------------------------

if getattr(sys, "frozen", False):
    BASE_DIR: str = os.path.dirname(os.path.abspath(sys.executable))
else:
    BASE_DIR: str = os.path.dirname(os.path.abspath(__file__))

DB_PATH: str = os.path.join(BASE_DIR, "aquarium_data.db")

if getattr(sys, "frozen", False):
    RESOURCES_DIR: str = getattr(sys, "_MEIPASS", BASE_DIR)
else:
    RESOURCES_DIR: str = BASE_DIR


def _find_existing_db() -> str | None:
    """Ищет существующую БД с данными в нескольких местах.

    Возвращает путь к найденной БД или None.
    Используется при первом запуске .exe, если БД рядом с ним пустая,
    но есть старая БД в других местах.
    """
    candidates: list[str] = []
    candidates.append(os.path.join(BASE_DIR, "aquarium_data.db"))
    candidates.append(os.path.join(os.getcwd(), "aquarium_data.db"))
    if sys.platform == "win32":
        try:
            import ctypes.wintypes
            buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
            ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf)
            docs = buf.value
            candidates.append(os.path.join(docs, "aquarium_data.db"))
            candidates.append(os.path.join(docs, "AquaUchet", "aquarium_data.db"))
        except Exception:
            pass
    best_path: str | None = None
    best_count: int = -1
    for path in candidates:
        if not os.path.exists(path):
            continue
        try:
            test_conn = sqlite3.connect(path)
            count = test_conn.execute("SELECT COUNT(*) FROM aquariums").fetchone()[0]
            test_conn.close()
            if count > best_count:
                best_count = count
                best_path = path
        except Exception:
            continue
    return best_path


# При первом запуске .exe: если БД рядом пустая, поищем старую с данными
if getattr(sys, "frozen", False):
    try:
        if not os.path.exists(DB_PATH) or os.path.getsize(DB_PATH) == 0:
            found = _find_existing_db()
            if found and found != DB_PATH:
                import shutil as _shutil
                _shutil.copy2(found, DB_PATH)
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Элементы, дозируемые удобрениями
# ---------------------------------------------------------------------------

ELEMENTS: list[tuple[str, str, str]] = [
    ("po4", "PO4", "Фосфат"), ("no3", "NO3", "Нитрат"), ("k", "K", "Калий"), ("fe", "Fe", "Железо"),
    ("mg", "Mg", "Магний"), ("ca", "Ca", "Кальций"), ("mn", "Mn", "Марганец"), ("b", "B", "Бор"),
    ("zn", "Zn", "Цинк"), ("cu", "Cu", "Медь"), ("mo", "Mo", "Молибден"), ("co", "Co", "Кобальт"),
]
ELEMENT_KEYS: list[str] = [e[0] for e in ELEMENTS]
ELEMENT_FORMULA: dict[str, str] = {e[0]: e[1] for e in ELEMENTS}
ELEMENT_RU: dict[str, str] = {e[0]: e[2] for e in ELEMENTS}

# ---------------------------------------------------------------------------
# Параметры, измеряемые тестами воды
# ---------------------------------------------------------------------------

TEST_PARAMS: list[tuple[str, str, str]] = [
    ("po4", "PO4", "мг/л"), ("no3", "NO3", "мг/л"), ("k", "K", "мг/л"),
    ("fe", "Fe", "мг/л"), ("mg", "Mg", "мг/л"), ("ca", "Ca", "мг/л"),
    ("gh", "GH", "°dGH"), ("kh", "KH", "°dKH"), ("ph", "pH", ""),
]

TEST_PARAM_RU: dict[str, str] = {
    "po4": "Фосфат", "no3": "Нитрат", "k": "Калий", "fe": "Железо",
    "mg": "Магний", "ca": "Кальций", "gh": "Общая жёсткость",
    "kh": "Карбонатная жёсткость", "ph": "Водородный показатель (pH)",
}

MEASURED_PARAM_KEYS: list[str] = ["po4", "no3", "ph"]
MEASURED_PARAMS: list[tuple[str, str, str]] = [p for p in TEST_PARAMS if p[0] in MEASURED_PARAM_KEYS]

SPIN_SETTINGS: dict[str, dict[str, object]] = {
    "po4": {"step": 0.1, "default": ""},
    "no3": {"step": 1.0, "default": ""},
    "k":   {"step": 0.1, "default": ""},
    "ph":  {"step": 0.5, "default": "7.0"},
}

# ---------------------------------------------------------------------------
# Цветовая палитра (тёмная тема с оранжевым акцентом)
# ---------------------------------------------------------------------------

COLOR_BG = "#121317"
COLOR_SIDEBAR = "#0a0b0e"
COLOR_SIDEBAR_HOVER = "#191b23"
COLOR_SIDEBAR_ACTIVE = "#ff7a1a"
COLOR_SIDEBAR_TEXT = "#aeb2c4"
COLOR_SIDEBAR_TEXT_ACTIVE = "#ffffff"
COLOR_ACCENT = "#ff7a1a"
COLOR_ACCENT_HOVER = "#e8690a"
COLOR_ACCENT_SOFT = "#2a2015"
COLOR_CARD = "#1b1d24"
COLOR_BORDER = "#2c2f3a"
COLOR_TEXT = "#eef0f5"
COLOR_TEXT_MUTED = "#b8bdc8"
COLOR_TEXT_SOFT = "#d6dae3"
COLOR_HEADER = "#0a0b0e"
COLOR_HEADER_TEXT = "#ff9a44"
COLOR_WARN = "#3a1418"
COLOR_WARN_TEXT = "#ff6b6b"
COLOR_OK_TEXT = "#51cf66"
COLOR_OK_ROW = "#1b1d24"
COLOR_OK_BG = "#132b1a"
COLOR_ALT_ROW = "#20232c"
COLOR_STATUS_WAITING = "#ffb84d"
COLOR_STATUS_URGENT = "#ff6b6b"
COLOR_STATUS_OVERDUE = "#c92a2a"
COLOR_STATUS_DONE = "#51cf66"
COLOR_STATUS_FIRED = "#868e96"
COLOR_TIMER_OK_BG = "#1b1d24"
COLOR_TIMER_URGENT_BG = "#2a1810"
COLOR_TIMER_OVERDUE_BG = "#2a1014"
COLOR_TIMER_DONE_BG = "#161a1b"
FONT_FAMILY = "Segoe UI"

# ---------------------------------------------------------------------------
# Цвета элементов для графиков
# ---------------------------------------------------------------------------

ELEMENT_COLORS: dict[str, str] = {
    "po4": "#4dabf7", "no3": "#e64980", "k": "#845ef7", "fe": "#a0522d",
    "mg": "#20c997", "ca": "#adb5bd", "mn": "#e64980", "b": "#4dabf7",
    "zn": "#fcc419", "cu": "#f76707", "mo": "#c92a2a", "co": "#ae3ec9",
    "ph": "#51cf66",
}

# ---------------------------------------------------------------------------
# Ориентировочные соотношения ключевых элементов (EI-метод)
# ---------------------------------------------------------------------------

RATIO_GUIDELINES: list[dict] = [
    {
        "num": "no3", "den": "po4", "label": "NO3:PO4",
        "lo": 5.0, "hi": 15.0, "hint": "ориентир ~10:1, Redfield ratio",
        "low_note": "Поднять NO3 или снизить PO4 — риск водорослей",
        "high_note": "Можно чуть поднять PO4 для лучшего роста",
    },
    {
        "num": "k", "den": "no3", "label": "K:NO3",
        "lo": 0.5, "hi": 2.0, "hint": "ориентир ~1:1–1.5:1, метод EI",
        "low_note": "Добавить калий — возможны дырки на старых листьях",
        "high_note": "Калий в избытке, не критично",
    },
    {
        "num": "fe", "den": "mn", "label": "Fe:Mn",
        "lo": 1.5, "hi": 3.5, "hint": "ориентир ~2:1–3:1, большинство трейс-миксов",
        "low_note": "Много марганца, обычно не проблема",
        "high_note": "Добавить марганец — possible пожелтение молодых листьев"
    },
]