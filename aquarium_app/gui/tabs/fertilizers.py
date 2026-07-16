"""Вкладка «Удобрения» — CRUD справочника удобрений с концентрациями элементов."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from aquarium_app.config import (
    COLOR_BG, COLOR_CARD, COLOR_ACCENT, COLOR_BORDER, COLOR_TEXT,
    COLOR_TEXT_MUTED, COLOR_TEXT_SOFT, COLOR_ACCENT_HOVER, COLOR_ALT_ROW,
    ELEMENT_KEYS, ELEMENT_FORMULA, ELEMENT_RU, COLOR_HEADER, COLOR_HEADER_TEXT,
)
from aquarium_app.db import (
    get_fertilizers, get_fertilizer, add_fertilizer,
    update_fertilizer, delete_fertilizer,
)
from aquarium_app.logic.formatters import parse_float


class FertilizersTab:
    """Миксин-вкладка «Удобрения»."""

    # ------------------------------------------------------------------
    # Построение вкладки
    # ------------------------------------------------------------------

    def build_ferts_tab(self):
        """Создаёт Treeview с колонками: имя, форма, + все элементы.
        Кнопки: Добавить / Редактировать / Удалить.
        """
        tab = self.tab_fertilizers  # type: tk.Frame
        FF = self.FF

        # заголовок
        hdr = tk.Frame(tab, bg=COLOR_BG)
        hdr.pack(fill="x", padx=16, pady=(12, 0))
        tk.Label(hdr, text="Удобрения", font=(FF, 16, "bold"),
                 bg=COLOR_BG, fg=COLOR_TEXT).pack(side="left")
        tk.Button(hdr, text="Добавить", font=(FF, 9), relief="flat",
                  bg=COLOR_ACCENT, fg="#151515", activebackground=COLOR_ACCENT_HOVER,
                  activeforeground="#151515", borderwidth=0, padx=12, pady=4,
                  command=self.add_fertilizer_dialog, cursor="hand2").pack(side="right")

        # дерево с горизонтальной прокруткой
        tree_frame = tk.Frame(tab, bg=COLOR_BG)
        tree_frame.pack(fill="both", expand=True, padx=12, pady=12)

        cols = ["name", "form"] + ELEMENT_KEYS
        self.fert_tree = ttk.Treeview(tree_frame, columns=cols, show="headings",
                                       height=10, selectmode="browse")
        self.fert_tree.heading("name", text="Название")
        self.fert_tree.heading("form", text="Форма")
        self.fert_tree.column("name", width=200, minwidth=120)
        self.fert_tree.column("form", width=120, minwidth=80)

        for ek in ELEMENT_KEYS:
            formula = ELEMENT_FORMULA[ek]
            ru = ELEMENT_RU[ek]
            heading = f"{ru} ({formula})"
            self.fert_tree.heading(ek, text=heading)
            self.fert_tree.column(ek, width=70, minwidth=50, anchor="center")

        # горизонтальный скроллбар
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.fert_tree.xview)
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.fert_tree.yview)
        self.fert_tree.configure(xscrollcommand=hsb.set, yscrollcommand=vsb.set)
        self.fert_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        # двойной клик — редактировать
        self.fert_tree.bind("<Double-1>", lambda e: self.edit_fertilizer())

        # кнопки
        btn_row = tk.Frame(tab, bg=COLOR_BG)
        btn_row.pack(fill="x", padx=16, pady=(0, 12))
        tk.Button(btn_row, text="Редактировать", font=(FF, 9), relief="flat",
                  bg=COLOR_CARD, fg=COLOR_TEXT, activebackground=COLOR_ALT_ROW,
                  borderwidth=0, padx=12, pady=4, command=self.edit_fertilizer,
                  cursor="hand2").pack(side="left")
        tk.Button(btn_row, text="Удалить", font=(FF, 9), relief="flat",
                  bg=COLOR_CARD, fg=COLOR_TEXT, activebackground=COLOR_ALT_ROW,
                  borderwidth=0, padx=12, pady=4, command=self.delete_fertilizer_selected,
                  cursor="hand2").pack(side="left", padx=(8, 0))

        self.fert_tree.after(100, self.refresh_ferts)

    # ------------------------------------------------------------------
    # Обновление таблицы
    # ------------------------------------------------------------------

    def refresh_ferts(self):
        """Заполняет дерево удобрениями из БД и обновляет выпадающий список дозирования."""
        tree = self.fert_tree
        if not tree.winfo_exists():
            return
        tree.delete(*tree.get_children())

        ferts = get_fertilizers(self.conn)
        for f in ferts:
            vals = [f["name"] or "", f["form"] or ""]
            for ek in ELEMENT_KEYS:
                v = f.get(ek)
                vals.append(f"{v:g}" if v is not None and v != 0 else "")
            tree.insert("", "end", iid=str(f["id"]), values=vals)

        # обновляем выпадающий список на вкладке дозирования (если он существует)
        self._refresh_fert_dropdown()

    # ------------------------------------------------------------------
    # Обновление выпадающего списка удобрений на вкладке дозирования
    # ------------------------------------------------------------------

    def _refresh_fert_dropdown(self):
        """Обновляет `self.dose_fert_combo` значениями и `self._fert_map`.

        Вызывается после любого изменения в справочнике удобрений.
        """
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
        # если текущее значение не в списке — сбрасываем
        cur = combo.get()
        if cur and cur not in names:
            combo.set("")

    # ------------------------------------------------------------------
    # Добавление
    # ------------------------------------------------------------------

    def add_fertilizer_dialog(self):
        """Открывает диалог создания нового удобрения."""
        data = self._fertilizer_form_dialog("Новое удобрение")
        if data is not None:
            add_fertilizer(self.conn, data)
            self.refresh_ferts()

    # ------------------------------------------------------------------
    # Редактирование
    # ------------------------------------------------------------------

    def edit_fertilizer(self):
        """Открывает диалог редактирования выбранного удобрения."""
        sel = self.fert_tree.selection()
        if not sel:
            return
        fid = int(sel[0])
        fert = get_fertilizer(self.conn, fid)
        if not fert:
            return
        data = self._fertilizer_form_dialog("Редактировать удобрение", fert=fert)
        if data is not None:
            update_fertilizer(self.conn, fid, data)
            self.refresh_ferts()

    # ------------------------------------------------------------------
    # Удаление
    # ------------------------------------------------------------------

    def delete_fertilizer_selected(self):
        """Удаляет выбранное удобрение после подтверждения."""
        sel = self.fert_tree.selection()
        if not sel:
            return
        fid = int(sel[0])
        fert = get_fertilizer(self.conn, fid)
        name = fert["name"] if fert else str(fid)
        if not messagebox.askyesno("Удаление",
                                    f"Удалить удобрение «{name}»?\n"
                                    "Связанные записи дозировок будут также удалены.",
                                    parent=self.root if hasattr(self, "root") else self):
            return
        delete_fertilizer(self.conn, fid)
        self.refresh_ferts()

    # ------------------------------------------------------------------
    # Форма удобрения (модальный диалог)
    # ------------------------------------------------------------------

    def _fertilizer_form_dialog(self, title, fert=None):
        """Модальный диалог с полями: название, форма, концентрации элементов, заметка.

        Parameters
        ----------
        title : str
            Заголовок окна.
        fert : sqlite3.Row | None
            Если передано — режим редактирования, поля заполняются из строки.

        Returns
        -------
        dict | None
            Словарь данных для add_fertilizer / update_fertilizer,
            либо None при отмене.
        """
        FF = self.FF
        is_edit = fert is not None

        dlg = tk.Toplevel(self.root if hasattr(self, "root") else self)
        dlg.title(title)
        dlg.configure(bg=COLOR_BG)
        dlg.transient(dlg.master)
        dlg.grab_set()
        dlg.resizable(False, False)

        pad = dict(padx=12, pady=3)

        # --- название ---
        name_frame = tk.Frame(dlg, bg=COLOR_BG)
        name_frame.pack(fill="x", **pad, pady=(12, 4))
        tk.Label(name_frame, text="Название:", width=16, anchor="w",
                 font=(FF, 10), bg=COLOR_BG, fg=COLOR_TEXT_SOFT).pack(side="left")
        name_var = tk.StringVar(value=fert["name"] if fert else "")
        ttk.Entry(name_frame, textvariable=name_var, width=40).pack(
            side="left", fill="x", expand=True)

        # --- форма ---
        form_frame = tk.Frame(dlg, bg=COLOR_BG)
        form_frame.pack(fill="x", **pad)
        tk.Label(form_frame, text="Форма:", width=16, anchor="w",
                 font=(FF, 10), bg=COLOR_BG, fg=COLOR_TEXT_SOFT).pack(side="left")
        form_var = tk.StringVar(value=fert["form"] if fert else "Жидкое (мг/мл)")
        form_combo = ttk.Combobox(form_frame, textvariable=form_var, width=36,
                                   values=["Жидкое (мг/мл)", "Сухое (мг/г)"],
                                   state="readonly")
        form_combo.pack(side="left", fill="x", expand=True)

        # --- концентрации элементов (сетка 3 колонки) ---
        ttk.Separator(dlg).pack(fill="x", padx=12, pady=8)
        tk.Label(dlg, text="Концентрации элементов (мг на единицу)",
                 font=(FF, 10, "bold"), bg=COLOR_BG, fg=COLOR_ACCENT).pack(
            anchor="w", padx=12)

        elem_vars = {}
        grid_frame = tk.Frame(dlg, bg=COLOR_BG)
        grid_frame.pack(fill="x", padx=12, pady=4)

        col_count = 3
        for idx, ek in enumerate(ELEMENT_KEYS):
            row_idx = idx // col_count
            col_idx = (idx % col_count) * 2

            formula = ELEMENT_FORMULA[ek]
            ru = ELEMENT_RU[ek]

            cell = tk.Frame(grid_frame, bg=COLOR_BG)
            cell.grid(row=row_idx, column=col_idx, sticky="w", padx=(0, 8), pady=2)

            tk.Label(cell, text=f"{ru} ({formula}):", font=(FF, 9),
                     bg=COLOR_BG, fg=COLOR_TEXT_SOFT, width=16, anchor="w").pack(side="left")
            val = fert.get(ek) if fert else 0.0
            var = tk.StringVar(value=f"{val:g}" if val is not None and val != 0 else "")
            ttk.Entry(cell, textvariable=var, width=8, justify="center").pack(side="left")
            elem_vars[ek] = var

        # --- заметка ---
        ttk.Separator(dlg).pack(fill="x", padx=12, pady=8)
        tk.Label(dlg, text="Заметка:", font=(FF, 10, "bold"),
                 bg=COLOR_BG, fg=COLOR_ACCENT).pack(anchor="w", padx=12)
        note_text = tk.Text(dlg, width=60, height=4, font=(FF, 9),
                            bg=COLOR_CARD, fg=COLOR_TEXT, insertbackground=COLOR_TEXT,
                            relief="flat", borderwidth=1, highlightbackground=COLOR_BORDER,
                            highlightthickness=1, wrap="word")
        note_text.pack(fill="x", padx=12, pady=(2, 4))
        if fert and fert.get("note"):
            note_text.insert("1.0", fert["note"])

        # --- кнопки ---
        btn_row = tk.Frame(dlg, bg=COLOR_BG)
        btn_row.pack(fill="x", padx=12, pady=(4, 12))

        def _save():
            name = name_var.get().strip()
            if not name:
                messagebox.showwarning("Внимание", "Укажите название удобрения.", parent=dlg)
                return
            data = {"name": name, "form": form_var.get()}
            for ek, var in elem_vars.items():
                v = parse_float(var.get(), None)
                if v is not None:
                    data[ek] = v
                else:
                    data[ek] = 0.0
            data["note"] = note_text.get("1.0", "end").strip() or None
            dlg.destroy()
            dlg._result = data  # type: ignore[attr-defined]

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

        dlg._result = None  # type: ignore[attr-defined]
        dlg.update_idletasks()
        pw = dlg.master.winfo_width()
        ph = dlg.master.winfo_height()
        px = dlg.master.winfo_rootx()
        py = dlg.master.winfo_rooty()
        dw = dlg.winfo_width()
        dh = dlg.winfo_height()
        dlg.geometry(f"+{px + (pw - dw) // 2}+{py + (ph - dh) // 2}")

        dlg.wait_window()
        return dlg._result  # type: ignore[attr-defined]