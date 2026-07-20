"""Вкладка «Таймеры» — чистка фильтра и пользовательские напоминания."""
from __future__ import annotations

import datetime as dt
import tkinter as tk
from tkinter import ttk, messagebox

from aquarium_app.config import (
    COLOR_BG, COLOR_CARD, COLOR_ACCENT, COLOR_BORDER, COLOR_TEXT,
    COLOR_TEXT_MUTED, COLOR_ALT_ROW, COLOR_WARN_TEXT, COLOR_OK_TEXT,
    COLOR_TIMER_OK_BG, COLOR_TIMER_URGENT_BG, COLOR_TIMER_OVERDUE_BG,
    COLOR_TIMER_DONE_BG,
    COLOR_STATUS_WAITING, COLOR_STATUS_URGENT, COLOR_STATUS_OVERDUE,
    COLOR_STATUS_DONE, COLOR_STATUS_FIRED,
    FONT_FAMILY,
)
from aquarium_app.db import (
    get_aquarium, get_active_timers, get_latest_filter_clean,
    mark_timer_fired, delete_timer, add_timer,
)
from aquarium_app.logic.formatters import format_remaining, format_dt, now_iso, parse_float
from aquarium_app.gui.widgets import LabeledEntry, SpinEntry


class TimersTab:
    """Mixin-класс с методами для вкладки «Таймеры»."""

    # ------------------------------------------------------------------
    # Построение вкладки
    # ------------------------------------------------------------------

    def build_timers_tab(self):
        FF = self.FF
        parent = self.tab_timers

        # --- верхняя панель ---
        top = tk.Frame(parent, bg=COLOR_BG)
        top.pack(fill="x", padx=12, pady=(10, 4))

        ttk.Label(top, text="Аквариум:", background=COLOR_BG).pack(side="left")
        self.timers_aq_var = tk.StringVar()
        self.timers_aq_combo = ttk.Combobox(
            top, textvariable=self.timers_aq_var,
            state="readonly", width=30,
        )
        self.timers_aq_combo.pack(side="left", padx=(6, 0))
        self.timers_aq_combo.bind("<<ComboboxSelected>>",
                                   lambda e: self.refresh_timers())

        # --- карточка чистки фильтра ---
        self.filter_card = tk.Frame(parent, bg=COLOR_TIMER_OK_BG, bd=0,
                                    highlightbackground=COLOR_BORDER,
                                    highlightthickness=1)
        self.filter_card.pack(fill="x", padx=12, pady=6)

        self.filter_card_inner = tk.Frame(self.filter_card, bg=COLOR_TIMER_OK_BG)
        self.filter_card_inner.pack(fill="x", padx=12, pady=10)

        # --- заголовок секции пользовательских таймеров ---
        custom_hdr = tk.Frame(parent, bg=COLOR_BG)
        custom_hdr.pack(fill="x", padx=12, pady=(12, 4))

        tk.Label(custom_hdr, text="Напоминания", bg=COLOR_BG, fg=COLOR_TEXT,
                 font=(FF, 12, "bold")).pack(side="left")

        tk.Button(
            custom_hdr, text="+ Добавить", font=(FF, 9, "bold"),
            bg=COLOR_ACCENT, fg="#151515", relief="flat",
            padx=10, pady=3, cursor="hand2",
            command=self.add_custom_timer_dialog,
        ).pack(side="right")

        # --- контейнер пользовательских таймеров ---
        self.timers_scroll_container = tk.Frame(parent, bg=COLOR_BG)
        self.timers_scroll_container.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    # ------------------------------------------------------------------
    # Аквариум
    # ------------------------------------------------------------------

    def refresh_timers_aq_combo(self):
        aqs = self.conn.execute("SELECT * FROM aquariums ORDER BY id").fetchall()
        items = [f"{r['id']} — {r['name']}" for r in aqs]
        self.timers_aq_combo["values"] = items
        if items and not self.timers_aq_var.get():
            self.timers_aq_combo.current(0)
            self.refresh_timers()

    def _current_timer_aq_id(self):
        s = self.timers_aq_var.get().strip()
        if not s:
            return None
        try:
            return int(s.split(" — ")[0])
        except (ValueError, IndexError):
            return None

    # ------------------------------------------------------------------
    # Обновление
    # ------------------------------------------------------------------

    def refresh_timers(self):
        aq_id = self._current_timer_aq_id()
        if not aq_id:
            return

        # --- карточка фильтра ---
        latest = get_latest_filter_clean(self.conn, aq_id)
        self._update_filter_card(latest)

        # --- пользовательские таймеры ---
        rows = get_active_timers(self.conn, aq_id)
        custom_rows = [r for r in rows if r["kind"] != "filter_clean"]
        self._update_timer_cards(custom_rows)

    # ------------------------------------------------------------------
    # Карточка чистки фильтра
    # ------------------------------------------------------------------

    def _update_filter_card(self, latest):
        FF = self.FF
        inner = self.filter_card_inner

        for w in inner.winfo_children():
            w.destroy()

        now = dt.datetime.now()
        is_fired = latest is not None and latest["fired"] == 1

        if latest is None:
            self._set_filter_card_colors(COLOR_CARD)
            tk.Label(inner, text="Чистка фильтра", bg=COLOR_CARD,
                     fg=COLOR_TEXT, font=(FF, 11, "bold")).pack(anchor="w")
            tk.Label(inner, text="Нет записей. Нажмите кнопку ниже, чтобы отметить.",
                     bg=COLOR_CARD, fg=COLOR_TEXT_MUTED, font=(FF, 9)).pack(anchor="w",
                                                                              pady=(2, 4))
        elif is_fired:
            self._set_filter_card_colors(COLOR_TIMER_DONE_BG)
            status_text = "Выполнено"
            status_color = COLOR_STATUS_DONE

            hdr = tk.Frame(inner, bg=COLOR_TIMER_DONE_BG)
            hdr.pack(fill="x")
            tk.Label(hdr, text="Чистка фильтра", bg=COLOR_TIMER_DONE_BG,
                     fg=COLOR_TEXT, font=(FF, 11, "bold")).pack(side="left")
            tk.Label(hdr, text=f"  {status_text}", bg=COLOR_TIMER_DONE_BG,
                     fg=status_color, font=(FF, 9, "bold")).pack(side="left", padx=(8, 0))

            due_str = format_dt(latest["due_at"])
            tk.Label(inner, text=f"Срок: {due_str}", bg=COLOR_TIMER_DONE_BG,
                     fg=COLOR_TEXT_MUTED, font=(FF, 9)).pack(anchor="w", pady=(2, 0))

            interval = latest.get("interval_days")
            if interval:
                tk.Label(inner, text=f"Интервал: {interval:g} дн.",
                         bg=COLOR_TIMER_DONE_BG, fg=COLOR_TEXT_MUTED,
                         font=(FF, 9)).pack(anchor="w")
        else:
            # активный таймер
            try:
                due_dt = dt.datetime.fromisoformat(latest["due_at"])
            except Exception:
                due_dt = now

            delta = (due_dt - now).total_seconds()
            interval = latest.get("interval_days") or 14
            started = latest.get("started_at")
            try:
                started_dt = dt.datetime.fromisoformat(started) if started else now
            except Exception:
                started_dt = now

            elapsed_days = (now - started_dt).total_seconds() / 86400
            progress = min(elapsed_days / interval, 1.0) if interval > 0 else 0

            if delta <= 0:
                bg = COLOR_TIMER_OVERDUE_BG
                status_text = "ПРОСРОЧЕНО"
                status_color = COLOR_STATUS_OVERDUE
            elif delta < 86400:
                bg = COLOR_TIMER_URGENT_BG
                status_text = "СКОРО"
                status_color = COLOR_STATUS_URGENT
            else:
                bg = COLOR_TIMER_OK_BG
                status_text = "ОЖИДАНИЕ"
                status_color = COLOR_STATUS_WAITING

            self._set_filter_card_colors(bg)

            hdr = tk.Frame(inner, bg=bg)
            hdr.pack(fill="x")
            tk.Label(hdr, text="Чистка фильтра", bg=bg,
                     fg=COLOR_TEXT, font=(FF, 11, "bold")).pack(side="left")
            tk.Label(hdr, text=f"  {status_text}", bg=bg,
                     fg=status_color, font=(FF, 9, "bold")).pack(side="left", padx=(8, 0))

            countdown = format_remaining(latest["due_at"])
            tk.Label(inner, text=countdown, bg=bg, fg=status_color,
                     font=(FF, 12, "bold")).pack(anchor="w", pady=(4, 0))

            # прогресс-бар
            bar_canvas = tk.Canvas(inner, bg=bg, height=12, highlightthickness=0)
            bar_canvas.pack(fill="x", pady=(6, 0))
            self._draw_filter_progress(progress, bg, status_color)

            # строка с кнопками
            btn_row = tk.Frame(inner, bg=bg)
            btn_row.pack(fill="x", pady=(8, 0))

            tk.Button(
                btn_row, text="Отметить чистку сейчас", font=(FF, 9, "bold"),
                bg=COLOR_ACCENT, fg="#151515", relief="flat",
                padx=12, pady=4, cursor="hand2",
                command=self.mark_filter_clean,
            ).pack(side="left")

            tk.Label(btn_row, text=f"Интервал:", bg=bg,
                     fg=COLOR_TEXT_MUTED, font=(FF, 9)).pack(side="left", padx=(16, 4))
            self.filter_interval_var = tk.StringVar(value=f"{interval:g}")
            interval_entry = ttk.Entry(btn_row, textvariable=self.filter_interval_var,
                                        width=5)
            interval_entry.pack(side="left")
            tk.Label(btn_row, text="дн.", bg=bg,
                     fg=COLOR_TEXT_MUTED, font=(FF, 9)).pack(side="left", padx=(2, 0))
            tk.Button(
                btn_row, text="OK", font=(FF, 8),
                bg=COLOR_CARD, fg=COLOR_TEXT, relief="flat",
                padx=6, pady=2, cursor="hand2",
                command=self.set_filter_interval,
            ).pack(side="left", padx=(4, 0))

    def _set_filter_card_colors(self, bg):
        """Меняет фон карточки фильтра и всех дочерних виджетов."""
        self.filter_card.config(bg=bg, highlightbackground=COLOR_BORDER)
        self._recursive_set_bg(self.filter_card_inner, bg)

    def _recursive_set_bg(self, widget, bg):
        try:
            wtype = widget.winfo_class()
            if wtype in ("Frame", "Label", "Canvas", "Button"):
                widget.configure(bg=bg)
            elif wtype == "TLabel":
                widget.configure(background=bg)
        except tk.TclError:
            return
        for child in widget.winfo_children():
            self._recursive_set_bg(child, bg)

    def _draw_filter_progress(self, progress, bg, bar_color):
        """Рисует горизонтальный прогресс-бар чистки фильтра."""
        inner = self.filter_card_inner
        # найдём canvas для прогресса (последний child)
        for w in inner.winfo_children():
            if isinstance(w, tk.Canvas) and w.winfo_height() <= 16:
                c = w
                break
        else:
            return
        if not c.winfo_exists():
            return
        c.delete("all")
        c.update_idletasks()
        w = max(c.winfo_width(), 100)
        h = max(c.winfo_height(), 10)
        pad = 2
        # фон трека
        c.create_rectangle(pad, pad, w - pad, h - pad, fill="#2c2f3a", outline="")
        # заполнение
        bar_w = int((w - 2 * pad) * progress)
        if bar_w > 0:
            c.create_rectangle(pad, pad, pad + bar_w, h - pad,
                               fill=bar_color, outline="")

    # ------------------------------------------------------------------
    # Действия с фильтром
    # ------------------------------------------------------------------

    def mark_filter_clean(self):
        aq_id = self._current_timer_aq_id()
        if not aq_id:
            return

        now = now_iso()

        # берём интервал из поля или из последнего таймера
        interval = 14.0
        try:
            v = parse_float(self.filter_interval_var.get(), None)
            if v and v > 0:
                interval = v
        except Exception:
            pass

        latest = get_latest_filter_clean(self.conn, aq_id)
        if latest:
            # обновим интервал, если он изменился
            old_interval = latest.get("interval_days") or 14
            if hasattr(self, "filter_interval_var"):
                new_iv = parse_float(self.filter_interval_var.get(), None)
                if new_iv and new_iv > 0:
                    old_interval = new_iv

        due_dt = dt.datetime.now() + dt.timedelta(days=interval)
        due_str = due_dt.strftime("%Y-%m-%d %H:%M:%S")

        add_timer(self.conn, aq_id, "filter_clean", "Чистка фильтра",
                  now, due_str, interval_days=interval)
        self.refresh_timers()

    def set_filter_interval(self):
        """Обновляет интервал для последнего активного таймера чистки."""
        aq_id = self._current_timer_aq_id()
        if not aq_id:
            return
        latest = get_latest_filter_clean(self.conn, aq_id)
        if not latest or latest["fired"]:
            messagebox.showinfo("Информация",
                                "Нет активного таймера чистки фильтра.")
            return
        new_interval = parse_float(self.filter_interval_var.get(), None)
        if not new_interval or new_interval <= 0:
            messagebox.showwarning("Ошибка", "Укажите корректный интервал (дн.).")
            return

        # пересчитаем due_at от started_at
        try:
            started = dt.datetime.fromisoformat(latest["started_at"])
        except Exception:
            started = dt.datetime.now()
        new_due = (started + dt.timedelta(days=new_interval)).strftime("%Y-%m-%d %H:%M:%S")

        self.conn.execute(
            "UPDATE timers SET interval_days=?, due_at=? WHERE id=?",
            (new_interval, new_due, latest["id"]),
        )
        self.conn.commit()
        self.refresh_timers()

    # ------------------------------------------------------------------
    # Пользовательские таймеры (карточки)
    # ------------------------------------------------------------------

    def _update_timer_cards(self, rows):
        for w in self.timers_scroll_container.winfo_children():
            w.destroy()

        if not rows:
            tk.Label(self.timers_scroll_container,
                     text="Нет активных напоминаний.",
                     bg=COLOR_BG, fg=COLOR_TEXT_MUTED, font=(self.FF, 9, "italic"),
                     anchor="w").pack(fill="x", pady=8)
            return

        for r in rows:
            self._build_timer_card(self.timers_scroll_container, r)

    def _build_timer_card(self, container, r):
        FF = self.FF
        timer_id = r["id"]
        now = dt.datetime.now()
        is_fired = r["fired"] == 1

        try:
            due_dt = dt.datetime.fromisoformat(r["due_at"])
        except Exception:
            due_dt = now

        delta = (due_dt - now).total_seconds()

        # определяем статус и цвета
        if is_fired:
            bg = COLOR_TIMER_DONE_BG
            status_text = "ВЫПОЛНЕНО"
            status_color = COLOR_STATUS_FIRED
            progress = 1.0
            bar_color = COLOR_STATUS_DONE
        elif delta <= 0:
            bg = COLOR_TIMER_OVERDUE_BG
            status_text = "ПРОСРОЧЕНО"
            status_color = COLOR_STATUS_OVERDUE
            progress = 1.0
            bar_color = COLOR_STATUS_OVERDUE
        elif delta < 86400:
            bg = COLOR_TIMER_URGENT_BG
            status_text = "СКОРО"
            status_color = COLOR_STATUS_URGENT
            # прогресс — приближаем к 1.0
            interval = r.get("interval_days")
            if interval and interval > 0:
                try:
                    started_dt = dt.datetime.fromisoformat(r["started_at"])
                    elapsed = (now - started_dt).total_seconds() / 86400
                    progress = min(elapsed / interval, 1.0)
                except Exception:
                    progress = 0.95
            else:
                progress = 0.95
            bar_color = COLOR_STATUS_URGENT
        else:
            bg = COLOR_TIMER_OK_BG
            status_text = "ОЖИДАНИЕ"
            status_color = COLOR_STATUS_WAITING
            interval = r.get("interval_days")
            if interval and interval > 0:
                try:
                    started_dt = dt.datetime.fromisoformat(r["started_at"])
                    elapsed = (now - started_dt).total_seconds() / 86400
                    progress = min(elapsed / interval, 1.0)
                except Exception:
                    progress = 0.0
            else:
                progress = 0.0
            bar_color = COLOR_STATUS_WAITING

        card = tk.Frame(container, bg=bg, bd=0,
                        highlightbackground=COLOR_BORDER, highlightthickness=1)
        card.pack(fill="x", pady=(0, 6))

        inner = tk.Frame(card, bg=bg)
        inner.pack(fill="x", padx=10, pady=8)

        # заголовок + бейдж
        hdr = tk.Frame(inner, bg=bg)
        hdr.pack(fill="x")

        tk.Label(hdr, text=r["title"] or "Напоминание", bg=bg,
                 fg=COLOR_TEXT, font=(FF, 10, "bold")).pack(side="left")
        tk.Label(hdr, text=f"  {status_text}", bg=bg,
                 fg=status_color, font=(FF, 8, "bold")).pack(side="left", padx=(8, 0))

        # обратный отсчёт
        countdown = format_remaining(r["due_at"])
        tk.Label(inner, text=countdown, bg=bg, fg=status_color,
                 font=(FF, 11, "bold")).pack(anchor="w", pady=(4, 0))

        # примечание
        note = r.get("note") or ""
        if note:
            tk.Label(inner, text=note, bg=bg, fg=COLOR_TEXT_MUTED,
                     font=(FF, 9), wraplength=400, anchor="w",
                     justify="left").pack(anchor="w", pady=(2, 0))

        # прогресс-бар
        bar_canvas = tk.Canvas(inner, bg=bg, height=8, highlightthickness=0)
        bar_canvas.pack(fill="x", pady=(6, 0))
        self._draw_timer_progress(bar_canvas, progress, bg, bar_color)

        # кнопки
        btn_row = tk.Frame(inner, bg=bg)
        btn_row.pack(fill="x", pady=(6, 0))

        if not is_fired:
            tk.Button(
                btn_row, text="Отметить выполненным", font=(FF, 9),
                bg=COLOR_ACCENT, fg="#151515", relief="flat",
                padx=10, pady=3, cursor="hand2",
                command=lambda tid=timer_id: self._mark_done_from_card(tid),
            ).pack(side="left")

        tk.Button(
            btn_row, text="Удалить", font=(FF, 9),
            bg=COLOR_CARD, fg=COLOR_WARN_TEXT, relief="flat",
            activebackground=COLOR_ALT_ROW,
            padx=10, pady=3, cursor="hand2",
            command=lambda tid=timer_id: self._delete_from_card(tid),
        ).pack(side="right")

    def _draw_timer_progress(self, canvas, progress, bg, bar_color):
        if not canvas.winfo_exists():
            return
        canvas.delete("all")
        canvas.update_idletasks()
        w = max(canvas.winfo_width(), 100)
        h = max(canvas.winfo_height(), 6)
        pad = 1
        canvas.create_rectangle(pad, pad, w - pad, h - pad, fill="#2c2f3a", outline="")
        bar_w = int((w - 2 * pad) * progress)
        if bar_w > 0:
            canvas.create_rectangle(pad, pad, pad + bar_w, h - pad,
                                    fill=bar_color, outline="")

    def _mark_done_from_card(self, timer_id):
        if messagebox.askyesno("Выполнено", "Отметить напоминание как выполненное?"):
            mark_timer_fired(self.conn, timer_id)
            self.refresh_timers()

    def _delete_from_card(self, timer_id):
        if messagebox.askyesno("Удаление", "Удалить это напоминание?"):
            delete_timer(self.conn, timer_id)
            self.refresh_timers()

    # ------------------------------------------------------------------
    # Диалог добавления таймера
    # ------------------------------------------------------------------

    def add_custom_timer_dialog(self):
        aq_id = self._current_timer_aq_id()
        if not aq_id:
            messagebox.showwarning("Внимание", "Выберите аквариум.")
            return

        FF = self.FF
        dlg = tk.Toplevel(self.root)
        dlg.title("Новое напоминание")
        dlg.configure(bg=COLOR_BG)
        dlg.transient(self.root)
        dlg.grab_set()
        dlg.resizable(False, False)

        inner = tk.Frame(dlg, bg=COLOR_CARD, padx=16, pady=12)
        inner.pack(padx=16, pady=16)

        # название
        tk.Label(inner, text="Название:", bg=COLOR_CARD, fg=COLOR_TEXT,
                 font=(FF, 10), anchor="w", width=20).grid(row=0, column=0,
                                                             sticky="w", pady=4)
        title_var = tk.StringVar()
        ttk.Entry(inner, textvariable=title_var, width=30).grid(
            row=0, column=1, sticky="w", pady=4)

        # тип срока: относительный или точный
        mode_var = tk.StringVar(value="relative")
        mode_frame = tk.Frame(inner, bg=COLOR_CARD)
        mode_frame.grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 4))
        tk.Radiobutton(mode_frame, text="Через:", variable=mode_var,
                       value="relative", bg=COLOR_CARD, fg=COLOR_TEXT,
                       selectcolor=COLOR_BG, activebackground=COLOR_CARD,
                       activeforeground=COLOR_TEXT, font=(FF, 9),
                       command=lambda: self._timer_mode_toggle(
                           dlg, mode_var, relative_frame, exact_frame)).pack(side="left")
        tk.Radiobutton(mode_frame, text="Точная дата:", variable=mode_var,
                       value="exact", bg=COLOR_CARD, fg=COLOR_TEXT,
                       selectcolor=COLOR_BG, activebackground=COLOR_CARD,
                       activeforeground=COLOR_TEXT, font=(FF, 9),
                       command=lambda: self._timer_mode_toggle(
                           dlg, mode_var, relative_frame, exact_frame)).pack(
            side="left", padx=(16, 0))

        # относительный: количество + единица
        relative_frame = tk.Frame(inner, bg=COLOR_CARD)
        relative_frame.grid(row=2, column=0, columnspan=2, sticky="w", pady=4)

        amount_var = tk.StringVar(value="7")
        ttk.Entry(relative_frame, textvariable=amount_var, width=6).pack(side="left")
        unit_var = tk.StringVar(value="дн")
        unit_combo = ttk.Combobox(relative_frame, textvariable=unit_var,
                                   values=["мин", "ч", "дн", "нед"],
                                   state="readonly", width=6)
        unit_combo.pack(side="left", padx=(4, 0))

        # точный: дата + время
        exact_frame = tk.Frame(inner, bg=COLOR_CARD)
        exact_frame.grid(row=3, column=0, columnspan=2, sticky="w", pady=4)

        date_var = tk.StringVar(value=dt.date.today().strftime("%d.%m.%Y"))
        ttk.Entry(exact_frame, textvariable=date_var, width=12).pack(side="left")
        tk.Label(exact_frame, text=" ", bg=COLOR_CARD).pack(side="left")
        time_var = tk.StringVar(value=dt.datetime.now().strftime("%H:%M"))
        ttk.Entry(exact_frame, textvariable=time_var, width=6).pack(side="left")

        # заметка
        tk.Label(inner, text="Заметка:", bg=COLOR_CARD, fg=COLOR_TEXT,
                 font=(FF, 10), anchor="w", width=20).grid(row=4, column=0,
                                                             sticky="w", pady=4)
        note_var = tk.StringVar()
        ttk.Entry(inner, textvariable=note_var, width=30).grid(
            row=4, column=1, sticky="w", pady=4)

        # кнопки
        btn_row = tk.Frame(inner, bg=COLOR_CARD)
        btn_row.grid(row=5, column=0, columnspan=2, pady=(12, 0))

        def _save():
            title = title_var.get().strip()
            if not title:
                messagebox.showwarning("Ошибка", "Укажите название.", parent=dlg)
                return

            now = dt.datetime.now()
            note = note_var.get().strip()

            if mode_var.get() == "relative":
                amount = parse_float(amount_var.get(), None)
                if not amount or amount <= 0:
                    messagebox.showwarning("Ошибка", "Укажите количество.",
                                            parent=dlg)
                    return
                unit = unit_var.get()
                if unit == "мин":
                    due_dt = now + dt.timedelta(minutes=amount)
                    interval_days = amount / 1440
                elif unit == "ч":
                    due_dt = now + dt.timedelta(hours=amount)
                    interval_days = amount / 24
                elif unit == "нед":
                    due_dt = now + dt.timedelta(weeks=amount)
                    interval_days = amount * 7
                else:
                    due_dt = now + dt.timedelta(days=amount)
                    interval_days = amount
            else:
                # точная дата
                date_str = date_var.get().strip()
                time_str = time_var.get().strip()
                try:
                    due_dt = dt.datetime.strptime(f"{date_str} {time_str}",
                                                   "%d.%m.%Y %H:%M")
                except ValueError:
                    messagebox.showwarning("Ошибка", "Некорректная дата/время.",
                                            parent=dlg)
                    return
                interval_days = max((due_dt - now).total_seconds() / 86400, 0.01)

            if due_dt <= now:
                messagebox.showwarning("Ошибка",
                                        "Срок должен быть в будущем.", parent=dlg)
                return

            add_timer(
                self.conn, aq_id, "custom", title,
                now.strftime("%Y-%m-%d %H:%M:%S"),
                due_dt.strftime("%Y-%m-%d %H:%M:%S"),
                interval_days=round(interval_days, 2),
                note=note,
            )
            dlg.destroy()
            self.refresh_timers()

        tk.Button(btn_row, text="Создать", font=(FF, 10, "bold"),
                  bg=COLOR_ACCENT, fg="#151515", relief="flat",
                  padx=16, pady=4, command=_save).pack(side="left")
        tk.Button(btn_row, text="Отмена", font=(FF, 10),
                  bg=COLOR_CARD, fg=COLOR_TEXT, relief="flat",
                  padx=12, pady=4, command=dlg.destroy).pack(side="right")

        dlg.bind("<Escape>", lambda e: dlg.destroy())
        dlg.update_idletasks()
        x = self.winfo_rootx() + 120
        y = self.winfo_rooty() + 80
        dlg.geometry(f"+{x}+{y}")

        # начальное состояние: показываем относительный, скрываем точный
        exact_frame.grid_remove()
        self._timer_relative_frame = relative_frame
        self._timer_exact_frame = exact_frame

        self.wait_window(dlg)

    def _timer_mode_toggle(self, dlg, mode_var, relative_frame, exact_frame):
        if mode_var.get() == "relative":
            relative_frame.grid()
            exact_frame.grid_remove()
        else:
            relative_frame.grid_remove()
            exact_frame.grid()

    # ------------------------------------------------------------------
    # Периодическая проверка таймеров
    # ------------------------------------------------------------------

    def _tick_timers(self):
        """Проверяет просроченные таймеры каждые 60 секунд."""
        self._check_due_timers()
        self.after(60000, self._tick_timers)

    def _check_due_timers(self):
        """Показывает уведомления о просроченных невыполненных таймерах."""
        try:
            from aquarium_app.db import get_due_timers
            due = get_due_timers(self.conn)
        except Exception:
            return

        if not due:
            self._update_timer_badge(0)
            return

        count = len(due)
        self._update_timer_badge(count)

        # показываем одно уведомление
        t = due[0]
        aq_name = t.get("aquarium_name") or "Аквариум"
        msg = (
            f"{aq_name}\n"
            f"«{t['title']}» — просрочено!\n"
            f"{format_remaining(t['due_at'])}"
        )
        try:
            messagebox.showwarning("⏰ Напоминание", msg)
        except Exception:
            pass

    def _update_timer_badge(self, count):
        """Обновляет текст кнопки навигации по таймерам."""
        if hasattr(self, "nav_btn_timers"):
            try:
                base = "Таймеры"
                text = f"{base} ({count})" if count > 0 else base
                self.nav_btn_timers.config(text=text)
            except tk.TclError:
                pass