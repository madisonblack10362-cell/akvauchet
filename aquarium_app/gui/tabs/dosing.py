"""Вкладка «Дозирование» — журнал дозировок с живым превью, визуальными сводками и графиками."""

from __future__ import annotations

import datetime as dt
import json
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from aquarium_app.config import (
    COLOR_BG, COLOR_CARD, COLOR_ACCENT, COLOR_BORDER, COLOR_TEXT,
    COLOR_TEXT_MUTED, COLOR_TEXT_SOFT, COLOR_ACCENT_HOVER, COLOR_ALT_ROW,
    COLOR_ACCENT_SOFT, COLOR_WARN_TEXT, COLOR_OK_TEXT, COLOR_WARN,
    ELEMENT_KEYS, ELEMENT_FORMULA, ELEMENT_RU, ELEMENT_COLORS,
    MEASURED_PARAMS, SPIN_SETTINGS,
)
from aquarium_app.db import (
    get_aquariums, get_aquarium,
    get_dosing, get_dosing_filtered, get_dosing_entry, add_dosing,
    update_dosing, delete_dosing, get_fertilizers, get_targets,
)
from aquarium_app.logic.calculations import (
    compute_deltas, sum_range_totals,
    get_element_dosing_cumulative_history, get_element_dosing_daily_history,
)
from aquarium_app.logic.formatters import from_iso, today_str, to_iso, parse_float
from aquarium_app.gui.charts import (
    draw_param_trend_chart, draw_daily_bars_chart, schedule_chart_draw,
)
from aquarium_app.gui.widgets import DateEntry, SpinEntry

# Ключевые элементы для сводных карточек
SUMMARY_KEYS = ["po4", "no3", "k", "fe", "mg"]
SUMMARY_INFO = {
    "no3": ("Нитрат", "NO3", ELEMENT_COLORS["no3"]),
    "po4": ("Фосфат", "PO4", ELEMENT_COLORS["po4"]),
    "k": ("Калий", "K", ELEMENT_COLORS["k"]),
    "fe": ("Железо", "Fe", ELEMENT_COLORS["fe"]),
    "mg": ("Магний", "Mg", ELEMENT_COLORS["mg"]),
}


class DosingTab:
    """Миксин-вкладка «Дозирование» — профессиональный интерфейс с живым превью."""

    # ------------------------------------------------------------------
    # Построение вкладки
    # ------------------------------------------------------------------

    def build_dosing_tab(self):
        tab = self.tab_dosing
        FF = self.FF

        # ---- верхняя панель: аквариум + период + калькулятор ----
        top = tk.Frame(tab, bg=COLOR_BG)
        top.pack(fill="x", padx=12, pady=(12, 4))

        tk.Label(top, text="Аквариум:", font=(FF, 10),
                 bg=COLOR_BG, fg=COLOR_TEXT_SOFT).pack(side="left")
        self.dose_aq_combo = ttk.Combobox(top, width=28, state="readonly")
        self.dose_aq_combo.pack(side="left", padx=(4, 16))
        self.dose_aq_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_dosing_table())

        # компактные фильтры периода
        self._dose_filter = "7d"
        filter_data = [("7d", "7 дн"), ("30d", "30 дн"), ("90d", "90 дн"), ("all", "Всё")]
        self.dose_filter_btns = {}
        for key, label in filter_data:
            b = tk.Button(top, text=label, font=(FF, 8), relief="flat",
                          bg=COLOR_ALT_ROW, fg=COLOR_TEXT_MUTED, borderwidth=0,
                          padx=8, pady=2, cursor="hand2",
                          command=lambda k=key: self._set_dose_filter(k))
            b.pack(side="left", padx=2)
            self.dose_filter_btns[key] = b

        tk.Button(top, text="Калькулятор", font=(FF, 9), relief="flat",
                  bg=COLOR_ACCENT_SOFT, fg=COLOR_ACCENT, activebackground=COLOR_ALT_ROW,
                  activeforeground=COLOR_ACCENT, borderwidth=0, padx=10, pady=3,
                  command=self._open_dose_calculator, cursor="hand2").pack(side="right")
        tk.Button(top, text="Экспорт JSON", font=(FF, 9), relief="flat",
                  bg=COLOR_CARD, fg=COLOR_TEXT, activebackground=COLOR_ALT_ROW,
                  borderwidth=0, padx=10, pady=3, cursor="hand2",
                  command=self.export_dosing_json).pack(side="right", padx=(0, 6))

        # ---- сводная полоса: карточки элементов ----
        self._dose_summary_frame = tk.Frame(tab, bg=COLOR_BG)
        self._dose_summary_frame.pack(fill="x", padx=12, pady=(4, 4))

        # ---- график тренда ----
        chart_outer = tk.Frame(tab, bg=COLOR_CARD,
                               highlightbackground=COLOR_BORDER, highlightthickness=1)
        chart_outer.pack(fill="x", padx=12, pady=(0, 4))

        # панель управления графиком
        chart_bar = tk.Frame(chart_outer, bg=COLOR_CARD)
        chart_bar.pack(fill="x", padx=8, pady=(4, 2))

        tk.Label(chart_bar, text="Тренд внесения", font=(FF, 9, "bold"),
                 bg=COLOR_CARD, fg=COLOR_ACCENT).pack(side="left")

        # режим графика
        self._dosing_trend_mode = "daily"
        self.dosing_trend_mode_btns = {}
        for key, label in [("daily", "По дням"), ("cumulative", "Нарастающий")]:
            b = tk.Button(chart_bar, text=label, font=(FF, 8), relief="flat",
                          bg=COLOR_ALT_ROW, fg=COLOR_TEXT_MUTED, borderwidth=0,
                          padx=6, pady=1, cursor="hand2",
                          command=lambda k=key: self._set_dosing_trend_mode(k))
            b.pack(side="left", padx=(8, 1))
            self.dosing_trend_mode_btns[key] = b

        self._dosing_trend_filter = "7d"
        self.dosing_trend_filter_btns = {}
        for key, label in [("7d", "7д"), ("30d", "30д"), ("90d", "90д"), ("all", "Всё")]:
            b = tk.Button(chart_bar, text=label, font=(FF, 8), relief="flat",
                          bg=COLOR_ALT_ROW, fg=COLOR_TEXT_MUTED, borderwidth=0,
                          padx=5, pady=1, cursor="hand2",
                          command=lambda k=key: self._set_dosing_trend_filter(k))
            b.pack(side="left", padx=1)
            self.dosing_trend_filter_btns[key] = b

        self.dosing_trend_canvas = tk.Canvas(chart_outer, bg=COLOR_CARD,
                                             highlightthickness=0, height=180)
        self.dosing_trend_canvas.pack(fill="x", padx=8, pady=(0, 6))

        # ---- форма добавления с живым превью ----
        add_frame = tk.LabelFrame(tab, text="  Добавить дозировку  ", font=(FF, 10, "bold"),
                                  bg=COLOR_CARD, fg=COLOR_ACCENT, bd=1, relief="solid")
        add_frame.pack(fill="x", padx=12, pady=4)

        row1 = tk.Frame(add_frame, bg=COLOR_CARD)
        row1.pack(fill="x", padx=8, pady=6)

        tk.Label(row1, text="Дата:", font=(FF, 9), bg=COLOR_CARD,
                 fg=COLOR_TEXT_SOFT).pack(side="left")
        self.dose_date_entry = DateEntry(row1, font_family=FF, width=12)
        self.dose_date_entry.pack(side="left", padx=(2, 12))

        tk.Label(row1, text="Удобрение:", font=(FF, 9), bg=COLOR_CARD,
                 fg=COLOR_TEXT_SOFT).pack(side="left")
        self.dose_fert_combo = ttk.Combobox(row1, width=24, state="readonly")
        self.dose_fert_combo.pack(side="left", padx=(2, 12))
        self.dose_fert_combo.bind("<<ComboboxSelected>>", lambda e: self._update_dose_preview())

        tk.Label(row1, text="Доза (мл):", font=(FF, 9), bg=COLOR_CARD,
                 fg=COLOR_TEXT_SOFT).pack(side="left")
        self.dose_spin = SpinEntry(row1, width=7, step=0.1, default="1.0",
                                    font_family=FF)
        self.dose_spin.pack(side="left", padx=(2, 0))
        self.dose_spin.var.trace_add("write", lambda *_: self._update_dose_preview())

        tk.Button(row1, text="Добавить", font=(FF, 9, "bold"), relief="flat",
                  bg=COLOR_ACCENT, fg="#151515", activebackground=COLOR_ACCENT_HOVER,
                  activeforeground="#151515", borderwidth=0, padx=12, pady=3,
                  command=self.add_dosing_entry, cursor="hand2").pack(side="right")

        # живое превью прироста элементов
        self._dose_preview_frame = tk.Frame(add_frame, bg=COLOR_BG)
        self._dose_preview_frame.pack(fill="x", padx=8, pady=(0, 2))

        # комментарий
        row2 = tk.Frame(add_frame, bg=COLOR_CARD)
        row2.pack(fill="x", padx=8, pady=(4, 6))
        tk.Label(row2, text="Комментарий:", font=(FF, 9), bg=COLOR_CARD,
                 fg=COLOR_TEXT_SOFT).pack(side="left")
        self.dose_comment_var = tk.StringVar()
        ttk.Entry(row2, textvariable=self.dose_comment_var, width=50).pack(
            side="left", padx=(2, 0), fill="x", expand=True)

        # кнопки над таблицей
        btn_row = tk.Frame(tab, bg=COLOR_BG)
        btn_row.pack(fill="x", padx=16, pady=(4, 0))
        tk.Button(btn_row, text="Редактировать", font=(FF, 9), relief="flat",
                  bg=COLOR_CARD, fg=COLOR_TEXT, activebackground=COLOR_ALT_ROW,
                  borderwidth=0, padx=12, pady=4, command=self.edit_dosing_entry,
                  cursor="hand2").pack(side="left")
        tk.Button(btn_row, text="Удалить", font=(FF, 9), relief="flat",
                  bg=COLOR_CARD, fg=COLOR_TEXT, activebackground=COLOR_ALT_ROW,
                  borderwidth=0, padx=12, pady=4, command=self.delete_dosing_selected,
                  cursor="hand2").pack(side="left", padx=(8, 0))

        # ---- таблица дозировок ----
        table_frame = tk.Frame(tab, bg=COLOR_BG)
        table_frame.pack(fill="both", expand=True, padx=12, pady=(4, 12))

        dose_cols = ("date", "fert", "dose", "comment",
                     "no3", "po4", "k", "fe", "mg", "ca")
        self.dose_tree = ttk.Treeview(table_frame, columns=dose_cols, show="headings",
                                       height=8, selectmode="browse")
        self.dose_tree.heading("date", text="Дата")
        self.dose_tree.heading("fert", text="Удобрение")
        self.dose_tree.heading("dose", text="Доза")
        self.dose_tree.heading("comment", text="Комментарий")
        self.dose_tree.heading("no3", text="NO3")
        self.dose_tree.heading("po4", text="PO4")
        self.dose_tree.heading("k", text="K")
        self.dose_tree.heading("fe", text="Fe")
        self.dose_tree.heading("mg", text="Mg")
        self.dose_tree.heading("ca", text="Ca")

        self.dose_tree.column("date", width=90, minwidth=80)
        self.dose_tree.column("fert", width=160, minwidth=100)
        self.dose_tree.column("dose", width=60, minwidth=50, anchor="center")
        self.dose_tree.column("comment", width=140, minwidth=80)
        for ek in ("no3", "po4", "k", "fe", "mg", "ca"):
            self.dose_tree.column(ek, width=55, minwidth=45, anchor="center")

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.dose_tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=self.dose_tree.xview)
        self.dose_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.dose_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # инициализация
        self._fert_map = {}
        self.refresh_dosing_aq_combo()
        self._refresh_fert_dropdown()
        self._update_filter_buttons()
        self._update_dosing_trend_filter_buttons()
        self._update_dosing_trend_mode_buttons()

    # ------------------------------------------------------------------
    # Живое превью прироста при вводе дозы
    # ------------------------------------------------------------------

    def _update_dose_preview(self):
        """Обновляет превью прироста элементов при изменении удобрения или дозы."""
        for w in self._dose_preview_frame.winfo_children():
            w.destroy()

        fert_name = getattr(self, "dose_fert_combo", None)
        if fert_name is None or not fert_name.winfo_exists():
            return
        fert_name = fert_name.get()
        if not fert_name:
            return

        fert_id = self._fert_map.get(fert_name)
        if fert_id is None:
            return
        fert = get_fertilizer(self.conn, fert_id)
        if not fert:
            return

        dose_str = self.dose_spin.get().strip()
        dose = parse_float(dose_str, 0) or 0
        if dose <= 0:
            tk.Label(self._dose_preview_frame, text="Выберите дозу для просмотра прироста",
                     bg=COLOR_BG, fg=COLOR_TEXT_MUTED, font=(self.FF, 8, "italic")).pack(
                anchor="w", padx=4, pady=2)
            return

        # получаем объём аквариума
        aq_id = getattr(self, "_dosing_aq_id", None)
        aq = get_aquarium(self.conn, aq_id) if aq_id else None
        volume = aq["volume_l"] if aq and aq["volume_l"] else 1.0

        deltas = compute_deltas(fert, dose, volume)
        active = [(ek, deltas[ek]) for ek in ELEMENT_KEYS if deltas[ek] > 0]

        if not active:
            return

        preview_inner = tk.Frame(self._dose_preview_frame, bg=COLOR_BG)
        preview_inner.pack(fill="x")

        tk.Label(preview_inner, text="Прирост:", bg=COLOR_BG, fg=COLOR_TEXT_MUTED,
                 font=(self.FF, 8, "bold")).pack(side="left", padx=(0, 6))

        macro = {"no3", "po4", "k"}
        for ek, val in active:
            color = ELEMENT_COLORS.get(ek, COLOR_ACCENT)
            formula = ELEMENT_FORMULA.get(ek, ek)
            if ek in macro:
                txt = f"{formula} +{val:.1f}"
            elif val < 0.01:
                txt = f"{formula} +{val:.4f}"
            elif val < 1:
                txt = f"{formula} +{val:.3f}"
            else:
                txt = f"{formula} +{val:.2f}"
            tk.Label(preview_inner, text=txt, bg=COLOR_BG, fg=color,
                     font=(self.FF, 8, "bold")).pack(side="left", padx=(0, 10))

    # ------------------------------------------------------------------
    # Сводная полоса элементов
    # ------------------------------------------------------------------

    def _build_summary_strip(self, totals, period_str):
        FF = self.FF
        for w in self._dose_summary_frame.winfo_children():
            w.destroy()

        if not totals or all(v == 0 for v in totals.values()):
            tk.Label(self._dose_summary_frame, text=f"Нет данных за {period_str}",
                     bg=COLOR_BG, fg=COLOR_TEXT_MUTED, font=(FF, 9, "italic")).pack(
                anchor="w", padx=4, pady=4)
            return

        tk.Label(self._dose_summary_frame, text=f"Внесено {period_str}:",
                 bg=COLOR_BG, fg=COLOR_TEXT_MUTED, font=(FF, 9, "bold")).pack(
            side="left", padx=(0, 8), pady=4)

        for ek in SUMMARY_KEYS:
            v = totals.get(ek, 0.0)
            if v <= 0:
                continue
            ru, formula, color = SUMMARY_INFO[ek]
            card = tk.Frame(self._dose_summary_frame, bg=COLOR_CARD,
                            highlightbackground=COLOR_BORDER, highlightthickness=1)
            card.pack(side="left", padx=(0, 4), pady=4)
            inner = tk.Frame(card, bg=COLOR_CARD)
            inner.pack(padx=8, pady=4)
            # цветная полоска сверху
            tk.Frame(inner, bg=color, height=3).pack(fill="x", pady=(0, 4))
            # название
            tk.Label(inner, text=formula, bg=COLOR_CARD, fg=COLOR_TEXT_MUTED,
                     font=(FF, 8)).pack(anchor="w")
            # значение
            if ek in ("no3", "po4", "k"):
                val_text = f"{v:.1f}"
            elif v < 0.01:
                val_text = f"{v:.4f}"
            elif v < 1:
                val_text = f"{v:.3f}"
            else:
                val_text = f"{v:.2f}"
            tk.Label(inner, text=f"{val_text} мг/л", bg=COLOR_CARD, fg=color,
                     font=(FF, 11, "bold")).pack(anchor="w")

    # ------------------------------------------------------------------
    # Выпадающие списки
    # ------------------------------------------------------------------

    def refresh_dosing_aq_combo(self):
        combo = getattr(self, "dose_aq_combo", None)
        if combo is None or not combo.winfo_exists():
            return
        aquariums = get_aquariums(self.conn)
        names = [a["name"] for a in aquariums]
        combo["values"] = names
        if names and not combo.get():
            combo.current(0)
        if combo.get():
            self.refresh_dosing_table()

    def _refresh_fert_dropdown(self):
        combo = getattr(self, "dose_fert_combo", None)
        if combo is None or not combo.winfo_exists():
            return
        ferts = get_fertilizers(self.conn)
        names = []
        self._fert_map = {}
        for f in ferts:
            name = f["name"] or ""
            names.append(name)
            self._fert_map[name] = f["id"]
        combo["values"] = names
        cur = combo.get()
        if cur and cur not in names:
            combo.set("")

    # ------------------------------------------------------------------
    # Обновление таблицы дозировок
    # ------------------------------------------------------------------

    def refresh_dosing_table(self):
        combo = getattr(self, "dose_aq_combo", None)
        if combo is None or not combo.winfo_exists():
            return
        aq_name = combo.get()
        if not aq_name:
            return

        aquariums = get_aquariums(self.conn)
        aq = None
        for a in aquariums:
            if a["name"] == aq_name:
                aq = a
                break
        if not aq:
            return
        aq_id = aq["id"]
        self._dosing_aq_id = aq_id

        date_from, date_to = self._get_dose_filter_range()
        rows = get_dosing_filtered(self.conn, aq_id,
                                    date_from=date_from, date_to=date_to)

        tree = self.dose_tree
        if not tree.winfo_exists():
            return
        tree.delete(*tree.get_children())

        volume = aq["volume_l"] or 1.0

        for r in rows:
            delta = compute_deltas(r, r["dose"], volume)
            comment = r["comment"] or ""
            vals = (
                from_iso(r["date"]),
                r["fert_name"] or "",
                f"{r['dose']:g}",
                comment,
                f"{delta['no3']:.1f}" if delta["no3"] else "",
                f"{delta['po4']:.1f}" if delta["po4"] else "",
                f"{delta['k']:.1f}" if delta["k"] else "",
                f"{delta['fe']:.4f}" if delta["fe"] else "",
                f"{delta['mg']:.3f}" if delta["mg"] else "",
                f"{delta['ca']:.3f}" if delta["ca"] else "",
            )
            tree.insert("", "end", iid=str(r["id"]), values=vals)

        # обновляем сводную полосу
        totals = sum_range_totals(self.conn, aq_id,
                                  date_from=date_from, date_to=date_to)
        period_parts = []
        if date_from:
            period_parts.append(f"с {from_iso(date_from)}")
        if date_to:
            period_parts.append(f"по {from_iso(date_to)}")
        period_str = " ".join(period_parts) if period_parts else "за всё время"
        self._build_summary_strip(totals, period_str)

        # обновляем тренд
        self.refresh_dosing_trend()

    # ------------------------------------------------------------------
    # Добавление записи дозировки
    # ------------------------------------------------------------------

    def add_dosing_entry(self):
        aq_name = self.dose_aq_combo.get()
        if not aq_name:
            messagebox.showwarning("Внимание", "Выберите аквариум.")
            return
        fert_name = self.dose_fert_combo.get()
        if not fert_name:
            messagebox.showwarning("Внимание", "Выберите удобрение.")
            return
        fert_id = self._fert_map.get(fert_name)
        if fert_id is None:
            messagebox.showwarning("Внимание", "Удобрение не найдено в справочнике.")
            return
        date_str = self.dose_date_entry.get().strip()
        date_iso = to_iso(date_str)
        if not date_iso:
            messagebox.showwarning("Внимание",
                                   "Неверный формат даты. Используйте ДД.ММ.ГГГГ.")
            return
        dose_str = self.dose_spin.get().strip()
        dose = parse_float(dose_str, None)
        if dose is None or dose <= 0:
            messagebox.showwarning("Внимание", "Укажите дозу (положительное число).")
            return
        comment = self.dose_comment_var.get().strip()

        aq_id = getattr(self, "_dosing_aq_id", None)
        if aq_id is None:
            for a in get_aquariums(self.conn):
                if a["name"] == aq_name:
                    aq_id = a["id"]
                    break
        if aq_id is None:
            return

        add_dosing(self.conn, aq_id, date_iso, fert_id, dose, comment)
        self.dose_comment_var.set("")
        self.refresh_dosing_table()

    # ------------------------------------------------------------------
    # Редактирование записи дозировки
    # ------------------------------------------------------------------

    def edit_dosing_entry(self):
        sel = self.dose_tree.selection()
        if not sel:
            return
        dosing_id = int(sel[0])
        entry = get_dosing_entry(self.conn, dosing_id)
        if not entry:
            return
        data = self._dosing_form_dialog("Редактировать дозировку", entry=entry)
        if data is not None:
            update_dosing(self.conn, dosing_id, **data)
            self.refresh_dosing_table()

    # ------------------------------------------------------------------
    # Удаление записи дозировки
    # ------------------------------------------------------------------

    def delete_dosing_selected(self):
        sel = self.dose_tree.selection()
        if not sel:
            return
        dosing_id = int(sel[0])
        if not messagebox.askyesno("Удаление", "Удалить выбранную запись дозировки?",
                                    parent=self.root if hasattr(self, "root") else self):
            return
        delete_dosing(self.conn, dosing_id)
        self.refresh_dosing_table()

    # ------------------------------------------------------------------
    # Диалог формы дозировки (редактирование)
    # ------------------------------------------------------------------

    def _dosing_form_dialog(self, title, entry=None):
        FF = self.FF
        parent = self.root if hasattr(self, "root") else self

        dlg = tk.Toplevel(parent)
        dlg.title(title)
        dlg.configure(bg=COLOR_BG)
        dlg.transient(parent)
        dlg.grab_set()
        dlg.resizable(False, False)

        inner = tk.Frame(dlg, bg=COLOR_CARD, padx=16, pady=12)
        inner.pack(padx=16, pady=16)

        # дата
        row_date = tk.Frame(inner, bg=COLOR_CARD)
        row_date.pack(fill="x", pady=4)
        tk.Label(row_date, text="Дата:", width=14, anchor="w",
                 bg=COLOR_CARD, fg=COLOR_TEXT, font=(FF, 10)).pack(side="left")
        date_entry = DateEntry(row_date, font_family=FF, width=12,
                               default=from_iso(entry["date"]) if entry else None)
        date_entry.pack(side="left")

        # удобрение
        row_fert = tk.Frame(inner, bg=COLOR_CARD)
        row_fert.pack(fill="x", pady=4)
        tk.Label(row_fert, text="Удобрение:", width=14, anchor="w",
                 bg=COLOR_CARD, fg=COLOR_TEXT, font=(FF, 10)).pack(side="left")
        ferts = get_fertilizers(self.conn)
        fert_names = [f["name"] for f in ferts]
        fert_name_var = tk.StringVar(value=entry["fert_name"] if entry else "")
        fert_combo = ttk.Combobox(row_fert, textvariable=fert_name_var,
                                   values=fert_names, state="readonly", width=36)
        fert_combo.pack(side="left")

        # доза
        row_dose = tk.Frame(inner, bg=COLOR_CARD)
        row_dose.pack(fill="x", pady=4)
        tk.Label(row_dose, text="Доза (мл):", width=14, anchor="w",
                 bg=COLOR_CARD, fg=COLOR_TEXT, font=(FF, 10)).pack(side="left")
        dose_spin = SpinEntry(row_dose, width=10, step=0.1, font_family=FF,
                               default=f"{entry['dose']:g}" if entry else "1.0")
        dose_spin.pack(side="left")

        # комментарий
        row_comm = tk.Frame(inner, bg=COLOR_CARD)
        row_comm.pack(fill="x", pady=4)
        tk.Label(row_comm, text="Комментарий:", width=14, anchor="w",
                 bg=COLOR_CARD, fg=COLOR_TEXT, font=(FF, 10)).pack(side="left")
        comm_var = tk.StringVar(value=(entry["comment"] or "") if entry else "")
        ttk.Entry(row_comm, textvariable=comm_var, width=40).pack(
            side="left", fill="x", expand=True)

        # кнопки
        btn_row = tk.Frame(inner, bg=COLOR_CARD)
        btn_row.pack(fill="x", pady=(10, 0))

        result = [None]

        def _save():
            date_iso = to_iso(date_entry.get().strip())
            if not date_iso:
                messagebox.showwarning("Внимание", "Неверный формат даты.", parent=dlg)
                return
            fn = fert_name_var.get()
            fid = None
            for f in ferts:
                if f["name"] == fn:
                    fid = f["id"]
                    break
            if fid is None:
                messagebox.showwarning("Внимание", "Выберите удобрение.", parent=dlg)
                return
            dose = parse_float(dose_spin.get(), None)
            if dose is None or dose <= 0:
                messagebox.showwarning("Внимание", "Укажите дозу.", parent=dlg)
                return
            result[0] = {
                "date": date_iso,
                "fert_id": fid,
                "dose": dose,
                "comment": comm_var.get().strip(),
            }
            dlg.destroy()

        def _cancel():
            dlg.destroy()

        tk.Button(btn_row, text="Отмена", font=(FF, 9), relief="flat",
                  bg=COLOR_CARD, fg=COLOR_TEXT, activebackground=COLOR_ALT_ROW,
                  borderwidth=0, padx=14, pady=4, command=_cancel,
                  cursor="hand2").pack(side="right", padx=(8, 0))
        tk.Button(btn_row, text="Сохранить", font=(FF, 9, "bold"), relief="flat",
                  bg=COLOR_ACCENT, fg="#151515", activebackground=COLOR_ACCENT_HOVER,
                  activeforeground="#151515", borderwidth=0, padx=14, pady=4,
                  command=_save, cursor="hand2").pack(side="right")

        dlg.update_idletasks()
        pw = dlg.master.winfo_width()
        ph = dlg.master.winfo_height()
        px = dlg.master.winfo_rootx()
        py = dlg.master.winfo_rooty()
        dw = dlg.winfo_width()
        dh = dlg.winfo_height()
        dlg.geometry(f"+{px + (pw - dw) // 2}+{py + (ph - dh) // 2}")
        dlg.wait_window()
        return result[0]

    # ------------------------------------------------------------------
    # Обратный калькулятор дозы
    # ------------------------------------------------------------------

    def _open_dose_calculator(self):
        FF = self.FF
        aq_id = getattr(self, "_dosing_aq_id", None)
        aq = get_aquarium(self.conn, aq_id) if aq_id else None
        volume = aq["volume_l"] if aq else None

        dlg = tk.Toplevel(self.root if hasattr(self, "root") else self)
        dlg.title("Калькулятор дозы")
        dlg.configure(bg=COLOR_BG)
        dlg.transient(dlg.master)
        dlg.grab_set()
        dlg.resizable(False, False)

        pad = dict(padx=14, pady=5)

        tk.Label(dlg, text="Калькулятор дозы", font=(FF, 13, "bold"),
                 bg=COLOR_BG, fg=COLOR_ACCENT).pack(anchor="w", padx=14, pady=(14, 2))
        tk.Label(dlg, text="Рассчитывает объём удобрения (мл) для заданного прироста элемента.",
                 font=(FF, 9), bg=COLOR_BG, fg=COLOR_TEXT_MUTED,
                 wraplength=400, justify="left").pack(anchor="w", padx=14, pady=(0, 8))

        info_text = f"Аквариум: {aq['name']}, объём {volume:.0f} л" if aq else "Аквариум не выбран"
        tk.Label(dlg, text=info_text, font=(FF, 10), bg=COLOR_BG,
                 fg=COLOR_TEXT_SOFT).pack(anchor="w", padx=14, pady=(0, 6))

        # удобрение
        row_fert = tk.Frame(dlg, bg=COLOR_BG)
        row_fert.pack(fill="x", **pad)
        tk.Label(row_fert, text="Удобрение:", font=(FF, 10), width=16, anchor="w",
                 bg=COLOR_BG, fg=COLOR_TEXT_SOFT).pack(side="left")
        ferts = get_fertilizers(self.conn)
        fert_names = [f["name"] for f in ferts]
        fert_var = tk.StringVar(value=fert_names[0] if fert_names else "")
        fert_combo = ttk.Combobox(row_fert, textvariable=fert_var,
                                   values=fert_names, state="readonly", width=34)
        fert_combo.pack(side="left", padx=(2, 0))

        # элемент
        row_elem = tk.Frame(dlg, bg=COLOR_BG)
        row_elem.pack(fill="x", **pad)
        tk.Label(row_elem, text="Элемент:", font=(FF, 10), width=16, anchor="w",
                 bg=COLOR_BG, fg=COLOR_TEXT_SOFT).pack(side="left")
        elem_names = [f"{ELEMENT_RU[ek]} ({ELEMENT_FORMULA[ek]})" for ek in ELEMENT_KEYS]
        elem_var = tk.StringVar(value=elem_names[0] if elem_names else "")
        elem_combo = ttk.Combobox(row_elem, textvariable=elem_var,
                                   values=elem_names, state="readonly", width=34)
        elem_combo.pack(side="left", padx=(2, 0))

        # желаемый прирост
        row_target = tk.Frame(dlg, bg=COLOR_BG)
        row_target.pack(fill="x", **pad)
        tk.Label(row_target, text="Прирост (мг/л):", font=(FF, 10), width=16, anchor="w",
                 bg=COLOR_BG, fg=COLOR_TEXT_SOFT).pack(side="left")
        target_var = tk.StringVar(value="1.0")
        ttk.Entry(row_target, textvariable=target_var, width=12,
                  justify="center").pack(side="left", padx=(2, 0))

        # результат
        result_frame = tk.Frame(dlg, bg=COLOR_ACCENT_SOFT)
        result_frame.pack(fill="x", padx=14, pady=10)
        result_label = tk.Label(result_frame, text="Результат появится здесь",
                                font=(FF, 11, "bold"), bg=COLOR_ACCENT_SOFT,
                                fg=COLOR_ACCENT, padx=10, pady=8)
        result_label.pack(fill="x")

        def _calc():
            fn = fert_var.get()
            fert = None
            for f in ferts:
                if f["name"] == fn:
                    fert = f
                    break
            if not fert:
                result_label.config(text="Выберите удобрение", fg=COLOR_WARN_TEXT)
                return
            ei = elem_combo.current()
            if ei < 0:
                result_label.config(text="Выберите элемент", fg=COLOR_WARN_TEXT)
                return
            ek = ELEMENT_KEYS[ei]
            content = fert.get(ek, 0) or 0
            if content <= 0:
                result_label.config(
                    text=f"{ELEMENT_FORMULA[ek]} не содержится в этом удобрении (концентрация = 0)",
                    fg=COLOR_WARN_TEXT)
                return
            target = parse_float(target_var.get(), None)
            if target is None or target <= 0:
                result_label.config(text="Укажите прирост > 0", fg=COLOR_WARN_TEXT)
                return
            if not volume or volume <= 0:
                result_label.config(text="Объём аквариума не задан", fg=COLOR_WARN_TEXT)
                return
            dose_ml = target * volume / content
            result_label.config(
                text=f"Доза: {dose_ml:.2f} мл   (прирост {ELEMENT_FORMULA[ek]} "
                     f"на {target:g} мг/л в {volume:.0f} л)",
                fg=COLOR_OK_TEXT)

        tk.Button(dlg, text="Рассчитать", font=(FF, 10, "bold"), relief="flat",
                  bg=COLOR_ACCENT, fg="#151515", activebackground=COLOR_ACCENT_HOVER,
                  activeforeground="#151515", borderwidth=0, padx=16, pady=5,
                  command=_calc, cursor="hand2").pack(padx=14, pady=(0, 6))
        tk.Button(dlg, text="Закрыть", font=(FF, 9), relief="flat",
                  bg=COLOR_CARD, fg=COLOR_TEXT, activebackground=COLOR_ALT_ROW,
                  borderwidth=0, padx=14, pady=4, command=dlg.destroy,
                  cursor="hand2").pack(padx=14, pady=(0, 14))

        dlg.update_idletasks()
        pw = dlg.master.winfo_width()
        ph = dlg.master.winfo_height()
        px = dlg.master.winfo_rootx()
        py = dlg.master.winfo_rooty()
        dw = dlg.winfo_width()
        dh = dlg.winfo_height()
        dlg.geometry(f"+{px + (pw - dw) // 2}+{py + (ph - dh) // 2}")

    # ------------------------------------------------------------------
    # Фильтры таблицы
    # ------------------------------------------------------------------

    def _set_dose_filter(self, key):
        self._dose_filter = key
        self._update_filter_buttons()
        self.refresh_dosing_table()

    def _update_filter_buttons(self):
        for k, btn in self.dose_filter_btns.items():
            if k == self._dose_filter:
                btn.config(bg=COLOR_ACCENT, fg="#151515")
            else:
                btn.config(bg=COLOR_ALT_ROW, fg=COLOR_TEXT_MUTED)

    def _get_dose_filter_range(self):
        today = dt.date.today()
        key = getattr(self, "_dose_filter", "30d")
        if key == "today":
            return today.isoformat(), today.isoformat()
        if key == "latest":
            aq_id = getattr(self, "_dosing_aq_id", None)
            if aq_id:
                from aquarium_app.db import get_latest_dosing_date
                latest = get_latest_dosing_date(self.conn, aq_id)
                if latest:
                    return latest, latest
            return today.isoformat(), today.isoformat()
        if key == "7d":
            since = (today - dt.timedelta(days=7)).isoformat()
            return since, today.isoformat()
        if key == "30d":
            since = (today - dt.timedelta(days=30)).isoformat()
            return since, today.isoformat()
        return None, today.isoformat()

    # ------------------------------------------------------------------
    # Фильтры тренда
    # ------------------------------------------------------------------

    def _set_dosing_trend_filter(self, key):
        self._dosing_trend_filter = key
        self._update_dosing_trend_filter_buttons()
        self.refresh_dosing_trend()

    def _update_dosing_trend_filter_buttons(self):
        for k, btn in self.dosing_trend_filter_btns.items():
            if k == self._dosing_trend_filter:
                btn.config(bg=COLOR_ACCENT, fg="#151515")
            else:
                btn.config(bg=COLOR_ALT_ROW, fg=COLOR_TEXT_MUTED)

    # ------------------------------------------------------------------
    # Режим тренда
    # ------------------------------------------------------------------

    def _set_dosing_trend_mode(self, key):
        self._dosing_trend_mode = key
        self._update_dosing_trend_mode_buttons()
        self.refresh_dosing_trend()

    def _update_dosing_trend_mode_buttons(self):
        for k, btn in self.dosing_trend_mode_btns.items():
            if k == self._dosing_trend_mode:
                btn.config(bg=COLOR_ACCENT, fg="#151515")
            else:
                btn.config(bg=COLOR_ALT_ROW, fg=COLOR_TEXT_MUTED)

    # ------------------------------------------------------------------
    # Отрисовка тренда
    # ------------------------------------------------------------------

    def refresh_dosing_trend(self):
        canvas = self.dosing_trend_canvas
        if not canvas.winfo_exists():
            return
        aq_id = getattr(self, "_dosing_aq_id", None)
        if aq_id is None:
            return

        FF = self.FF
        mode = self._dosing_trend_mode
        filter_key = self._dosing_trend_filter

        param_defs = [
            ("po4", ELEMENT_COLORS["po4"], "PO4"),
            ("no3", ELEMENT_COLORS["no3"], "NO3"),
            ("k", ELEMENT_COLORS["k"], "K"),
            ("fe", ELEMENT_COLORS["fe"], "Fe"),
        ]

        days = None
        since_iso = None
        if filter_key == "7d":
            days = 7
        elif filter_key == "30d":
            days = 30
        elif filter_key == "90d":
            days = 90

        if mode == "cumulative":
            history_fn = lambda key: get_element_dosing_cumulative_history(
                self.conn, aq_id, key, days=days, since_iso=since_iso)
            draw_fn = draw_param_trend_chart
        else:
            history_fn = lambda key: get_element_dosing_daily_history(
                self.conn, aq_id, key, days=days, since_iso=since_iso)
            draw_fn = draw_daily_bars_chart

        self._schedule_dosing_trend_chart_draw(
            canvas, draw_fn, self.conn, aq_id, param_defs,
            days=days, since_iso=since_iso, history_fn=history_fn,
            font_family=FF,
            empty_message="недостаточно данных для графика",
        )

    def _schedule_dosing_trend_chart_draw(self, canvas, draw_fn, *args, **kwargs):
        schedule_chart_draw(canvas, draw_fn, *args, **kwargs)

    # ------------------------------------------------------------------
    # Экспорт в JSON
    # ------------------------------------------------------------------

    def export_dosing_json(self):
        aq_id = getattr(self, "_dosing_aq_id", None)
        if aq_id is None:
            messagebox.showwarning("Внимание", "Сначала выберите аквариум.")
            return
        date_from, date_to = self._get_dose_filter_range()
        rows = get_dosing_filtered(self.conn, aq_id,
                                    date_from=date_from, date_to=date_to)
        if not rows:
            messagebox.showinfo("Экспорт", "Нет данных за выбранный период.")
            return
        export = []
        for r in rows:
            item = {"date": r["date"], "fertilizer": r["fert_name"], "dose": r["dose"]}
            if r["comment"]:
                item["comment"] = r["comment"]
            export.append(item)
        path = filedialog.asksaveasfilename(
            title="Экспорт дозировок в JSON",
            defaultextension=".json",
            filetypes=[("JSON файлы", "*.json"), ("Все файлы", "*.*")],
            initialfile=f"dosing_{self._dose_filter}.json",
        )
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            json.dump(export, f, ensure_ascii=False, indent=2)
        messagebox.showinfo("Экспорт", f"Экспортировано {len(export)} записей в:\n{path}")