"""Переиспользуемые виджеты: LabeledEntry, SpinEntry, CalendarDialog, DateEntry."""

import datetime as dt
import tkinter as tk
from tkinter import ttk

from aquarium_app.config import (
    FONT_FAMILY,
    COLOR_BG,
    COLOR_CARD,
    COLOR_BORDER,
    COLOR_TEXT,
    COLOR_TEXT_MUTED,
    COLOR_ACCENT,
    COLOR_ACCENT_HOVER,
    COLOR_ACCENT_SOFT,
    COLOR_ALT_ROW,
)
from aquarium_app.logic.formatters import parse_float, today_str


# ---------------------------------------------------------------------------
# LabeledEntry
# ---------------------------------------------------------------------------

class LabeledEntry(ttk.Frame):
    """Строка «подпись + поле ввода» для форм."""

    def __init__(self, parent, label, width=28, default=""):
        super().__init__(parent)
        ttk.Label(self, text=label, width=22, anchor="w").pack(side="left", padx=(0, 6))
        self.var = tk.StringVar(value=str(default) if default is not None else "")
        self.entry = ttk.Entry(self, textvariable=self.var, width=width)
        self.entry.pack(side="left", fill="x", expand=True)

    def get(self):
        return self.var.get()

    def set(self, value):
        self.var.set(str(value) if value is not None else "")


# ---------------------------------------------------------------------------
# SpinEntry
# ---------------------------------------------------------------------------

class SpinEntry(ttk.Frame):
    """Поле ввода числа с кнопками +/− (spinner).

    Шаг, минимум и максимум настраиваются. Пустое значение разрешено,
    если allow_empty=True (по умолчанию) — удобно для параметров тестов.
    """

    def __init__(self, parent, width=8, step=0.1, default="", min_val=None,
                 max_val=None, allow_empty=True, font_family=None):
        super().__init__(parent)
        self.step = step
        self.min_val = min_val
        self.max_val = max_val
        self.allow_empty = allow_empty
        self.FF = font_family or FONT_FAMILY
        self.var = tk.StringVar(value=str(default) if default not in (None, "") else "")
        self.entry = ttk.Entry(self, textvariable=self.var, width=width, justify="center")
        self.entry.pack(side="left")
        # вертикальная пара кнопок
        btns = tk.Frame(self, bg=COLOR_BG)
        btns.pack(side="left", padx=(2, 0))
        b_plus = tk.Button(btns, text="+", width=2, command=lambda: self._bump(1),
                           font=(self.FF, 8, "bold"), relief="flat",
                           bg=COLOR_CARD, fg=COLOR_ACCENT, activebackground=COLOR_ALT_ROW,
                           activeforeground=COLOR_ACCENT, borderwidth=0, padx=0, pady=0)
        b_minus = tk.Button(btns, text="−", width=2, command=lambda: self._bump(-1),
                            font=(self.FF, 8, "bold"), relief="flat",
                            bg=COLOR_CARD, fg=COLOR_ACCENT, activebackground=COLOR_ALT_ROW,
                            activeforeground=COLOR_ACCENT, borderwidth=0, padx=0, pady=0)
        b_plus.pack(side="top", fill="x")
        b_minus.pack(side="top", fill="x")
        # колесо мыши
        self.entry.bind("<MouseWheel>", lambda e: self._bump(1 if e.delta > 0 else -1))
        # Enter — пробуем подставить шаг если поле пустое
        self.entry.bind("<Return>", lambda e: self._bump(1) if not self.var.get() else None)

    def _bump(self, sign):
        cur = parse_float(self.var.get(), None)
        if cur is None:
            if not self.allow_empty:
                cur = 0.0
            else:
                # если поле пустое — первый клик начинает со значения шага
                new = round(self.step, 4) if sign > 0 else 0.0
                self.var.set(self._fmt_num(new))
                return
        new = cur + sign * self.step
        if self.min_val is not None and new < self.min_val:
            new = self.min_val
        if self.max_val is not None and new > self.max_val:
            new = self.max_val
        self.var.set(self._fmt_num(new))

    @staticmethod
    def _fmt_num(v):
        if v == int(v):
            return str(int(v))
        s = f"{v:.4f}".rstrip("0").rstrip(".")
        return s

    def get(self):
        return self.var.get()

    def set(self, value):
        if value is None or value == "":
            self.var.set("")
        else:
            try:
                self.var.set(self._fmt_num(float(value)))
            except (TypeError, ValueError):
                self.var.set(str(value))


# ---------------------------------------------------------------------------
# CalendarDialog
# ---------------------------------------------------------------------------

class CalendarDialog(tk.Toplevel):
    """Простой календарь на чистом tkinter — без внешних зависимостей.

    Открывается модально, возвращает выбранную дату (dt.date) в .result
    или None, если пользователь закрыл без выбора.
    """

    MONTHS = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
              "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
    WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

    def __init__(self, parent, title="Выберите дату", initial_date=None,
                 font_family=None, min_date=None, max_date=None):
        super().__init__(parent)
        self.title(title)
        self.configure(bg=COLOR_BG)
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        self.FF = font_family or FONT_FAMILY
        self.result = None
        self.min_date = min_date
        self.max_date = max_date

        today = dt.date.today()
        initial = initial_date or today
        try:
            initial = dt.date.fromisoformat(initial.isoformat()) if hasattr(initial, "isoformat") else initial
        except Exception:
            initial = today

        self.view_year = initial.year
        self.view_month = initial.month
        self.selected = initial

        # шапка с переключателем месяца
        header = tk.Frame(self, bg=COLOR_BG)
        header.pack(fill="x", padx=12, pady=(12, 4))
        tk.Button(header, text="‹", width=3, font=(self.FF, 10, "bold"),
                  command=self._prev_month, relief="flat", bg=COLOR_CARD, fg=COLOR_TEXT,
                  activebackground=COLOR_ALT_ROW, borderwidth=0).pack(side="left")
        self.title_lbl = tk.Label(header, text="", font=(self.FF, 11, "bold"),
                                  bg=COLOR_BG, fg=COLOR_ACCENT, width=18)
        self.title_lbl.pack(side="left", expand=True, fill="x")
        tk.Button(header, text="›", width=3, font=(self.FF, 10, "bold"),
                  command=self._next_month, relief="flat", bg=COLOR_CARD, fg=COLOR_TEXT,
                  activebackground=COLOR_ALT_ROW, borderwidth=0).pack(side="left")

        # заголовки дней недели
        whdr = tk.Frame(self, bg=COLOR_BG)
        whdr.pack(fill="x", padx=12)
        for d in self.WEEKDAYS:
            tk.Label(whdr, text=d, width=4, font=(self.FF, 9, "bold"),
                     bg=COLOR_BG, fg=COLOR_TEXT_MUTED).pack(side="left", expand=True)

        # сетка дней
        self.grid = tk.Frame(self, bg=COLOR_BG)
        self.grid.pack(fill="x", padx=12, pady=(0, 10))

        # нижние кнопки
        btns = tk.Frame(self, bg=COLOR_BG)
        btns.pack(fill="x", padx=12, pady=(0, 12))
        tk.Button(btns, text="Сегодня", command=self._today, relief="flat",
                  bg=COLOR_CARD, fg=COLOR_TEXT, activebackground=COLOR_ALT_ROW,
                  borderwidth=0, padx=10, pady=4).pack(side="left")
        tk.Button(btns, text="Отмена", command=self._cancel, relief="flat",
                  bg=COLOR_CARD, fg=COLOR_TEXT, activebackground=COLOR_ALT_ROW,
                  borderwidth=0, padx=10, pady=4).pack(side="right", padx=(6, 0))
        tk.Button(btns, text="Выбрать", command=self._ok, relief="flat",
                  bg=COLOR_ACCENT, fg="#151515", activebackground=COLOR_ACCENT_HOVER,
                  borderwidth=0, padx=14, pady=4, font=(self.FF, 9, "bold")).pack(side="right")

        self.bind("<Escape>", lambda e: self._cancel())

        self._render_days()
        self.update_idletasks()
        x = parent.winfo_rootx() + 80
        y = parent.winfo_rooty() + 60
        self.geometry(f"+{x}+{y}")

    def _month_title(self):
        self.title_lbl.config(text=f"{self.MONTHS[self.view_month - 1]} {self.view_year}")

    def _render_days(self):
        for w in self.grid.winfo_children():
            w.destroy()
        self._month_title()
        first = dt.date(self.view_year, self.view_month, 1)
        offset = first.weekday()  # Mon=0
        if self.view_month == 12:
            next_first = dt.date(self.view_year + 1, 1, 1)
        else:
            next_first = dt.date(self.view_year, self.view_month + 1, 1)
        days_in_month = (next_first - first).days

        for i in range(offset):
            tk.Label(self.grid, text="", width=4, height=2,
                     bg=COLOR_BG).grid(row=0, column=i, padx=1, pady=1)

        today = dt.date.today()
        for d in range(1, days_in_month + 1):
            day_date = dt.date(self.view_year, self.view_month, d)
            col = (offset + d - 1) % 7
            row = (offset + d - 1) // 7
            is_today = (day_date == today)
            is_selected = (day_date == self.selected)
            disabled = ((self.min_date and day_date < self.min_date) or
                        (self.max_date and day_date > self.max_date))
            if is_selected:
                bg, fg = COLOR_ACCENT, "#151515"
            elif disabled:
                bg, fg = COLOR_BG, "#3a3d48"
            elif is_today:
                bg, fg = COLOR_ACCENT_SOFT, COLOR_ACCENT
            else:
                bg, fg = COLOR_CARD, COLOR_TEXT
            weight = "bold" if is_today else "normal"
            cell = tk.Label(self.grid, text=str(d), width=4, height=2,
                            bg=bg, fg=fg, font=(self.FF, 9, weight),
                            cursor="" if disabled else "hand2")
            cell.grid(row=row, column=col, padx=1, pady=1)
            if not disabled:
                cell.bind("<Button-1>", lambda e, dd=day_date: self._select_day(dd))
                cell.bind("<Double-Button-1>", lambda e, dd=day_date: (self._select_day(dd), self._ok()))

    def _select_day(self, d):
        self.selected = d
        self._render_days()

    def _prev_month(self):
        if self.view_month == 1:
            self.view_month, self.view_year = 12, self.view_year - 1
        else:
            self.view_month -= 1
        self._render_days()

    def _next_month(self):
        if self.view_month == 12:
            self.view_month, self.view_year = 1, self.view_year + 1
        else:
            self.view_month += 1
        self._render_days()

    def _today(self):
        t = dt.date.today()
        self.view_year, self.view_month = t.year, t.month
        self.selected = t
        self._render_days()

    def _ok(self):
        self.result = self.selected
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()


# ---------------------------------------------------------------------------
# DateEntry
# ---------------------------------------------------------------------------

class DateEntry(ttk.Frame):
    """Поле ввода даты с кнопкой открытия календаря.

    Текст можно вводить вручную (ДД.ММ.ГГГГ) или выбрать мышью.
    """

    def __init__(self, parent, font_family=None, width=12, default=None):
        super().__init__(parent)
        self.FF = font_family or FONT_FAMILY
        initial = default if default else today_str()
        self.var = tk.StringVar(value=initial)
        self.entry = ttk.Entry(self, textvariable=self.var, width=width)
        self.entry.pack(side="left")
        self.btn = tk.Button(self, text="📅", width=3, font=(self.FF, 10),
                             relief="flat", bg=COLOR_CARD, fg=COLOR_ACCENT,
                             activebackground=COLOR_ALT_ROW, borderwidth=0,
                             command=self._open_calendar, cursor="hand2")
        self.btn.pack(side="left", padx=(2, 0))

    def _open_calendar(self):
        cur = self.var.get().strip()
        try:
            d = dt.datetime.strptime(cur, "%d.%m.%Y").date()
        except Exception:
            d = dt.date.today()
        dlg = CalendarDialog(self, initial_date=d, font_family=self.FF)
        self.wait_window(dlg)
        if dlg.result:
            self.var.set(dlg.result.strftime("%d.%m.%Y"))

    def get(self):
        return self.var.get()

    def set(self, value):
        if not value:
            self.var.set("")
        elif isinstance(value, dt.date):
            self.var.set(value.strftime("%d.%m.%Y"))
        else:
            self.var.set(str(value))