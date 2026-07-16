"""Вкладка «Обзор» — сводная информация по всем аквариумам."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from aquarium_app.config import (
    COLOR_BG, COLOR_CARD, COLOR_ACCENT, COLOR_BORDER, COLOR_TEXT,
    COLOR_TEXT_MUTED, COLOR_TEXT_SOFT, COLOR_OK_TEXT, COLOR_OK_BG,
    COLOR_ACCENT_SOFT, COLOR_WARN, COLOR_WARN_TEXT, ELEMENTS, ELEMENT_FORMULA,
    ELEMENT_RU, COLOR_ALT_ROW, COLOR_HEADER_TEXT,
    MEASURED_PARAMS,
)
from aquarium_app.db import get_aquariums, get_aquarium
from aquarium_app.logic.calculations import (
    sum_current_calendar_week, compute_element_ratios, out_of_range_flags,
)
from aquarium_app.logic.formatters import from_iso
from aquarium_app.gui.charts import draw_element_bars, schedule_chart_draw
from aquarium_app.db import get_water_change_stats


class DashboardTab:
    """Миксин-вкладка «Обзор»."""

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

        # два столбца: замеры + статусы
        two_col = tk.Frame(card, bg=COLOR_CARD)
        two_col.pack(fill="x", pady=(0, 6))

        left_col = tk.Frame(two_col, bg=COLOR_CARD)
        left_col.pack(side="left", fill="both", expand=True)

        right_col = tk.Frame(two_col, bg=COLOR_CARD)
        right_col.pack(side="left", fill="both", expand=True, padx=(12, 0))

        # --- последние замеры ---
        from aquarium_app.db import get_readings
        readings = get_readings(self.conn, aq_id)
        if readings:
            latest = readings[0]
            tk.Label(left_col, text="Последний замер", font=(FF, 9, "bold"),
                     bg=COLOR_CARD, fg=COLOR_TEXT_SOFT).pack(anchor="w")
            tk.Label(left_col, text=from_iso(latest["date"]), font=(FF, 9),
                     bg=COLOR_CARD, fg=COLOR_TEXT_MUTED).pack(anchor="w", pady=(0, 4))

            for key, label, unit in MEASURED_PARAMS:
                v = latest.get(key)
                if v is not None:
                    unit_s = f" {unit}" if unit else ""
                    row = tk.Frame(left_col, bg=COLOR_CARD)
                    row.pack(fill="x", pady=1)
                    tk.Label(row, text=f"{label}:", font=(FF, 9),
                             bg=COLOR_CARD, fg=COLOR_TEXT_MUTED, width=14, anchor="w").pack(side="left")
                    tk.Label(row, text=f"{v:g}{unit_s}", font=(FF, 9, "bold"),
                             bg=COLOR_CARD, fg=COLOR_TEXT).pack(side="left")

            # статусы
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

        # --- бары элементов за неделю ---
        totals, week_start, week_end = sum_current_calendar_week(self.conn, aq_id)
        bar_label = (f"Внесено за неделю ({week_start.strftime('%d.%m')} - "
                     f"{week_end.strftime('%d.%m')}):")
        tk.Label(card, text=bar_label, font=(FF, 9, "bold"),
                 bg=COLOR_CARD, fg=COLOR_ACCENT_SOFT).pack(anchor="w", pady=(6, 2))

        bar_canvas = tk.Canvas(card, bg=COLOR_CARD, highlightthickness=0, height=28)
        bar_canvas.pack(fill="x", pady=(0, 4))
        items = []
        for ek, formula, ru in ELEMENTS:
            v = totals.get(ek, 0.0)
            if v > 0:
                items.append((ru, formula, v))
        if items:
            schedule_chart_draw(bar_canvas, draw_element_bars, items, font_family=self.FF)

        # --- соотношения элементов ---
        ratios = compute_element_ratios(totals)
        if ratios:
            ratio_frame = tk.Frame(card, bg=COLOR_CARD)
            ratio_frame.pack(fill="x", pady=(4, 2))
            tk.Label(ratio_frame, text="Соотношения:", font=(FF, 9, "bold"),
                     bg=COLOR_CARD, fg=COLOR_TEXT_SOFT).pack(anchor="w")
            for r in ratios:
                row = tk.Frame(ratio_frame, bg=COLOR_CARD)
                row.pack(fill="x", pady=1)
                if r["ratio"] is not None:
                    if r["status"] == "ok":
                        clr = COLOR_OK_TEXT
                        note_s = ""
                    else:
                        clr = COLOR_WARN_TEXT
                        note_s = f" - {r['note']}" if r.get("note") else ""
                    txt = f"{r['label']}: {r['ratio']:.1f} (норма {r['lo']:.0f}-{r['hi']:.0f}){note_s}"
                else:
                    clr = COLOR_TEXT_MUTED
                    txt = f"{r['label']}: недостаточно данных"
                tk.Label(row, text=txt, font=(FF, 9), bg=COLOR_CARD, fg=clr,
                         anchor="w", wraplength=500, justify="left").pack(anchor="w")

        # --- индикатор подмены воды (за неделю) ---
        wc_stats = get_water_change_stats(self.conn, aq_id, days=7)
        wc_frame = tk.Frame(card, bg=COLOR_ACCENT_SOFT, highlightbackground=COLOR_ACCENT,
                            highlightthickness=1)
        wc_frame.pack(fill="x", pady=(8, 0))

        wc_hdr = tk.Frame(wc_frame, bg=COLOR_ACCENT_SOFT)
        wc_hdr.pack(fill="x", padx=10, pady=(8, 2))
        tk.Label(wc_hdr, text="💧", font=(FF, 12),
                 bg=COLOR_ACCENT_SOFT, fg=COLOR_TEXT).pack(side="left")
        tk.Label(wc_hdr, text="  Подмена воды", font=(FF, 10, "bold"),
                 bg=COLOR_ACCENT_SOFT, fg=COLOR_ACCENT).pack(side="left")

        if wc_stats["count"] > 0:
            wc_body = tk.Frame(wc_frame, bg=COLOR_ACCENT_SOFT)
            wc_body.pack(fill="x", padx=10, pady=(0, 4))

            # последняя подмена — главное число
            if wc_stats["last_pct"] is not None:
                last_txt = f"Последняя: {wc_stats['last_pct']:.1f}%"
            elif wc_stats["last_l"] is not None:
                last_txt = f"Последняя: {wc_stats['last_l']:g} л"
            else:
                last_txt = ""
            tk.Label(wc_body, text=last_txt,
                     font=(FF, 11, "bold"), bg=COLOR_ACCENT_SOFT,
                     fg=COLOR_TEXT).pack(side="left")

            if wc_stats["last_date"]:
                tk.Label(wc_body, text=f"  {from_iso(wc_stats['last_date'])}",
                         font=(FF, 10), bg=COLOR_ACCENT_SOFT,
                         fg=COLOR_TEXT_MUTED).pack(side="left")

            # итог за неделю
            wc_summary = tk.Frame(wc_frame, bg=COLOR_ACCENT_SOFT)
            wc_summary.pack(fill="x", padx=10, pady=(0, 8))
            parts = [f"{wc_stats['count']} раз за 7 дн"]
            if wc_stats["total_pct"] > 0:
                parts.append(f"итого {wc_stats['total_pct']:.0f}% объёма")
            tk.Label(wc_summary, text="  |  ".join(parts),
                     font=(FF, 9), bg=COLOR_ACCENT_SOFT,
                     fg=COLOR_TEXT_MUTED).pack(anchor="w")

            # индикатор достаточности
            if wc_stats["total_pct"] < 30:
                wc_tip = "  ⚠ Мало подмен — рекомендуется от 30% в неделю"
                tip_clr = COLOR_WARN_TEXT
            elif wc_stats["total_pct"] >= 50:
                wc_tip = "  ✓ Подмены в норме"
                tip_clr = COLOR_OK_TEXT
            else:
                wc_tip = ""
                tip_clr = COLOR_TEXT_MUTED
            if wc_tip:
                tip_row = tk.Frame(wc_frame, bg=COLOR_ACCENT_SOFT)
                tip_row.pack(fill="x", padx=10, pady=(0, 8))
                tk.Label(tip_row, text=wc_tip, font=(FF, 9),
                         bg=COLOR_ACCENT_SOFT, fg=tip_clr).pack(anchor="w")
        else:
            tk.Label(wc_frame, text="  Подмен не было неделю — пора!",
                     font=(FF, 10), bg=COLOR_ACCENT_SOFT,
                     fg=COLOR_WARN_TEXT).pack(anchor="w", padx=10, pady=(0, 8))