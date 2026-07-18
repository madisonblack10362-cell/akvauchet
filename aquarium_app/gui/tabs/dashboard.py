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
    COLOR_WARN, COLOR_WARN_TEXT,
    COLOR_STATUS_WAITING, ELEMENTS,
    MEASURED_PARAMS,
)
from aquarium_app.db import get_aquariums, get_aquarium, get_readings, get_dosing
from aquarium_app.logic.calculations import out_of_range_flags, sum_last_n_days
from aquarium_app.logic.formatters import from_iso
from aquarium_app.gui.charts import draw_element_bars, schedule_chart_draw


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

        for aq in aquariums:
            self._build_aquarium_card(container, aq)

        container.update_idletasks()
        self.dash_canvas.configure(scrollregion=self.dash_canvas.bbox("all"))

    # ------------------------------------------------------------------
    # Карточка аквариума
    # ------------------------------------------------------------------

    def _build_aquarium_card(self, parent, aq):
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
                    row = tk.Frame(left_col, bg=COLOR_CARD)
                    row.pack(fill="x", pady=1)

                    # название параметра
                    tk.Label(row, text=f"{label}:", font=(FF, 9),
                             bg=COLOR_CARD, fg=COLOR_TEXT_MUTED, width=8, anchor="w").pack(side="left")

                    # значение
                    tk.Label(row, text=f"{v:g}{unit_s}", font=(FF, 10, "bold"),
                             bg=COLOR_CARD, fg=COLOR_TEXT).pack(side="left")

                    # тренд: стрелка + разница по сравнению с предыдущим замером
                    if prev and prev.get(key) is not None:
                        pv = prev[key]
                        diff = v - pv
                        if abs(diff) < 0.01:
                            trend_txt, trend_clr = " ->", COLOR_TEXT_MUTED
                        elif diff > 0:
                            trend_txt = f" +{diff:g}"
                            trend_clr = COLOR_OK_TEXT if key == "no3" else COLOR_WARN_TEXT
                        else:
                            trend_txt = f" {diff:g}"
                            trend_clr = COLOR_OK_TEXT if key != "no3" else COLOR_WARN_TEXT
                        tk.Label(row, text=trend_txt, font=(FF, 9),
                                 bg=COLOR_CARD, fg=trend_clr).pack(side="left", padx=(4, 0))

            # --- правая колонка: статусы + расход + дозировка ---
            values = {key: latest.get(key) for key, _, _ in MEASURED_PARAMS}
            flags = out_of_range_flags(self.conn, aq_id, values)
            if flags:
                for flag in flags:
                    tk.Label(right_col, text=f"  {flag}", font=(FF, 9),
                             bg=COLOR_WARN, fg=COLOR_WARN_TEXT, anchor="w",
                             padx=6, pady=3).pack(fill="x", pady=1)
            else:
                tk.Label(right_col, text="  Все параметры в норме", font=(FF, 9),
                         bg=COLOR_OK_BG, fg=COLOR_OK_TEXT, padx=6, pady=3).pack(fill="x")

            # последняя дозировка (плашка в стиле статусов)
            dosing_rows = get_dosing(self.conn, aq_id)
            if dosing_rows:
                d = dosing_rows[0]
                fert_name = d["fert_name"] or "Удобрение"
                dose_val = d["dose"]
                date_s = from_iso(d["date"])
                dose_frame = tk.Frame(right_col, bg="#1c1f2e", padx=6, pady=3)
                dose_frame.pack(fill="x", pady=(4, 0))
                tk.Label(dose_frame, text="Дозировка", font=(FF, 8),
                         bg="#1c1f2e", fg=COLOR_TEXT_MUTED).pack(anchor="w")
                tk.Label(dose_frame, text=f"{fert_name} {dose_val:g} мл",
                         font=(FF, 9, "bold"), bg="#1c1f2e", fg=COLOR_ACCENT).pack(side="left")
                tk.Label(dose_frame, text=f"  — {date_s}",
                         font=(FF, 9), bg="#1c1f2e", fg=COLOR_TEXT_MUTED).pack(side="left")
        else:
            tk.Label(left_col, text="Замеров пока нет", font=(FF, 9),
                     bg=COLOR_CARD, fg=COLOR_TEXT_MUTED).pack(anchor="w")

        # --- подмена воды: дней до следующей + краткая статистика ---
        self._build_water_change_block(card, aq_id, readings)

        # --- внесено за неделю ---
        self._build_weekly_dose_bars(card, aq_id)

    # ------------------------------------------------------------------
    # Блок подмены воды (прогресс-бар с заливкой по %)
    # ------------------------------------------------------------------

    def _build_water_change_block(self, card, aq_id, readings):
        FF = self.FF

        wc_frame = tk.Frame(card, bg=COLOR_CARD)
        wc_frame.pack(fill="x", pady=(6, 0))

        # находим последнюю подмену из readings
        last_wc_date = None
        last_wc_pct = None
        for r in (readings or []):
            if r.get("water_change_pct") is not None or r.get("water_change_l") is not None:
                last_wc_date = r["date"]
                last_wc_pct = r.get("water_change_pct")
                if last_wc_pct is None and r.get("water_change_l"):
                    aq = get_aquarium(self.conn, aq_id)
                    vol = aq["volume_l"] if aq else 0
                    if vol and vol > 0:
                        last_wc_pct = round(r["water_change_l"] / vol * 100, 1)
                break

        # рассчитываем дней до следующей подмены
        days_since = None
        days_until = None
        if last_wc_date:
            try:
                wc_d = dt.date.fromisoformat(last_wc_date)
                days_since = (dt.date.today() - wc_d).days
                if last_wc_pct and last_wc_pct >= 30:
                    interval = max(4, int(10 - last_wc_pct / 10))
                    days_until = max(0, interval - days_since)
                else:
                    interval = 7
                    days_until = max(0, interval - days_since)
            except (ValueError, TypeError):
                pass

        # верхняя строка: текст + прогноз
        top_row = tk.Frame(wc_frame, bg=COLOR_CARD)
        top_row.pack(fill="x", padx=4, pady=(4, 2))

        if last_wc_date:
            pct_str = f" {last_wc_pct:.0f}%" if last_wc_pct else ""
            wc_main = f"Подмена{pct_str} — {from_iso(last_wc_date)}"
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
            tk.Label(top_row, text="Подмен ещё не было", font=(FF, 9),
                     bg=COLOR_CARD, fg=COLOR_TEXT_MUTED).pack(side="left")
            tk.Label(top_row, text="Пора!", font=(FF, 10, "bold"),
                     bg=COLOR_CARD, fg=COLOR_WARN_TEXT).pack(side="right")

        # прогресс-бар: заливка по проценту подмены, цвет воды
        bar_outer = tk.Canvas(wc_frame, bg=COLOR_BORDER, highlightthickness=0, height=8)
        bar_outer.pack(fill="x", padx=4, pady=(2, 6))
        bar_outer.update_idletasks()

        # откладываем заливку чтобы canvas получил реальную ширину
        pct_for_bar = min(last_wc_pct or 0, 100) / 100.0

        def _draw_wc_bar():
            if not bar_outer.winfo_exists():
                return
            w = bar_outer.winfo_width()
            h = bar_outer.winfo_height()
            bar_outer.delete("all")
            if pct_for_bar > 0:
                fill_w = max(1, int(w * pct_for_bar))
                # градиент воды: от тёмно-синего к голубому
                bar_outer.create_rectangle(0, 0, fill_w, h, fill="#1a6b8a", outline="")
                bar_outer.create_rectangle(0, 0, fill_w, h // 2, fill="#2196a8", outline="")

        bar_outer.after(50, _draw_wc_bar)
        bar_outer.bind("<Configure>", lambda e: _draw_wc_bar())

    # ------------------------------------------------------------------
    # Внесено за неделю — горизонтальные бары
    # ------------------------------------------------------------------

    def _build_weekly_dose_bars(self, card, aq_id):
        FF = self.FF
        totals = sum_last_n_days(self.conn, aq_id, 7)

        week_end = dt.date.today()
        week_start = week_end - dt.timedelta(days=7)
        bar_label = (f"Внесено за 7 дней ({week_start.strftime('%d.%m')} - "
                     f"{week_end.strftime('%d.%m')}):")
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

