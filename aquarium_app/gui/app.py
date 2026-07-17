"""Главный класс приложения АкваУчёт."""
from __future__ import annotations

import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import shutil
import subprocess

from aquarium_app.config import (
    COLOR_BG, COLOR_SIDEBAR, COLOR_SIDEBAR_HOVER, COLOR_SIDEBAR_ACTIVE,
    COLOR_SIDEBAR_TEXT, COLOR_SIDEBAR_TEXT_ACTIVE, COLOR_ACCENT, COLOR_ACCENT_SOFT,
    COLOR_BORDER, COLOR_TEXT, COLOR_TEXT_MUTED, COLOR_HEADER_TEXT,
    RESOURCES_DIR, FONT_FAMILY,
)
from aquarium_app.db import (
    get_connection, init_db,
    get_aquariums, get_aquarium, get_fertilizers,
    get_due_timers,
)
from aquarium_app.logic.formatters import today_str, from_iso, format_dt
from aquarium_app.gui.theme import setup_style
from aquarium_app.gui.widgets import DateEntry, SpinEntry, LabeledEntry

# Импортируем все миксины вкладок
from aquarium_app.gui.tabs.dashboard import DashboardTab
from aquarium_app.gui.tabs.journal import JournalTab
from aquarium_app.gui.tabs.aquariums import AquariumsTab
from aquarium_app.gui.tabs.fertilizers import FertilizersTab
from aquarium_app.gui.tabs.dosing import DosingTab
from aquarium_app.gui.tabs.readings import ReadingsTab
from aquarium_app.gui.tabs.timers import TimersTab
from aquarium_app.gui.tabs.processes import ProcessesTab


class App(
    tk.Tk,
    DashboardTab,
    JournalTab,
    AquariumsTab,
    FertilizersTab,
    DosingTab,
    ReadingsTab,
    TimersTab,
    ProcessesTab,
):
    """Главное окно приложения."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Аквариум — Учёт удобрений")
        self.geometry("1280x760")
        self.minsize(1000, 600)
        self.configure(bg=COLOR_BG)

        self._set_app_icon()

        self.conn = get_connection()
        init_db(self.conn)

        self.FF = setup_style(self, FONT_FAMILY)

        self._build_menu()

        # ---- каркас: сайдбар + контент ----
        body = tk.Frame(self, bg=COLOR_BG)
        body.pack(fill="both", expand=True)

        self.sidebar = tk.Frame(body, bg=COLOR_SIDEBAR, width=230)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        self.content = tk.Frame(body, bg=COLOR_BG)
        self.content.pack(side="left", fill="both", expand=True)

        # Логотип
        logo = tk.Frame(self.sidebar, bg=COLOR_SIDEBAR, height=80)
        logo.pack(fill="x")
        logo.pack_propagate(False)
        logo_inner = tk.Frame(logo, bg=COLOR_SIDEBAR)
        logo_inner.pack(side="left", padx=16, pady=16)
        icon_loaded = False
        for icon_path in [
            os.path.join(RESOURCES_DIR, "icon_sidebar_large.png"),
            os.path.join(RESOURCES_DIR, "icon_sidebar.png"),
            os.path.join(RESOURCES_DIR, "icon.png"),
        ]:
            if os.path.exists(icon_path):
                try:
                    photo = tk.PhotoImage(file=icon_path)
                    ratio = photo.width() // 48
                    if ratio > 1:
                        photo = photo.subsample(ratio)
                    self._logo_icon = photo
                    tk.Label(logo_inner, image=self._logo_icon, bg=COLOR_SIDEBAR).pack(
                        side="left", padx=(0, 14))
                    icon_loaded = True
                    break
                except tk.TclError:
                    pass
        if not icon_loaded:
            bar = tk.Frame(logo_inner, bg=COLOR_ACCENT, width=4, height=32)
            bar.pack(side="left", padx=(0, 14))
        tk.Label(logo_inner, text="АкваУчёт", bg=COLOR_SIDEBAR, fg="#ffffff",
                 font=(self.FF, 16, "bold")).pack(side="left")

        # Фреймы вкладок
        self.tab_dashboard = tk.Frame(self.content, bg=COLOR_BG)
        self.tab_journal = tk.Frame(self.content, bg=COLOR_BG)
        self.tab_aquariums = tk.Frame(self.content, bg=COLOR_BG)
        self.tab_ferts = tk.Frame(self.content, bg=COLOR_BG)
        self.tab_dosing = tk.Frame(self.content, bg=COLOR_BG)
        self.tab_readings = tk.Frame(self.content, bg=COLOR_BG)
        self.tab_timers = tk.Frame(self.content, bg=COLOR_BG)
        self.tab_processes = tk.Frame(self.content, bg=COLOR_BG)
        for f in (self.tab_dashboard, self.tab_journal, self.tab_aquariums,
                  self.tab_ferts, self.tab_dosing, self.tab_readings, self.tab_timers,
                  self.tab_processes):
            f.place(relx=0, rely=0, relwidth=1, relheight=1)

        # Строим все вкладки
        self.build_dashboard_tab()
        self.build_journal_tab()
        self.build_aquariums_tab()
        self.build_ferts_tab()
        self.build_dosing_tab()
        self.build_readings_tab()
        self.build_timers_tab()
        self.build_processes_tab()

        # Навигация
        self._nav_items = [
            ("📊", "Сводка", self.tab_dashboard),
            ("📋", "Журнал", self.tab_journal),
            ("⚙", "Аквариумы", self.tab_aquariums),
            ("🌿", "Удобрения", self.tab_ferts),
            ("💧", "Дозирование", self.tab_dosing),
            ("🧪", "Показания", self.tab_readings),
            ("⏰", "Таймеры", self.tab_timers),
            ("🔁", "Процессы", self.tab_processes),
        ]
        self._nav_buttons: dict = {}
        nav_wrap = tk.Frame(self.sidebar, bg=COLOR_SIDEBAR)
        nav_wrap.pack(fill="x", pady=(10, 0))
        for icon, label, frame in self._nav_items:
            row = tk.Frame(nav_wrap, bg=COLOR_SIDEBAR)
            row.pack(fill="x")
            indicator = tk.Frame(row, bg=COLOR_SIDEBAR, width=4)
            indicator.pack(side="left", fill="y")
            btn = tk.Label(row, text=f"   {icon}   {label}", anchor="w",
                            bg=COLOR_SIDEBAR, fg=COLOR_SIDEBAR_TEXT,
                            font=(self.FF, 11), padx=2, pady=13, cursor="hand2")
            btn.pack(side="left", fill="both", expand=True)
            for widget in (row, indicator, btn):
                widget.bind("<Button-1>", lambda e, f=frame: self.switch_tab(f))
                widget.bind("<Enter>", lambda e, f=frame: self._nav_hover(f, True))
                widget.bind("<Leave>", lambda e, f=frame: self._nav_hover(f, False))
            self._nav_buttons[frame] = (row, indicator, btn)

        self._active_tab = None
        self.switch_tab(self.tab_dashboard)
        self.refresh_all()

        # Проверка таймеров
        self.after(2000, self._check_due_timers)
        self.after(60000, self._tick_timers)

    # ------------------------------------------------------------------
    # Навигация
    # ------------------------------------------------------------------

    def switch_tab(self, frame: tk.Frame) -> None:
        for f, (row, indicator, btn) in self._nav_buttons.items():
            active = (f is frame)
            bg = COLOR_ACCENT_SOFT if active else COLOR_SIDEBAR
            fg = COLOR_ACCENT if active else COLOR_SIDEBAR_TEXT
            row.configure(bg=bg)
            indicator.configure(bg=COLOR_ACCENT if active else COLOR_SIDEBAR)
            btn.configure(bg=bg, fg=fg, font=(self.FF, 11, "bold" if active else "normal"))
        self._active_tab = frame
        frame.tkraise()
        self.refresh_all()

    def _nav_hover(self, frame: tk.Frame, entering: bool) -> None:
        if frame is self._active_tab:
            return
        row, indicator, btn = self._nav_buttons[frame]
        bg = COLOR_SIDEBAR_HOVER if entering else COLOR_SIDEBAR
        fg = COLOR_SIDEBAR_TEXT_ACTIVE if entering else COLOR_SIDEBAR_TEXT
        row.configure(bg=bg)
        indicator.configure(bg=bg)
        btn.configure(bg=bg, fg=fg)

    def switch_to_tab(self, frame: tk.Frame) -> None:
        """Переключается на указанную вкладку (для вызова из других вкладок)."""
        self.switch_tab(frame)

    # ------------------------------------------------------------------
    # Общие утилиты
    # ------------------------------------------------------------------

    def aquarium_choices(self) -> tuple:
        """Возвращает (rows, labels) для выпадающих списков аквариумов."""
        rows = get_aquariums(self.conn)
        return rows, [f'{r["id"]} — {r["name"]}' for r in rows]

    @staticmethod
    def _fmt(v) -> str:
        if v is None:
            return ""
        return f"{v:g}" if v else "0"

    @staticmethod
    def _fmt_axis(val: float) -> str:
        if val == 0:
            return "0"
        av = abs(val)
        if av < 0.01:
            return f"{val:.3f}"
        elif av < 1:
            return f"{val:.2f}"
        return f"{val:.1f}"

    def refresh_all(self) -> None:
        """Обновляет все вкладки."""
        self.refresh_dashboard()
        self.refresh_aquariums()
        self.refresh_ferts()
        self.refresh_dosing_aq_combo()
        self.refresh_readings_aq_combo()
        self.refresh_timers_aq_combo()
        self.refresh_timers()
        self.refresh_journal_aq_combo()
        self.refresh_journal()
        self.refresh_processes_aq_combo()
        self.refresh_processes()

    def _make_scrollable_area(self, parent, bg=None):
        """Создаёт прокручиваемую область с auto-hide скроллбаром."""
        if bg is None:
            bg = COLOR_BG
        canvas = tk.Canvas(parent, bg=bg, highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        inner = tk.Frame(canvas, bg=bg)
        win_id = canvas.create_window((0, 0), anchor="nw", window=inner)
        vsb = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)

        def on_scroll(first, last):
            vsb.set(first, last)
            try:
                f = float(first)
                l = float(last)
                if f <= 0.0 and l >= 1.0:
                    if vsb.winfo_ismapped():
                        vsb.place_forget()
                else:
                    if not vsb.winfo_ismapped():
                        vsb.place(relx=1.0, rely=0.0, relheight=1.0, anchor="ne")
            except (ValueError, tk.TclError):
                pass

        canvas.configure(yscrollcommand=on_scroll)
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfig(win_id, width=e.width))
        self._enable_mousewheel_scroll(canvas)
        return canvas, inner, win_id

    def _enable_mousewheel_scroll(self, canvas) -> None:
        """Включает прокрутку колесом мыши для canvas."""

        def _content_overflows():
            if not canvas.winfo_exists():
                return False
            bbox = canvas.bbox("all")
            if not bbox:
                return False
            return (bbox[3] - bbox[1]) > canvas.winfo_height() > 1

        def _on_wheel_windows(event):
            if canvas.winfo_exists() and _content_overflows():
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _on_wheel_linux_up(event):
            if canvas.winfo_exists() and _content_overflows():
                canvas.yview_scroll(-1, "units")

        def _on_wheel_linux_down(event):
            if canvas.winfo_exists() and _content_overflows():
                canvas.yview_scroll(1, "units")

        def _bind(_event=None):
            canvas.bind_all("<MouseWheel>", _on_wheel_windows)
            canvas.bind_all("<Button-4>", _on_wheel_linux_up)
            canvas.bind_all("<Button-5>", _on_wheel_linux_down)

        def _unbind(_event=None):
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind_all("<Button-4>")
            canvas.unbind_all("<Button-5>")

        canvas.bind("<Enter>", _bind)
        canvas.bind("<Leave>", _unbind)

    # ------------------------------------------------------------------
    # Меню
    # ------------------------------------------------------------------

    def _build_menu(self) -> None:
        menubar = tk.Menu(self, bg=COLOR_SIDEBAR, fg=COLOR_TEXT, activebackground=COLOR_ACCENT,
                           activeforeground="#151515", bd=0)
        filemenu = tk.Menu(menubar, tearoff=0, bg=COLOR_BG, fg=COLOR_TEXT,
                            activebackground=COLOR_ACCENT, activeforeground="#151515")
        filemenu.add_command(label="Обновить всё", command=self.refresh_all)
        filemenu.add_separator()
        filemenu.add_command(label="Открыть папку с базой данных", command=self._open_db_folder)
        filemenu.add_command(label="Импорт базы данных...", command=self._import_db)
        filemenu.add_command(label="Сохранить резервную копию...", command=self._backup_db)
        filemenu.add_separator()
        filemenu.add_command(label="Выход", command=self.destroy)
        menubar.add_cascade(label="Файл", menu=filemenu)

        helpmenu = tk.Menu(menubar, tearoff=0, bg=COLOR_BG, fg=COLOR_TEXT,
                            activebackground=COLOR_ACCENT, activeforeground="#151515")
        helpmenu.add_command(label="О программе", command=self._show_about)
        menubar.add_cascade(label="Справка", menu=helpmenu)
        self.config(menu=menubar)

    def _open_db_folder(self) -> None:
        from aquarium_app.config import DB_PATH
        folder = os.path.dirname(os.path.abspath(DB_PATH))
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", DB_PATH])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", folder])
        else:
            subprocess.Popen(["xdg-open", folder])

    def _import_db(self) -> None:
        from aquarium_app.config import DB_PATH
        if not messagebox.askyesno("Импорт базы данных",
                                    "Эта функция заменит текущую базу данных на выбранную.\n\n"
                                    "Текущие данные будут потеряны!\n\nПродолжить?"):
            return
        src = filedialog.askopenfilename(
            title="Выберите файл базы данных (aquarium_data.db)",
            filetypes=[("SQLite база данных", "*.db"), ("Все файлы", "*.*")],
            initialfile="aquarium_data.db")
        if not src:
            return
        try:
            self.conn.close()
            shutil.copy2(src, DB_PATH)
            self.conn = get_connection()
            init_db(self.conn)
            self.refresh_all()
            messagebox.showinfo("Готово", f"База данных импортирована:\n{src}\n→\n{DB_PATH}")
        except PermissionError:
            messagebox.showerror("Ошибка", "Не удалось заменить файл базы данных.")
            self.conn = get_connection()
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось импортировать:\n{e}")
            self.conn = get_connection()

    def _backup_db(self) -> None:
        import datetime as dt
        from aquarium_app.config import DB_PATH
        dst = filedialog.asksaveasfilename(
            title="Сохранить резервную копию",
            defaultextension=".db",
            filetypes=[("SQLite база данных", "*.db"), ("Все файлы", "*.*")],
            initialfile=f"aquarium_backup_{dt.date.today().isoformat()}.db")
        if not dst:
            return
        try:
            shutil.copy2(DB_PATH, dst)
            messagebox.showinfo("Готово", f"Резервная копия сохранена:\n{dst}")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось создать копию:\n{e}")

    def _show_about(self) -> None:
        from aquarium_app.config import DB_PATH, BASE_DIR, RESOURCES_DIR
        db_exists = os.path.exists(DB_PATH)
        db_size = os.path.getsize(DB_PATH) if db_exists else 0
        try:
            aq_count = self.conn.execute("SELECT COUNT(*) FROM aquariums").fetchone()[0]
            dosing_count = self.conn.execute("SELECT COUNT(*) FROM dosing").fetchone()[0]
            readings_count = self.conn.execute("SELECT COUNT(*) FROM readings").fetchone()[0]
            timers_count = self.conn.execute("SELECT COUNT(*) FROM timers").fetchone()[0]
        except Exception:
            aq_count = dosing_count = readings_count = timers_count = "?"
        frozen = getattr(sys, "frozen", False)
        exe_path = sys.executable if frozen else __file__
        meipass = getattr(sys, "_MEIPASS", "—")
        messagebox.showinfo(
            "О программе",
            "АкваУчёт — учёт удобрений для аквариума\n\n"
            "Журнал дозирования и показаний тестов воды для нескольких аквариумов "
            "с автоматическим расчётом прироста концентрации элементов (мг/л).\n\n"
            "──────────────────────────────\n"
            "ДИАГНОСТИКА БАЗЫ ДАННЫХ:\n"
            f"  Путь к БД: {DB_PATH}\n"
            f"  Файл существует: {'ДА' if db_exists else 'НЕТ'}\n"
            f"  Размер: {db_size} байт\n"
            f"  Аквариумов: {aq_count}\n"
            f"  Записей дозирования: {dosing_count}\n"
            f"  Записей показаний: {readings_count}\n"
            f"  Таймеров: {timers_count}\n"
            "──────────────────────────────\n"
            "ЗАПУСК:\n"
            f"  Режим: {'СОБРАННЫЙ .exe' if frozen else 'python скрипт'}\n"
            f"  Исполняемый файл: {exe_path}\n"
            f"  _MEIPASS: {meipass}\n"
            f"  BASE_DIR: {BASE_DIR}\n"
            f"  RESOURCES_DIR: {RESOURCES_DIR}\n"
            "──────────────────────────────\n"
            "Данные хранятся локально в SQLite.")

    def _set_app_icon(self) -> None:
        """Устанавливает иконку окна приложения."""
        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                    "AquaUchet.AquariumApp.1")
            except (AttributeError, OSError):
                pass
        # при frozen — иконка уже вшита в .exe через --icon, не трогаем
        if getattr(sys, "frozen", False):
            return
        # для разработки — ищем иконку рядом
        icon_path_ico = os.path.join(RESOURCES_DIR, "aquarium_app.ico")
        icon_path_png = os.path.join(RESOURCES_DIR, "icon.png")
        self._icon_photo = None
        if os.path.exists(icon_path_ico):
            try:
                self.iconbitmap(default=True, bitmap=icon_path_ico)
                return
            except tk.TclError:
                pass
        if os.path.exists(icon_path_png):
            try:
                self._icon_photo = tk.PhotoImage(file=icon_path_png)
                self.iconphoto(True, self._icon_photo)
                return
            except tk.TclError:
                pass