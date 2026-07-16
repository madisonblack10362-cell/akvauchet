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

    # ------------------------------------------------------------------
    # Построение вкладки
    # ------------------------------------------------------------------

    def build_dashboard_tab(self):
        """Создаёт заголовок и прокручиваемую область с `self.dash_container`."""
        tab = self.tab_dashboard  # type: tk.Frame
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

        vscroll = ttk.Scrollbar(outer, orient="vertical")
        vscroll.pack(side="right", fill="y")

        self.dash_container = tk.Frame(outer, bg=COLOR_BG)
        self.dash_container.pack(side="left", fill="both", expand=True)

        self.dash_canvas = tk.Canvas(outer, bg=COLOR_BG, highlightthickness=0,
                                     yscrollcommand=vscroll.set)
        self.dash_canvas.pack(side="left", fill="both", expand=True)
        vscroll.config(command=self.dash_canvas.yview)

        self.dash_inner = tk.Frame(self.dash_canvas, bg=COLOR_BG)
        self.dash_canvas.create_window((0, 0), window=self.dash_inner, anchor="nw")
        self.dash_inner.bind("<Configure>",
                             lambda e: self.dash_canvas.configure(
                                 scrollregion=self.dash_canvas.bbox("all")))

        # enable mouse-wheel scrolling
        def _on_mousewheel(event):
            self.dash_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self.dash_canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # отложенная первая загрузка
        self.dash_canvas.after(100, self.refresh_dashboard)

    # ------------------------------------------------------------------
    # Обновление
    # ------------------------------------------------------------------

    def refresh_dashboard(self):
        """Перерисовывает карточки всех аквариумов."""
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

        # обновляем scrollregion после отрисовки
        container.update_idletasks()
        self.dash_canvas.configure(scrollregion=self.dash_canvas.bbox("all"))

    # ------------------------------------------------------------------
    # Карточка одного аквариума
    # ------------------------------------------------------------------

    def _build_aquarium_card(self, parent, aq):
        FF = self.FF
        aq_id = aq["id"]

        card = tk.LabelFrame(parent, text=f"  {aq['name']}  ", font=(FF, 11, "bold"),
                             bg=COLOR_CARD, fg=COLOR_ACCENT, bd=1, relief="solid",
                             highlightbackground=COLOR_BORDER, padx=12, pady=8)
        card.pack(fill="x", padx=6, pady=(0, 10))

        # --- основная информация ---
        info_row = tk.Frame(card, bg=COLOR_CARD)
        info_row.pack(fill="x", pady=(0, 6))
        parts = [f"Объём: {aq['volume_l']:.0f} л"]
        if aq["co2"]:
            parts.append(f"CO₂: {aq['co2']}")
        if aq["light"]:
            parts.append(f"Свет: {aq['light']}")
        tk.Label(info_row, text="   |   ".join(parts), font=(FF, 10),
                 bg=COLOR_CARD, fg=COLOR_TEXT_MUTED).pack(anchor="w")

        # --- последние замеры (измеряемые параметры) ---
        from aquarium_app.db import get_readings
        readings = get_readings(self.conn, aq_id)
        if readings:
            latest = readings[0]
            measured_row = tk.Frame(card, bg=COLOR_CARD)
            measured_row.pack(fill="x", pady=(2, 4))
            tk.Label(measured_row, text="Последний замер: ", font=(FF, 9, "bold"),
                     bg=COLOR_CARD, fg=COLOR_TEXT_SOFT).pack(side="left")
            parts_m = [f"{from_iso(latest['date'])}"]
            for key, label, unit in MEASURED_PARAMS:
                v = latest.get(key)
                if v is not None:
                    unit_s = f" {unit}" if unit else ""
                    parts_m.append(f"{label}={v:g}{unit_s}")
            tk.Label(measured_row, text="  ".join(parts_m), font=(FF, 9),
                     bg=COLOR_CARD, fg=COLOR_TEXT_MUTED).pack(side="left", fill="x", expand=True)

            # --- out-of-range предупреждения ---
            values = {key: latest.get(key) for key, _, _ in MEASURED_PARAMS}
            flags = out_of_range_flags(self.conn, aq_id, values)
            if flags:
                warn_frame = tk.Frame(card, bg=COLOR_OK_BG)
                warn_frame.pack(fill="x", pady=(0, 6))
                for flag in flags:
                    tk.Label(warn_frame, text=f"⚠ {flag}", font=(FF, 9),
                             bg=COLOR_WARN, fg=COLOR_WARN_TEXT, anchor="w",
                             padx=6, pady=2).pack(fill="x")
            else:
                ok_frame = tk.Frame(card, bg=COLOR_OK_BG)
                ok_frame.pack(fill="x", pady=(0, 6))
                tk.Label(ok_frame, text="✔ Все параметры в норме", font=(FF, 9),
                         bg=COLOR_OK_BG, fg=COLOR_OK_TEXT, padx=6, pady=2).pack(anchor="w")

        # --- бары элементов за неделю ---
        totals, week_start, week_end = sum_current_calendar_week(self.conn, aq_id)
        bar_label = (f"Внесено за неделю ({week_start.strftime('%d.%m')} – "
                     f"{week_end.strftime('%d.%m')}):")
        tk.Label(card, text=bar_label, font=(FF, 9, "bold"),
                 bg=COLOR_CARD, fg=COLOR_ACCENT_SOFT).pack(anchor="w", pady=(4, 2))

        bar_canvas = tk.Canvas(card, bg=COLOR_CARD, highlightthickness=0, height=24)
        bar_canvas.pack(fill="x", pady=(0, 4))
        items = []
        for ek, formula, ru in ELEMENTS:
            v = totals.get(ek, 0.0)
            if v > 0:
                items.append((ru, formula, v))
        if items:
            self._schedule_chart_draw(bar_canvas, draw_element_bars, items)

        # --- соотношения элементов ---
        ratios = compute_element_ratios(totals)
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
                elif r["status"] == "low":
                    clr = COLOR_WARN_TEXT
                    note_s = f" — {r['note']}" if r.get("note") else ""
                else:
                    clr = COLOR_WARN_TEXT
                    note_s = f" — {r['note']}" if r.get("note") else ""
                txt = f"{r['label']}: {r['ratio']:.1f} (норма {r['lo']:.0f}–{r['hi']:.0f}){note_s}"
            else:
                clr = COLOR_TEXT_MUTED
                txt = f"{r['label']}: недостаточно данных"
            tk.Label(row, text=txt, font=(FF, 9), bg=COLOR_CARD, fg=clr,
                     anchor="w", wraplength=600, justify="left").pack(anchor="w")

        # --- статистика подмен воды (30 дней) ---
        wc_stats = get_water_change_stats(self.conn, aq_id, days=30)
        if wc_stats["count"] > 0:
            wc_frame = tk.Frame(card, bg=COLOR_ACCENT_SOFT)
            wc_frame.pack(fill="x", pady=(6, 2))
            wc_parts = [f"Подмены воды (30 дн): {wc_stats['count']} раз"]
            if wc_stats["total_pct"] > 0:
                wc_parts.append(f"∑ {wc_stats['total_pct']:.0f}%")
            if wc_stats["total_l"] > 0:
                wc_parts.append(f"∑ {wc_stats['total_l']:.0f} л")
            if wc_stats["last_date"]:
                wc_parts.append(f"последняя {from_iso(wc_stats['last_date'])}")
            tk.Label(wc_frame, text="  |  ".join(wc_parts), font=(FF, 9),
                     bg=COLOR_ACCENT_SOFT, fg=COLOR_TEXT_MUTED, padx=6,
                     pady=4).pack(anchor="w")

    # ------------------------------------------------------------------
    # Вспомогательные
    # ------------------------------------------------------------------

    def _schedule_chart_draw(self, canvas, items):
        """Отложенная отрисовка баров с перерисовкой при ресайзе."""
        schedule_chart_draw(canvas, draw_element_bars, items, font_family=self.FF)

    def _element_color(self, formula):
        """Цвет по группе элемента (макро / железо / прочие микро)."""
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

    def _draw_element_bars(self, canvas, items):
        """Обёртка над draw_element_bars из gui.charts."""
        draw_element_bars(canvas, items, font_family=self.FF)