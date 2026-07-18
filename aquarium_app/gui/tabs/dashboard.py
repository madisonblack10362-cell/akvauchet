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
    COLOR_BG, COLOR_CARD, COLOR_ACCENT, COLOR_BORDER, COLOR_TEXT,
    COLOR_TEXT_MUTED, COLOR_TEXT_SOFT, COLOR_OK_TEXT, COLOR_OK_BG,
    COLOR_ACCENT_SOFT, COLOR_WARN, COLOR_WARN_TEXT,
    COLOR_STATUS_WAITING,
    MEASURED_PARAMS,
)
from aquarium_app.db import get_aquariums, get_aquarium, get_readings, get_dosing
from aquarium_app.logic.calculations import out_of_range_flags
from aquarium_app.logic.formatters import from_iso


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

            # --- статусы отклонений ---
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
        else:
            tk.Label(left_col, text="Замеров пока нет", font=(FF, 9),
                     bg=COLOR_CARD, fg=COLOR_TEXT_MUTED).pack(anchor="w")

        # --- подмена воды: дней до следующей + краткая статистика ---
        self._build_water_change_block(card, aq_id, readings)

        # --- последняя активность ---
        self._build_activity_line(card, aq_id, readings)

    # ------------------------------------------------------------------
    # Блок подмены воды (компактный, с прогнозом)
    # ------------------------------------------------------------------

    def _build_water_change_block(self, card, aq_id, readings):
        FF = self.FF

        wc_frame = tk.Frame(card, bg=COLOR_ACCENT_SOFT, highlightbackground=COLOR_ACCENT,
                            highlightthickness=1)
        wc_frame.pack(fill="x", pady=(6, 0))

        wc_row = tk.Frame(wc_frame, bg=COLOR_ACCENT_SOFT)
        wc_row.pack(fill="x", padx=10, pady=8)

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
                # рекомендации: при 30% подмене — раз в 5-7 дней, при 50% — раз в 7-10
                if last_wc_pct and last_wc_pct >= 30:
                    interval = max(4, int(10 - last_wc_pct / 10))  # 30% -> 7 дн, 50% -> 5 дн
                    days_until = max(0, interval - days_since)
                else:
                    interval = 7
                    days_until = max(0, interval - days_since)
            except (ValueError, TypeError):
                pass

        # левая часть: статус
        left = tk.Frame(wc_row, bg=COLOR_ACCENT_SOFT)
        left.pack(side="left", fill="both", expand=True)

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
            tk.Label(left, text=wc_main, font=(FF, 9),
                     bg=COLOR_ACCENT_SOFT, fg=COLOR_TEXT).pack(anchor="w")
        else:
            tk.Label(left, text="Подмен ещё не было", font=(FF, 9),
                     bg=COLOR_ACCENT_SOFT, fg=COLOR_TEXT_MUTED).pack(anchor="w")

        # правая часть: дней до следующей / предупреждение
        right = tk.Frame(wc_row, bg=COLOR_ACCENT_SOFT)
        right.pack(side="right")

        if days_until is not None:
            if days_until <= 0:
                hint, hclr = "Пора подменять!", COLOR_WARN_TEXT
            elif days_until == 1:
                hint, hclr = "Завтра подмена", COLOR_STATUS_WAITING
            elif days_until <= 3:
                hint, hclr = f"Через {days_until} дн.", COLOR_TEXT_MUTED
            else:
                hint, hclr = f"Через {days_until} дн.", COLOR_TEXT_MUTED
            tk.Label(right, text=hint, font=(FF, 10, "bold"),
                     bg=COLOR_ACCENT_SOFT, fg=hclr).pack(anchor="e")
        elif not last_wc_date:
            tk.Label(right, text="Пора подменять!", font=(FF, 10, "bold"),
                     bg=COLOR_ACCENT_SOFT, fg=COLOR_WARN_TEXT).pack(anchor="e")

    # ------------------------------------------------------------------
    # Последняя активность — хронология из 3 событий
    # ------------------------------------------------------------------

    def _build_activity_line(self, card, aq_id, readings):
        FF = self.FF

        act_frame = tk.Frame(card, bg=COLOR_CARD)
        act_frame.pack(fill="x", pady=(8, 0))

        tk.Label(act_frame, text="Последняя активность", font=(FF, 9, "bold"),
                 bg=COLOR_CARD, fg=COLOR_TEXT_MUTED).pack(anchor="w", pady=(0, 3))

        events = []

        # последний замер
        if readings:
            events.append((readings[0]["date"], "Замер", COLOR_TEXT))

        # последняя дозировка
        dosing_rows = get_dosing(self.conn, aq_id)
        if dosing_rows:
            d = dosing_rows[0]
            fert_name = d["fert_name"] or "Удобрение"
            events.append((d["date"], f"Дозировка: {fert_name}", COLOR_ACCENT))

        # последняя подмена (из readings)
        for r in (readings or []):
            if r.get("water_change_pct") is not None or r.get("water_change_l") is not None:
                events.append((r["date"], "Подмена воды", COLOR_OK_TEXT))
                break

        # сортируем по дате (убывание) и берём 3 свежих
        events.sort(key=lambda e: e[0], reverse=True)
        events = events[:3]

        if not events:
            tk.Label(act_frame, text="  Нет записей", font=(FF, 9),
                     bg=COLOR_CARD, fg=COLOR_TEXT_MUTED).pack(anchor="w")
            return

        row = tk.Frame(act_frame, bg=COLOR_CARD)
        row.pack(fill="x")

        for i, (date_iso, text, clr) in enumerate(events):
            if i > 0:
                tk.Label(row, text="  >  ", font=(FF, 9),
                         bg=COLOR_CARD, fg=COLOR_BORDER).pack(side="left")
            date_s = from_iso(date_iso)
            lbl_text = f"{date_s}  {text}"
            tk.Label(row, text=lbl_text, font=(FF, 9),
                     bg=COLOR_CARD, fg=clr).pack(side="left")