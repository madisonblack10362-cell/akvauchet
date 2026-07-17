"""Функции отрисовки графиков: бары элементов, линейные тренды, столбчатые диаграммы."""

import datetime as dt
import tkinter as tk

from aquarium_app.config import (
    FONT_FAMILY,
    COLOR_ACCENT,
    COLOR_CARD,
    COLOR_BORDER,
    COLOR_TEXT,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_SOFT,
    ELEMENT_COLORS,
    ELEMENT_FORMULA,
)
from aquarium_app.logic.formatters import from_iso


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def _element_color(formula):
    """Цвет бара в зависимости от группы элемента.

    Макроэлементы — акцентный цвет, железо — тёплый оранжево-коричневый,
    прочие микроэлементы — холодный голубоватый.
    """
    macro = {"NO3", "PO4", "K", "Mg", "Ca"}
    micro_fe = {"Fe"}
    micro_other = {"Mn", "B", "Zn", "Cu", "Mo", "Co"}
    if formula in macro:
        return COLOR_ACCENT
    if formula in micro_fe:
        return "#e08742"
    if formula in micro_other:
        return "#8fb8c9"
    return COLOR_ACCENT


def fmt_axis(val):
    """Форматирует значение для подписи оси графика с адаптивной точностью.

    Микроэлементы (Fe, Mn и т.п.) обычно вносятся в дозах 0.01-0.05 мг/л —
    при фиксированном форматировании "{val:.1f}" такие значения всегда
    округляются до "0.0", из-за чего шкала графика выглядит нерабочей
    (сверху и снизу одна и та же подпись "0.0", хотя столбик на графике
    явно виден). Даём больше знаков после запятой для маленьких величин.
    """
    if val == 0:
        return "0"
    av = abs(val)
    if av < 0.01:
        return f"{val:.3f}"
    elif av < 1:
        return f"{val:.2f}"
    return f"{val:.1f}"


def _get_chart_font(canvas):
    """Возвращает имя шрифта, сохранённое на canvas, или fallback."""
    return getattr(canvas, "_chart_font_family", FONT_FAMILY)


def _lighten(hex_color, factor=0.25):
    """Осветляет hex-цвет на factor (0-1), возвращая новый hex."""
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[:2], 16), int(hex_color[2:4], 16), int(hex_color[4:], 16)
    r = min(255, int(r + (255 - r) * factor))
    g = min(255, int(g + (255 - g) * factor))
    b = min(255, int(b + (255 - b) * factor))
    return f"#{r:02x}{g:02x}{b:02x}"


def _darken(hex_color, factor=0.3):
    """Затемняет hex-цвет."""
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[:2], 16), int(hex_color[2:4], 16), int(hex_color[4:], 16)
    r = max(0, int(r * (1 - factor)))
    g = max(0, int(g * (1 - factor)))
    b = max(0, int(b * (1 - factor)))
    return f"#{r:02x}{g:02x}{b:02x}"


# ---------------------------------------------------------------------------
# draw_element_bars — горизонтальная диаграмма прироста на дашборде
# ---------------------------------------------------------------------------

def draw_element_bars(canvas, items, font_family="Segoe UI"):
    """Рисует мини-диаграмму горизонтальных баров прироста элементов на canvas.

    Parameters
    ----------
    canvas : tk.Canvas
        Холст для отрисовки.
    items : list
        Список кортежей (ru_name, formula, value), например
        [("Нитрат", "NO3", 3.14), ...].
    font_family : str
        Шрифт для текста на графике.
    """
    if not canvas.winfo_exists():
        return
    canvas.delete("all")
    if not items:
        canvas.config(height=24)
        canvas.create_text(10, 12, anchor="w", text="за 7 дней удобрения не вносились",
                           fill=COLOR_TEXT_MUTED, font=(font_family, 9, "italic"))
        return
    row_h = 18
    pad_top = 4
    needed_h = pad_top * 2 + row_h * len(items)
    canvas.config(height=needed_h)
    canvas.update_idletasks()
    # реальная ширина canvas после размещения
    w = max(int(canvas.winfo_width()), 300)
    max_val = max(v for _, _, v in items) or 1.0
    # компоновка: подпись | бар | значение (мг/л)
    label_w = 130
    val_w = 70  # место под «X.XX мг/л»
    bar_x0 = label_w + 6
    bar_max_w = max(w - bar_x0 - val_w - 8, 60)

    for i, (ru, formula, v) in enumerate(items):
        y0 = pad_top + i * row_h
        y1 = y0 + row_h - 4
        ymid = (y0 + y1) // 2
        # подпись элемента слева
        canvas.create_text(4, ymid, anchor="w",
                           text=f"{ru} ({formula})", fill=COLOR_TEXT_SOFT,
                           font=(font_family, 9))
        # фон трека
        canvas.create_rectangle(bar_x0, y0, bar_x0 + bar_max_w, y1,
                                outline="", fill="#3a2e1c")
        # сам бар
        color = _element_color(formula)
        bar_w = int(bar_max_w * (v / max_val))
        if bar_w < 2:
            bar_w = 2
        canvas.create_rectangle(bar_x0, y0, bar_x0 + bar_w, y1,
                                outline="", fill=color)
        # значение с единицей измерения справа от бара
        val_text = f"{fmt_axis(v)} мг/л"
        canvas.create_text(bar_x0 + bar_max_w + 6, ymid, anchor="w",
                           text=val_text, fill=COLOR_ACCENT,
                           font=(font_family, 9, "bold"))


# ---------------------------------------------------------------------------
# draw_param_trend_chart — линейный график с несколькими полосами (shared X)
# ---------------------------------------------------------------------------

def draw_param_trend_chart(
    canvas, conn, aq_id,
    param_defs,
    days=None, since_iso=None,
    history_fn=None,
    font_family="Segoe UI",
    empty_message="недостаточно данных для графика",
    target_ranges=None,
    wc_events=None,
    dose_events=None,
):
    """Обобщённая отрисовка графика динамики нескольких параметров.

    Parameters
    ----------
    canvas : tk.Canvas
    conn : sqlite3.Connection
    aq_id : int
        Идентификатор аквариума.
    param_defs : list[tuple[str, str, str]]
        Список (ключ, цвет, подпись), например
        [("po4", "#51cf66", "PO4"), ("no3", "#ff922b", "NO3")].
    days : int | None
        Количество последних дней (альтернатива since_iso).
    since_iso : str | None
        Явная дата начала периода в ISO (YYYY-MM-DD).
    history_fn : callable | None
        Необязательная функция (key) -> [(date_iso, value), ...],
        которой график вызывается для получения истории по каждому ключу вместо
        стандартной get_parameter_history.
    font_family : str
    empty_message : str
        Текст, показываемый при недостатке данных.
    target_ranges : dict | None
        Словарь {key: (min, max)} с целевыми диапазонами.
    """
    if not canvas.winfo_exists():
        return
    canvas.delete("all")
    canvas.update_idletasks()
    w = max(int(canvas.winfo_width()), 200)
    h = max(int(canvas.winfo_height()), 80)

    # сохраняем шрифт для hover-подсказок
    canvas._chart_font_family = font_family

    if history_fn is None:
        from aquarium_app.db import get_parameter_history
        history_fn = lambda key: get_parameter_history(conn, aq_id, key, days=days, since_iso=since_iso)

    strips = []
    for key, color, label in param_defs:
        hist = history_fn(key)
        if len(hist) >= 2:
            strips.append((key, color, label, hist))

    # подмена воды — отдельная полоса как остальные параметры
    wc_color = "#20c997"
    wc_label = "Подмена"
    wc_hist = []
    if wc_events:
        wc_hist = [(d, pct) for d, pct in wc_events]
        if len(wc_hist) >= 1:
            strips.append(("_wc", wc_color, wc_label, wc_hist))

    if not strips:
        canvas.create_text(w // 2, h // 2, text=empty_message,
                           fill=COLOR_TEXT_MUTED, font=(font_family, 8, "italic"))
        canvas._hover_points = []
        return

    pad_l, pad_r, pad_t, pad_b = 30, 34, 8, 20
    gap = 10  # промежуток между верхней и нижней полосой
    plot_w = w - pad_l - pad_r

    n_strips = len(strips)
    strip_h = (h - pad_t - pad_b - gap * (n_strips - 1)) / n_strips

    # ---- общая календарная шкала X для ВСЕХ полос сразу ----
    all_dates = []
    for _key, _color, _label, hist in strips:
        for date_iso, _v in hist:
            try:
                all_dates.append(dt.date.fromisoformat(date_iso))
            except Exception:
                pass
    today = dt.date.today()
    if since_iso:
        try:
            period_start = dt.date.fromisoformat(since_iso)
        except Exception:
            period_start = min(all_dates) if all_dates else today
    elif days is not None:
        period_start = today - dt.timedelta(days=days)
    else:
        period_start = min(all_dates) if all_dates else today
    # правый край шкалы всегда "сегодня"
    period_end = max(all_dates + [today]) if all_dates else today
    span_days = max((period_end - period_start).days, 1)

    def x_for_date(date_iso):
        try:
            d = dt.date.fromisoformat(date_iso)
        except Exception:
            return pad_l
        offset = max(0, min((d - period_start).days, span_days))
        return pad_l + plot_w * offset / span_days

    hover_points = []

    for idx, (key, color, label, hist) in enumerate(strips):
        strip_top = pad_t + idx * (strip_h + gap)
        strip_bottom = strip_top + strip_h

        vals = [v for _, v in hist]
        local_max = max(vals) * 1.1
        local_min = min(0, min(vals))
        if local_max == local_min:
            local_max = local_min + 1

        # сетка внутри полосы (верх/низ)
        for frac, val in [(0.0, local_max), (1.0, local_min)]:
            y = strip_top + strip_h * frac
            canvas.create_line(pad_l, y, pad_l + plot_w, y, fill="#2c2f3a", width=1)
            canvas.create_text(pad_l - 4, y, anchor="e", text=fmt_axis(val),
                               fill=COLOR_TEXT_MUTED, font=(font_family, 7))

        # целевой диапазон (зелёная полоса)
        if target_ranges and key in target_ranges:
            t_min, t_max = target_ranges[key]
            if t_min is not None and t_max is not None and t_max > t_min:
                range_span = local_max - local_min
                if range_span > 0:
                    y_hi = strip_bottom - strip_h * ((t_max - local_min) / range_span)
                    y_lo = strip_bottom - strip_h * ((t_min - local_min) / range_span)
                    y_hi = max(strip_top, min(strip_bottom, y_hi))
                    y_lo = max(strip_top, min(strip_bottom, y_lo))
                    canvas.create_rectangle(pad_l, y_hi, pad_l + plot_w, y_lo,
                                             fill="#0d2818", outline="")
                    canvas.create_line(pad_l, y_hi, pad_l + plot_w, y_hi,
                                     fill="#1a4a2e", width=1, dash=(3, 3))
                    canvas.create_line(pad_l, y_lo, pad_l + plot_w, y_lo,
                                     fill="#1a4a2e", width=1, dash=(3, 3))

        points = []
        for date_iso, v in hist:
            x = x_for_date(date_iso)
            frac = (v - local_min) / (local_max - local_min)
            y = strip_bottom - strip_h * frac
            points.append((x, y))
            hover_points.append({"x": x, "y": y, "date": date_iso, "value": v,
                                  "label": label, "color": color,
                                  "_is_wc": key == "_wc"})

        for i in range(len(points) - 1):
            canvas.create_line(points[i][0], points[i][1],
                                points[i + 1][0], points[i + 1][1],
                                fill=color, width=2, smooth=True)
        for x, y in points:
            canvas.create_oval(x - 2, y - 2, x + 2, y + 2, outline="", fill=color)

        last_x, last_y = points[-1]
        label_x = min(last_x + 6, w - 4)
        canvas.create_text(label_x, last_y, anchor="w", text=label,
                           fill=color, font=(font_family, 8, "bold"))

    # ---- подписи оси X (даты начала и конца периода) ----
    axis_y = h - 2
    canvas.create_text(pad_l, axis_y, anchor="sw", text=period_start.strftime("%d.%m"),
                       fill=COLOR_TEXT_MUTED, font=(font_family, 7))
    canvas.create_text(pad_l + plot_w, axis_y, anchor="se", text=period_end.strftime("%d.%m"),
                       fill=COLOR_TEXT_MUTED, font=(font_family, 7))
    if span_days > 3:
        mid_date = period_start + dt.timedelta(days=span_days // 2)
        mid_x = x_for_date(mid_date.isoformat())
        canvas.create_text(mid_x, axis_y, anchor="s", text=mid_date.strftime("%d.%m"),
                           fill=COLOR_TEXT_MUTED, font=(font_family, 7))

    # подсказка при наведении курсора
    canvas._hover_points = hover_points
    canvas._hover_h = h
    canvas._hover_w = w
    canvas._hover_type = "trend"
    # все метки чтобы показывать 0 для отсутствующих в конкретный день
    canvas._hover_all_labels = [(color, label) for _key, color, label, _hist in strips if _key != "_wc"]
    canvas._dose_events = dose_events or {}
    canvas.bind("<Motion>", lambda e, c=canvas: on_chart_hover(c, e))
    canvas.bind("<Leave>", lambda e, c=canvas: on_chart_leave(c))


# ---------------------------------------------------------------------------
# draw_daily_bars_chart — stacked bar: один столбик на день
# ---------------------------------------------------------------------------

def draw_daily_bars_chart(
    canvas, conn, aq_id,
    param_defs,
    days=None, since_iso=None,
    history_fn=None,
    font_family="Segoe UI",
    empty_message="недостаточно данных для графика",
):
    """Столбчатый график суточных доз — ОДИН стаканный столбик на день.

    Высота столбика = сумма доз всех элементов за этот день.
    Сегменты внутри столбика раскрашены по элементам.
    При наведении — подсказка с разбивкой по каждому элементу.
    """
    if not canvas.winfo_exists():
        return

    canvas._chart_font_family = font_family

    if history_fn is None:
        from aquarium_app.db import get_parameter_history
        history_fn = lambda key: get_parameter_history(conn, aq_id, key, days=days, since_iso=since_iso)

    # ---- собираем данные ----
    elem_data = []
    for key, color, label in param_defs:
        hist = history_fn(key)
        if len(hist) >= 1:
            elem_data.append((key, color, label, hist))

    if not elem_data:
        canvas.config(height=80)
        canvas.delete("all")
        canvas.update_idletasks()
        w = max(int(canvas.winfo_width()), 200)
        canvas.create_text(w // 2, 40, text=empty_message,
                           fill=COLOR_TEXT_MUTED, font=(font_family, 8, "italic"))
        canvas._hover_points = []
        return

    # ---- безопасный парсинг дат ----
    def _parse_date(raw):
        if isinstance(raw, dt.date):
            return raw
        return dt.date.fromisoformat(str(raw))

    # ---- собираем сумму по дням ----
    # day_totals: {date: [(key, color, label, val), ...]}
    day_totals = {}
    for key, color, label, hist in elem_data:
        for date_raw, v in hist:
            if not isinstance(v, (int, float)):
                continue
            try:
                d = _parse_date(date_raw)
            except Exception:
                continue
            day_totals.setdefault(d, []).append((key, color, label, v))

    all_dates_sorted = sorted(day_totals.keys())
    if not all_dates_sorted:
        canvas.config(height=80)
        canvas.delete("all")
        canvas.update_idletasks()
        w = max(int(canvas.winfo_width()), 200)
        canvas.create_text(w // 2, 40, text=empty_message,
                           fill=COLOR_TEXT_MUTED, font=(font_family, 8, "italic"))
        canvas._hover_points = []
        return

    # ---- максимум = максимальная сумма за день ----
    day_sums = {}
    for d, elems in day_totals.items():
        day_sums[d] = sum(v for _, _, _, v in elems)
    max_total = max(day_sums.values()) * 1.12 if day_sums else 1.0
    if max_total == 0:
        max_total = 1.0

    # ---- период ----
    today = dt.date.today()
    if since_iso:
        try:
            period_start = _parse_date(since_iso)
        except Exception:
            period_start = min(all_dates_sorted)
    elif days is not None:
        period_start = today - dt.timedelta(days=days)
    else:
        period_start = min(all_dates_sorted)
    period_end = max(all_dates_sorted + [today])
    span_days = max((period_end - period_start).days, 1)

    # ---- размеры ----
    chart_h = 230
    legend_h = 18
    dates_h = 16
    pad_l, pad_r, pad_t, pad_b = 46, 14, 10, 6
    h = pad_t + chart_h + dates_h + legend_h + pad_b
    canvas.config(height=h)

    canvas.delete("all")
    canvas.update_idletasks()
    w = max(int(canvas.winfo_width()), 200)
    plot_w = w - pad_l - pad_r
    chart_bottom = pad_t + chart_h

    def x_for_date(d):
        offset = max(0, min((d - period_start).days, span_days))
        return pad_l + plot_w * offset / span_days

    def y_for_val(val):
        return chart_bottom - (val / max_total) * chart_h

    # ---- единица измерения ----
    canvas.create_text(pad_l + plot_w, pad_t - 2, anchor="ne",
                       text="мг/л", fill="#3a3d48", font=(font_family, 7))

    # ---- сетка ----
    nice_steps = [0.0, 0.25, 0.5, 0.75, 1.0]
    for frac in nice_steps:
        y = y_for_val(max_total * frac)
        val = max_total * frac
        is_zero = (frac == 0.0)
        canvas.create_line(pad_l, y, pad_l + plot_w, y,
                            fill="#2c2f3a" if is_zero else "#181a22",
                            width=1)
        canvas.create_text(pad_l - 6, y, anchor="e",
                           text=fmt_axis(val),
                           fill=COLOR_TEXT_MUTED if is_zero else "#2e313b",
                           font=(font_family, 7))

    # ---- ширина столбиков ----
    n_dates = len(all_dates_sorted)
    bar_w = max(12, min(40, plot_w / max(n_dates, 1) * 0.55))

    hover_points = []

    for d in all_dates_sorted:
        elems = day_totals[d]
        total = day_sums[d]
        gx = x_for_date(d)
        bx1 = gx - bar_w / 2
        bx2 = gx + bar_w / 2

        # рисуем сегменты снизу вверх
        y_cursor = chart_bottom
        for key, color, label, v in elems:
            seg_h = (v / max_total) * chart_h
            seg_top = y_cursor - seg_h

            # сегмент
            canvas.create_rectangle(bx1, seg_top, bx2, y_cursor,
                                    fill=color, outline="")
            # тёмная линия-разделитель сверху сегмента
            if seg_h > 2:
                canvas.create_line(bx1, seg_top, bx2, seg_top,
                                    fill=_darken(color, 0.3), width=1)
            # блик слева
            if seg_h > 4:
                canvas.create_rectangle(bx1, seg_top, bx1 + 3, y_cursor,
                                        fill=_lighten(color, 0.2), outline="")

            y_cursor = seg_top

        # hover — точка на вершине столбика с разбивкой
        hover_points.append({
            "x": gx, "y": y_for_val(total),
            "date": d.isoformat(), "value": total,
            "_breakdown": elems,
        })

    # ---- ось X: даты под столбиками ----
    dates_y = chart_bottom + 4
    for d in all_dates_sorted:
        dx = x_for_date(d)
        canvas.create_text(dx, dates_y, anchor="n",
                           text=d.strftime("%d.%m"),
                           fill=COLOR_TEXT_MUTED, font=(font_family, 7))

    # ---- легенда ----
    legend_y = dates_y + dates_h + 2
    lx = pad_l
    for key, color, label, hist in elem_data:
        vals = [v for _, v in hist if isinstance(v, (int, float))]
        total = sum(vals)
        txt = f"{label}  {fmt_axis(total)}"
        canvas.create_rectangle(lx, legend_y - 4, lx + 10, legend_y + 4,
                                fill=color, outline="")
        canvas.create_text(lx + 14, legend_y, anchor="w",
                           text=txt, fill=COLOR_TEXT_SOFT,
                           font=(font_family, 8))
        lx += 18 + len(txt) * 5 + 12

    # ---- hover ----
    canvas._hover_points = hover_points
    canvas._hover_h = h
    canvas._hover_w = w
    canvas._hover_type = "bars"
    canvas.bind("<Motion>", lambda e, c=canvas: _on_bars_hover(c, e))
    canvas.bind("<Leave>", lambda e, c=canvas: on_chart_leave(c))


def _on_bars_hover(canvas, event):
    """Подсказка для stacked bar: дата + разбивка по элементам."""
    if not canvas.winfo_exists():
        return
    points = getattr(canvas, "_hover_points", [])
    canvas.delete("hover")
    if not points:
        return
    nearest = min(points, key=lambda p: abs(p["x"] - event.x))
    if abs(nearest["x"] - event.x) > 30:
        return

    h = getattr(canvas, "_hover_h", 80)
    w = getattr(canvas, "_hover_w", 200)
    ff = _get_chart_font(canvas)

    # вертикальная линия
    canvas.create_line(nearest["x"], 0, nearest["x"], h,
                        fill="#3a3f4d", dash=(2, 2), tags="hover")

    # построим подсказку
    raw_date = nearest["date"]
    if isinstance(raw_date, dt.date):
        date_str = raw_date.strftime("%d.%m.%Y")
    else:
        date_str = from_iso(raw_date)

    breakdown = nearest.get("_breakdown", [])
    if not breakdown:
        return

    line_h = 15
    box_h = line_h * (len(breakdown) + 1) + 10
    text_w = 170  # фиксированная ширина, хватит для "NO3: 0.300 мг/л"
    tx = nearest["x"] + 12
    if tx + text_w > w:
        tx = max(4, nearest["x"] - text_w - 12)
    ty = 4
    if ty + box_h > h:
        ty = max(4, h - box_h - 4)

    # фон
    canvas.create_rectangle(tx, ty, tx + text_w, ty + box_h,
                             fill="#0a0b10", outline=COLOR_BORDER, tags="hover")
    # дата
    canvas.create_text(tx + 10, ty + 6, anchor="nw", text=date_str,
                        fill=COLOR_TEXT_MUTED, font=(ff, 9), tags="hover")
    # элементы — каждый со своей цветной точкой
    for i, (key, color, label, val) in enumerate(breakdown):
        py = ty + 6 + line_h * (i + 1)
        canvas.create_oval(tx + 10, py + 2, tx + 18, py + 10,
                            fill=color, outline="", tags="hover")
        canvas.create_text(tx + 22, py + 6, anchor="w",
                            text=f"{label}:  {fmt_axis(val)} мг/л",
                            fill=color, font=(ff, 9, "bold"), tags="hover")


# ---------------------------------------------------------------------------
# on_chart_hover / on_chart_leave — подсказки при наведении
# ---------------------------------------------------------------------------

def on_chart_hover(canvas, event):
    """Показывает подсказку (дата + значения ВСЕХ параметров) для колонки точек
    рядом с курсором. Для отсутствующих в этот день параметров показывает
    значение ближайшей точки (carry forward для нарастающего графика).
    """
    if not canvas.winfo_exists():
        return
    points = getattr(canvas, "_hover_points", [])
    canvas.delete("hover")
    if not points:
        return
    nearest = min(points, key=lambda p: abs(p["x"] - event.x))
    if abs(nearest["x"] - event.x) > 25:
        return
    x = nearest["x"]
    h = getattr(canvas, "_hover_h", 80)
    w = getattr(canvas, "_hover_w", 200)
    ff = _get_chart_font(canvas)
    # направляющая вертикальная линия
    canvas.create_line(x, 0, x, h, fill="#3a3f4d", dash=(2, 2), tags="hover")
    # подсвеченные точки (только те что реально есть на этой дате)
    same_x = [p for p in points if p["date"] == nearest["date"]]
    for p in same_x:
        canvas.create_oval(p["x"] - 4, p["y"] - 4, p["x"] + 4, p["y"] + 4,
                            outline="#ffffff", width=1.5, fill=p["color"], tags="hover")
    # собираем tooltip: для каждого элемента ищем ближайшую точку слева (<= x)
    all_labels = getattr(canvas, "_hover_all_labels", [])
    tip_lines = []
    for color, label in all_labels:
        matched = [p for p in same_x if p["label"] == label]
        if matched:
            p = matched[0]
            tip_lines.append((label, f'{label}: {fmt_axis(p["value"])}', color))
        else:
            # нет точки на этой дате — ищем ближайшую слева (carry forward)
            left_points = [p for p in points if p["label"] == label and p["x"] <= x]
            if left_points:
                closest = max(left_points, key=lambda p: p["x"])
                tip_lines.append((label, f'{label}: {fmt_axis(closest["value"])}', color))
            else:
                # нет точек слева — ищем ближайшую справа
                right_points = [p for p in points if p["label"] == label and p["x"] > x]
                if right_points:
                    closest = min(right_points, key=lambda p: p["x"])
                    tip_lines.append((label, f'{label}: {fmt_axis(closest["value"])}', color))
                else:
                    tip_lines.append((label, f"{label}: 0", color))
    # подмена — отдельно, без carry-forward
    wc_matched = [p for p in same_x if p.get("_is_wc")]
    if wc_matched:
        p = wc_matched[0]
        tip_lines.append(("wc", f'Подмена: {p["value"]:.1f}%', "#20c997"))
    # дозировки — из предзагруженных данных
    dose_map = getattr(canvas, "_dose_events", {})
    dose_list = []
    if dose_map:
        raw = nearest["date"]
        d_key = raw if isinstance(raw, str) else raw.isoformat()
        dose_list = dose_map.get(d_key, [])
    if dose_list:
        # разделитель перед блоком удобрений
        tip_lines.append(("sep", "", ""))
        tip_lines.append(("dose_hdr", "Удобрения:", "#fcc419"))
        for entry in dose_list:
            tip_lines.append(("dose", entry, "#fcc419"))
    # текст подсказки
    raw_date = nearest["date"]
    if isinstance(raw_date, dt.date):
        date_str = raw_date.strftime("%d.%m.%Y")
    else:
        date_str = from_iso(raw_date)
    # собираем текстовые строки для подсчёта ширины
    vis_lines = [t for _lbl, t, _c in tip_lines if _lbl != "sep"]
    n_vis = len(vis_lines) + 1  # +1 для даты
    line_h = 14
    n_seps = sum(1 for _lbl, _, _ in tip_lines if _lbl == "sep")
    box_h = line_h * n_vis + 4 * n_seps + 10
    # точная ширина через measure_text
    tmp = canvas.create_text(0, 0, text="", font=(ff, 8, "bold"))
    max_tw = 0
    for t in [date_str] + vis_lines:
        canvas.itemconfig(tmp, text=t)
        max_tw = max(max_tw, canvas.bbox(tmp)[2] - canvas.bbox(tmp)[0])
    canvas.delete(tmp)
    text_w = max_tw + 18
    tx = x + 8
    if tx + text_w > w:
        tx = max(0, x - text_w - 8)
    ty = 2
    if ty + box_h > h:
        ty = max(0, h - box_h - 2)
    canvas.create_rectangle(tx, ty, tx + text_w, ty + box_h,
                             fill="#05060a", outline=COLOR_BORDER, tags="hover")
    # левый отступ для текста (центрируем по самой длинной строке)
    pad_l = (text_w - max_tw) // 2
    cur_y = ty + 7
    canvas.create_text(tx + pad_l, cur_y, anchor="w", text=date_str,
                        fill=COLOR_TEXT_MUTED, font=(ff, 7), tags="hover")
    cur_y += line_h
    for _lbl, text, color in tip_lines:
        if _lbl == "sep":
            # тонкая линия-разделитель
            canvas.create_line(tx + 6, cur_y - 1, tx + text_w - 6, cur_y - 1,
                               fill=COLOR_BORDER, dash=(2, 2), tags="hover")
            cur_y += 4
            continue
        canvas.create_text(tx + pad_l, cur_y, anchor="w",
                            text=text,
                            fill=color, font=(ff, 8, "bold"), tags="hover")
        cur_y += line_h


def on_chart_leave(canvas):
    """Убирает подсказку при уходе курсора с графика."""
    if canvas.winfo_exists():
        canvas.delete("hover")


# ---------------------------------------------------------------------------
# schedule_chart_draw — отложенная отрисовка с перерисовкой при ресайзе
# ---------------------------------------------------------------------------
# БАГ: раньше каждый вызов добавлял НОВЫЙ <Configure> обработчик без
# удаления старого. При переключении «Нарастающий» → «По дням» старый
# обработчик продолжал перезаписывать новый график. Фикс: генерационный
# счётчик — устаревшие обработчики просто игнорируются.

def schedule_chart_draw(canvas, draw_fn, *args, **kwargs):
    """Планирует отрисовку диаграммы после того, как canvas получит реальную ширину.
    Также перерисовывает при изменении размера окна.

    Поколение (gen) хранится НА САМОМ CANVAS — каждый canvas независим.
    При новом вызове gen увеличивается, и старые обработчики этого же
    canvas игнорируются. Другие canvas'ы не затрагиваются.

    Parameters
    ----------
    canvas : tk.Canvas
    draw_fn : callable
    *args, **kwargs
    """
    my_gen = getattr(canvas, "_chart_draw_gen", 0) + 1
    canvas._chart_draw_gen = my_gen

    def deferred_draw():
        if canvas.winfo_exists() and canvas._chart_draw_gen == my_gen:
            draw_fn(canvas, *args, **kwargs)

    canvas.after(50, deferred_draw)

    def on_resize(event):
        if not canvas.winfo_exists():
            return
        if canvas._chart_draw_gen != my_gen:
            return  # устаревший обработчик — пропускаем
        if not hasattr(canvas, "_last_w") or canvas._last_w != event.width:
            canvas._last_w = event.width
            draw_fn(canvas, *args, **kwargs)

    canvas.bind("<Configure>", on_resize)