"""Утилиты форматирования дат, чисел и временных интервалов."""

import datetime as dt


def parse_float(s, default=None):
    """Безопасный парсинг числа из строки. Поддерживает запятую как разделитель."""
    if s is None:
        return default
    s = str(s).strip().replace(",", ".")
    if s == "":
        return default
    try:
        return float(s)
    except ValueError:
        return default


def today_str():
    """Возвращает сегодняшнюю дату в формате ДД.ММ.ГГГГ."""
    return dt.date.today().strftime("%d.%m.%Y")


def to_iso(date_str):
    """DD.MM.YYYY -> YYYY-MM-DD (для сортировки/сравнения); None если некорректно."""
    try:
        return dt.datetime.strptime(date_str.strip(), "%d.%m.%Y").date().isoformat()
    except Exception:
        return None


def from_iso(iso_str):
    """YYYY-MM-DD -> DD.MM.YYYY. При ошибке возвращает исходную строку."""
    try:
        return dt.date.fromisoformat(iso_str).strftime("%d.%m.%Y")
    except Exception:
        return iso_str


def now_iso():
    """Текущее время в ISO формате (для БД)."""
    return dt.datetime.now().isoformat()


def format_dt(iso_str):
    """ISO datetime -> 'ДД.ММ.ГГГГ ЧЧ:ММ'."""
    try:
        d = dt.datetime.fromisoformat(iso_str)
        return d.strftime("%d.%m.%Y %H:%M")
    except Exception:
        return iso_str


def format_date_only(iso_str):
    """ISO datetime/date -> 'ДД.ММ.ГГГГ'."""
    try:
        d = dt.datetime.fromisoformat(iso_str)
        return d.strftime("%d.%m.%Y")
    except Exception:
        try:
            return dt.date.fromisoformat(iso_str).strftime("%d.%m.%Y")
        except Exception:
            return iso_str


def format_remaining(iso_str):
    """Человекочитаемый остаток времени до срока.

    Форматы: «через X дн Y ч», «через X ч», «через X мин»,
    «просрочено на X дн», «просрочено на X ч», «просрочено на X мин».
    """
    try:
        due = dt.datetime.fromisoformat(iso_str)
    except Exception:
        return "—"
    now = dt.datetime.now()
    delta = due - now
    total_seconds = delta.total_seconds()
    if total_seconds <= 0:
        abs_sec = int(abs(total_seconds))
        if abs_sec < 3600:
            return f"просрочено на {abs_sec // 60} мин"
        if abs_sec < 86400:
            return f"просрочено на {abs_sec // 3600} ч"
        return f"просрочено на {abs_sec // 86400} дн"
    total_seconds = int(total_seconds)
    if total_seconds < 3600:
        return f"через {max(1, total_seconds // 60)} мин"
    if total_seconds < 86400:
        return f"через {total_seconds // 3600} ч"
    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    if hours:
        return f"через {days} дн {hours} ч"
    return f"через {days} дн"


def format_elapsed(started_at):
    """Возвращает человекочитаемый прошедший период с даты старта."""
    try:
        try:
            start = dt.datetime.fromisoformat(started_at)
            now = dt.datetime.now()
        except ValueError:
            start = dt.datetime.combine(dt.date.fromisoformat(started_at), dt.time.min)
            now = dt.datetime.now()
        delta = now - start
        total_seconds = int(delta.total_seconds())
        if total_seconds < 0:
            return "в будущем"
        if total_seconds < 60:
            return "только что"
        if total_seconds < 3600:
            return f"{total_seconds // 60} мин"
        if total_seconds < 86400:
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            if minutes:
                return f"{hours} ч {minutes} мин"
            return f"{hours} ч"
        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600
        if days == 1:
            return f"1 день {hours} ч" if hours else "1 день"
        if 2 <= days <= 4:
            return f"{days} дня {hours} ч" if hours else f"{days} дня"
        return f"{days} дней {hours} ч" if hours else f"{days} дней"
    except Exception:
        return "—"