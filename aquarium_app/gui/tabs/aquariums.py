"""Вкладка «Аквариумы» — список аквариумов, редактирование, целевые диапазоны."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from aquarium_app.config import (
    COLOR_BG, COLOR_CARD, COLOR_ACCENT, COLOR_BORDER, COLOR_TEXT,
    COLOR_TEXT_MUTED, COLOR_TEXT_SOFT, COLOR_ACCENT_HOVER, COLOR_ALT_ROW,
    FONT_FAMILY, TEST_PARAMS, TEST_PARAM_RU,
)
from aquarium_app.db import get_aquariums, update_aquarium, get_targets, update_target
from aquarium_app.gui.widgets import LabeledEntry


class AquariumsTab:
    """Миксин-вкладка «Аквариумы»."""

    # ------------------------------------------------------------------
    # Построение вкладки
    # ------------------------------------------------------------------

    def build_aquariums_tab(self):
        """Создаёт Treeview с колонками (имя, объём, CO₂, свет) + кнопку добавления."""
        tab = self.tab_aquariums  # type: tk.Frame
        FF = self.FF

        # заголовок
        hdr = tk.Frame(tab, bg=COLOR_BG)
        hdr.pack(fill="x", padx=16, pady=(12, 0))
        tk.Label(hdr, text="Аквариумы", font=(FF, 16, "bold"),
                 bg=COLOR_BG, fg=COLOR_TEXT).pack(side="left")
        tk.Button(hdr, text="Добавить", font=(FF, 9), relief="flat",
                  bg=COLOR_ACCENT, fg="#151515", activebackground=COLOR_ACCENT_HOVER,
                  activeforeground="#151515", borderwidth=0, padx=12, pady=4,
                  command=self.add_aquarium_dialog, cursor="hand2").pack(side="right")

        # дерево
        tree_frame = tk.Frame(tab, bg=COLOR_BG)
        tree_frame.pack(fill="both", expand=True, padx=12, pady=12)

        cols = ("name", "volume", "co2", "light")
        self.aq_tree = ttk.Treeview(tree_frame, columns=cols, show="headings",
                                     height=12, selectmode="browse")
        self.aq_tree.heading("name", text="Название")
        self.aq_tree.heading("volume", text="Объём, л")
        self.aq_tree.heading("co2", text="CO₂")
        self.aq_tree.heading("light", text="Освещение")
        self.aq_tree.column("name", width=250, minwidth=150)
        self.aq_tree.column("volume", width=100, minwidth=70, anchor="center")
        self.aq_tree.column("co2", width=80, minwidth=60, anchor="center")
        self.aq_tree.column("light", width=200, minwidth=120)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.aq_tree.yview)
        self.aq_tree.configure(yscrollcommand=vsb.set)
        self.aq_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # двойной клик — редактировать
        self.aq_tree.bind("<Double-1>", lambda e: self.edit_aquarium())

        # кнопки под таблицей
        btn_row = tk.Frame(tab, bg=COLOR_BG)
        btn_row.pack(fill="x", padx=16, pady=(0, 12))
        tk.Button(btn_row, text="Редактировать", font=(FF, 9), relief="flat",
                  bg=COLOR_CARD, fg=COLOR_TEXT, activebackground=COLOR_ALT_ROW,
                  borderwidth=0, padx=12, pady=4, command=self.edit_aquarium,
                  cursor="hand2").pack(side="left")
        tk.Button(btn_row, text="Удалить", font=(FF, 9), relief="flat",
                  bg=COLOR_CARD, fg=COLOR_TEXT, activebackground=COLOR_ALT_ROW,
                  borderwidth=0, padx=12, pady=4, command=self.delete_aquarium_selected,
                  cursor="hand2").pack(side="left", padx=(8, 0))

        self.aq_tree.after(100, self.refresh_aquariums)

    # ------------------------------------------------------------------
    # Обновление таблицы
    # ------------------------------------------------------------------

    def refresh_aquariums(self):
        """Заполняет дерево аквариумами из БД."""
        tree = self.aq_tree
        if not tree.winfo_exists():
            return
        tree.delete(*tree.get_children())
        for aq in get_aquariums(self.conn):
            co2 = aq["co2"] or ""
            light = aq["light"] or ""
            tree.insert("", "end", iid=str(aq["id"]),
                        values=(aq["name"], f"{aq['volume_l']:.0f}", co2, light))

    # ------------------------------------------------------------------
    # Диалог редактирования аквариума
    # ------------------------------------------------------------------

    def edit_aquarium(self):
        """Открывает диалог редактирования выбранного аквариума."""
        try:
            sel = self.aq_tree.selection()
            if not sel:
                return
            aq_id = int(sel[0])
            aq = get_aquarium(self.conn, aq_id)
            if not aq:
                return
            self._aquarium_form_dialog("Редактировать аквариум", aq)
        except Exception as e:
            import traceback
            traceback.print_exc()
            messagebox.showerror("Ошибка", str(e))

    def add_aquarium_dialog(self):
        """Открывает диалог создания нового аквариума."""
        self._aquarium_form_dialog("Новый аквариум", None)

    def _aquarium_form_dialog(self, title, aq=None):
        """Модальный диалог для создания/редактирования аквариума.

        Содержит поля: название, объём, CO₂, освещение, а также целевые
        диапазоны для всех TEST_PARAMS (param, min, max).
        """
        FF = self.FF
        is_new = aq is None
        aq_id = aq["id"] if aq else None

        dlg = tk.Toplevel(self.root if hasattr(self, "root") else self)
        dlg.title(title)
        dlg.configure(bg=COLOR_BG)
        dlg.transient(dlg.master)
        dlg.grab_set()
        dlg.resizable(False, False)
        dlg.lift()
        dlg.focus_force()

        pad = dict(padx=12, pady=3)

        # --- основные поля ---
        tk.Label(dlg, text="Основные параметры", font=(FF, 11, "bold"),
                 bg=COLOR_BG, fg=COLOR_ACCENT).pack(anchor="w", **pad, pady=(12, 4))

        name_entry = LabeledEntry(dlg, "Название:", width=30,
                                   default=aq["name"] if aq else "Новый аквариум")
        name_entry.pack(fill="x", **pad)

        vol_entry = LabeledEntry(dlg, "Объём (л):", width=30,
                                  default=f"{aq['volume_l']:.0f}" if aq else "60")
        vol_entry.pack(fill="x", **pad)

        co2_entry = LabeledEntry(dlg, "CO₂:", width=30,
                                  default=aq["co2"] if aq else "Да")
        co2_entry.pack(fill="x", **pad)

        light_entry = LabeledEntry(dlg, "Освещение:", width=30,
                                    default=aq["light"] if aq else "")
        light_entry.pack(fill="x", **pad)

        wc_goal_entry = LabeledEntry(dlg, "Подмена % в неделю:", width=30,
                                     default=str(int(aq["wc_week_goal"])) if aq and aq.get("wc_week_goal") else "30")
        wc_goal_entry.pack(fill="x", **pad)

        # --- целевые диапазоны ---
        ttk.Separator(dlg).pack(fill="x", padx=12, pady=8)
        tk.Label(dlg, text="Целевые диапазоны параметров", font=(FF, 11, "bold"),
                 bg=COLOR_BG, fg=COLOR_ACCENT).pack(anchor="w", **pad, pady=(0, 4))

        # получаем текущие цели
        targets = {}
        if aq_id:
            targets = get_targets(self.conn, aq_id)

        target_entries = {}
        for key, label, unit in TEST_PARAMS:
            ru = TEST_PARAM_RU.get(key, label)
            row = tk.Frame(dlg, bg=COLOR_BG)
            row.pack(fill="x", **pad)
            tk.Label(row, text=ru, width=24, anchor="w", font=(FF, 9),
                     bg=COLOR_BG, fg=COLOR_TEXT_SOFT).pack(side="left")
            mn_var = tk.StringVar()
            mx_var = tk.StringVar()
            rng = targets.get(key)
            if rng:
                mn_var.set(str(rng[0]) if rng[0] is not None else "")
                mx_var.set(str(rng[1]) if rng[1] is not None else "")
            mn_e = ttk.Entry(row, textvariable=mn_var, width=8, justify="center")
            mn_e.pack(side="left", padx=(0, 4))
            tk.Label(row, text="–", bg=COLOR_BG, fg=COLOR_TEXT_MUTED,
                     font=(FF, 9)).pack(side="left")
            mx_e = ttk.Entry(row, textvariable=mx_var, width=8, justify="center")
            mx_e.pack(side="left", padx=(4, 0))
            if unit:
                tk.Label(row, text=f" {unit}", bg=COLOR_BG, fg=COLOR_TEXT_MUTED,
                         font=(FF, 9)).pack(side="left", padx=(4, 0))
            target_entries[key] = (mn_var, mx_var)

        # --- кнопки ---
        btn_row = tk.Frame(dlg, bg=COLOR_BG)
        btn_row.pack(fill="x", padx=12, pady=(12, 12))

        def _save():
            name = name_entry.get().strip()
            if not name:
                messagebox.showwarning("Внимание", "Укажите название аквариума.", parent=dlg)
                return
            try:
                volume = float(vol_entry.get().strip())
            except (ValueError, AttributeError):
                messagebox.showwarning("Внимание", "Объём должен быть числом.", parent=dlg)
                return
            co2 = co2_entry.get().strip() or None
            light = light_entry.get().strip() or None
            try:
                wc_goal = float(wc_goal_entry.get().strip())
            except (ValueError, AttributeError):
                wc_goal = 30

            if is_new:
                from aquarium_app.db import add_aquarium as db_add
                # add_aquarium not in db/__init__.py — use raw SQL
                cur = self.conn.execute(
                    "INSERT INTO aquariums (name, volume_l, co2, light, wc_week_goal) VALUES (?,?,?,?,?)",
                    (name, volume, co2, light, wc_goal))
                self.conn.commit()
                aq_id_new = cur.lastrowid
            else:
                update_aquarium(self.conn, aq_id, name, volume, co2, light, wc_goal)
                aq_id_new = aq_id

            # сохраняем целевые диапазоны
            for key, (mn_var, mx_var) in target_entries.items():
                mn_s = mn_var.get().strip()
                mx_s = mx_var.get().strip()
                mn = float(mn_s) if mn_s else None
                mx = float(mx_s) if mx_s else None
                if mn is not None and mx is not None:
                    update_target(self.conn, aq_id_new, key, mn, mx)

            self.refresh_aquariums()
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

        # центрирование
        dlg.update_idletasks()
        pw = dlg.master.winfo_width()
        ph = dlg.master.winfo_height()
        px = dlg.master.winfo_rootx()
        py = dlg.master.winfo_rooty()
        dw = dlg.winfo_width()
        dh = dlg.winfo_height()
        dlg.geometry(f"+{px + (pw - dw) // 2}+{py + (ph - dh) // 2}")

        dlg.wait_window()

    # ------------------------------------------------------------------
    # Удаление аквариума
    # ------------------------------------------------------------------

    def delete_aquarium_selected(self):
        """Удаляет выбранный аквариум после подтверждения."""
        sel = self.aq_tree.selection()
        if not sel:
            return
        aq_id = int(sel[0])
        vals = self.aq_tree.item(sel[0], "values")
        name = vals[0] if vals else str(aq_id)
        if not messagebox.askyesno("Удаление",
                                    f"Удалить аквариум «{name}»?\n"
                                    "Все связанные данные (дозировки, замеры, таймеры) "
                                    "будут удалены.",
                                    parent=self.root if hasattr(self, "root") else self):
            return
        self.conn.execute("DELETE FROM aquariums WHERE id=?", (aq_id,))
        self.conn.commit()
        self.refresh_aquariums()