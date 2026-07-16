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
        val_text = f"{v:.2f} мг/л"
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

        points = []
        for date_iso, v in hist:
            x = x_for_date(date_iso)
            frac = (v - local_min) / (local_max - local_min)
            y = strip_bottom - strip_h * frac
            points.append((x, y))
            hover_points.append({"x": x, "y": y, "date": date_iso, "value": v,
                                  "label": label, "color": color})

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
    if not getattr(canvas, "_hover_bound", False):
        canvas.bind("<Motion>", lambda e, c=canvas: on_chart_hover(c, e))
        canvas.bind("<Leave>", lambda e, c=canvas: on_chart_leave(c))
        canvas._hover_bound = True


# ---------------------------------------------------------------------------
# draw_daily_bars_chart — столбчатый график суточных доз
# ---------------------------------------------------------------------------

def draw_daily_bars_chart(
    canvas, conn, aq_id,
    param_defs,
    days=None, since_iso=None,
    history_fn=None,
    font_family="Segoe UI",
    empty_message="недостаточно данных для графика",
):
    """Столбчатый график: сколько элемента внесено В КАЖДЫЙ КОНКРЕТНЫЙ день
    (без накопления). Дни без внесений просто остаются пустыми.

    Оформление специально сделано менее «шумным», чем у линейного графика:
    одна подпись максимума на полосу, мягкая чередующаяся заливка фона,
    высота canvas подстраивается под количество элементов.

    Parameters
    ----------
    canvas : tk.Canvas
    conn : sqlite3.Connection
    aq_id : int
    param_defs : list[tuple[str, str, str]]
        Список (ключ, цвет, подпись).
    days : int | None
    since_iso : str | None
    history_fn : callable | None
        Функция (key) -> [(date_iso, value), ...].
    font_family : str
    empty_message : str
    """
    if not canvas.winfo_exists():
        return

    # сохраняем шрифт для hover-подсказок
    canvas._chart_font_family = font_family

    if history_fn is None:
        from aquarium_app.db import get_parameter_history
        history_fn = lambda key: get_parameter_history(conn, aq_id, key, days=days, since_iso=since_iso)

    strips = []
    for key, color, label in param_defs:
        hist = history_fn(key)
        if len(hist) >= 1:
            strips.append((key, color, label, hist))

    if not strips:
        canvas.config(height=80)
        canvas.delete("all")
        canvas.update_idletasks()
        w = max(int(canvas.winfo_width()), 200)
        canvas.create_text(w // 2, 40, text=empty_message,
                           fill=COLOR_TEXT_MUTED, font=(font_family, 8, "italic"))
        canvas._hover_points = []
        return

    # высота полосы подстраивается под число элементов
    n_strips = len(strips)
    strip_h = 42
    gap = 16
    pad_l, pad_r, pad_t, pad_b = 34, 40, 14, 24
    content_h = n_strips * strip_h + (n_strips - 1) * gap
    h = pad_t + content_h + pad_b
    canvas.config(height=h)

    canvas.delete("all")
    canvas.update_idletasks()
    w = max(int(canvas.winfo_width()), 200)
    plot_w = w - pad_l - pad_r

    # общая календарная шкала X
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
    period_end = max(all_dates + [today]) if all_dates else today
    span_days = max((period_end - period_start).days, 1)

    def x_for_date(date_iso):
        try:
            d = dt.date.fromisoformat(date_iso)
        except Exception:
            return pad_l
        offset = max(0, min((d - period_start).days, span_days))
        return pad_l + plot_w * offset / span_days

    # ширина одного столбика
    bar_w = max(3, min(12, plot_w / max(span_days, 1) * 0.6))
    min_bar_h = 3

    hover_points = []

    for idx, (key, color, label, hist) in enumerate(strips):
        strip_top = pad_t + idx * (strip_h + gap)
        strip_bottom = strip_top + strip_h

        # мягкая чередующаяся заливка фона
        if idx % 2 == 0:
            canvas.create_rectangle(0, strip_top - gap / 2, w, strip_bottom + gap / 2,
                                    fill="#14161f", outline="")

        vals = [v for _, v in hist]
        local_max = max(vals) * 1.15 if vals else 1.0
        if local_max == 0:
            local_max = 1.0

        # линия-основание (0) и подпись максимума
        canvas.create_line(pad_l, strip_bottom, pad_l + plot_w, strip_bottom,
                            fill="#2c2f3a", width=1)
        canvas.create_text(pad_l - 4, strip_top, anchor="ne", text=fmt_axis(local_max),
                           fill=COLOR_TEXT_MUTED, font=(font_family, 7))

        for date_iso, v in hist:
            x = x_for_date(date_iso)
            frac = v / local_max
            bar_h = max(min_bar_h, strip_h * frac)
            bar_top = strip_bottom - bar_h
            canvas.create_rectangle(x - bar_w / 2, bar_top, x + bar_w / 2, strip_bottom,
                                    fill=color, outline="")
            hover_points.append({"x": x, "y": bar_top, "date": date_iso, "value": v,
                                  "label": label, "color": color})

        # подпись элемента справа
        label_x = min(pad_l + plot_w + 10, w - 30)
        dot_y = strip_top + strip_h / 2
        canvas.create_oval(label_x, dot_y - 3, label_x + 6, dot_y + 3, fill=color, outline="")
        canvas.create_text(label_x + 10, dot_y, anchor="w", text=label,
                           fill=color, font=(font_family, 8, "bold"))

    axis_y = h - 4
    canvas.create_text(pad_l, axis_y, anchor="sw", text=period_start.strftime("%d.%m"),
                       fill=COLOR_TEXT_MUTED, font=(font_family, 7))
    canvas.create_text(pad_l + plot_w, axis_y, anchor="se", text=period_end.strftime("%d.%m"),
                       fill=COLOR_TEXT_MUTED, font=(font_family, 7))
    if span_days > 3:
        mid_date = period_start + dt.timedelta(days=span_days // 2)
        mid_x = x_for_date(mid_date.isoformat())
        canvas.create_text(mid_x, axis_y, anchor="s", text=mid_date.strftime("%d.%m"),
                           fill=COLOR_TEXT_MUTED, font=(font_family, 7))

    canvas._hover_points = hover_points
    canvas._hover_h = h
    canvas._hover_w = w
    if not getattr(canvas, "_hover_bound", False):
        canvas.bind("<Motion>", lambda e, c=canvas: on_chart_hover(c, e))
        canvas.bind("<Leave>", lambda e, c=canvas: on_chart_leave(c))
        canvas._hover_bound = True


# ---------------------------------------------------------------------------
# on_chart_hover / on_chart_leave — подсказки при наведении
# ---------------------------------------------------------------------------

def on_chart_hover(canvas, event):
    """Показывает подсказку (дата + значения ВСЕХ параметров) для колонки точек
    рядом с курсором. Раньше бралась только одна ближайшая точка, и из-за этого
    при совпадении дат всегда «выигрывал» NO3 (он первый в списке параметров),
    а PO4/K из подсказки пропадали.
    """
    if not canvas.winfo_exists():
        return
    points = getattr(canvas, "_hover_points", [])
    canvas.delete("hover")
    if not points:
        return
    nearest = min(points, key=lambda p: abs(p["x"] - event.x))
    if abs(nearest["x"] - event.x) > 20:
        return
    # все точки на той же дате (сопоставляем по дате, а не по пикселям)
    same_x = [p for p in points if p["date"] == nearest["date"]]
    x = nearest["x"]
    h = getattr(canvas, "_hover_h", 80)
    w = getattr(canvas, "_hover_w", 200)
    ff = _get_chart_font(canvas)
    # направляющая вертикальная линия
    canvas.create_line(x, 0, x, h, fill="#3a3f4d", dash=(2, 2), tags="hover")
    # подсвеченная точка на каждой линии в этой колонке
    for p in same_x:
        canvas.create_oval(p["x"] - 4, p["y"] - 4, p["x"] + 4, p["y"] + 4,
                            outline="#ffffff", width=1.5, fill=p["color"], tags="hover")
    # текст подсказки: дата + по строке на каждый параметр, в рамке
    date_str = from_iso(nearest["date"])
    lines = [f'{p["label"]}: {p["value"]:.2f}' for p in same_x]
    line_h = 13
    box_h = line_h * (len(lines) + 1) + 6
    text_w = max(7 * len(t) for t in [date_str] + lines) + 14
    tx = x + 8
    if tx + text_w > w:
        tx = max(0, x - text_w - 8)
    ty = 2
    if ty + box_h > h:
        ty = max(0, h - box_h - 2)
    canvas.create_rectangle(tx, ty, tx + text_w, ty + box_h,
                             fill="#05060a", outline=COLOR_BORDER, tags="hover")
    canvas.create_text(tx + 7, ty + 7, anchor="w", text=date_str,
                        fill=COLOR_TEXT_MUTED, font=(ff, 7), tags="hover")
    for i, p in enumerate(same_x):
        canvas.create_text(tx + 7, ty + 7 + line_h * (i + 1), anchor="w",
                            text=f'{p["label"]}: {p["value"]:.2f}',
                            fill=p["color"], font=(ff, 8, "bold"), tags="hover")


def on_chart_leave(canvas):
    """Убирает подсказку при уходе курсора с графика."""
    if canvas.winfo_exists():
        canvas.delete("hover")


# ---------------------------------------------------------------------------
# schedule_chart_draw — отложенная отрисовка с перерисовкой при ресайзе
# ---------------------------------------------------------------------------

def schedule_chart_draw(canvas, draw_fn, *args, **kwargs):
    """Планирует отрисовку диаграммы после того, как canvas получит реальную ширину.
    Также перерисовывает при изменении размера окна.

    Parameters
    ----------
    canvas : tk.Canvas
        Холст, на котором рисуется график.
    draw_fn : callable
        Функция отрисовки (первый аргумент — canvas).
    *args, **kwargs
        Передаются в draw_fn после canvas.
    """
    # отрисовка через 50мс (когда layout уже посчитан)
    def deferred_draw():
        if canvas.winfo_exists():
            draw_fn(canvas, *args, **kwargs)
    canvas.after(50, deferred_draw)
    # перерисовка при изменении размера canvas
    def on_resize(event):
        # canvas мог быть уничтожен к моменту события
        if not canvas.winfo_exists():
            return
        if not hasattr(canvas, "_last_w") or canvas._last_w != event.width:
            canvas._last_w = event.width
            draw_fn(canvas, *args, **kwargs)
    canvas.bind("<Configure>", on_resize)