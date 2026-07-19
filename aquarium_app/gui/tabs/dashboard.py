"""Вкладка «Обзор» — оперативный дашборд по всем аквариумам.

Логика Сводки уникальна и НЕ дублирует другие вкладки:
- Показания: подробный трендовый график + таблица всех замеров
- Дозирование: журнал дозировок, график тренда по дням/нарастающий, калькулятор

Сводка отвечает на вопрос «что происходит сейчас и что нужно сделать»:
1. Последний замер + отклонения от целевых диапазонов
2. Тренды параметров (↑↓→) за последние 2 замера — растёт/падает/стабильно
3. Подмена воды: дней до следующей + краткая статистика
4. Последняя активность: хронология (замер / дозировка / подмена)
"""

from __future__ import annotations

import datetime as dt
import tkinter as tk
from tkinter import ttk

from aquarium_app.config import (
    COLOR_BG, COLOR_CARD, COLOR_ACCENT, COLOR_ALT_ROW, COLOR_BORDER, COLOR_TEXT,
    COLOR_TEXT_MUTED, COLOR_TEXT_SOFT, COLOR_OK_TEXT, COLOR_OK_BG,
    COLOR_WARN, COLOR_WARN_TEXT, ELEMENT_COLORS,
    COLOR_STATUS_WAITING, ELEMENTS,
    MEASURED_PARAMS,
)
from aquarium_app.db import get_aquariums, get_aquarium, get_readings, get_dosing
from aquarium_app.logic.calculations import out_of_range_flags, sum_range_totals
from aquarium_app.logic.formatters import from_iso
from aquarium_app.gui.charts import draw_element_bars, schedule_chart_draw
from aquarium_app.gui.widgets import DateEntry


class DashboardTab:
    """Миксин-вкладка «Обзор» — оперативный дашборд."""

    def build_dashboard_tab(self):
        tab = self.tab_dashboard
        FF = self.FF

        # заголовок
        hdr = tk.Frame(tab, bg=COLOR_BG)
        hdr.pack(fill="x", padx=16, pady=(12, 0))
        tk.Label(hdr, text="Обзор аквариумов", font=(FF, 16, "bold"),
                 bg=COLOR_BG, fg=COLOR_TEXT).pack(side="left")
        tk.Button(hdr, text="Обновить", font=(FF, 9), relief="flat",
                  bg=COLOR_CARD, fg=COLOR_ACCENT, activebackground=COLOR_ALT_ROW,
                  activeforeground=COLOR_ACCENT, borderwidth=0, padx=10, pady=3,
                  command=self.refresh_dashboard, cursor="hand2").pack(side="right")

        # --- фильтр периода для «Внесено» ---
        filter_bar = tk.Frame(tab, bg=COLOR_BG)
        filter_bar.pack(fill="x", padx=16, pady=(4, 0))
        tk.Label(filter_bar, text="Период:", bg=COLOR_BG, fg=COLOR_TEXT_MUTED,
                 font=(FF, 9)).pack(side="left")
        self._dash_filter_var = tk.StringVar(value="week")
        filter_data = [
            ("week", "Неделя"), ("2weeks", "2 недели"),
            ("month", "Месяц"), ("custom", "..."),
        ]
        self._dash_filter_btns = {}
        for key, label in filter_data:
            b = tk.Button(filter_bar, text=label, font=(FF, 8), relief="flat",
                          bg=COLOR_ALT_ROW, fg=COLOR_TEXT_MUTED, borderwidth=0,
                          padx=8, pady=2, cursor="hand2",
                          command=lambda k=key: self._set_dash_filter(k))
            b.pack(side="left", padx=2)
            self._dash_filter_btns[key] = b
        self._update_dash_filter_buttons()

        # строка произвольного диапазона (скрыта по умолчанию)
        self._dash_custom_frame = tk.Frame(tab, bg=COLOR_BG)
        self._dash_custom_frame.pack(fill="x", padx=16, pady=(0, 0))
        tk.Label(self._dash_custom_frame, text="С:", bg=COLOR_BG,
                 fg=COLOR_TEXT_MUTED, font=(FF, 9)).pack(side="left")
        monday = dt.date.today() - dt.timedelta(days=dt.date.today().weekday())
        self._dash_from_entry = DateEntry(
            self._dash_custom_frame, font_family=FF, width=12,
            default=monday.strftime("%d.%m.%Y"))
        self._dash_from_entry.pack(side="left", padx=(2, 8))
        tk.Label(self._dash_custom_frame, text="По:", bg=COLOR_BG,
                 fg=COLOR_TEXT_MUTED, font=(FF, 9)).pack(side="left")
        self._dash_to_entry = DateEntry(
            self._dash_custom_frame, font_family=FF, width=12,
            default=dt.date.today().strftime("%d.%m.%Y"))
        self._dash_to_entry.pack(side="left", padx=(2, 8))
        tk.Button(self._dash_custom_frame, text="Показать", font=(FF, 9),
                  relief="flat", bg=COLOR_ACCENT, fg="#151515",
                  activebackground=COLOR_ALT_ROW, borderwidth=0,
                  padx=10, pady=2, cursor="hand2",
                  command=self.refresh_dashboard).pack(side="left")
        self._dash_custom_frame.pack_forget()

        # прокручиваемая область
        outer = tk.Frame(tab, bg=COLOR_BG)
        outer.pack(fill="both", expand=True, padx=8, pady=8)

        self.dash_canvas = tk.Canvas(outer, bg=COLOR_BG, highlightthickness=0)
        vscroll = ttk.Scrollbar(outer, orient="vertical", command=self.dash_canvas.yview)
        self.dash_canvas.configure(yscrollcommand=vscroll.set)

        vscroll.pack(side="right", fill="y")
        self.dash_canvas.pack(side="left", fill="both", expand=True)

        self.dash_inner = tk.Frame(self.dash_canvas, bg=COLOR_BG)
        self._dash_win = self.dash_canvas.create_window((0, 0), window=self.dash_inner, anchor="nw")
        self.dash_inner.bind("<Configure>",
                             lambda e: self.dash_canvas.configure(scrollregion=self.dash_canvas.bbox("all")))
        self.dash_canvas.bind("<Configure>",
                              lambda e: self.dash_canvas.itemconfig(self._dash_win, width=e.width))

        self.dash_canvas.bind("<Enter>", lambda e: self.dash_canvas.bind_all("<MouseWheel>", self._dash_wheel))
        self.dash_canvas.bind("<Leave>", lambda e: self.dash_canvas.unbind_all("<MouseWheel>"))

        self.after(100, self.refresh_dashboard)

    def _dash_wheel(self, event):
        self.dash_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    # ------------------------------------------------------------------
    # Фильтр периода
    # ------------------------------------------------------------------

    def _set_dash_filter(self, key):
        self._dash_filter_var.set(key)
        self._update_dash_filter_buttons()
        if key == "custom":
            self._dash_custom_frame.pack(fill="x", padx=16, pady=(0, 0))
        else:
            self._dash_custom_frame.pack_forget()
        self.refresh_dashboard()

    def _update_dash_filter_buttons(self):
        current = self._dash_filter_var.get()
        for k, btn in self._dash_filter_btns.items():
            if k == current:
                btn.config(bg=COLOR_ACCENT, fg="#151515")
            else:
                btn.config(bg=COLOR_ALT_ROW, fg=COLOR_TEXT_MUTED)

    def _dash_date_range(self):
        """(date_from_iso, date_to_iso) по текущему фильтру."""
        key = self._dash_filter_var.get()
        today = dt.date.today()
        weekday = today.weekday()

        if key == "week":
            monday = today - dt.timedelta(days=weekday)
            sunday = monday + dt.timedelta(days=6)
            return monday.isoformat(), sunday.isoformat()

        if key == "2weeks":
            this_monday = today - dt.timedelta(days=weekday)
            prev_monday = this_monday - dt.timedelta(days=14)
            this_sunday = this_monday + dt.timedelta(days=6)
            return prev_monday.isoformat(), this_sunday.isoformat()

        if key == "month":
            first = today.replace(day=1)
            last = (today.replace(day=28) + dt.timedelta(days=4)).replace(day=1) - dt.timedelta(days=1)
            return first.isoformat(), last.isoformat()

        if key == "custom":
            try:
                d_from = dt.datetime.strptime(
                    self._dash_from_entry.get().strip(), "%d.%m.%Y").date()
            except Exception:
                d_from = None
            try:
                d_to = dt.datetime.strptime(
                    self._dash_to_entry.get().strip(), "%d.%m.%Y").date()
            except Exception:
                d_to = None
            return (
                d_from.isoformat() if d_from else None,
                d_to.isoformat() if d_to else None,
            )

        return None, None

    def _dash_period_label(self, date_from, date_to):
        """Читаемая подпись периода для заголовка баров."""
        key = self._dash_filter_var.get()
        names = {"week": "Неделя", "2weeks": "2 недели", "month": "Месяц"}
        if key in names:
            d1 = dt.date.fromisoformat(date_from)
            d2 = dt.date.fromisoformat(date_to)
            return f"{names[key]} ({d1.strftime('%d.%m')} - {d2.strftime('%d.%m')})"
        return f"Период ({date_from} - {date_to})"

    @staticmethod
    def _fert_color(dosing_row):
        """Цвет удобрения: микро-удобрения — зелёно-коричневый, макро — по элементу."""
        name = (dosing_row.get("fert_name") or "").lower()
        if "микро" in name or "micro" in name:
            return "#8B7D5E"
        for key in ("f_no3", "f_po4", "f_k", "f_mg", "f_ca"):
            if dosing_row.get(key):
                return ELEMENT_COLORS.get(key[2:], COLOR_ACCENT)
        for key in ("f_fe", "f_mn", "f_b", "f_zn", "f_cu", "f_mo", "f_co"):
            if dosing_row.get(key):
                return "#8B7D5E"
        return COLOR_ACCENT

    @staticmethod
    def _fert_sort_key(dosing_row):
        """Ключ сортировки: PO4, NO3, K, макро, микро."""
        for i, key in enumerate(("f_po4", "f_no3", "f_k", "f_mg", "f_ca")):
            if dosing_row.get(key):
                return i
        return 99  # микро — в конце

    def refresh_dashboard(self):
        container = self.dash_inner
        FF = self.FF

        for w in container.winfo_children():
            w.destroy()

        aquariums = get_aquariums(self.conn)
        if not aquariums:
            tk.Label(container, text="Нет аквариумов. Создайте первый на вкладке «Аквариумы».",
                     font=(FF, 11), bg=COLOR_BG, fg=COLOR_TEXT_MUTED).pack(pady=40)
            return

        date_from, date_to = self._dash_date_range()

        for aq in aquariums:
            self._build_aquarium_card(container, aq, date_from, date_to)

        container.update_idletasks()
        self.dash_canvas.configure(scrollregion=self.dash_canvas.bbox("all"))

    # ------------------------------------------------------------------
    # Карточка аквариума
    # ------------------------------------------------------------------

    def _build_aquarium_card(self, parent, aq, date_from, date_to):
        FF = self.FF
        aq_id = aq["id"]

        card = tk.Frame(parent, bg=COLOR_CARD, highlightbackground=COLOR_BORDER,
                        highlightthickness=1, padx=14, pady=10)
        card.pack(fill="x", padx=6, pady=(0, 8))

        # заголовок карточки
        hdr = tk.Frame(card, bg=COLOR_CARD)
        hdr.pack(fill="x", pady=(0, 8))
        tk.Label(hdr, text=aq["name"], font=(FF, 13, "bold"),
                 bg=COLOR_CARD, fg=COLOR_ACCENT).pack(side="left")

        info_parts = [f"{aq['volume_l']:.0f} л"]
        if aq.get("co2"):
            info_parts.append(f"CO2: {aq['co2']}")
        if aq.get("light"):
            info_parts.append(f"Свет: {aq['light']}")
        tk.Label(hdr, text="  |  ".join(info_parts), font=(FF, 9),
                 bg=COLOR_CARD, fg=COLOR_TEXT_MUTED).pack(side="right")

        # --- два столбца: замеры + статусы ---
        two_col = tk.Frame(card, bg=COLOR_CARD)
        two_col.pack(fill="x", pady=(0, 6))

        left_col = tk.Frame(two_col, bg=COLOR_CARD)
        left_col.pack(side="left", fill="both", expand=True)

        right_col = tk.Frame(two_col, bg=COLOR_CARD)
        right_col.pack(side="left", fill="both", expand=True, padx=(12, 0))

        # --- последние замеры с трендами ---
        readings = get_readings(self.conn, aq_id)
        if readings:
            latest = readings[0]
            prev = readings[1] if len(readings) > 1 else None

            tk.Label(left_col, text="Последний замер", font=(FF, 9, "bold"),
                     bg=COLOR_CARD, fg=COLOR_TEXT).pack(anchor="w")
            tk.Label(left_col, text=from_iso(latest["date"]), font=(FF, 9),
                     bg=COLOR_CARD, fg=COLOR_TEXT_MUTED).pack(anchor="w", pady=(0, 4))

            for key, label, unit in MEASURED_PARAMS:
                v = latest.get(key)
                if v is not None:
                    unit_s = f" {unit}" if unit else ""
                    param_clr = ELEMENT_COLORS.get(key, COLOR_TEXT)
                    row = tk.Frame(left_col, bg=COLOR_CARD)
                    row.pack(fill="x", pady=1)

                    # название параметра
                    tk.Label(row, text=f"{label}:", font=(FF, 9),
                             bg=COLOR_CARD, fg=param_clr, width=8, anchor="w").pack(side="left")

                    # значение
                    tk.Label(row, text=f"{v:g}{unit_s}", font=(FF, 10, "bold"),
                             bg=COLOR_CARD, fg=param_clr).pack(side="left")

                    # тренд: стрелка + разница по сравнению с предыдущим замером
                    if prev and prev.get(key) is not None:
                        pv = prev[key]
                        diff = v - pv
                        if abs(diff) < 0.01:
                            trend_txt, trend_clr = " ->", COLOR_TEXT_MUTED
                        elif diff > 0:
                            trend_txt = f" +{diff:g}"
                            trend_clr = "#6bcb77"  # добавлено — зелёный
                        else:
                            trend_txt = f" {diff:g}"
                            trend_clr = "#e64980"  # израсходовано — красный
                        tk.Label(row, text=trend_txt, font=(FF, 9),
                                 bg=COLOR_CARD, fg=trend_clr).pack(side="left", padx=(4, 0))

            # --- правая колонка: дозировка с цветами по элементам ---
            dosing_rows = get_dosing(self.conn, aq_id)
            if dosing_rows:
                # берём все записи за последнюю дату дозирования
                last_dose_date = dosing_rows[0]["date"]
                last_doses = sorted(
                    [d for d in dosing_rows if d["date"] == last_dose_date],
                    key=self._fert_sort_key,
                )
                date_s = from_iso(last_dose_date)
                tk.Label(right_col, text="Дозировка", font=(FF, 9, "bold"),
                         bg=COLOR_CARD, fg=COLOR_TEXT).pack(anchor="w")
                tk.Label(right_col, text=date_s, font=(FF, 9),
                         bg=COLOR_CARD, fg=COLOR_TEXT_MUTED).pack(anchor="w", pady=(0, 2))
                for d in last_doses:
                    fert_name = d["fert_name"] or "Удобрение"
                    dose_val = d["dose"]
                    elem_clr = self._fert_color(d)
                    row = tk.Frame(right_col, bg=COLOR_CARD)
                    row.pack(fill="x", anchor="w")
                    tk.Label(row, text=f"{fert_name} ", font=(FF, 9, "bold"),
                             bg=COLOR_CARD, fg=elem_clr).pack(side="left")
                    tk.Label(row, text=f"+{dose_val:g} мл", font=(FF, 9, "bold"),
                             bg=COLOR_CARD, fg="#6bcb77").pack(side="left")
        else:
            tk.Label(left_col, text="Замеров пока нет", font=(FF, 9),
                     bg=COLOR_CARD, fg=COLOR_TEXT_MUTED).pack(anchor="w")

        # --- подмена воды: дней до следующей + краткая статистика ---
        self._build_water_change_block(card, aq_id, date_from, date_to)

        # --- внесено за неделю ---
        self._build_weekly_dose_bars(card, aq_id, date_from, date_to)

        # --- отклонения параметров (внизу карточки) ---
        if readings:
            latest = readings[0]
            values = {key: latest.get(key) for key, _, _ in MEASURED_PARAMS}
            flags = out_of_range_flags(self.conn, aq_id, values)
            if flags:
                flags_frame = tk.Frame(card, bg=COLOR_CARD)
                flags_frame.pack(fill="x", pady=(4, 0))
                for flag in flags:
                    tk.Label(flags_frame, text=f"  {flag}", font=(FF, 9),
                             bg=COLOR_WARN, fg=COLOR_WARN_TEXT, anchor="w",
                             padx=6, pady=3).pack(fill="x", pady=1)

    # ------------------------------------------------------------------
    # Блок подмены воды (прогресс-бар с заливкой по %)
    # ------------------------------------------------------------------

    def _build_water_change_block(self, card, aq_id, date_from, date_to):
        FF = self.FF

        wc_frame = tk.Frame(card, bg=COLOR_CARD)
        wc_frame.pack(fill="x", pady=(6, 0))

        # собираем все подмены за выбранный период
        wc_where = ["aquarium_id=?"]
        wc_params: list = [aq_id]
        if date_from:
            wc_where.append("date>=?")
            wc_params.append(date_from)
        if date_to:
            wc_where.append("date<=?")
            wc_params.append(date_to)
        wc_sql = " AND ".join(wc_where)

        wc_rows = self.conn.execute(
            f"SELECT date, water_change_pct, water_change_l FROM readings WHERE {wc_sql} "
            "AND (water_change_pct IS NOT NULL OR water_change_l IS NOT NULL) "
            "ORDER BY date DESC", wc_params
        ).fetchall()

        # суммарный % за период
        aq = get_aquarium(self.conn, aq_id)
        vol = aq["volume_l"] if aq else 0
        total_pct = 0.0
        for r in wc_rows:
            pct = r["water_change_pct"]
            if pct is None and r["water_change_l"] and vol:
                pct = round(r["water_change_l"] / vol * 100, 1)
            if pct:
                total_pct += pct
        total_pct = min(total_pct, 100)

        # последняя подмена (для текста и прогноза)
        last_wc_date = wc_rows[0]["date"] if wc_rows else None
        last_wc_pct = None
        if wc_rows:
            p = wc_rows[0]["water_change_pct"]
            if p is None and wc_rows[0].get("water_change_l") and vol:
                p = round(wc_rows[0]["water_change_l"] / vol * 100, 1)
            last_wc_pct = p

        # рассчитываем дней до следующей подмены от последней
        days_since = None
        days_until = None
        if last_wc_date:
            try:
                wc_d = dt.date.fromisoformat(last_wc_date)
                days_since = (dt.date.today() - wc_d).days
                if last_wc_pct and last_wc_pct >= 30:
                    interval = max(4, int(10 - last_wc_pct / 10))
                else:
                    interval = 7
                days_until = max(0, interval - days_since)
            except (ValueError, TypeError):
                pass

        # верхняя строка: текст + прогноз
        top_row = tk.Frame(wc_frame, bg=COLOR_CARD)
        top_row.pack(fill="x", padx=4, pady=(4, 2))

        if wc_rows:
            count_txt = f" ({len(wc_rows)} подм.)" if len(wc_rows) > 1 else ""
            wc_main = f"Подмена{count_txt} — итого {total_pct:.0f}%"
            if days_since is not None:
                if days_since == 0:
                    wc_main += " (сегодня)"
                elif days_since == 1:
                    wc_main += " (вчера)"
                else:
                    wc_main += f" ({days_since} дн. назад)"
            tk.Label(top_row, text=wc_main, font=(FF, 9),
                     bg=COLOR_CARD, fg=COLOR_TEXT).pack(side="left")

            if days_until is not None:
                if days_until <= 0:
                    hint, hclr = "Пора!", COLOR_WARN_TEXT
                elif days_until == 1:
                    hint, hclr = "Завтра", COLOR_STATUS_WAITING
                else:
                    hint, hclr = f"Через {days_until} дн.", COLOR_TEXT_MUTED
                tk.Label(top_row, text=hint, font=(FF, 10, "bold"),
                         bg=COLOR_CARD, fg=hclr).pack(side="right")
        else:
            tk.Label(top_row, text="Подмен за период нет", font=(FF, 9),
                     bg=COLOR_CARD, fg=COLOR_TEXT_MUTED).pack(side="left")
            tk.Label(top_row, text="Пора!", font=(FF, 10, "bold"),
                     bg=COLOR_CARD, fg=COLOR_WARN_TEXT).pack(side="right")

        # прогресс-бар: заливка по суммарному %, цвет воды
        bar_outer = tk.Canvas(wc_frame, bg=COLOR_BORDER, highlightthickness=0, height=8)
        bar_outer.pack(fill="x", padx=4, pady=(2, 6))
        bar_outer.update_idletasks()

        pct_for_bar = min(total_pct, 100) / 100.0

        def _draw_wc_bar():
            if not bar_outer.winfo_exists():
                return
            w = bar_outer.winfo_width()
            h = bar_outer.winfo_height()
            bar_outer.delete("all")
            if pct_for_bar > 0:
                fill_w = max(1, int(w * pct_for_bar))
                bar_outer.create_rectangle(0, 0, fill_w, h, fill="#1a6b8a", outline="")
                bar_outer.create_rectangle(0, 0, fill_w, h // 2, fill="#2196a8", outline="")

        bar_outer.after(50, _draw_wc_bar)
        bar_outer.bind("<Configure>", lambda e: _draw_wc_bar())

    # ------------------------------------------------------------------
    # Внесено за неделю — горизонтальные бары
    # ------------------------------------------------------------------

    def _build_weekly_dose_bars(self, card, aq_id, date_from, date_to):
        FF = self.FF
        totals = sum_range_totals(self.conn, aq_id, date_from, date_to)

        bar_label = f"Внесено за {self._dash_period_label(date_from, date_to)}:"
        tk.Label(card, text=bar_label, font=(FF, 9, "bold"),
                 bg=COLOR_CARD, fg=COLOR_TEXT).pack(anchor="w", pady=(6, 2))

        bar_canvas = tk.Canvas(card, bg=COLOR_CARD, highlightthickness=0, height=28)
        bar_canvas.pack(fill="x", pady=(0, 4))
        items = []
        for ek, formula, ru in ELEMENTS:
            v = totals.get(ek, 0.0)
            if v > 0:
                items.append((ru, formula, v))
        if items:
            schedule_chart_draw(bar_canvas, draw_element_bars, items, font_family=self.FF)

