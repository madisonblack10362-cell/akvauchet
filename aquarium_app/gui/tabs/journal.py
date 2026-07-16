"""Вкладка «Журнал» — объединённый вид дозировок и показаний по дням с полной статистикой."""

from __future__ import annotations

import datetime as dt
import tkinter as tk
from tkinter import ttk

from aquarium_app.config import (
    COLOR_BG, COLOR_CARD, COLOR_ACCENT, COLOR_BORDER, COLOR_TEXT,
    COLOR_TEXT_MUTED, COLOR_TEXT_SOFT, COLOR_OK_TEXT, COLOR_WARN_TEXT,
    COLOR_OK_BG, COLOR_ALT_ROW, COLOR_WARN, COLOR_ACCENT_SOFT,
    ELEMENT_COLORS, ELEMENT_FORMULA, MEASURED_PARAM_KEYS,
    TEST_PARAMS, TEST_PARAM_RU, FONT_FAMILY,
)
from aquarium_app.db import (
    get_aquarium, get_targets, get_journal_data,
    get_parameter_history,
)
from aquarium_app.logic.formatters import from_iso, parse_float
from aquarium_app.logic.calculations import out_of_range_flags
from aquarium_app.gui.charts import draw_param_trend_chart, schedule_chart_draw

from collections import Counter

WEEKDAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

# Параметры для графика в журнале
JOURNAL_CHART_PARAMS = [
    ("po4", ELEMENT_COLORS.get("po4", "#51cf66"), "PO4"),
    ("no3", ELEMENT_COLORS.get("no3", "#ff922b"), "NO3"),
    ("k", ELEMENT_COLORS.get("k", "#845ef7"), "K"),
]


class JournalTab:
    """Mixin-класс с методами для вкладки «Журнал»."""

    # ------------------------------------------------------------------
    # Построение вкладки
    # ------------------------------------------------------------------

    def build_journal_tab(self):
        FF = self.FF
        parent = self.tab_journal

        # --- верхняя панель: аквариум + период ---
        top = tk.Frame(parent, bg=COLOR_BG)
        top.pack(fill="x", padx=12, pady=(10, 4))

        tk.Label(top, text="Аквариум:", background=COLOR_BG, fg=COLOR_TEXT_SOFT,
                 font=(FF, 10)).pack(side="left")
        self.journal_aq_var = tk.StringVar()
        self.journal_aq_combo = ttk.Combobox(
            top, textvariable=self.journal_aq_var,
            state="readonly", width=28,
        )
        self.journal_aq_combo.pack(side="left", padx=(4, 16))
        self.journal_aq_combo.bind("<<ComboboxSelected>>",
                                    lambda e: self.refresh_journal())

        # фильтры периода
        self._journal_filter_var = tk.StringVar(value="7d")
        filter_data = [("7d", "7 дн"), ("30d", "30 дн"), ("90d", "90 дн"), ("all", "Всё")]
        self._journal_filter_btns = {}
        for key, label in filter_data:
            b = tk.Button(top, text=label, font=(FF, 8), relief="flat",
                          bg=COLOR_ALT_ROW, fg=COLOR_TEXT_MUTED, borderwidth=0,
                          padx=8, pady=2, cursor="hand2",
                          command=lambda k=key: self._set_journal_filter(k))
            b.pack(side="left", padx=2)
            self._journal_filter_btns[key] = b

        # кнопки действий
        tk.Button(top, text="+ Показания", font=(FF, 9), relief="flat",
                  bg=COLOR_CARD, fg=COLOR_TEXT, activebackground=COLOR_ALT_ROW,
                  borderwidth=0, padx=10, pady=3, cursor="hand2",
                  command=self._journal_add_reading).pack(side="right", padx=(6, 0))
        tk.Button(top, text="+ Доза", font=(FF, 9, "bold"), relief="flat",
                  bg=COLOR_ACCENT, fg="#151515", activebackground=COLOR_ACCENT_HOVER,
                  borderwidth=0, padx=10, pady=3, cursor="hand2",
                  command=self._journal_add_dose).pack(side="right")

        # --- сводная полоса статистики ---
        self._journal_stats_frame = tk.Frame(parent, bg=COLOR_BG)
        self._journal_stats_frame.pack(fill="x", padx=12, pady=(4, 4))

        # --- график параметров воды ---
        chart_outer = tk.Frame(parent, bg=COLOR_CARD,
                               highlightbackground=COLOR_BORDER, highlightthickness=1)
        chart_outer.pack(fill="x", padx=12, pady=(0, 4))

        chart_bar = tk.Frame(chart_outer, bg=COLOR_CARD)
        chart_bar.pack(fill="x", padx=8, pady=(4, 2))
        tk.Label(chart_bar, text="Динамика показаний воды", font=(FF, 9, "bold"),
                 bg=COLOR_CARD, fg=COLOR_ACCENT).pack(side="left")
        self.journal_count_label = tk.Label(chart_bar, text="", bg=COLOR_CARD,
                                             fg=COLOR_TEXT_MUTED, font=(FF, 8))
        self.journal_count_label.pack(side="right")

        self._journal_chart_canvas = tk.Canvas(chart_outer, bg=COLOR_CARD,
                                                highlightthickness=0, height=140)
        self._journal_chart_canvas.pack(fill="x", padx=8, pady=(0, 6))

        # --- прокручиваемая область с карточками ---
        container = tk.Frame(parent, bg=COLOR_BG)
        container.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self.journal_canvas = tk.Canvas(container, bg=COLOR_BG,
                                         highlightthickness=0)
        sb = ttk.Scrollbar(container, orient="vertical",
                           command=self.journal_canvas.yview)
        self.journal_scroll_inner = tk.Frame(self.journal_canvas, bg=COLOR_BG)
        self.journal_scroll_inner.bind(
            "<Configure>",
            lambda e: self.journal_canvas.configure(
                scrollregion=self.journal_canvas.bbox("all")),
        )
        self.journal_canvas.create_window((0, 0), window=self.journal_scroll_inner,
                                           anchor="nw")
        self.journal_canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.journal_canvas.pack(side="left", fill="both", expand=True)

        self.journal_canvas.bind("<Enter>",
                                  lambda e: self.journal_canvas.bind_all(
                                      "<MouseWheel>", self._journal_mousewheel))
        self.journal_canvas.bind("<Leave>",
                                  lambda e: self.journal_canvas.unbind_all("<MouseWheel>"))

    def _journal_mousewheel(self, event):
        self.journal_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    # ------------------------------------------------------------------
    # Аквариум
    # ------------------------------------------------------------------

    def refresh_journal_aq_combo(self):
        aqs = self.conn.execute("SELECT * FROM aquariums ORDER BY id").fetchall()
        items = [f"{r['id']} — {r['name']}" for r in aqs]
        self.journal_aq_combo["values"] = items
        if items and not self.journal_aq_var.get():
            self.journal_aq_combo.current(0)
            self.refresh_journal()

    def _current_journal_aq_id(self):
        s = self.journal_aq_var.get().strip()
        if not s:
            return None
        try:
            return int(s.split(" — ")[0])
        except (ValueError, IndexError):
            return None

    # ------------------------------------------------------------------
    # Фильтр
    # ------------------------------------------------------------------

    def _set_journal_filter(self, key):
        self._journal_filter_var.set(key)
        self._update_journal_filter_buttons()
        self.refresh_journal()

    def _update_journal_filter_buttons(self):
        current = self._journal_filter_var.get()
        for k, btn in self._journal_filter_btns.items():
            if k == current:
                btn.config(bg=COLOR_ACCENT, fg="#151515")
            else:
                btn.config(bg=COLOR_ALT_ROW, fg=COLOR_TEXT_MUTED)

    # ------------------------------------------------------------------
    # Обновление журнала
    # ------------------------------------------------------------------

    def refresh_journal(self):
        aq_id = self._current_journal_aq_id()
        for w in self.journal_scroll_inner.winfo_children():
            w.destroy()

        if not aq_id:
            self.journal_count_label.config(text="")
            return

        filter_key = self._journal_filter_var.get()
        date_from = None
        date_to = None
        if filter_key != "all":
            days = int(filter_key.replace("d", ""))
            date_from = (dt.date.today() - dt.timedelta(days=days)).isoformat()

        days_data = get_journal_data(self.conn, aq_id, date_from, date_to)

        aq = get_aquarium(self.conn, aq_id)
        volume_l = aq["volume_l"] if aq else 0
        targets = get_targets(self.conn, aq_id)

        # сводная статистика
        self._build_journal_stats(days_data, aq_id, targets)

        self.journal_count_label.config(text=f"{len(days_data)} записей")

        today_iso = dt.date.today().isoformat()

        for day in days_data:
            self._build_journal_day_card(day, volume_l, aq_id, targets, today_iso)

        # обновляем большой график
        self._refresh_journal_chart(aq_id, date_from)

    # ------------------------------------------------------------------
    # Сводная статистика
    # ------------------------------------------------------------------

    def _build_journal_stats(self, days_data, aq_id, targets):
        FF = self.FF
        for w in self._journal_stats_frame.winfo_children():
            w.destroy()

        # подсчёт статистики
        dosing_count = 0
        reading_count = 0
        water_changes = 0
        warnings_count = 0
        last_dose_date = None
        last_reading_date = None

        for day in days_data:
            if day.get("dosing"):
                dosing_count += len(day["dosing"])
                if last_dose_date is None:
                    last_dose_date = day["date"]
            readings = day.get("readings", {})
            has_reading = any(readings.get(k) is not None for k in MEASURED_PARAM_KEYS)
            if has_reading:
                reading_count += 1
                if last_reading_date is None:
                    last_reading_date = day["date"]
            if readings.get("water_change_l") is not None or readings.get("water_change_pct") is not None:
                water_changes += 1
            # подсчёт предупреждений
            vals = {k: readings.get(k) for k in MEASURED_PARAM_KEYS}
            flags = out_of_range_flags(self.conn, aq_id, vals)
            warnings_count += len(flags)

        stats = [
            ("Дозировок", str(dosing_count), COLOR_ACCENT),
            ("Замеров", str(reading_count), "#4dabf7"),
            ("Подмен", str(water_changes), "#20c997"),
        ]
        if warnings_count > 0:
            stats.append(("Внимание", str(warnings_count), COLOR_WARN_TEXT))
        if last_dose_date:
            stats.append(("Последн. доза", from_iso(last_dose_date), COLOR_TEXT_MUTED))
        if last_reading_date:
            stats.append(("Последн. замер", from_iso(last_reading_date), COLOR_TEXT_MUTED))

        for label, value, color in stats:
            card = tk.Frame(self._journal_stats_frame, bg=COLOR_CARD,
                            highlightbackground=COLOR_BORDER, highlightthickness=1)
            card.pack(side="left", padx=(0, 4), pady=2)
            inner = tk.Frame(card, bg=COLOR_CARD)
            inner.pack(padx=8, pady=4)
            tk.Label(inner, text=label, bg=COLOR_CARD, fg=COLOR_TEXT_MUTED,
                     font=(FF, 8)).pack(anchor="w")
            tk.Label(inner, text=value, bg=COLOR_CARD, fg=color,
                     font=(FF, 10, "bold")).pack(anchor="w")

    # ------------------------------------------------------------------
    # Большой график параметров воды
    # ------------------------------------------------------------------

    def _refresh_journal_chart(self, aq_id, date_from):
        canvas = self._journal_chart_canvas
        if not canvas.winfo_exists():
            return

        param_defs = list(JOURNAL_CHART_PARAMS)
        # добавляем pH если есть данные
        ph_hist = get_parameter_history(self.conn, aq_id, "ph", since_iso=date_from)
        if len(ph_hist) >= 2:
            param_defs.append(("ph", ELEMENT_COLORS.get("ph", "#adb5bd"), "pH"))

        def history_fn(key):
            return get_parameter_history(self.conn, aq_id, key, since_iso=date_from)

        # получаем целевые диапазоны для графика
        targets = get_targets(self.conn, aq_id)
        target_ranges = {}
        for key, _color, _label in param_defs:
            rng = targets.get(key)
            if rng and rng[0] is not None and rng[1] is not None:
                target_ranges[key] = rng

        schedule_chart_draw(
            canvas, draw_param_trend_chart, self.conn, aq_id, param_defs,
            since_iso=date_from, history_fn=history_fn,
            font_family=self.FF,
            empty_message="нет данных о показаниях за период",
            target_ranges=target_ranges,
        )

    # ------------------------------------------------------------------
    # Карточка дня
    # ------------------------------------------------------------------

    def _build_journal_day_card(self, day_data, volume_l, aq_id, targets, today_iso):
        FF = self.FF
        parent = self.journal_scroll_inner

        date_iso = day_data["date"]
        dosing_list = day_data.get("dosing", [])
        readings = day_data.get("readings", {})

        card = tk.Frame(parent, bg=COLOR_CARD, bd=0,
                        highlightbackground=COLOR_BORDER, highlightthickness=1)
        card.pack(fill="x", pady=(0, 6), padx=2)

        inner = tk.Frame(card, bg=COLOR_CARD)
        inner.pack(fill="x", padx=10, pady=8)

        # --- заголовок: дата ---
        try:
            d = dt.date.fromisoformat(date_iso)
            weekday = WEEKDAYS_RU[d.weekday()]
            date_display = f"{d.strftime('%d.%m.%Y')} ({weekday})"
        except Exception:
            date_display = from_iso(date_iso)
            weekday = ""

        hdr = tk.Frame(inner, bg=COLOR_CARD)
        hdr.pack(fill="x", pady=(0, 6))

        # индикатор дня недели
        is_weekend = weekday in ("Сб", "Вс")
        dot_color = COLOR_ACCENT if not is_weekend else "#868e96"
        tk.Frame(hdr, bg=dot_color, width=6, height=20).pack(side="left", padx=(0, 8))

        tk.Label(hdr, text=date_display, bg=COLOR_CARD, fg=COLOR_TEXT,
                 font=(FF, 11, "bold")).pack(side="left")

        if date_iso == today_iso:
            tk.Label(hdr, text="СЕГОДНЯ", bg=COLOR_ACCENT, fg="#151515",
                     font=(FF, 7, "bold"), padx=6, pady=1).pack(side="left", padx=(10, 0))

        # --- строка меток дня ---
        tags = []
        if dosing_list:
            tags.append((f"{len(dosing_list)} доз.", COLOR_ACCENT))
        has_readings = any(readings.get(k) is not None for k in MEASURED_PARAM_KEYS)
        if has_readings:
            tags.append(("замер", "#4dabf7"))
        wc_l = readings.get("water_change_l")
        wc_pct = readings.get("water_change_pct")
        if wc_l is not None or wc_pct is not None:
            tags.append(("подмена", "#20c997"))

        for tag_text, tag_color in tags:
            tk.Label(hdr, text=tag_text, bg=COLOR_BG, fg=tag_color,
                     font=(FF, 7, "bold"), padx=5, pady=1).pack(side="right", padx=(4, 0))

        # --- два столбца: дозировки и показания ---
        content = tk.Frame(inner, bg=COLOR_CARD)
        content.pack(fill="x")

        # левый столбец — дозировки
        if dosing_list:
            left_col = tk.Frame(content, bg=COLOR_BG)
            left_col.pack(side="left", fill="both", expand=True, padx=(0, 4))

            tk.Label(left_col, text="Удобрения", bg=COLOR_BG, fg=COLOR_TEXT_MUTED,
                     font=(FF, 8, "bold")).pack(anchor="w", padx=6, pady=(4, 2))

            for d_row in dosing_list:
                fert_name = d_row.get("fert_name", "?")
                dose = d_row.get("dose", 0) or 0
                comment = d_row.get("comment", "")

                row = tk.Frame(left_col, bg=COLOR_BG)
                row.pack(fill="x", padx=6, pady=1)
                tk.Label(row, text=f"{fert_name}", bg=COLOR_BG,
                         fg=COLOR_TEXT, font=(FF, 9)).pack(side="left")
                tk.Label(row, text=f"{dose:g} мл", bg=COLOR_BG,
                         fg=COLOR_ACCENT, font=(FF, 9, "bold")).pack(side="left", padx=(6, 0))
                if comment:
                    tk.Label(row, text=f"  {comment}", bg=COLOR_BG,
                             fg=COLOR_TEXT_MUTED, font=(FF, 8, "italic")).pack(side="left")

        # правый столбец — показания
        if has_readings:
            right_col = tk.Frame(content, bg=COLOR_BG)
            right_col.pack(side="left", fill="both", expand=True, padx=(4, 0) if dosing_list else (0, 0))

            tk.Label(right_col, text="Показания", bg=COLOR_BG, fg=COLOR_TEXT_MUTED,
                     font=(FF, 8, "bold")).pack(anchor="w", padx=6, pady=(4, 2))

            # флаги предупреждений
            values_for_flags = {k: readings.get(k) for k in MEASURED_PARAM_KEYS}
            flags = out_of_range_flags(self.conn, aq_id, values_for_flags)

            params_row = tk.Frame(right_col, bg=COLOR_BG)
            params_row.pack(fill="x", padx=6)

            for key, formula, unit in TEST_PARAMS:
                v = readings.get(key)
                if v is None:
                    continue
                rng = targets.get(key)
                in_range = True
                if rng and rng[0] is not None and rng[1] is not None:
                    if v < rng[0] or v > rng[1]:
                        in_range = False
                fg = COLOR_OK_TEXT if in_range else COLOR_WARN_TEXT
                bg_pill = COLOR_OK_BG if in_range else COLOR_WARN

                pill = tk.Frame(params_row, bg=bg_pill, padx=4, pady=1)
                pill.pack(side="left", padx=(0, 4), pady=1)
                lbl = tk.Label(pill, text=f"{formula}: {v:g} {unit}".strip(),
                               bg=bg_pill, fg=fg, font=(FF, 9, "bold"))
                lbl.pack()

            # предупреждения
            if flags:
                for f in flags:
                    tk.Label(right_col, text=f"  {f}", bg=COLOR_BG,
                             fg=COLOR_WARN_TEXT, font=(FF, 8),
                             wraplength=400, anchor="w", justify="left").pack(
                        anchor="w", padx=6, pady=(2, 0))

        # --- подмена воды ---
        if wc_l is not None or wc_pct is not None:
            wc_frame = tk.Frame(inner, bg="#0d2b1a", highlightbackground="#20c997",
                                highlightthickness=1)
            wc_frame.pack(fill="x", pady=(4, 0))
            parts = []
            if wc_l is not None:
                parts.append(f"{wc_l:g} л")
            if wc_pct is not None:
                parts.append(f"{wc_pct:.1f}%")
            tk.Label(wc_frame, text=f"Подмена воды: {', '.join(parts)}",
                     bg="#0d2b1a", fg="#20c997", font=(FF, 9), padx=8, pady=4).pack(anchor="w")

        # --- комментарий ---
        cmt = readings.get("comment") or ""
        if cmt:
            tk.Label(inner, text=cmt, bg=COLOR_CARD, fg=COLOR_TEXT_MUTED,
                     font=(FF, 8, "italic"), wraplength=500, anchor="w",
                     justify="left").pack(anchor="w", pady=(4, 0))

    # ------------------------------------------------------------------
    # Переходы на другие вкладки
    # ------------------------------------------------------------------

    def _journal_add_dose(self):
        if hasattr(self, "switch_to_tab"):
            self.switch_to_tab(self.tab_dosing)

    def _journal_add_reading(self):
        if hasattr(self, "switch_to_tab"):
            self.switch_to_tab(self.tab_readings)