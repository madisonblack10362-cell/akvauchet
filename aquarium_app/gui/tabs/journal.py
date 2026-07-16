"""Вкладка «Журнал» — объединённый вид дозировок и показаний по дням."""
from __future__ import annotations

import datetime as dt
import tkinter as tk
from tkinter import ttk

from aquarium_app.config import (
    COLOR_BG, COLOR_CARD, COLOR_ACCENT, COLOR_BORDER, COLOR_TEXT,
    COLOR_TEXT_MUTED, COLOR_TEXT_SOFT, COLOR_OK_TEXT, COLOR_WARN_TEXT,
    COLOR_OK_BG, COLOR_ALT_ROW, COLOR_WARN, ELEMENT_COLORS, MEASURED_PARAM_KEYS,
    TEST_PARAMS, TEST_PARAM_RU, FONT_FAMILY,
)
from aquarium_app.db import (
    get_aquarium, get_targets, get_journal_data,
)
from aquarium_app.logic.formatters import from_iso, parse_float
from aquarium_app.logic.calculations import out_of_range_flags
from aquarium_app.gui.charts import draw_param_trend_chart, schedule_chart_draw


WEEKDAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


class JournalTab:
    """Mixin-класс с методами для вкладки «Журнал»."""

    # ------------------------------------------------------------------
    # Построение вкладки
    # ------------------------------------------------------------------

    def build_journal_tab(self):
        FF = self.FF
        parent = self.tab_journal

        # --- верхняя панель ---
        top = tk.Frame(parent, bg=COLOR_BG)
        top.pack(fill="x", padx=12, pady=(10, 4))

        ttk.Label(top, text="Аквариум:", background=COLOR_BG).pack(side="left")
        self.journal_aq_var = tk.StringVar()
        self.journal_aq_combo = ttk.Combobox(
            top, textvariable=self.journal_aq_var,
            state="readonly", width=30,
        )
        self.journal_aq_combo.pack(side="left", padx=(6, 0))
        self.journal_aq_combo.bind("<<ComboboxSelected>>",
                                    lambda e: self.refresh_journal())

        # --- фильтр периода ---
        filter_frame = tk.Frame(parent, bg=COLOR_BG)
        filter_frame.pack(fill="x", padx=12, pady=(6, 2))

        self._journal_filter_var = tk.StringVar(value="7d")
        filter_data = [("7d", "7 дн"), ("30d", "30 дн"), ("90d", "90 дн"), ("all", "Всё")]
        self._journal_filter_btns = {}
        for key, label in filter_data:
            b = tk.Button(
                filter_frame, text=label, font=(FF, 9),
                relief="flat", bg=COLOR_CARD, fg=COLOR_TEXT_MUTED,
                activebackground=COLOR_ALT_ROW, activeforeground=COLOR_TEXT,
                borderwidth=0, padx=8, pady=2, cursor="hand2",
                command=lambda k=key: self._set_journal_filter(k),
            )
            b.pack(side="left", padx=2)
            self._journal_filter_btns[key] = b
        self._update_journal_filter_buttons()

        # счётчик записей
        self.journal_count_label = tk.Label(
            filter_frame, text="", bg=COLOR_BG, fg=COLOR_TEXT_MUTED, font=(FF, 9))
        self.journal_count_label.pack(side="right", padx=(0, 4))

        # --- кнопки быстрого добавления ---
        btns_frame = tk.Frame(parent, bg=COLOR_BG)
        btns_frame.pack(fill="x", padx=12, pady=(2, 4))

        tk.Button(
            btns_frame, text="+ Доза", font=(FF, 9, "bold"),
            bg=COLOR_ACCENT, fg="#151515", relief="flat",
            padx=12, pady=3, cursor="hand2",
            command=self._journal_add_dose,
        ).pack(side="left", padx=(0, 6))
        tk.Button(
            btns_frame, text="+ Показания", font=(FF, 9, "bold"),
            bg=COLOR_CARD, fg=COLOR_TEXT, relief="flat",
            activebackground=COLOR_ALT_ROW,
            padx=12, pady=3, cursor="hand2",
            command=self._journal_add_reading,
        ).pack(side="left")

        # --- прокручиваемая область ---
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

        # прокрутка колесом
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
                btn.config(bg=COLOR_CARD, fg=COLOR_TEXT_MUTED)

    # ------------------------------------------------------------------
    # Обновление журнала
    # ------------------------------------------------------------------

    def refresh_journal(self):
        aq_id = self._current_journal_aq_id()
        # очистить старые карточки
        for w in self.journal_scroll_inner.winfo_children():
            w.destroy()

        if not aq_id:
            self.journal_count_label.config(text="")
            return

        # вычисляем период
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

        self.journal_count_label.config(text=f"{len(days_data)} дн.")

        today_iso = dt.date.today().isoformat()

        for day in days_data:
            self._build_journal_day_card(day, volume_l, aq_id, targets, today_iso)

    # ------------------------------------------------------------------
    # Карточка дня
    # ------------------------------------------------------------------

    def _build_journal_day_card(self, day_data, volume_l, aq_id, targets, today_iso):
        FF = self.FF
        parent = self.journal_scroll_inner

        date_iso = day_data["date"]
        dosing_list = day_data.get("dosing", [])
        readings = day_data.get("readings", {})

        # --- контейнер карточки ---
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

        tk.Label(hdr, text=date_display, bg=COLOR_CARD, fg=COLOR_ACCENT,
                 font=(FF, 11, "bold")).pack(side="left")

        if date_iso == today_iso:
            tk.Label(hdr, text="сегодня", bg=COLOR_ACCENT_SOFT, fg=COLOR_ACCENT,
                     font=(FF, 8, "bold"), padx=6, pady=1).pack(side="left", padx=(8, 0))

        # --- секция дозировок ---
        if dosing_list:
            sec = tk.Frame(inner, bg=COLOR_BG)
            sec.pack(fill="x", pady=(0, 6))
            sec_inner = tk.Frame(sec, bg=COLOR_BG)
            sec_inner.pack(fill="x", padx=8, pady=6)

            tk.Label(sec_inner, text="Удобрения", bg=COLOR_BG, fg=COLOR_TEXT_MUTED,
                     font=(FF, 8, "bold")).pack(anchor="w")

            for d_row in dosing_list:
                row = tk.Frame(sec_inner, bg=COLOR_BG)
                row.pack(fill="x", pady=1)
                fert_name = d_row.get("fert_name", "?")
                dose = d_row.get("dose", 0) or 0
                tk.Label(row, text=f"  {fert_name}", bg=COLOR_BG,
                         fg=COLOR_TEXT, font=(FF, 9)).pack(side="left")
                tk.Label(row, text=f"{dose:g} мл", bg=COLOR_BG,
                         fg=COLOR_TEXT_MUTED, font=(FF, 9)).pack(side="left", padx=(6, 0))
                if d_row.get("comment"):
                    tk.Label(row, text=f"  — {d_row['comment']}", bg=COLOR_BG,
                             fg=COLOR_TEXT_MUTED, font=(FF, 8, "italic")).pack(side="left")

        # --- секция показаний ---
        if readings and any(readings.get(k) is not None for k in MEASURED_PARAM_KEYS):
            sec = tk.Frame(inner, bg=COLOR_BG)
            sec.pack(fill="x", pady=(0, 6))
            sec_inner = tk.Frame(sec, bg=COLOR_BG)
            sec_inner.pack(fill="x", padx=8, pady=6)

            tk.Label(sec_inner, text="Показания", bg=COLOR_BG, fg=COLOR_TEXT_MUTED,
                     font=(FF, 8, "bold")).pack(anchor="w")

            # флаги предупреждений
            values_for_flags = {k: readings.get(k) for k in MEASURED_PARAM_KEYS}
            flags = out_of_range_flags(self.conn, aq_id, values_for_flags)

            params_row = tk.Frame(sec_inner, bg=COLOR_BG)
            params_row.pack(fill="x")

            for key, formula, unit in TEST_PARAMS:
                v = readings.get(key)
                if v is None:
                    continue
                # определим цвет
                rng = targets.get(key)
                in_range = True
                if rng and rng[0] is not None and rng[1] is not None:
                    if v < rng[0] or v > rng[1]:
                        in_range = False
                fg = COLOR_OK_TEXT if in_range else COLOR_WARN_TEXT

                lbl = tk.Label(params_row, text=f"{formula}: {v:g} {unit}".strip(),
                               bg=COLOR_BG, fg=fg, font=(FF, 9, "bold"))
                lbl.pack(side="left", padx=(0, 16))

            # предупреждения
            if flags:
                for f in flags:
                    tk.Label(sec_inner, text=f"  ⚠ {f}", bg=COLOR_BG,
                             fg=COLOR_WARN_TEXT, font=(FF, 8),
                             wraplength=500, anchor="w", justify="left").pack(
                        anchor="w", pady=(2, 0))

        # --- подмена воды ---
        wc_l = readings.get("water_change_l")
        wc_pct = readings.get("water_change_pct")
        if wc_l is not None or wc_pct is not None:
            parts = []
            if wc_l is not None:
                parts.append(f"{wc_l:g} л")
            if wc_pct is not None:
                parts.append(f"{wc_pct:.1f}%")
            tk.Label(inner, text=f"💧 Подмена воды: {', '.join(parts)}",
                     bg=COLOR_CARD, fg=COLOR_TEXT_MUTED, font=(FF, 9)).pack(
                anchor="w", pady=(2, 0))

        # --- мини-график (14-дневный тренд PO4/NO3) ---
        mini_chart = tk.Canvas(inner, bg=COLOR_CARD, height=70, highlightthickness=0)
        mini_chart.pack(fill="x", pady=(6, 0))
        self._schedule_journal_chart_draw(mini_chart, aq_id, date_iso)

        # --- комментарий ---
        cmt = readings.get("comment") or ""
        if cmt:
            tk.Label(inner, text=cmt, bg=COLOR_CARD, fg=COLOR_TEXT_MUTED,
                     font=(FF, 8, "italic"), wraplength=500, anchor="w",
                     justify="left").pack(anchor="w", pady=(4, 0))

    # ------------------------------------------------------------------
    # Мини-график в карточке дня
    # ------------------------------------------------------------------

    def _schedule_journal_chart_draw(self, canvas, aq_id, center_date_iso):
        """Отложенная отрисовка мини-графика."""
        def _deferred():
            if canvas.winfo_exists():
                self._draw_journal_chart(canvas, aq_id, center_date_iso)
        canvas.after(80, _deferred)

    def _draw_journal_chart(self, canvas, aq_id, center_date_iso):
        if not canvas.winfo_exists():
            return

        # 14-дневный тренд вокруг даты карточки
        try:
            center = dt.date.fromisoformat(center_date_iso)
        except Exception:
            center = dt.date.today()

        since = (center - dt.timedelta(days=13)).isoformat()
        to = (center + dt.timedelta(days=1)).isoformat()

        param_defs = [
            ("po4", ELEMENT_COLORS.get("po4", "#51cf66"), "PO4"),
            ("no3", ELEMENT_COLORS.get("no3", "#ff922b"), "NO3"),
        ]

        def history_fn(key):
            rows = self.conn.execute(
                "SELECT date, ? AS val FROM readings "
                "WHERE aquarium_id=? AND ? IS NOT NULL AND date>=? AND date<? "
                "ORDER BY date ASC",
                (key, aq_id, key, since, to),
            ).fetchall()
            return [(r["date"], r["val"]) for r in rows]

        draw_param_trend_chart(
            canvas, self.conn, aq_id, param_defs,
            since_iso=since,
            history_fn=history_fn,
            font_family=self.FF,
            empty_message="",
        )

    # ------------------------------------------------------------------
    # Переходы на другие вкладки
    # ------------------------------------------------------------------

    def _journal_add_dose(self):
        if hasattr(self, "switch_to_tab"):
            self.switch_to_tab("dosing")

    def _journal_add_reading(self):
        if hasattr(self, "switch_to_tab"):
            self.switch_to_tab("readings")