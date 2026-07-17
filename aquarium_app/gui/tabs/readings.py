"""Вкладка «Показания» — замеры воды, трендовый график, таблица."""
from __future__ import annotations

import datetime as dt
import tkinter as tk
from tkinter import ttk, messagebox

from aquarium_app.config import (
    COLOR_BG, COLOR_CARD, COLOR_ACCENT, COLOR_BORDER, COLOR_TEXT,
    COLOR_TEXT_MUTED, COLOR_OK_BG, COLOR_OK_ROW, COLOR_WARN, COLOR_ALT_ROW, COLOR_WARN_TEXT,
    MEASURED_PARAMS, SPIN_SETTINGS, MEASURED_PARAM_KEYS, FONT_FAMILY,
    ELEMENT_COLORS,
)
from aquarium_app.db import (
    get_readings, get_readings_by_date, add_reading, delete_reading,
    get_reading, update_reading, get_aquarium,
)
from aquarium_app.logic.calculations import out_of_range_flags
from aquarium_app.logic.formatters import from_iso, to_iso, today_str, parse_float
from aquarium_app.gui.charts import draw_param_trend_chart, schedule_chart_draw
from aquarium_app.gui.widgets import DateEntry, SpinEntry


class ReadingsTab:
    """Mixin-класс с методами для вкладки «Показания»."""

    # ------------------------------------------------------------------
    # Построение вкладки
    # ------------------------------------------------------------------

    def build_readings_tab(self):
        """Создаёт весь интерфейс вкладки «Показания»."""
        FF = self.FF
        parent = self.tab_readings

        # --- верхняя панель: выбор аквариума ---
        top = tk.Frame(parent, bg=COLOR_BG)
        top.pack(fill="x", padx=12, pady=(10, 4))

        ttk.Label(top, text="Аквариум:", background=COLOR_BG).pack(side="left")
        self.readings_aq_var = tk.StringVar()
        self.readings_aq_combo = ttk.Combobox(
            top, textvariable=self.readings_aq_var,
            state="readonly", width=30,
        )
        self.readings_aq_combo.pack(side="left", padx=(6, 0))
        self.readings_aq_combo.bind("<<ComboboxSelected>>",
                                     lambda e: self._on_readings_aq_changed())

        # --- фильтр периода графика ---
        filter_frame = tk.Frame(parent, bg=COLOR_BG)
        filter_frame.pack(fill="x", padx=12, pady=(6, 2))

        ttk.Label(filter_frame, text="Период графика:",
                  background=COLOR_BG, foreground=COLOR_TEXT_MUTED).pack(side="left")

        self._trend_filter_var = tk.StringVar(value="7d")
        filter_btns_data = [
            ("7d", "7 дн"), ("30d", "30 дн"), ("90d", "90 дн"),
            ("180d", "180 дн"), ("365d", "365 дн"), ("all", "Всё"),
        ]
        self._trend_filter_btns = {}
        for key, label in filter_btns_data:
            b = tk.Button(
                filter_frame, text=label, font=(FF, 9),
                relief="flat", bg=COLOR_CARD, fg=COLOR_TEXT_MUTED,
                activebackground=COLOR_ALT_ROW, activeforeground=COLOR_TEXT,
                borderwidth=0, padx=8, pady=2, cursor="hand2",
                command=lambda k=key: self._set_trend_filter(k),
            )
            b.pack(side="left", padx=2)
            self._trend_filter_btns[key] = b
        self._update_trend_filter_buttons()

        # --- трендовый график ---
        chart_card = tk.Frame(parent, bg=COLOR_CARD, bd=1, relief="solid",
                              highlightbackground=COLOR_BORDER, highlightthickness=1)
        chart_card.pack(fill="x", padx=12, pady=4)
        self.readings_trend_canvas = tk.Canvas(chart_card, bg=COLOR_CARD,
                                               height=140, highlightthickness=0)
        self.readings_trend_canvas.pack(fill="x", padx=2, pady=2)

        # --- форма добавления ---
        form_card = tk.Frame(parent, bg=COLOR_CARD, bd=1, relief="solid",
                             highlightbackground=COLOR_BORDER, highlightthickness=1)
        form_card.pack(fill="x", padx=12, pady=4)

        form_inner = tk.Frame(form_card, bg=COLOR_CARD)
        form_inner.pack(fill="x", padx=8, pady=6)

        # дата
        row_date = tk.Frame(form_inner, bg=COLOR_CARD)
        row_date.pack(fill="x", pady=2)
        ttk.Label(row_date, text="Дата:", width=16, anchor="w",
                  background=COLOR_CARD).pack(side="left")
        self.read_date_entry = DateEntry(row_date, font_family=FF, width=12)
        self.read_date_entry.pack(side="left")

        # строка параметров
        row_params = tk.Frame(form_inner, bg=COLOR_CARD)
        row_params.pack(fill="x", pady=2)
        ttk.Label(row_params, text="Параметры:", width=16, anchor="w",
                  background=COLOR_CARD).pack(side="left")

        self.read_spin_vars = {}
        self.read_spin_entries = {}
        for key, formula, unit in MEASURED_PARAMS:
            cell = tk.Frame(row_params, bg=COLOR_CARD)
            cell.pack(side="left", padx=(0, 12))
            cfg = SPIN_SETTINGS.get(key, {"step": 0.1, "default": ""})
            se = SpinEntry(cell, width=7, step=cfg["step"],
                           default=cfg.get("default", ""))
            se.pack(side="left")
            lbl_text = f"{formula} {unit}".strip()
            tk.Label(cell, text=lbl_text, bg=COLOR_CARD, fg=COLOR_TEXT_MUTED,
                     font=(FF, 9)).pack(side="left", padx=(6, 0))
            self.read_spin_vars[key] = se.var
            self.read_spin_entries[key] = se

        # подмена воды
        row_wc = tk.Frame(form_inner, bg=COLOR_CARD)
        row_wc.pack(fill="x", pady=2)
        ttk.Label(row_wc, text="Подмена воды:", width=16, anchor="w",
                  background=COLOR_CARD).pack(side="left")
        self.read_wc_spin = SpinEntry(row_wc, width=6, step=5, default="")
        self.read_wc_spin.pack(side="left")
        self.read_wc_spin.entry.bind("<KeyRelease>", lambda e: self._update_read_wc_pct())
        self.read_wc_l_var = self.read_wc_spin.var
        ttk.Label(row_wc, text="л", background=COLOR_CARD, foreground=COLOR_TEXT_MUTED).pack(
            side="left", padx=(4, 10))
        self.read_wc_pct_label = tk.Label(row_wc, text="= —%", bg=COLOR_CARD,
                                          fg=COLOR_TEXT_MUTED, font=(FF, 9))
        self.read_wc_pct_label.pack(side="left")

        # комментарий
        row_cmt = tk.Frame(form_inner, bg=COLOR_CARD)
        row_cmt.pack(fill="x", pady=2)
        ttk.Label(row_cmt, text="Комментарий:", width=16, anchor="w",
                  background=COLOR_CARD).pack(side="left")
        self.read_comment_var = tk.StringVar()
        ttk.Entry(row_cmt, textvariable=self.read_comment_var, width=50).pack(
            side="left", fill="x", expand=True)

        # кнопки
        row_btns = tk.Frame(form_inner, bg=COLOR_CARD)
        row_btns.pack(fill="x", pady=(6, 2))
        tk.Button(row_btns, text="Добавить", font=(FF, 10, "bold"),
                  bg=COLOR_ACCENT, fg="#151515", activebackground=COLOR_ACCENT,
                  relief="flat", padx=16, pady=4, cursor="hand2",
                  command=self.add_reading_entry).pack(side="left")
        tk.Button(row_btns, text="Изменить выбранное", font=(FF, 9),
                  bg=COLOR_CARD, fg=COLOR_TEXT, activebackground=COLOR_ALT_ROW,
                  relief="flat", padx=10, pady=4, cursor="hand2",
                  command=self.edit_reading_entry).pack(side="left", padx=(8, 0))
        tk.Button(row_btns, text="Удалить выбранное", font=(FF, 9),
                  bg=COLOR_CARD, fg=COLOR_WARN_TEXT, activebackground=COLOR_ALT_ROW,
                  relief="flat", padx=10, pady=4, cursor="hand2",
                  command=self.delete_reading_selected).pack(side="right")

        # --- таблица ---
        table_card = tk.Frame(parent, bg=COLOR_CARD, bd=1, relief="solid",
                              highlightbackground=COLOR_BORDER, highlightthickness=1)
        table_card.pack(fill="both", expand=True, padx=12, pady=(4, 12))

        cols = ("date", "po4", "no3", "ph", "wc", "flags", "comment")
        self.readings_tree = ttk.Treeview(table_card, columns=cols,
                                           show="headings", height=12)
        self.readings_tree.heading("date", text="Дата")
        self.readings_tree.heading("po4", text="PO4")
        self.readings_tree.heading("no3", text="NO3")
        self.readings_tree.heading("ph", text="pH")
        self.readings_tree.heading("wc", text="Подмена")
        self.readings_tree.heading("flags", text="Флаги")
        self.readings_tree.heading("comment", text="Комментарий")

        self.readings_tree.column("date", width=90, minwidth=80)
        self.readings_tree.column("po4", width=60, minwidth=50, anchor="center")
        self.readings_tree.column("no3", width=60, minwidth=50, anchor="center")
        self.readings_tree.column("ph", width=60, minwidth=50, anchor="center")
        self.readings_tree.column("wc", width=80, minwidth=60, anchor="center")
        self.readings_tree.column("flags", width=200, minwidth=120)
        self.readings_tree.column("comment", width=180, minwidth=100)

        sb = ttk.Scrollbar(table_card, orient="vertical",
                           command=self.readings_tree.yview)
        self.readings_tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.readings_tree.pack(fill="both", expand=True)

        # теги для раскраски строк
        self.readings_tree.tag_configure("ok", background=COLOR_OK_ROW)
        self.readings_tree.tag_configure("warn", background=COLOR_WARN)
        self.readings_tree.tag_configure("alt", background=COLOR_ALT_ROW)

        self.readings_tree.bind("<Double-1>", lambda e: self.edit_reading_entry())

        # идентификаторы строк: reading_id -> iid
        self._readings_iid_map = {}

    # ------------------------------------------------------------------
    # Заполнение комбо аквариумов
    # ------------------------------------------------------------------

    def refresh_readings_aq_combo(self):
        aqs = self.conn.execute("SELECT * FROM aquariums ORDER BY id").fetchall()
        items = [f"{r['id']} — {r['name']}" for r in aqs]
        self.readings_aq_combo["values"] = items
        if items and not self.readings_aq_var.get():
            self.readings_aq_combo.current(0)
        if self.readings_aq_var.get():
            self._on_readings_aq_changed()

    def _on_readings_aq_changed(self):
        self.refresh_readings_table()
        self._schedule_trend_chart_draw()

    def _current_read_aq_id(self):
        s = self.readings_aq_var.get().strip()
        if not s:
            return None
        try:
            return int(s.split(" — ")[0])
        except (ValueError, IndexError):
            return None

    # ------------------------------------------------------------------
    # Таблица
    # ------------------------------------------------------------------

    def refresh_readings_table(self):
        aq_id = self._current_read_aq_id()
        for iid in self.readings_tree.get_children():
            self.readings_tree.delete(iid)
        self._readings_iid_map.clear()

        if not aq_id:
            return

        rows = get_readings(self.conn, aq_id)
        for i, r in enumerate(rows):
            rid = r["id"]
            date_str = from_iso(r["date"])
            po4_v = r["po4"]
            no3_v = r["no3"]
            ph_v = r["ph"]

            def _fmt(v):
                return f"{v:g}" if v is not None else ""

            po4_s = _fmt(po4_v)
            no3_s = _fmt(no3_v)
            ph_s = _fmt(ph_v)

            if r["water_change_pct"] is not None:
                wc_str = f"{r['water_change_pct']:.1f}%"
            elif r["water_change_l"] is not None:
                wc_str = f"{r['water_change_l']:g} л"
            else:
                wc_str = ""

            values = {k: r[k] for k in MEASURED_PARAM_KEYS}
            flags = out_of_range_flags(self.conn, aq_id, values)
            flags_str = " | ".join(flags) if flags else ""

            tag = "alt" if i % 2 else ""
            if flags:
                tag = "warn"
            elif flags_str == "" and any(v is not None for v in values.values()):
                tag = "ok" if i % 2 == 0 else "ok"

            iid = self.readings_tree.insert(
                "", "end", values=(
                    date_str, po4_s, no3_s, ph_s, wc_str, flags_str,
                    r["comment"] or "",
                ), tags=(tag,),
            )
            self._readings_iid_map[iid] = rid

    # ------------------------------------------------------------------
    # Добавление
    # ------------------------------------------------------------------

    def add_reading_entry(self):
        aq_id = self._current_read_aq_id()
        if not aq_id:
            messagebox.showwarning("Внимание", "Выберите аквариум.")
            return

        date_iso = to_iso(self.read_date_entry.get())
        if not date_iso:
            messagebox.showwarning("Ошибка", "Некорректная дата.")
            return

        # проверка дубликата
        existing = get_readings_by_date(self.conn, aq_id, date_iso)
        if existing:
            if not messagebox.askyesno(
                "Дубликат даты",
                f"На дату {from_iso(date_iso)} уже есть запись.\n"
                "Заменить существующую?",
            ):
                return
            # заменяем существующую
            values = {}
            for key in MEASURED_PARAM_KEYS:
                v = parse_float(self.read_spin_vars[key].get(), None)
                values[key] = v
            comment = self.read_comment_var.get().strip()
            wc_l = parse_float(self.read_wc_l_var.get(), None)
            wc_pct = None
            if wc_l is not None:
                aq = get_aquarium(self.conn, aq_id)
                vol = aq["volume_l"] if aq else 0
                if vol:
                    wc_pct = round(wc_l / vol * 100, 1)
            update_reading(self.conn, existing["id"], date_iso, values,
                           comment, wc_pct, wc_l)
            self.refresh_readings_table()
            self._schedule_trend_chart_draw()
            return

        values = {}
        for key in MEASURED_PARAM_KEYS:
            v = parse_float(self.read_spin_vars[key].get(), None)
            values[key] = v

        comment = self.read_comment_var.get().strip()
        wc_l = parse_float(self.read_wc_l_var.get(), None)
        wc_pct = None
        if wc_l is not None:
            aq = get_aquarium(self.conn, aq_id)
            vol = aq["volume_l"] if aq else 0
            if vol:
                wc_pct = round(wc_l / vol * 100, 1)

        add_reading(self.conn, aq_id, date_iso, values, comment, wc_pct, wc_l)
        self.refresh_readings_table()
        self._schedule_trend_chart_draw()
        # сбрасываем форму
        for key in MEASURED_PARAM_KEYS:
            self.read_spin_entries[key].set("")
        self.read_wc_spin.set("")
        self.read_wc_pct_label.config(text="= —%")
        self.read_comment_var.set("")

    # ------------------------------------------------------------------
    # Редактирование
    # ------------------------------------------------------------------

    def edit_reading_entry(self):
        sel = self.readings_tree.selection()
        if not sel:
            return
        iid = sel[0]
        rid = self._readings_iid_map.get(iid)
        if not rid:
            return
        entry = get_reading(self.conn, rid)
        if not entry:
            return
        self._reading_form_dialog("Редактировать показание", entry)

    def _reading_form_dialog(self, title, entry=None):
        """Модальный диалог для добавления/редактирования показания."""
        dlg = tk.Toplevel(self.root if hasattr(self, "root") else self)
        dlg.title(title)
        dlg.configure(bg=COLOR_BG)
        parent = self.root if hasattr(self, "root") else self
        dlg.transient(parent)
        dlg.grab_set()
        dlg.resizable(False, False)

        FF = self.FF
        is_edit = entry is not None

        inner = tk.Frame(dlg, bg=COLOR_CARD, padx=16, pady=12)
        inner.pack(padx=16, pady=16)

        # дата
        row = tk.Frame(inner, bg=COLOR_CARD)
        row.pack(fill="x", pady=4)
        tk.Label(row, text="Дата:", width=16, anchor="w", bg=COLOR_CARD,
                 fg=COLOR_TEXT, font=(FF, 10)).pack(side="left")
        date_default = from_iso(entry["date"]) if is_edit else today_str()
        date_entry = DateEntry(row, font_family=FF, width=12, default=date_default)
        date_entry.pack(side="left")

        # параметры
        spin_vars = {}
        spin_entries = {}
        for key, formula, unit in MEASURED_PARAMS:
            row = tk.Frame(inner, bg=COLOR_CARD)
            row.pack(fill="x", pady=4)
            cfg = SPIN_SETTINGS.get(key, {"step": 0.1, "default": ""})
            tk.Label(row, text=f"{formula} {unit}".strip() + ":", width=16, anchor="w",
                     bg=COLOR_CARD, fg=COLOR_TEXT, font=(FF, 10)).pack(side="left")
            default_val = entry[key] if (is_edit and entry[key] is not None) else ""
            se = SpinEntry(row, width=8, step=cfg["step"], default=default_val)
            se.pack(side="left")
            spin_vars[key] = se.var
            spin_entries[key] = se

        # подмена воды
        row = tk.Frame(inner, bg=COLOR_CARD)
        row.pack(fill="x", pady=4)
        tk.Label(row, text="Подмена воды (л):", width=16, anchor="w",
                 bg=COLOR_CARD, fg=COLOR_TEXT, font=(FF, 10)).pack(side="left")
        wc_l_var = tk.StringVar(
            value=str(entry["water_change_l"]) if (is_edit and entry["water_change_l"] is not None) else ""
        )
        wc_entry = ttk.Entry(row, textvariable=wc_l_var, width=10)
        wc_entry.pack(side="left")
        wc_pct_label = tk.Label(row, text="= —%", bg=COLOR_CARD,
                                fg=COLOR_TEXT_MUTED, font=(FF, 9))
        wc_pct_label.pack(side="left", padx=6)

        def _update_pct():
            v = parse_float(wc_l_var.get(), None)
            if v is not None:
                aq_id = self._current_read_aq_id()
                aq = get_aquarium(self.conn, aq_id) if aq_id else None
                vol = aq["volume_l"] if aq else 0
                if vol:
                    wc_pct_label.config(text=f"= {v / vol * 100:.1f}%")
                    return
            wc_pct_label.config(text="= —%")

        wc_entry.bind("<KeyRelease>", lambda e: _update_pct())
        if is_edit and entry["water_change_l"] is not None:
            _update_pct()

        # комментарий
        row = tk.Frame(inner, bg=COLOR_CARD)
        row.pack(fill="x", pady=4)
        tk.Label(row, text="Комментарий:", width=16, anchor="w",
                 bg=COLOR_CARD, fg=COLOR_TEXT, font=(FF, 10)).pack(side="left")
        cmt_var = tk.StringVar(value=entry["comment"] or "" if is_edit else "")
        ttk.Entry(row, textvariable=cmt_var, width=40).pack(side="left", fill="x",
                                                              expand=True)

        # кнопки
        btns = tk.Frame(inner, bg=COLOR_CARD)
        btns.pack(fill="x", pady=(10, 0))
        result = {"saved": False}

        def _save():
            date_iso = to_iso(date_entry.get())
            if not date_iso:
                messagebox.showwarning("Ошибка", "Некорректная дата.", parent=dlg)
                return
            values = {}
            for key in MEASURED_PARAM_KEYS:
                values[key] = parse_float(spin_vars[key].get(), None)
            comment = cmt_var.get().strip()
            wc_l = parse_float(wc_l_var.get(), None)
            wc_pct = None
            if wc_l is not None:
                aq_id = self._current_read_aq_id()
                aq = get_aquarium(self.conn, aq_id) if aq_id else None
                vol = aq["volume_l"] if aq else 0
                if vol:
                    wc_pct = round(wc_l / vol * 100, 1)

            if is_edit:
                update_reading(self.conn, entry["id"], date_iso, values,
                               comment, wc_pct, wc_l)
            else:
                aq_id = self._current_read_aq_id()
                if not aq_id:
                    messagebox.showwarning("Ошибка", "Выберите аквариум.", parent=dlg)
                    return
                add_reading(self.conn, aq_id, date_iso, values, comment, wc_pct, wc_l)
            result["saved"] = True
            dlg.destroy()
            self.refresh_readings_table()
            self._schedule_trend_chart_draw()

        tk.Button(btns, text="Сохранить", font=(FF, 10, "bold"),
                  bg=COLOR_ACCENT, fg="#151515", relief="flat",
                  padx=16, pady=4, command=_save).pack(side="left")
        tk.Button(btns, text="Отмена", font=(FF, 10),
                  bg=COLOR_CARD, fg=COLOR_TEXT, relief="flat",
                  padx=12, pady=4, command=dlg.destroy).pack(side="right")

        dlg.bind("<Escape>", lambda e: dlg.destroy())
        dlg.update_idletasks()
        x = self.winfo_rootx() + 100
        y = self.winfo_rooty() + 60
        dlg.geometry(f"+{x}+{y}")
        self.wait_window(dlg)

    # ------------------------------------------------------------------
    # Удаление
    # ------------------------------------------------------------------

    def delete_reading_selected(self):
        sel = self.readings_tree.selection()
        if not sel:
            messagebox.showinfo("Информация", "Выберите строку для удаления.")
            return
        iid = sel[0]
        rid = self._readings_iid_map.get(iid)
        if not rid:
            return
        if not messagebox.askyesno("Удаление", "Удалить выбранное показание?"):
            return
        delete_reading(self.conn, rid)
        self.refresh_readings_table()
        self._schedule_trend_chart_draw()

    # ------------------------------------------------------------------
    # Авто-расчёт % подмены
    # ------------------------------------------------------------------

    def _update_read_wc_pct(self):
        v = parse_float(self.read_wc_l_var.get(), None)
        if v is not None:
            aq_id = self._current_read_aq_id()
            aq = get_aquarium(self.conn, aq_id) if aq_id else None
            vol = aq["volume_l"] if aq else 0
            if vol:
                pct = v / vol * 100
                self.read_wc_pct_label.config(text=f"= {pct:.1f}%", fg=COLOR_ACCENT)
                return
        self.read_wc_pct_label.config(text="= —%", fg=COLOR_TEXT_MUTED)

    # ------------------------------------------------------------------
    # Фильтр периода графика
    # ------------------------------------------------------------------

    def _set_trend_filter(self, key):
        self._trend_filter_var.set(key)
        self._update_trend_filter_buttons()
        self._schedule_trend_chart_draw()

    def _update_trend_filter_buttons(self):
        current = self._trend_filter_var.get()
        for k, btn in self._trend_filter_btns.items():
            if k == current:
                btn.config(bg=COLOR_ACCENT, fg="#151515")
            else:
                btn.config(bg=COLOR_CARD, fg=COLOR_TEXT_MUTED)

    # ------------------------------------------------------------------
    # Трендовый график
    # ------------------------------------------------------------------

    def _schedule_trend_chart_draw(self):
        schedule_chart_draw(
            self.readings_trend_canvas,
            self.refresh_readings_trend,
        )

    def refresh_readings_trend(self, canvas=None):
        """Перерисовывает трендовый график PO4 / NO3 / pH."""
        c = canvas or self.readings_trend_canvas
        aq_id = self._current_read_aq_id()
        if not aq_id or not c.winfo_exists():
            return

        filter_key = self._trend_filter_var.get()
        days = None
        since_iso = None
        if filter_key == "all":
            days = None
            since_iso = None
        else:
            days = int(filter_key.replace("d", ""))

        param_defs = [
            (k, ELEMENT_COLORS.get(k, COLOR_ACCENT), formula)
            for k, formula, _unit in MEASURED_PARAMS
        ]

        def history_fn(key):
            # key — имя колонки (no3, po4, ...), подставляем напрямую
            query = (
                f"SELECT date, {key} AS val FROM readings "
                f"WHERE aquarium_id=? AND {key} IS NOT NULL "
                f"ORDER BY date ASC"
            )
            rows = self.conn.execute(query, (aq_id,)).fetchall()
            result = []
            for r in rows:
                if days is not None:
                    try:
                        rd = dt.date.fromisoformat(r["date"])
                        cutoff = dt.date.today() - dt.timedelta(days=days)
                        if rd < cutoff:
                            continue
                    except Exception:
                        pass
                result.append((r["date"], r["val"]))
            return result

        # подмены воды для графика
        wc_rows = self.conn.execute(
            "SELECT date, water_change_pct, water_change_l FROM readings "
            "WHERE aquarium_id=? AND (water_change_pct IS NOT NULL OR water_change_l IS NOT NULL) "
            "ORDER BY date ASC", (aq_id,)
        ).fetchall()
        wc_events = []
        for r in wc_rows:
            if days is not None:
                try:
                    rd = dt.date.fromisoformat(r["date"])
                    if rd < dt.date.today() - dt.timedelta(days=days):
                        continue
                except Exception:
                    pass
            pct = r["water_change_pct"]
            if pct is None and r["water_change_l"] is not None:
                aq = get_aquarium(self.conn, aq_id)
                vol = aq["volume_l"] if aq else 0
                if vol:
                    pct = round(r["water_change_l"] / vol * 100, 1)
            if pct is not None:
                wc_events.append((r["date"], pct))

        draw_param_trend_chart(
            c, self.conn, aq_id, param_defs,
            days=days, since_iso=since_iso,
            history_fn=history_fn,
            font_family=self.FF,
            empty_message="недостаточно данных для графика",
            wc_events=wc_events if wc_events else None,
        )