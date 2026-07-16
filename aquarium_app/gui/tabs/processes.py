"""Вкладка «Процессы» — отслеживание длительных процессов (диагностика, циклы и т.д.)."""
from __future__ import annotations

import datetime as dt
import tkinter as tk
from tkinter import ttk, messagebox

from aquarium_app.config import (
    COLOR_BG, COLOR_CARD, COLOR_ACCENT, COLOR_BORDER, COLOR_TEXT,
    COLOR_TEXT_MUTED, COLOR_ALT_ROW, COLOR_WARN_TEXT, COLOR_OK_TEXT,
    COLOR_TIMER_OK_BG, COLOR_TIMER_URGENT_BG, COLOR_TIMER_OVERDUE_BG,
    COLOR_STATUS_WAITING, COLOR_STATUS_URGENT, COLOR_STATUS_OVERDUE,
    COLOR_STATUS_DONE, FONT_FAMILY,
)
from aquarium_app.db import (
    get_aquarium,
    # импортируем для совместимости, но используем self.conn напрямую
    # (функции процессов работают со своей схемой)
    add_process as _add_process,
    get_active_processes as _get_active_processes,
    get_process as _get_process,
    update_process as _update_process,
    archive_process as _archive_process,
    restart_process as _restart_process,
    delete_process as _delete_process,
)
from aquarium_app.logic.formatters import format_elapsed, now_iso, parse_float
from aquarium_app.gui.widgets import DateEntry, SpinEntry


# Схема таблицы processes:
#   id, aquarium_id, title, started_at, expected_days, note, archived, created_at


class ProcessesTab:
    """Mixin-класс с методами для вкладки «Процессы»."""

    # ------------------------------------------------------------------
    # Построение вкладки
    # ------------------------------------------------------------------

    def build_processes_tab(self):
        FF = self.FF
        parent = self.tab_processes

        # --- верхняя панель ---
        top = tk.Frame(parent, bg=COLOR_BG)
        top.pack(fill="x", padx=12, pady=(10, 4))

        ttk.Label(top, text="Аквариум:", background=COLOR_BG).pack(side="left")
        self.proc_aq_var = tk.StringVar()
        self.proc_aq_combo = ttk.Combobox(
            top, textvariable=self.proc_aq_var,
            state="readonly", width=30,
        )
        self.proc_aq_combo.pack(side="left", padx=(6, 0))
        self.proc_aq_combo.bind("<<ComboboxSelected>>",
                                 lambda e: self.refresh_processes())

        # --- кнопка добавления ---
        tk.Button(
            top, text="+ Добавить процесс", font=(FF, 9, "bold"),
            bg=COLOR_ACCENT, fg="#151515", relief="flat",
            padx=12, pady=4, cursor="hand2",
            command=self.add_process_dialog,
        ).pack(side="right")

        # --- прокручиваемый контейнер карточек ---
        self.proc_scroll_container = tk.Frame(parent, bg=COLOR_BG)
        self.proc_scroll_container.pack(fill="both", expand=True, padx=12, pady=(4, 12))

    # ------------------------------------------------------------------
    # Аквариум
    # ------------------------------------------------------------------

    def refresh_processes_aq_combo(self):
        aqs = self.conn.execute("SELECT * FROM aquariums ORDER BY id").fetchall()
        items = [f"{r['id']} — {r['name']}" for r in aqs]
        self.proc_aq_combo["values"] = items
        if items and not self.proc_aq_var.get():
            self.proc_aq_combo.current(0)
            self.refresh_processes()

    def _current_proc_aq_id(self):
        s = self.proc_aq_var.get().strip()
        if not s:
            return None
        try:
            return int(s.split(" — ")[0])
        except (ValueError, IndexError):
            return None

    # ------------------------------------------------------------------
    # Обновление
    # ------------------------------------------------------------------

    def refresh_processes(self):
        aq_id = self._current_proc_aq_id()
        for w in self.proc_scroll_container.winfo_children():
            w.destroy()

        if not aq_id:
            return

        rows = self.conn.execute(
            "SELECT * FROM processes WHERE aquarium_id=? AND archived=0 "
            "ORDER BY started_at DESC",
            (aq_id,),
        ).fetchall()

        if not rows:
            tk.Label(
                self.proc_scroll_container,
                text="Нет активных процессов.",
                bg=COLOR_BG, fg=COLOR_TEXT_MUTED,
                font=(self.FF, 9, "italic"), anchor="w",
            ).pack(fill="x", pady=12)
            return

        for r in rows:
            self._build_process_card(r)

    # ------------------------------------------------------------------
    # Карточка процесса
    # ------------------------------------------------------------------

    def _build_process_card(self, r):
        FF = self.FF
        parent = self.proc_scroll_container
        proc_id = r["id"]
        title = r["title"] or "Без названия"
        expected = r.get("expected_days")
        note = r.get("note") or ""
        started_at = r.get("started_at") or now_iso()

        # вычисляем прошедшее время и прогресс
        try:
            start_dt = dt.datetime.fromisoformat(started_at)
        except (ValueError, TypeError):
            start_dt = dt.datetime.now()

        now = dt.datetime.now()
        elapsed_seconds = max((now - start_dt).total_seconds(), 0)
        elapsed_days = elapsed_seconds / 86400

        # статус
        if expected and expected > 0:
            progress = min(elapsed_days / expected, 1.5)
            if elapsed_days > expected * 1.1:
                status_text = "ПРОСРОЧЕНО"
                status_color = COLOR_STATUS_OVERDUE
                bg = COLOR_TIMER_OVERDUE_BG
                bar_color = COLOR_STATUS_OVERDUE
            elif elapsed_days > expected * 0.85:
                status_text = "СКОРО ЗАВЕРШЕНИЕ"
                status_color = COLOR_STATUS_URGENT
                bg = COLOR_TIMER_URGENT_BG
                bar_color = COLOR_STATUS_URGENT
            else:
                status_text = "ИДЁТ"
                status_color = COLOR_STATUS_WAITING
                bg = COLOR_TIMER_OK_BG
                bar_color = COLOR_STATUS_WAITING
            remaining_days = expected - elapsed_days
            remaining_str = f"осталось {max(0, remaining_days):.1f} дн." if remaining_days > 0 else "срок истёк"
        else:
            progress = 0
            status_text = "ИДЁТ"
            status_color = COLOR_STATUS_WAITING
            bg = COLOR_TIMER_OK_BG
            bar_color = COLOR_STATUS_WAITING
            remaining_str = "—"

        # карточка
        card = tk.Frame(parent, bg=bg, bd=0,
                        highlightbackground=COLOR_BORDER, highlightthickness=1)
        card.pack(fill="x", pady=(0, 6))

        inner = tk.Frame(card, bg=bg)
        inner.pack(fill="x", padx=12, pady=10)

        # заголовок + бейдж
        hdr = tk.Frame(inner, bg=bg)
        hdr.pack(fill="x")

        tk.Label(hdr, text=title, bg=bg, fg=COLOR_TEXT,
                 font=(FF, 11, "bold")).pack(side="left")
        tk.Label(hdr, text=f"  {status_text}", bg=bg,
                 fg=status_color, font=(FF, 8, "bold")).pack(side="left", padx=(8, 0))

        # прошедшее время (крупно)
        elapsed_str = format_elapsed(started_at)
        tk.Label(inner, text=elapsed_str, bg=bg, fg=status_color,
                 font=(FF, 16, "bold")).pack(anchor="w", pady=(6, 0))

        # доп. информация
        sub_parts = []
        if expected and expected > 0:
            sub_parts.append(f"ожидается: {expected:g} дн.")
        if remaining_str != "—":
            sub_parts.append(remaining_str)
        if sub_parts:
            tk.Label(inner, text=" | ".join(sub_parts), bg=bg,
                     fg=COLOR_TEXT_MUTED, font=(FF, 9)).pack(anchor="w", pady=(2, 0))

        # заметка
        if note:
            tk.Label(inner, text=note, bg=bg, fg=COLOR_TEXT_MUTED,
                     font=(FF, 9), wraplength=450, anchor="w",
                     justify="left").pack(anchor="w", pady=(4, 0))

        # прогресс-бар
        bar_canvas = tk.Canvas(inner, bg=bg, height=10, highlightthickness=0)
        bar_canvas.pack(fill="x", pady=(8, 0))
        self._draw_proc_progress(bar_canvas, min(progress, 1.0), bg, bar_color)

        # кнопки
        btn_row = tk.Frame(inner, bg=bg)
        btn_row.pack(fill="x", pady=(8, 0))

        tk.Button(
            btn_row, text="Перезапустить", font=(FF, 8),
            bg=COLOR_CARD, fg=COLOR_TEXT, relief="flat",
            activebackground=COLOR_ALT_ROW,
            padx=8, pady=3, cursor="hand2",
            command=lambda pid=proc_id: self._restart_process_from_card(pid),
        ).pack(side="left", padx=(0, 4))

        tk.Button(
            btn_row, text="Редактировать", font=(FF, 8),
            bg=COLOR_CARD, fg=COLOR_TEXT, relief="flat",
            activebackground=COLOR_ALT_ROW,
            padx=8, pady=3, cursor="hand2",
            command=lambda pid=proc_id: self._edit_process_from_card(pid),
        ).pack(side="left", padx=(0, 4))

        tk.Button(
            btn_row, text="В архив", font=(FF, 8),
            bg=COLOR_CARD, fg=COLOR_TEXT_MUTED, relief="flat",
            activebackground=COLOR_ALT_ROW,
            padx=8, pady=3, cursor="hand2",
            command=lambda pid=proc_id: self._archive_process_from_card(pid),
        ).pack(side="left", padx=(0, 4))

        tk.Button(
            btn_row, text="Удалить", font=(FF, 8),
            bg=COLOR_CARD, fg=COLOR_WARN_TEXT, relief="flat",
            activebackground=COLOR_ALT_ROW,
            padx=8, pady=3, cursor="hand2",
            command=lambda pid=proc_id: self._delete_process_from_card(pid),
        ).pack(side="right")

    # ------------------------------------------------------------------
    # Прогресс-бар процесса
    # ------------------------------------------------------------------

    def _draw_proc_progress(self, canvas, progress, bg, bar_color):
        if not canvas.winfo_exists():
            return
        canvas.delete("all")
        canvas.update_idletasks()
        w = max(canvas.winfo_width(), 100)
        h = max(canvas.winfo_height(), 8)
        pad = 1
        canvas.create_rectangle(pad, pad, w - pad, h - pad, fill="#2c2f3a", outline="")
        bar_w = int((w - 2 * pad) * progress)
        if bar_w > 0:
            canvas.create_rectangle(pad, pad, pad + bar_w, h - pad,
                                    fill=bar_color, outline="")

    # ------------------------------------------------------------------
    # Действия с карточки
    # ------------------------------------------------------------------

    def _restart_process_from_card(self, process_id):
        if not messagebox.askyesno("Перезапуск", "Перезапустить процесс с текущего момента?"):
            return
        now = now_iso()
        self.conn.execute(
            "UPDATE processes SET started_at=?, archived=0 WHERE id=?",
            (now, process_id),
        )
        self.conn.commit()
        self.refresh_processes()

    def _edit_process_from_card(self, process_id):
        row = self.conn.execute(
            "SELECT * FROM processes WHERE id=?", (process_id,)
        ).fetchone()
        if not row:
            return
        self._process_form_dialog("Редактировать процесс", entry=row)

    def _archive_process_from_card(self, process_id):
        if not messagebox.askyesno("В архив", "Отправить процесс в архив?"):
            return
        self.conn.execute(
            "UPDATE processes SET archived=1 WHERE id=?", (process_id,),
        )
        self.conn.commit()
        self.refresh_processes()

    def _delete_process_from_card(self, process_id):
        if not messagebox.askyesno("Удаление", "Удалить процесс навсегда?"):
            return
        self.conn.execute("DELETE FROM processes WHERE id=?", (process_id,))
        self.conn.commit()
        self.refresh_processes()

    # ------------------------------------------------------------------
    # Диалог создания/редактирования процесса
    # ------------------------------------------------------------------

    def add_process_dialog(self):
        aq_id = self._current_proc_aq_id()
        if not aq_id:
            messagebox.showwarning("Внимание", "Выберите аквариум.")
            return
        self._process_form_dialog("Новый процесс")

    def _process_form_dialog(self, title, entry=None):
        """Модальный диалог для создания/редактирования процесса."""
        FF = self.FF
        is_edit = entry is not None

        dlg = tk.Toplevel(self.root)
        dlg.title(title)
        dlg.configure(bg=COLOR_BG)
        dlg.transient(self.root)
        dlg.grab_set()
        dlg.resizable(False, False)

        inner = tk.Frame(dlg, bg=COLOR_CARD, padx=16, pady=14)
        inner.pack(padx=16, pady=16)

        # название
        row = tk.Frame(inner, bg=COLOR_CARD)
        row.pack(fill="x", pady=4)
        tk.Label(row, text="Название:", width=18, anchor="w", bg=COLOR_CARD,
                 fg=COLOR_TEXT, font=(FF, 10)).pack(side="left")
        title_var = tk.StringVar(value=entry["title"] if is_edit else "")
        ttk.Entry(row, textvariable=title_var, width=30).pack(side="left",
                                                                fill="x", expand=True)

        # дата + время
        row = tk.Frame(inner, bg=COLOR_CARD)
        row.pack(fill="x", pady=4)
        tk.Label(row, text="Дата и время:", width=18, anchor="w", bg=COLOR_CARD,
                 fg=COLOR_TEXT, font=(FF, 10)).pack(side="left")

        if is_edit:
            try:
                start_dt = dt.datetime.fromisoformat(entry["started_at"])
                date_default = start_dt.strftime("%d.%m.%Y")
                time_default = start_dt.strftime("%H:%M")
            except Exception:
                date_default = dt.date.today().strftime("%d.%m.%Y")
                time_default = dt.datetime.now().strftime("%H:%M")
        else:
            date_default = dt.date.today().strftime("%d.%m.%Y")
            time_default = dt.datetime.now().strftime("%H:%M")

        date_entry = DateEntry(row, font_family=FF, width=12, default=date_default)
        date_entry.pack(side="left")

        tk.Label(row, text=" ", bg=COLOR_CARD).pack(side="left")

        time_var = tk.StringVar(value=time_default)
        ttk.Entry(row, textvariable=time_var, width=6).pack(side="left")

        def _set_now():
            n = dt.datetime.now()
            date_entry.set(n.strftime("%d.%m.%Y"))
            time_var.set(n.strftime("%H:%M"))

        tk.Button(row, text="Сейчас", font=(FF, 8), bg=COLOR_BG, fg=COLOR_TEXT_MUTED,
                  relief="flat", padx=6, pady=2, cursor="hand2",
                  command=_set_now).pack(side="left", padx=(4, 0))

        # ожидаемая длительность
        row = tk.Frame(inner, bg=COLOR_CARD)
        row.pack(fill="x", pady=4)
        tk.Label(row, text="Длительность:", width=18, anchor="w", bg=COLOR_CARD,
                 fg=COLOR_TEXT, font=(FF, 10)).pack(side="left")
        exp_default = entry.get("expected_days") if (is_edit and entry.get("expected_days")) else ""
        exp_spin = SpinEntry(row, width=8, step=1.0, default=exp_default, min_val=0.1)
        exp_spin.pack(side="left")
        tk.Label(row, text="дн.", bg=COLOR_CARD, fg=COLOR_TEXT_MUTED,
                 font=(FF, 10)).pack(side="left", padx=(4, 0))

        # заметка
        row = tk.Frame(inner, bg=COLOR_CARD)
        row.pack(fill="x", pady=4)
        tk.Label(row, text="Заметка:", width=18, anchor="w", bg=COLOR_CARD,
                 fg=COLOR_TEXT, font=(FF, 10)).pack(side="left")
        note_text = tk.Text(row, width=36, height=4, bg=COLOR_BG, fg=COLOR_TEXT,
                            insertbackground=COLOR_TEXT, relief="flat",
                            font=(FF, 10), padx=6, pady=4,
                            borderwidth=1, highlightbackground=COLOR_BORDER,
                            highlightthickness=1)
        note_text.pack(side="left", fill="both", expand=True)
        if is_edit and entry.get("note"):
            note_text.insert("1.0", entry["note"])

        # кнопки
        btns = tk.Frame(inner, bg=COLOR_CARD)
        btns.pack(fill="x", pady=(12, 0))

        def _save():
            ptitle = title_var.get().strip()
            if not ptitle:
                messagebox.showwarning("Ошибка", "Укажите название процесса.",
                                        parent=dlg)
                return

            # парсим дату и время
            date_iso = None
            date_str = date_entry.get().strip()
            time_str = time_var.get().strip()
            try:
                dt_obj = dt.datetime.strptime(f"{date_str} {time_str}",
                                               "%d.%m.%Y %H:%M")
                date_iso = dt_obj.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                messagebox.showwarning("Ошибка", "Некорректная дата или время.",
                                        parent=dlg)
                return

            exp_days = parse_float(exp_spin.get(), None)
            note = note_text.get("1.0", "end").strip()

            if is_edit:
                self.conn.execute(
                    "UPDATE processes SET title=?, started_at=?, expected_days=?, note=? "
                    "WHERE id=?",
                    (ptitle, date_iso, exp_days, note, entry["id"]),
                )
                self.conn.commit()
            else:
                aq_id = self._current_proc_aq_id()
                if not aq_id:
                    messagebox.showwarning("Ошибка", "Выберите аквариум.",
                                            parent=dlg)
                    return
                self.conn.execute(
                    "INSERT INTO processes "
                    "(aquarium_id, title, started_at, expected_days, note, created_at) "
                    "VALUES (?,?,?,?,?,?)",
                    (aq_id, ptitle, date_iso, exp_days, note, now_iso()),
                )
                self.conn.commit()

            dlg.destroy()
            self.refresh_processes()

        tk.Button(btns, text="Сохранить", font=(FF, 10, "bold"),
                  bg=COLOR_ACCENT, fg="#151515", relief="flat",
                  padx=16, pady=4, command=_save).pack(side="left")
        tk.Button(btns, text="Отмена", font=(FF, 10),
                  bg=COLOR_CARD, fg=COLOR_TEXT, relief="flat",
                  padx=12, pady=4, command=dlg.destroy).pack(side="right")

        dlg.bind("<Escape>", lambda e: dlg.destroy())
        dlg.update_idletasks()
        x = self.root.winfo_rootx() + 120
        y = self.root.winfo_rooty() + 80
        dlg.geometry(f"+{x}+{y}")
        self.root.wait_window(dlg)

    # ------------------------------------------------------------------
    # Периодическое обновление
    # ------------------------------------------------------------------

    def _proc_tick(self):
        """Обновляет карточки процессов каждые 60 секунд."""
        try:
            if hasattr(self, "tab_processes") and self.tab_processes.winfo_exists():
                self.refresh_processes()
        except tk.TclError:
            return
        self.root.after(60000, self._proc_tick)