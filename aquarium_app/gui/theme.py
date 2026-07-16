"""Настройка тёмной темы ttk для всего приложения."""

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

from aquarium_app.config import (
    FONT_FAMILY,
    COLOR_BG,
    COLOR_SIDEBAR,
    COLOR_SIDEBAR_TEXT,
    COLOR_ACCENT,
    COLOR_ACCENT_HOVER,
    COLOR_ACCENT_SOFT,
    COLOR_CARD,
    COLOR_BORDER,
    COLOR_TEXT,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_SOFT,
    COLOR_HEADER,
    COLOR_HEADER_TEXT,
    COLOR_WARN_TEXT,
    COLOR_OK_TEXT,
    COLOR_ALT_ROW,
)


def setup_style(root: tk.Tk, font_family: str) -> str:
    """Настраивает тему ttk для тёмного интерфейса. Возвращает имя использованного шрифта.

    Parameters
    ----------
    root : tk.Tk
        Корневое окно приложения.
    font_family : str
        Предпочтительное семейство шрифтов (например, «Segoe UI»).
        Если шрифт недоступен в системе, будет подобран fallback.

    Returns
    -------
    str
        Имя шрифта, которое реально используется (может отличаться от
        переданного, если оно недоступно в системе).
    """
    # --- выбор реально доступного шрифта ---
    available = set(tkfont.families())
    ff = next(
        (f for f in (font_family, "Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans")
         if f in available),
        "TkDefaultFont",
    )

    root.configure(bg=COLOR_BG)
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    # --- базовые стили ---
    style.configure(".", background=COLOR_BG, foreground=COLOR_TEXT, font=(ff, 10))
    style.configure("TFrame", background=COLOR_BG)
    style.configure("TLabel", background=COLOR_BG, foreground=COLOR_TEXT, font=(ff, 10))
    style.configure("Header.TLabel", font=(ff, 16, "bold"), foreground=COLOR_TEXT,
                     background=COLOR_BG)
    style.configure("SubHeader.TLabel", font=(ff, 10), foreground=COLOR_TEXT_MUTED,
                     background=COLOR_BG)
    style.configure("Status.TLabel", background=COLOR_SIDEBAR, foreground=COLOR_SIDEBAR_TEXT,
                     font=(ff, 9))

    # --- карточки (LabelFrame) ---
    style.configure("TLabelframe", background=COLOR_CARD, bordercolor=COLOR_BORDER,
                     relief="solid", borderwidth=1)
    style.configure("TLabelframe.Label", background=COLOR_CARD, foreground=COLOR_ACCENT,
                     font=(ff, 10, "bold"))
    style.configure("Card.TLabel", background=COLOR_CARD, foreground=COLOR_TEXT,
                     font=(ff, 10))
    style.configure("CardBold.TLabel", background=COLOR_CARD, foreground=COLOR_TEXT,
                     font=(ff, 10, "bold"))
    style.configure("CardMuted.TLabel", background=COLOR_CARD, foreground=COLOR_TEXT_MUTED,
                     font=(ff, 9))
    style.configure("CardWarn.TLabel", background=COLOR_CARD, foreground=COLOR_WARN_TEXT,
                     font=(ff, 10, "bold"))
    style.configure("CardOk.TLabel", background=COLOR_CARD, foreground=COLOR_OK_TEXT,
                     font=(ff, 10))

    # --- стили для сводки (карточка «За 7 дней») ---
    style.configure("Summary.TFrame", background=COLOR_ACCENT_SOFT, relief="flat",
                     bordercolor=COLOR_ACCENT, borderwidth=0)
    style.configure("SummaryTitle.TLabel", background=COLOR_ACCENT_SOFT, foreground=COLOR_ACCENT,
                     font=(ff, 10, "bold"))
    style.configure("SummaryText.TLabel", background=COLOR_ACCENT_SOFT, foreground=COLOR_TEXT_SOFT,
                     font=(ff, 10))
    style.configure("SummaryMuted.TLabel", background=COLOR_ACCENT_SOFT, foreground=COLOR_TEXT_MUTED,
                     font=(ff, 10, "italic"))

    # --- кнопки ---
    style.configure("TButton", padding=(12, 7), font=(ff, 10), background=COLOR_CARD,
                     foreground=COLOR_TEXT, bordercolor=COLOR_BORDER, borderwidth=1, relief="flat")
    style.map("TButton", background=[("active", COLOR_ALT_ROW)])
    style.configure("Accent.TButton", padding=(14, 8), font=(ff, 10, "bold"),
                     background=COLOR_ACCENT, foreground="#151515", borderwidth=0)
    style.map("Accent.TButton", background=[("active", COLOR_ACCENT_HOVER)],
              foreground=[("active", "#151515")])

    # --- поля ввода ---
    style.configure("TEntry", fieldbackground=COLOR_CARD, foreground=COLOR_TEXT,
                     bordercolor=COLOR_BORDER, padding=6, relief="flat", insertcolor=COLOR_TEXT)
    style.map("TEntry", fieldbackground=[("readonly", COLOR_CARD)],
              bordercolor=[("focus", COLOR_ACCENT)])

    # --- выпадающие списки ---
    style.configure("TCombobox", fieldbackground=COLOR_CARD, foreground=COLOR_TEXT,
                     background=COLOR_CARD, arrowcolor=COLOR_ACCENT, padding=6)
    style.map("TCombobox", fieldbackground=[("readonly", COLOR_CARD)],
              foreground=[("readonly", COLOR_TEXT)],
              selectbackground=[("readonly", COLOR_CARD)],
              selectforeground=[("readonly", COLOR_TEXT)])
    root.option_add("*TCombobox*Listbox.background", COLOR_CARD)
    root.option_add("*TCombobox*Listbox.foreground", COLOR_TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", COLOR_ACCENT)
    root.option_add("*TCombobox*Listbox.selectForeground", "#151515")

    # --- разделители ---
    style.configure("TSeparator", background=COLOR_BORDER)

    # --- полосы прокрутки ---
    for orient in ("Vertical", "Horizontal"):
        style.configure(f"{orient}.TScrollbar", background=COLOR_CARD, troughcolor=COLOR_BG,
                         bordercolor=COLOR_BG, arrowcolor=COLOR_TEXT_MUTED, relief="flat")
        style.map(f"{orient}.TScrollbar", background=[("active", COLOR_ACCENT)])

    # --- таблицы (Treeview) ---
    style.configure("Treeview", rowheight=26, font=(ff, 10), fieldbackground=COLOR_CARD,
                     background=COLOR_CARD, foreground=COLOR_TEXT, borderwidth=0)
    style.configure("Treeview.Heading", font=(ff, 10, "bold"),
                     background=COLOR_HEADER, foreground=COLOR_HEADER_TEXT, relief="flat")
    style.map("Treeview.Heading", background=[("active", COLOR_HEADER)])
    style.map("Treeview", background=[("selected", COLOR_ACCENT)],
              foreground=[("selected", "#151515")])

    return ff