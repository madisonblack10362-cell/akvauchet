"""Расчётные функции: прирост элементов, суммарные дозы, соотношения, валидация."""

import datetime as dt

from aquarium_app.config import (
    ELEMENT_KEYS,
    TEST_PARAMS,
    TEST_PARAM_RU,
    RATIO_GUIDELINES,
)
from aquarium_app.db import get_aquarium, get_targets


def compute_deltas(fert_row, dose, volume_l):
    """Прирост каждого элемента, мг/л, от заданной дозы удобрения."""
    if not volume_l:
        return {k: 0.0 for k in ELEMENT_KEYS}
    result = {}
    for k in ELEMENT_KEYS:
        # поддерживаем оба варианта ключей: po4 и f_po4
        v = fert_row.get(k) or fert_row.get(f"f_{k}") or 0.0
        result[k] = v * dose / volume_l
    return result


def sum_last_n_days(conn, aq_id, n=7):
    """Сумма прироста каждого элемента (мг/л) за последние n дней."""
    aq = get_aquarium(conn, aq_id)
    volume = aq["volume_l"]
    since = (dt.date.today() - dt.timedelta(days=n)).isoformat()
    rows = conn.execute("""
        SELECT d.dose, f.no3,f.po4,f.k,f.fe,f.mg,f.ca,f.mn,f.b,f.zn,f.cu,f.mo,f.co
        FROM dosing d JOIN fertilizers f ON d.fert_id=f.id
        WHERE d.aquarium_id=? AND d.date>=?
    """, (aq_id, since)).fetchall()
    totals = {k: 0.0 for k in ELEMENT_KEYS}
    for r in rows:
        for k in ELEMENT_KEYS:
            totals[k] += (r[k] or 0.0) * r["dose"] / volume if volume else 0.0
    return totals


def sum_current_calendar_week(conn, aq_id):
    """Сумма прироста каждого элемента (мг/л) с начала ТЕКУЩЕЙ календарной недели
    (с понедельника) по сегодняшний день включительно.

    В отличие от sum_last_n_days (скользящее окно 7 дней), здесь период "привязан"
    к календарной неделе: в понедельник счётчик естественным образом начинает
    считать заново (обнуляется), т.к. датой начала периода всегда становится
    понедельник ТЕКУЩЕЙ недели. Отдельного "обнуления" в БД не требуется —
    это просто способ выбрать данные за нужный период (данные за прошлые недели
    никуда не удаляются, они просто не попадают в эту выборку).

    Возвращает (totals, week_start, week_end):
      totals     — словарь {элемент: суммарный прирост, мг/л}
      week_start — дата понедельника текущей недели (datetime.date)
      week_end   — сегодняшняя дата (datetime.date)
    """
    aq = get_aquarium(conn, aq_id)
    volume = aq["volume_l"]
    today = dt.date.today()
    week_start = today - dt.timedelta(days=today.weekday())  # понедельник (weekday()==0)
    since = week_start.isoformat()
    rows = conn.execute("""
        SELECT d.dose, f.no3,f.po4,f.k,f.fe,f.mg,f.ca,f.mn,f.b,f.zn,f.cu,f.mo,f.co
        FROM dosing d JOIN fertilizers f ON d.fert_id=f.id
        WHERE d.aquarium_id=? AND d.date>=?
    """, (aq_id, since)).fetchall()
    totals = {k: 0.0 for k in ELEMENT_KEYS}
    for r in rows:
        for k in ELEMENT_KEYS:
            totals[k] += (r[k] or 0.0) * r["dose"] / volume if volume else 0.0
    return totals, week_start, today


def sum_range_totals(conn, aq_id, date_from=None, date_to=None):
    """Сумма прироста каждого элемента (мг/л) за произвольный диапазон дат
    (ISO, включительно с обеих сторон). date_from/date_to можно не указывать —
    отсутствующая граница просто не применяется (оба None = вся история).

    В отличие от sum_period_totals (только "последние N дней ДО сегодня"),
    здесь можно задать любой промежуток в прошлом, включая уже завершённый —
    используется для сводки "Итого за период" на вкладке «Дозирование».
    """
    aq = get_aquarium(conn, aq_id)
    volume = aq["volume_l"]
    where = []
    params = [aq_id]
    if date_from:
        where.append("d.date>=?")
        params.append(date_from)
    if date_to:
        where.append("d.date<=?")
        params.append(date_to)
    where_sql = (" AND " + " AND ".join(where)) if where else ""
    rows = conn.execute(f"""
        SELECT d.dose, f.no3,f.po4,f.k,f.fe,f.mg,f.ca,f.mn,f.b,f.zn,f.cu,f.mo,f.co
        FROM dosing d JOIN fertilizers f ON d.fert_id=f.id
        WHERE d.aquarium_id=?{where_sql}
    """, params).fetchall()
    totals = {k: 0.0 for k in ELEMENT_KEYS}
    for r in rows:
        for k in ELEMENT_KEYS:
            totals[k] += (r[k] or 0.0) * r["dose"] / volume if volume else 0.0
    return totals


def sum_period_totals(conn, aq_id, days=None, since_iso=None):
    """Сумма прироста каждого элемента (мг/л), внесённого со всеми удобрениями
    за указанный период (см. get_parameter_history — days/since_iso работают
    так же). Если оба параметра None — считается вся история аквариума.

    В отличие от sum_current_calendar_week (жёстко текущая неделя), период
    здесь произвольный — используется для графика трендов внесения удобрений.
    """
    aq = get_aquarium(conn, aq_id)
    volume = aq["volume_l"]
    params = [aq_id]
    where_date = ""
    if since_iso:
        where_date = " AND d.date>=?"
        params.append(since_iso)
    elif days is not None:
        since = (dt.date.today() - dt.timedelta(days=days)).isoformat()
        where_date = " AND d.date>=?"
        params.append(since)
    rows = conn.execute(f"""
        SELECT d.dose, f.no3,f.po4,f.k,f.fe,f.mg,f.ca,f.mn,f.b,f.zn,f.cu,f.mo,f.co
        FROM dosing d JOIN fertilizers f ON d.fert_id=f.id
        WHERE d.aquarium_id=?{where_date}
    """, params).fetchall()
    totals = {k: 0.0 for k in ELEMENT_KEYS}
    for r in rows:
        for k in ELEMENT_KEYS:
            totals[k] += (r[k] or 0.0) * r["dose"] / volume if volume else 0.0
    return totals


def _get_element_daily_deltas(conn, aq_id, element_key, days=None, since_iso=None):
    """Внутренний хелпер: сколько элемента (мг/л) внесено В КАЖДЫЙ конкретный
    день (без накопления), просуммировано по всем удобрениям за этот день.

    Возвращает (daily_dict, period_start_iso), где daily_dict — это
    {date_iso: сумма_за_день}, а period_start_iso — начало периода выборки
    (None, если период не ограничен, т.е. "всё время").

    Используется и для накопительной истории (get_element_dosing_cumulative_history),
    и для истории "по дням" (get_element_dosing_daily_history) — так эти две
    функции не дублируют один и тот же SQL-запрос.
    """
    aq = get_aquarium(conn, aq_id)
    volume = aq["volume_l"]
    period_start_iso = None
    params = [aq_id]
    where_date = ""
    if since_iso:
        where_date = " AND d.date>=?"
        params.append(since_iso)
        period_start_iso = since_iso
    elif days is not None:
        since = (dt.date.today() - dt.timedelta(days=days)).isoformat()
        where_date = " AND d.date>=?"
        params.append(since)
        period_start_iso = since
    rows = conn.execute(f"""
        SELECT d.date, d.dose, f.{element_key} AS content
        FROM dosing d JOIN fertilizers f ON d.fert_id=f.id
        WHERE d.aquarium_id=?{where_date} AND f.{element_key} IS NOT NULL AND f.{element_key} > 0
        ORDER BY d.date ASC, d.id ASC
    """, params).fetchall()
    if not volume:
        return {}, period_start_iso
    daily = {}
    for r in rows:
        delta = (r["content"] or 0.0) * r["dose"] / volume
        daily[r["date"]] = daily.get(r["date"], 0.0) + delta
    return daily, period_start_iso


def get_element_dosing_daily_history(conn, aq_id, element_key, days=None, since_iso=None):
    """История внесения элемента ПО ДНЯМ (мг/л), БЕЗ накопления — сколько было
    внесено конкретно в этот день. В отличие от cumulative-версии, дни без
    внесений просто отсутствуют в списке (это ожидаемо для столбчатого графика:
    там, где столбика нет, просто ничего не вносилось).

    Формат: список (date_iso, значение), отсортированный по возрастанию даты.
    """
    daily, _period_start_iso = _get_element_daily_deltas(conn, aq_id, element_key, days, since_iso)
    return sorted(daily.items())


def get_element_dosing_cumulative_history(conn, aq_id, element_key, days=None, since_iso=None):
    """История НАКОПИТЕЛЬНОГО (нарастающим итогом) внесения одного элемента, мг/л,
    просуммированного по ВСЕМ удобрениям, которые его содержат (например, калий
    из KNO3 и из KH2PO4 в один и тот же день складывается в одну точку).

    Формат возврата такой же, как у get_parameter_history — список
    (date_iso, значение), отсортированный по возрастанию даты — поэтому график
    строится тем же самым методом _draw_param_trend_chart, что и для показаний.

    Каждая точка — это сумма внесения элемента со старта периода ПО эту дату
    включительно, поэтому график всегда монотонно не убывает и прямо отвечает
    на вопрос "сколько всего внесено на такой-то день".
    """
    daily, period_start_iso = _get_element_daily_deltas(conn, aq_id, element_key, days, since_iso)
    result = []
    running = 0.0
    for date_iso in sorted(daily.keys()):
        running += daily[date_iso]
        result.append((date_iso, running))
    # если период ограничен (не "всё время") и первое внесение было позже даты
    # начала периода — добавляем точку "0" на дату начала периода И ещё одну
    # точку "0" на день перед первой реальной записью. Без второй точки линия
    # рисуется прямой диагональю от начала периода до первого внесения, как
    # будто элемент рос равномерно всё это время — хотя на самом деле все эти
    # дни должно быть ровно 0, а рост начинается резко, только с первой дозы
    if period_start_iso and result and result[0][0] > period_start_iso:
        first_real_date = dt.date.fromisoformat(result[0][0])
        day_before_first = (first_real_date - dt.timedelta(days=1)).isoformat()
        if day_before_first > period_start_iso:
            result.insert(0, (day_before_first, 0.0))
        result.insert(0, (period_start_iso, 0.0))
    # если последнее внесение было раньше сегодняшнего дня — продлеваем линию
    # плоско до сегодня с тем же накопленным значением. Без этого график
    # обрывается на дате последнего внесения, и справа не видно, сколько
    # всего накоплено на текущий момент (особенно заметно, если элемент не
    # вносился в последние несколько дней периода)
    today_iso = dt.date.today().isoformat()
    if result and result[-1][0] < today_iso:
        result.append((today_iso, result[-1][1]))
    return result


def compute_element_ratios(totals):
    """Считает соотношения ключевых элементов по словарю сумм (например, за неделю).

    Возвращает список словарей {label, ratio, lo, hi, status, hint, note}, где
    status: "ok" | "low" | "high" | None (None — если данных недостаточно,
    т.е. один из элементов пары равен нулю за период). note — понятное
    пояснение "что это значит на практике и что можно сделать" для
    status "low"/"high"; для "ok" note всегда None (пояснять нечего).
    """
    result = []
    for g in RATIO_GUIDELINES:
        num_key = g["num"]
        den_key = g["den"]
        num = totals.get(num_key, 0.0)
        den = totals.get(den_key, 0.0)
        label = g["label"]
        lo = g["lo"]
        hi = g["hi"]
        if not num or not den or den <= 0:
            result.append({"label": label, "ratio": None, "lo": lo, "hi": hi,
                            "status": None, "hint": g["hint"], "note": None})
            continue
        ratio = num / den
        if ratio < lo:
            status = "low"
            note = g.get("low_note")
        elif ratio > hi:
            status = "high"
            note = g.get("high_note")
        else:
            status = "ok"
            note = None
        result.append({"label": label, "ratio": ratio, "lo": lo, "hi": hi,
                        "status": status, "hint": g["hint"], "note": note})
    return result


def out_of_range_flags(conn, aq_id, values):
    """Возвращает список конкретных подсказок по параметрам, вышедшим за диапазон.

    Каждая подсказка содержит: название элемента, текущее значение,
    целевой диапазон и что именно не так (мало/много).
    Пример: «Калий (K): 0.5 — мало, цель 10–25 мг/л»
    """
    targets = get_targets(conn, aq_id)
    flags = []
    for key, label, unit in TEST_PARAMS:
        v = values.get(key)
        if v is None or v == "":
            continue
        try:
            v = float(v)
        except (TypeError, ValueError):
            continue
        rng = targets.get(key)
        if not rng or rng[0] is None or rng[1] is None:
            continue
        mn, mx = rng
        ru = TEST_PARAM_RU.get(key, key)
        unit_str = f" {unit}" if unit else ""
        if v < mn:
            flags.append(f"{ru} ({label}): {v:g} — мало, цель {mn:g}–{mx:g}{unit_str}")
        elif v > mx:
            flags.append(f"{ru} ({label}): {v:g} — много, цель {mn:g}–{mx:g}{unit_str}")
    return flags