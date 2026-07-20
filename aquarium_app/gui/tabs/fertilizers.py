"""Вкладка «Удобрения» — карточный справочник с визуальным отображением состава."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from aquarium_app.config import (
    COLOR_BG, COLOR_CARD, COLOR_ACCENT, COLOR_BORDER, COLOR_TEXT,
    COLOR_TEXT_MUTED, COLOR_TEXT_SOFT, COLOR_ACCENT_HOVER, COLOR_ALT_ROW,
    COLOR_ACCENT_SOFT, COLOR_OK_TEXT,
    ELEMENT_KEYS, ELEMENT_FORMULA, ELEMENT_RU, ELEMENT_COLORS,
    FONT_FAMILY,
)
from aquarium_app.db import (
    get_fertilizers, get_fertilizer, add_fertilizer,
    update_fertilizer, delete_fertilizer,
)
from aquarium_app.logic.formatters import parse_float

# Группы элементов для визуального разделения
MACRO_KEYS = ["no3", "po4", "k", "mg", "ca"]
MICRO_KEYS = ["fe", "mn", "b", "zn", "cu", "mo", "co"]

# ---------------------------------------------------------------------------
# Единые константы отступов
# ---------------------------------------------------------------------------
PAD_X = 16
PAD_Y_TOP = 14
GAP_BODY = 10
CARD_PAD = 10
CARD_GAP = 6


class FertilizersTab:
    """Миксин-вкладка «Удобрения» — карточки на всю ширину."""

    # ------------------------------------------------------------------
    # Построение вкладки
    # ------------------------------------------------------------------

    def build_ferts_tab(self):
        tab = self.tab_ferts
        FF = self.FF

        # --- верхняя панель: заголовок + поиск + кнопки ---
        top = tk.Frame(tab, bg=COLOR_BG)
        top.pack(fill="x", padx=PAD_X, pady=(PAD_Y_TOP, 0))

        tk.Label(top, text="Удобрения", font=(FF, 16, "bold"),
                 bg=COLOR_BG, fg=COLOR_TEXT).pack(side="left")

        # поиск
        self._fert_widgets = []
        self._selected_fert_id = None
        self.fert_tree = None

        search_frame = tk.Frame(top, bg=COLOR_BG)
        search_frame.pack(side="left", padx=(24, 0))
        self._fert_search_var = tk.StringVar()
        self._fert_search_var.trace_add("write", lambda *_: self._filter_fert_cards())
        search_entry = ttk.Entry(search_frame, textvariable=self._fert_search_var, width=22)
        search_entry.pack(side="left")
        search_entry.insert(0, "Поиск...")
        search_entry.bind("<FocusIn>", lambda e: (search_entry.delete(0, "end"),
                                                   self._filter_fert_cards()))
        search_entry.bind("<FocusOut>", lambda e: (search_entry.delete(0, "end"),
                                                    search_entry.insert(0, "Поиск..."),
                                                    self._fert_search_var.set("")))

        # кнопки действий (справа)
        self._fert_edit_btn = tk.Button(
            top, text="Редактировать", font=(FF, 9), relief="flat",
            bg=COLOR_ALT_ROW, fg=COLOR_TEXT_MUTED, activebackground=COLOR_BORDER,
            borderwidth=0, padx=10, pady=5, command=self.edit_fertilizer,
            cursor="hand2", state="disabled")
        self._fert_edit_btn.pack(side="right", padx=(6, 0))

        self._fert_del_btn = tk.Button(
            top, text="Удалить", font=(FF, 9), relief="flat",
            bg=COLOR_ALT_ROW, fg=COLOR_TEXT_MUTED, activebackground=COLOR_BORDER,
            borderwidth=0, padx=10, pady=5, command=self.delete_fertilizer_selected,
            cursor="hand2", state="disabled")
        self._fert_del_btn.pack(side="right", padx=(0, 0))

        tk.Button(top, text="+ Добавить", font=(FF, 9, "bold"), relief="flat",
                  bg=COLOR_ACCENT, fg="#151515", activebackground=COLOR_ACCENT_HOVER,
                  activeforeground="#151515", borderwidth=0, padx=14, pady=5,
                  command=self.add_fertilizer_dialog, cursor="hand2").pack(side="right", padx=(0, 8))

        # --- тело: карточки на всю ширину ---
        body = tk.Frame(tab, bg=COLOR_BG)
        body.pack(fill="both", expand=True, padx=PAD_X, pady=(GAP_BODY, PAD_X))

        self._fert_cards_inner = body
        self._fert_detail = None  # не используется

        self._fert_widgets = []
        self._selected_fert_id = None
        self.fert_tree = None

    # ------------------------------------------------------------------
    # Фильтрация по поиску
    # ------------------------------------------------------------------

    def _filter_fert_cards(self):
        query = self._fert_search_var.get().lower().strip()
        for card_frame, fert_id in self._fert_widgets:
            fert = get_fertilizer(self.conn, fert_id)
            if not fert:
                continue
            name = (fert["name"] or "").lower()
            form = (fert["form"] or "").lower()
            note = (fert["note"] or "").lower()
            match = not query or query in name or query in form or query in note
            if match:
                card_frame.pack(fill="x", pady=(0, CARD_GAP))
            else:
                card_frame.pack_forget()

    # ------------------------------------------------------------------
    # Обновление списка
    # ------------------------------------------------------------------

    def refresh_ferts(self):
        for w in self._fert_cards_inner.winfo_children():
            w.destroy()
        self._fert_widgets = []

        ferts = get_fertilizers(self.conn)
        for f in ferts:
            self._build_fert_card(f)

        # выделяем первый если ничего не выбрано
        if ferts and not self._selected_fert_id:
            self._select_fert_card(ferts[0]["id"])

        self._refresh_fert_dropdown()

    # ------------------------------------------------------------------
    # Карточка удобрения
    # ------------------------------------------------------------------

    def _build_fert_card(self, f):
        FF = self.FF
        parent = self._fert_cards_inner
        fid = f["id"]

        card = tk.Frame(parent, bg=COLOR_CARD, cursor="hand2",
                        highlightbackground=COLOR_BORDER, highlightthickness=1)
        card.pack(fill="x", pady=(0, CARD_GAP))

        inner = tk.Frame(card, bg=COLOR_CARD)
        inner.pack(fill="x", padx=CARD_PAD, pady=10)

        # строка 1: название + форма
        hdr = tk.Frame(inner, bg=COLOR_CARD)
        hdr.pack(fill="x")
        tk.Label(hdr, text=f["name"] or "Без названия", bg=COLOR_CARD, fg=COLOR_TEXT,
                 font=(FF, 11, "bold")).pack(side="left")
        if f.get("form"):
            tk.Label(hdr, text=f["form"], bg=COLOR_ALT_ROW, fg=COLOR_TEXT_MUTED,
                     font=(FF, 8), padx=6, pady=2).pack(side="right")

        # мини-бары состава (только непустые элементы)
        active = [(ek, f.get(ek, 0) or 0) for ek in ELEMENT_KEYS if (f.get(ek, 0) or 0) > 0]
        if active:
            bars_frame = tk.Frame(inner, bg=COLOR_CARD)
            bars_frame.pack(fill="x", pady=(8, 0))
            max_val = max(v for _, v in active) or 1.0
            for ek, val in active:
                row = tk.Frame(bars_frame, bg=COLOR_CARD)
                row.pack(fill="x", pady=1)
                color = ELEMENT_COLORS.get(ek, COLOR_ACCENT)
                ru = ELEMENT_RU.get(ek, ek)
                formula = ELEMENT_FORMULA.get(ek, ek)
                tk.Label(row, text=f"{ru} ({formula})", bg=COLOR_CARD, fg=COLOR_TEXT_MUTED,
                         font=(FF, 8), width=12, anchor="w").pack(side="left")
                # трек
                track = tk.Frame(row, bg="#2a2015", height=8)
                track.pack(side="left", fill="x", expand=True, padx=(0, 6))
                track.pack_propagate(False)
                # бар
                bar_w = max(4, int(200 * (val / max_val)))
                bar = tk.Frame(track, bg=color, height=8, width=bar_w)
                bar.place(x=0, y=0, relheight=1.0)
                # значение
                tk.Label(row, text=f"{val:.1f}", bg=COLOR_CARD, fg=color,
                         font=(FF, 8, "bold"), width=6, anchor="e").pack(side="right")

        # заметка (если есть, свёрнутая)
        if f.get("note"):
            tk.Label(inner, text=f["note"], bg=COLOR_CARD, fg=COLOR_TEXT_MUTED,
                     font=(FF, 8, "italic"), wraplength=700, anchor="w",
                     justify="left").pack(anchor="w", pady=(6, 0))

        # привязка кликов
        def _on_click(e, _fid=fid):
            self._select_fert_card(_fid)

        def _on_dbl_click(e, _fid=fid):
            self._select_fert_card(_fid)
            self.edit_fertilizer()

        for w in (card, inner, *inner.winfo_children()):
            w.bind("<Button-1>", _on_click)
            w.bind("<Double-1>", _on_dbl_click)

        self._fert_widgets.append((card, fid))

    # ------------------------------------------------------------------
    # Выбор карточки
    # ------------------------------------------------------------------

    def _select_fert_card(self, fid):
        self._selected_fert_id = fid
        for card_frame, _fid in self._fert_widgets:
            if _fid == fid:
                card_frame.configure(highlightbackground=COLOR_ACCENT, highlightthickness=2)
            else:
                card_frame.configure(highlightbackground=COLOR_BORDER, highlightthickness=1)
        # активировать кнопки
        self._fert_edit_btn.config(state="normal", bg=COLOR_ACCENT, fg="#151515")
        self._fert_del_btn.config(state="normal")

    # ------------------------------------------------------------------
    # Обновление выпадающего списка на вкладке дозирования
    # ------------------------------------------------------------------

    def _refresh_fert_dropdown(self):
        """Обновляет сетку удобрений на вкладке дозирования после изменений."""
        self._rebuild_dose_fert_grid()

    # ------------------------------------------------------------------
    # Добавление
    # ------------------------------------------------------------------

    def add_fertilizer_dialog(self):
        data = self._fertilizer_form_dialog("Новое удобрение")
        if data is not None:
            add_fertilizer(self.conn, data)
            self.refresh_ferts()

    # ------------------------------------------------------------------
    # Редактирование
    # ------------------------------------------------------------------

    def edit_fertilizer(self):
        fid = self._selected_fert_id
        if fid is None:
            return
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
        fid = self._selected_fert_id
        if fid is None:
            return
        fert = get_fertilizer(self.conn, fid)
        name = fert["name"] if fert else str(fid)
        if not messagebox.askyesno("Удаление",
                                    f"Удалить удобрение «{name}»?\n"
                                    "Связанные записи дозировок будут также удалены.",
                                    parent=self.root if hasattr(self, "root") else self):
            return
        delete_fertilizer(self.conn, fid)
        self._selected_fert_id = None
        self._fert_edit_btn.config(state="disabled", bg=COLOR_ALT_ROW, fg=COLOR_TEXT_MUTED)
        self._fert_del_btn.config(state="disabled")
        self.refresh_ferts()

    # ------------------------------------------------------------------
    # Форма удобрения (модальный диалог)
    # ------------------------------------------------------------------

    def _fertilizer_form_dialog(self, title, fert=None):
        FF = self.FF

        dlg = tk.Toplevel(self.root if hasattr(self, "root") else self)
        dlg.title(title)
        dlg.configure(bg=COLOR_BG)
        dlg.transient(dlg.master)
        dlg.grab_set()
        dlg.resizable(False, False)
        dlg.geometry("580x700")

        P = 20

        # --- название ---
        name_frame = tk.Frame(dlg, bg=COLOR_BG)
        name_frame.pack(fill="x", padx=P, pady=(P, 6))
        tk.Label(name_frame, text="Название:", width=16, anchor="w",
                 font=(FF, 10), bg=COLOR_BG, fg=COLOR_TEXT_SOFT).pack(side="left")
        name_var = tk.StringVar(value=fert["name"] if fert else "")
        ttk.Entry(name_frame, textvariable=name_var, width=40).pack(
            side="left", fill="x", expand=True)

        # --- форма ---
        form_frame = tk.Frame(dlg, bg=COLOR_BG)
        form_frame.pack(fill="x", padx=P, pady=6)
        tk.Label(form_frame, text="Форма:", width=16, anchor="w",
                 font=(FF, 10), bg=COLOR_BG, fg=COLOR_TEXT_SOFT).pack(side="left")
        form_var = tk.StringVar(value=fert["form"] if fert else "Жидкое (мг/мл)")
        form_combo = ttk.Combobox(form_frame, textvariable=form_var, width=36,
                                   values=["Жидкое (мг/мл)", "Сухое (мг/г)"],
                                   state="readonly")
        form_combo.pack(side="left", fill="x", expand=True)

        # --- разделитель ---
        ttk.Separator(dlg).pack(fill="x", padx=P, pady=12)
        tk.Label(dlg, text="Концентрации элементов (мг на единицу)",
                 font=(FF, 10, "bold"), bg=COLOR_BG, fg=COLOR_ACCENT).pack(
            anchor="w", padx=P, pady=(0, 8))

        # --- макроэлементы ---
        macro_frame = tk.LabelFrame(dlg, text="  Макроэлементы  ", font=(FF, 9, "bold"),
                                    bg=COLOR_BG, fg=COLOR_TEXT_MUTED, bd=1, relief="groove")
        macro_frame.pack(fill="x", padx=P, pady=(0, 6))

        elem_vars = {}
        for ek in MACRO_KEYS:
            row = tk.Frame(macro_frame, bg=COLOR_BG)
            row.pack(fill="x", padx=10, pady=4)
            color = ELEMENT_COLORS.get(ek, COLOR_ACCENT)
            ind = tk.Frame(row, bg=color, width=4, height=18)
            ind.pack(side="left", padx=(0, 8))
            ind.pack_propagate(False)
            ru = ELEMENT_RU[ek]
            formula = ELEMENT_FORMULA[ek]
            tk.Label(row, text=f"{ru} ({formula}):", font=(FF, 9),
                     bg=COLOR_BG, fg=COLOR_TEXT_SOFT, width=18, anchor="w").pack(side="left")
            val = fert.get(ek) if fert else 0.0
            var = tk.StringVar(value=f"{val:g}" if val is not None and val != 0 else "")
            entry = ttk.Entry(row, textvariable=var, width=12, justify="center")
            entry.pack(side="left", padx=(0, 6))
            tk.Label(row, text="мг/мл", font=(FF, 8), bg=COLOR_BG,
                     fg=COLOR_TEXT_MUTED).pack(side="left")
            elem_vars[ek] = var

        # --- микроэлементы ---
        micro_frame = tk.LabelFrame(dlg, text="  Микроэлементы  ", font=(FF, 9, "bold"),
                                    bg=COLOR_BG, fg=COLOR_TEXT_MUTED, bd=1, relief="groove")
        micro_frame.pack(fill="x", padx=P, pady=6)

        for ek in MICRO_KEYS:
            row = tk.Frame(micro_frame, bg=COLOR_BG)
            row.pack(fill="x", padx=10, pady=4)
            color = ELEMENT_COLORS.get(ek, COLOR_ACCENT)
            ind = tk.Frame(row, bg=color, width=4, height=18)
            ind.pack(side="left", padx=(0, 8))
            ind.pack_propagate(False)
            ru = ELEMENT_RU[ek]
            formula = ELEMENT_FORMULA[ek]
            tk.Label(row, text=f"{ru} ({formula}):", font=(FF, 9),
                     bg=COLOR_BG, fg=COLOR_TEXT_SOFT, width=18, anchor="w").pack(side="left")
            val = fert.get(ek) if fert else 0.0
            var = tk.StringVar(value=f"{val:g}" if val is not None and val != 0 else "")
            entry = ttk.Entry(row, textvariable=var, width=12, justify="center")
            entry.pack(side="left", padx=(0, 6))
            tk.Label(row, text="мг/мл", font=(FF, 8), bg=COLOR_BG,
                     fg=COLOR_TEXT_MUTED).pack(side="left")
            elem_vars[ek] = var

        # --- заметка ---
        ttk.Separator(dlg).pack(fill="x", padx=P, pady=12)
        tk.Label(dlg, text="Заметка:", font=(FF, 10, "bold"),
                 bg=COLOR_BG, fg=COLOR_ACCENT).pack(anchor="w", padx=P, pady=(0, 6))
        note_text = tk.Text(dlg, width=60, height=3, font=(FF, 9),
                            bg=COLOR_CARD, fg=COLOR_TEXT, insertbackground=COLOR_TEXT,
                            relief="flat", borderwidth=1, highlightbackground=COLOR_BORDER,
                            highlightthickness=1, wrap="word")
        note_text.pack(fill="x", padx=P, pady=(0, 6))
        if fert and fert.get("note"):
            note_text.insert("1.0", fert["note"])

        # --- кнопки ---
        btn_row = tk.Frame(dlg, bg=COLOR_BG)
        btn_row.pack(fill="x", padx=P, pady=(12, P))

        def _save():
            name = name_var.get().strip()
            if not name:
                messagebox.showwarning("Внимание", "Укажите название удобрения.", parent=dlg)
                return
            data = {"name": name, "form": form_var.get()}
            for ek, var in elem_vars.items():
                v = parse_float(var.get(), None)
                data[ek] = v if v is not None else 0.0
            data["note"] = note_text.get("1.0", "end").strip() or None
            dlg.destroy()
            dlg._result = data

        def _cancel():
            dlg.destroy()

        tk.Button(btn_row, text="Отмена", font=(FF, 9), relief="flat",
                  bg=COLOR_CARD, fg=COLOR_TEXT, activebackground=COLOR_ALT_ROW,
                  borderwidth=0, padx=14, pady=5, command=_cancel,
                  cursor="hand2").pack(side="right", padx=(8, 0))
        tk.Button(btn_row, text="Сохранить", font=(FF, 9, "bold"), relief="flat",
                  bg=COLOR_ACCENT, fg="#151515", activebackground=COLOR_ACCENT_HOVER,
                  activeforeground="#151515", borderwidth=0, padx=14, pady=5,
                  command=_save, cursor="hand2").pack(side="right")

        dlg._result = None
        dlg.update_idletasks()
        pw = dlg.master.winfo_width()
        ph = dlg.master.winfo_height()
        px = dlg.master.winfo_rootx()
        py = dlg.master.winfo_rooty()
        dw = dlg.winfo_width()
        dh = dlg.winfo_height()
        dlg.geometry(f"+{px + (pw - dw) // 2}+{py + (ph - dh) // 2}")

        dlg.wait_window()
        return dlg._result