"""
Log Analyzer | Pro Edition
Drop this file next to your current GUI file (same folder), so the
`src` imports and the project_root logic keep working exactly as before.

Shortcuts:  Ctrl+O open file   F5 analyze   Ctrl+K command palette
            Ctrl+F jump to explorer search   Ctrl+B collapse sidebar
"""

import csv
import json
import os
import subprocess
import sys
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, ttk

import customtkinter as ctk

from src.log_reader import read_log_file
from src.log_parser import parse_log_entry

from src.analyser import (
    count_log_levels,
    find_errors,
    find_common_errors,
    find_common_messages,
    calculate_error_percentage,
    find_time_range,
)

from src.report_generator import generate_json_report, generate_csv_report


# ====================== THEME ======================

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

BG = "#070D1A"
SIDEBAR = "#0C1426"
PANEL = "#111C31"
CARD = "#16243D"
CARD_HOVER = "#1B2D4B"
BORDER = "#22324F"
TRACK = "#1F2E48"
INPUT = "#0A1222"
WHITE = "#F1F5F9"
MUTED = "#8195B2"
DIM = "#5B6E8C"

CYAN = "#22D3EE"
GREEN = "#22C55E"
ORANGE = "#F59E0B"
RED = "#EF4444"
PURPLE = "#A78BFA"
BLUE = "#3B82F6"

ACCENTS = {
    "Electric Blue": "#3B82F6",
    "Cyan": "#06B6D4",
    "Violet": "#8B5CF6",
    "Emerald": "#10B981",
    "Rose": "#F43F5E",
}

LEVEL_COLORS = {
    "DEBUG": MUTED,
    "INFO": CYAN,
    "WARNING": ORANGE,
    "WARN": ORANGE,
    "ERROR": RED,
    "CRITICAL": PURPLE,
    "FATAL": PURPLE,
}

FONT = "Segoe UI"


# ====================== HELPERS ======================

def open_path(path):
    path = str(path)
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception:
        pass


def entry_field(entry, keys, default=""):
    """Read a field from a parsed log entry whether it is a dict or an object."""
    for key in keys:
        if isinstance(entry, dict):
            if key in entry and entry[key] is not None:
                return entry[key]
        elif hasattr(entry, key):
            return getattr(entry, key)
    return default


def entry_to_row(entry):
    if isinstance(entry, (list, tuple)) and len(entry) >= 3:
        return (str(entry[0]), str(entry[1]).upper(), str(entry[2]))
    ts = entry_field(entry, ("timestamp", "time", "datetime", "date"))
    level = entry_field(entry, ("level", "severity", "log_level"), "INFO")
    msg = entry_field(entry, ("message", "msg", "text"), str(entry))
    return (str(ts), str(level).upper(), str(msg))


def level_color(level):
    return LEVEL_COLORS.get(str(level).upper(), MUTED)


# ====================== CUSTOM WIDGETS ======================

class DonutChart(tk.Canvas):

    def __init__(self, parent, size=230, bg=PANEL):
        super().__init__(parent, width=size, height=size, bg=bg, highlightthickness=0)
        self.size = size

    def draw(self, data, center_title="ENTRIES"):
        self.delete("all")
        s, pad, thick = self.size, 20, 24
        box = (pad, pad, s - pad, s - pad)
        self.create_oval(*box, outline=TRACK, width=thick)

        total = sum(data.values())
        start = 90
        if total:
            for level, value in data.items():
                if value <= 0:
                    continue
                extent = max(-359.9, -360 * value / total)
                self.create_arc(*box, start=start, extent=extent, style="arc",
                                outline=level_color(level), width=thick)
                start += extent

        self.create_text(s / 2, s / 2 - 8, text=f"{total:,}", fill=WHITE,
                         font=(FONT, 26, "bold"))
        self.create_text(s / 2, s / 2 + 20, text=center_title, fill=MUTED,
                         font=(FONT, 9, "bold"))


class HealthGauge(tk.Canvas):

    def __init__(self, parent, width=290, height=170, bg=PANEL):
        super().__init__(parent, width=width, height=height, bg=bg, highlightthickness=0)
        self.w, self.h = width, height

    def draw(self, health):
        self.delete("all")
        box = (30, 25, self.w - 30, self.w - 35)
        self.create_arc(*box, start=180, extent=-180, style="arc", outline=TRACK, width=20)

        if health is None:
            color, label, shown = DIM, "AWAITING DATA", "--"
        else:
            color = GREEN if health >= 85 else ORANGE if health >= 60 else RED
            label = "HEALTHY" if health >= 85 else "DEGRADED" if health >= 60 else "CRITICAL"
            shown = f"{health:.0f}"
            self.create_arc(*box, start=180, extent=-180 * health / 100, style="arc",
                            outline=color, width=20)

        self.create_text(self.w / 2, self.h - 62, text=shown, fill=WHITE, font=(FONT, 34, "bold"))
        self.create_text(self.w / 2, self.h - 24, text=label, fill=color, font=(FONT, 10, "bold"))


class BarChart(tk.Canvas):

    def __init__(self, parent, bg=PANEL, color=RED):
        super().__init__(parent, height=60, bg=bg, highlightthickness=0)
        self.items, self.color = [], color
        self.bind("<Configure>", lambda e: self._render())

    def draw(self, items, color=None):
        self.items = list(items)
        if color:
            self.color = color
        self._render()

    def _render(self):
        self.delete("all")
        width = max(self.winfo_width(), 300)
        if not self.items:
            self.configure(height=60)
            self.create_text(10, 30, anchor="w", text="Nothing to show yet.", fill=DIM,
                             font=(FONT, 11))
            return

        row_h = 44
        self.configure(height=row_h * len(self.items) + 6)
        peak = max(v for _, v in self.items) or 1
        for i, (label, value) in enumerate(self.items):
            y = i * row_h + 4
            text = label if len(label) <= 62 else label[:59] + "..."
            self.create_text(2, y + 8, anchor="w", text=text, fill=WHITE, font=(FONT, 10))
            self.create_text(width - 2, y + 8, anchor="e", text=f"{value:,}", fill=MUTED,
                             font=(FONT, 10, "bold"))
            self.create_rectangle(2, y + 22, width - 2, y + 30, fill=TRACK, outline="")
            self.create_rectangle(2, y + 22, 2 + (width - 4) * value / peak, y + 30,
                                  fill=self.color, outline="")


class Toast(ctk.CTkFrame):

    def __init__(self, parent, message, kind="info", duration=3200):
        color = {"info": BLUE, "success": GREEN, "warning": ORANGE, "error": RED}.get(kind, BLUE)
        super().__init__(parent, fg_color=CARD, corner_radius=12, border_width=1,
                         border_color=color)
        ctk.CTkFrame(self, width=5, fg_color=color, corner_radius=3).pack(
            side="left", fill="y", padx=(8, 0), pady=10)
        ctk.CTkLabel(self, text=message, font=(FONT, 12), text_color=WHITE,
                     justify="left", wraplength=340).pack(side="left", padx=14, pady=14)
        self.place(relx=1.0, rely=1.0, x=-26, y=-52, anchor="se")
        self.lift()
        self.after(duration, self.destroy)


# ====================== MAIN APP ======================

class LogAnalyzerApp(ctk.CTk):

    NAV = [
        ("Dashboard", "▦", "Overview & live metrics"),
        ("Analyze", "⌕", "Run a new analysis"),
        ("Explorer", "☰", "Search & filter every entry"),
        ("Reports", "▤", "Generated exports"),
        ("Settings", "⚙", "Personalise the app"),
    ]

    def __init__(self):
        super().__init__()

        self.title("Log Analyzer Pro")
        self.geometry("1360x860")
        self.minsize(1120, 720)
        self.configure(fg_color=BG)

        self.project_root = Path(__file__).resolve().parent.parent
        self.reports_folder = self.project_root / "reports"
        self.reports_folder.mkdir(exist_ok=True)

        self.accent = ACCENTS["Electric Blue"]
        self.animations = True
        self.selected_file = None
        self.analysis_data = None
        self.recent_files = []
        self.current_page = "Dashboard"
        self.sidebar_open = True
        self.analysing = False
        self.search_job = None
        self.explorer_level = "ALL"
        self.explorer_query = ""

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.build_sidebar()

        self.main = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self.main.grid(row=0, column=1, sticky="nsew", padx=(28, 28), pady=(22, 8))
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_rowconfigure(1, weight=1)

        self.build_statusbar()
        self.setup_tree_style()
        self.bind_shortcuts()
        self.navigate("Dashboard")
        self.tick_clock()

    # ---------------- shortcuts & status bar ----------------

    def bind_shortcuts(self):
        self.bind("<Control-o>", lambda e: self.browse_file())
        self.bind("<F5>", lambda e: self.start_analysis())
        self.bind("<Control-k>", lambda e: self.open_palette())
        self.bind("<Control-b>", lambda e: self.toggle_sidebar())
        self.bind("<Control-f>", lambda e: self.focus_explorer_search())

    def build_statusbar(self):
        bar = ctk.CTkFrame(self, height=30, fg_color=SIDEBAR, corner_radius=0)
        bar.grid(row=1, column=0, columnspan=2, sticky="ew")
        bar.grid_propagate(False)

        self.status_dot = ctk.CTkLabel(bar, text="●  Ready", font=(FONT, 11, "bold"),
                                       text_color=GREEN)
        self.status_dot.pack(side="left", padx=(16, 20))

        self.status_file = ctk.CTkLabel(bar, text="No file loaded", font=(FONT, 11),
                                        text_color=MUTED)
        self.status_file.pack(side="left")

        self.status_clock = ctk.CTkLabel(bar, text="", font=(FONT, 11), text_color=MUTED)
        self.status_clock.pack(side="right", padx=16)

        ctk.CTkLabel(bar, text="Ctrl+K  Command palette", font=(FONT, 11),
                     text_color=DIM).pack(side="right", padx=16)

    def tick_clock(self):
        self.status_clock.configure(text=datetime.now().strftime("%a %d %b  •  %H:%M:%S"))
        self.after(1000, self.tick_clock)

    def set_status(self, text, color=GREEN):
        self.status_dot.configure(text=f"●  {text}", text_color=color)

    def toast(self, message, kind="info"):
        Toast(self, message, kind)

    # ---------------- sidebar ----------------

    def build_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=250, fg_color=SIDEBAR, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)

        top = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        top.pack(fill="x", padx=18, pady=(30, 28))

        self.logo_mark = ctk.CTkLabel(top, text="◈", font=(FONT, 30, "bold"), text_color=CYAN)
        self.logo_mark.pack(side="left")

        self.logo_text = ctk.CTkFrame(top, fg_color="transparent")
        self.logo_text.pack(side="left", padx=(10, 0))
        ctk.CTkLabel(self.logo_text, text="LOG ANALYZER", font=(FONT, 16, "bold"),
                     text_color=WHITE).pack(anchor="w")
        ctk.CTkLabel(self.logo_text, text="PRO EDITION  •  v3.0", font=(FONT, 9, "bold"),
                     text_color=MUTED).pack(anchor="w")

        self.nav_widgets = {}
        for name, symbol, _hint in self.NAV:
            row = ctk.CTkFrame(self.sidebar, fg_color="transparent", height=48)
            row.pack(fill="x", padx=(0, 14), pady=3)
            row.pack_propagate(False)

            indicator = ctk.CTkFrame(row, width=4, fg_color="transparent", corner_radius=2)
            indicator.pack(side="left", fill="y", pady=8)

            button = ctk.CTkButton(
                row, text=f"  {symbol}    {name}", anchor="w", height=44, corner_radius=10,
                font=(FONT, 14, "bold"), fg_color="transparent", hover_color=CARD,
                text_color=MUTED, command=lambda n=name: self.navigate(n))
            button.pack(side="left", fill="x", expand=True, padx=(10, 0))
            self.nav_widgets[name] = (indicator, button, symbol)

        bottom = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        bottom.pack(side="bottom", fill="x", padx=16, pady=20)

        self.collapse_btn = ctk.CTkButton(
            bottom, text="«  Collapse", height=34, corner_radius=8, fg_color=CARD,
            hover_color=CARD_HOVER, text_color=MUTED, font=(FONT, 12),
            command=self.toggle_sidebar)
        self.collapse_btn.pack(fill="x", pady=(0, 14))

        self.engine_card = ctk.CTkFrame(bottom, fg_color=CARD, corner_radius=12)
        self.engine_card.pack(fill="x")
        ctk.CTkLabel(self.engine_card, text="●  ENGINE ONLINE", font=(FONT, 10, "bold"),
                     text_color=GREEN).pack(anchor="w", padx=14, pady=(12, 2))
        ctk.CTkLabel(self.engine_card, text="Parser · Analyser · Reports", font=(FONT, 10),
                     text_color=MUTED).pack(anchor="w", padx=14, pady=(0, 12))

    def toggle_sidebar(self):
        self.sidebar_open = not self.sidebar_open
        if self.sidebar_open:
            self.sidebar.configure(width=250)
            self.logo_text.pack(side="left", padx=(10, 0))
            self.engine_card.pack(fill="x")
            self.collapse_btn.configure(text="«  Collapse")
        else:
            self.sidebar.configure(width=76)
            self.logo_text.pack_forget()
            self.engine_card.pack_forget()
            self.collapse_btn.configure(text="»")
        for name, (_i, button, symbol) in self.nav_widgets.items():
            button.configure(text=f"  {symbol}    {name}" if self.sidebar_open else f" {symbol}")

    # ---------------- navigation ----------------

    def navigate(self, page):
        self.current_page = page
        for name, (indicator, button, _s) in self.nav_widgets.items():
            active = name == page
            indicator.configure(fg_color=self.accent if active else "transparent")
            button.configure(fg_color=CARD if active else "transparent",
                             text_color=WHITE if active else MUTED)

        for widget in self.main.winfo_children():
            widget.destroy()

        {
            "Dashboard": self.page_dashboard,
            "Analyze": self.page_analyze,
            "Explorer": self.page_explorer,
            "Reports": self.page_reports,
            "Settings": self.page_settings,
        }[page]()

    def header(self, title, subtitle):
        head = ctk.CTkFrame(self.main, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", pady=(0, 20))
        head.grid_columnconfigure(0, weight=1)

        left = ctk.CTkFrame(head, fg_color="transparent")
        left.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(left, text=title, font=(FONT, 30, "bold"), text_color=WHITE).pack(anchor="w")
        ctk.CTkLabel(left, text=subtitle, font=(FONT, 13), text_color=MUTED).pack(anchor="w", pady=(2, 0))

        right = ctk.CTkFrame(head, fg_color="transparent")
        right.grid(row=0, column=1, sticky="e")

        ctk.CTkButton(right, text="⌘  Ctrl+K", width=100, height=36, corner_radius=10,
                      fg_color=CARD, hover_color=CARD_HOVER, text_color=MUTED,
                      font=(FONT, 12), command=self.open_palette).pack(side="left", padx=(0, 10))

        chip_text = Path(self.selected_file).name if self.selected_file else "No file"
        ctk.CTkLabel(right, text=f"  ▤  {chip_text}  ", height=36, corner_radius=10,
                     fg_color=CARD, text_color=CYAN, font=(FONT, 12, "bold")).pack(side="left")

    def card(self, parent, **grid):
        frame = ctk.CTkFrame(parent, fg_color=PANEL, corner_radius=16, border_width=1,
                             border_color=BORDER)
        frame.grid(**grid)
        return frame

    def card_title(self, parent, text, color=None):
        ctk.CTkLabel(parent, text=text, font=(FONT, 12, "bold"),
                     text_color=color or self.accent).pack(anchor="w", padx=22, pady=(20, 10))

    # ---------------- dashboard ----------------

    def page_dashboard(self):
        self.header("Dashboard", "Live overview of your latest log analysis.")
        data = self.analysis_data

        body = ctk.CTkScrollableFrame(self.main, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew")
        body.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="k")

        # hero
        hero = ctk.CTkFrame(body, fg_color="#14294B", corner_radius=18, border_width=1,
                            border_color="#24427A")
        hero.grid(row=0, column=0, columnspan=4, sticky="ew", pady=(0, 18))
        hero.grid_columnconfigure(0, weight=1)

        text = ctk.CTkFrame(hero, fg_color="transparent")
        text.grid(row=0, column=0, sticky="w", padx=28, pady=24)
        ctk.CTkLabel(text, text=self.greeting(), font=(FONT, 12, "bold"),
                     text_color=CYAN).pack(anchor="w")
        ctk.CTkLabel(text, text="Turn raw logs into answers.", font=(FONT, 26, "bold"),
                     text_color=WHITE).pack(anchor="w", pady=(4, 2))
        ctk.CTkLabel(text, text="Drop in a .log or .txt file and get stats, trends, and "
                     "reports in seconds.", font=(FONT, 12), text_color="#B7CCEB").pack(anchor="w")

        actions = ctk.CTkFrame(hero, fg_color="transparent")
        actions.grid(row=0, column=1, padx=28)
        ctk.CTkButton(actions, text="＋  New Analysis", width=170, height=44, corner_radius=12,
                      fg_color=self.accent, font=(FONT, 14, "bold"),
                      command=lambda: self.navigate("Analyze")).pack(pady=(0, 8))
        ctk.CTkButton(actions, text="☰  Open Explorer", width=170, height=36, corner_radius=12,
                      fg_color="transparent", border_width=1, border_color="#3A5A94",
                      hover_color="#1B3560", command=lambda: self.navigate("Explorer")).pack()

        # KPIs
        if data:
            total = len(data["logs"])
            errors = len(data["errors"])
            warns = data["statistics"].get("WARNING", 0)
            crit = data["statistics"].get("CRITICAL", 0)
            sub = [f"{len(data['rows']):,} rows parsed", f"{data['error_percentage']:.2f}% of all logs",
                   "needs attention" if warns else "all quiet", "highest severity"]
        else:
            total = errors = warns = crit = 0
            sub = ["waiting for data"] * 4

        for col, (title, value, color, s) in enumerate([
            ("TOTAL LOGS", total, CYAN, sub[0]), ("ERRORS", errors, RED, sub[1]),
            ("WARNINGS", warns, ORANGE, sub[2]), ("CRITICAL", crit, PURPLE, sub[3])]):
            self.kpi_card(body, 1, col, title, value, color, s)

        # charts row
        levels = dict(data["statistics"]) if data else {}

        donut_card = self.card(body, row=2, column=0, columnspan=2, sticky="nsew",
                               padx=(0, 9), pady=(18, 0))
        self.card_title(donut_card, "LOG LEVEL DISTRIBUTION")
        inner = ctk.CTkFrame(donut_card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=22, pady=(0, 22))
        donut = DonutChart(inner)
        donut.pack(side="left")
        donut.draw(levels)

        legend = ctk.CTkFrame(inner, fg_color="transparent")
        legend.pack(side="left", padx=26, fill="y")
        total_levels = sum(levels.values()) or 1
        if levels:
            for level, count in levels.items():
                row = ctk.CTkFrame(legend, fg_color="transparent")
                row.pack(anchor="w", pady=5, fill="x")
                ctk.CTkLabel(row, text="●", text_color=level_color(level),
                             font=(FONT, 16)).pack(side="left")
                ctk.CTkLabel(row, text=f" {level}", text_color=WHITE,
                             font=(FONT, 12, "bold"), width=95, anchor="w").pack(side="left")
                ctk.CTkLabel(row, text=f"{count:,}  ({count / total_levels * 100:.1f}%)",
                             text_color=MUTED, font=(FONT, 12)).pack(side="left")
        else:
            ctk.CTkLabel(legend, text="Run an analysis to see\nthe breakdown here.",
                         text_color=DIM, font=(FONT, 12), justify="left").pack(anchor="w")

        gauge_card = self.card(body, row=2, column=2, columnspan=2, sticky="nsew",
                               padx=(9, 0), pady=(18, 0))
        self.card_title(gauge_card, "SYSTEM HEALTH SCORE")
        gauge = HealthGauge(gauge_card)
        gauge.pack(pady=(0, 6))
        gauge.draw(None if not data else max(0.0, 100 - data["error_percentage"]))
        ctk.CTkLabel(gauge_card, text="Score = 100 − error percentage", font=(FONT, 11),
                     text_color=DIM).pack(pady=(0, 20))

        # top errors + insights
        err_card = self.card(body, row=3, column=0, columnspan=2, sticky="nsew",
                             padx=(0, 9), pady=(18, 0))
        self.card_title(err_card, "TOP RECURRING ERRORS", RED)
        bars = BarChart(err_card, bg=PANEL, color=RED)
        bars.pack(fill="x", padx=22, pady=(0, 20))
        if data and data["common_errors"]:
            bars.draw(data["common_errors"].most_common(5), RED)
        else:
            bars.draw([])

        ins_card = self.card(body, row=3, column=2, columnspan=2, sticky="nsew",
                             padx=(9, 0), pady=(18, 0))
        self.card_title(ins_card, "AUTO INSIGHTS", PURPLE)
        for icon, color, line in self.build_insights():
            row = ctk.CTkFrame(ins_card, fg_color=CARD, corner_radius=10)
            row.pack(fill="x", padx=22, pady=4)
            ctk.CTkLabel(row, text=icon, text_color=color, font=(FONT, 16)).pack(
                side="left", padx=(12, 8), pady=10)
            ctk.CTkLabel(row, text=line, text_color=WHITE, font=(FONT, 12), justify="left",
                         wraplength=330, anchor="w").pack(side="left", fill="x", expand=True,
                                                          padx=(0, 12))
        ctk.CTkFrame(ins_card, height=14, fg_color="transparent").pack()

        # time range strip
        if data:
            strip = self.card(body, row=4, column=0, columnspan=4, sticky="ew", pady=(18, 10))
            inner = ctk.CTkFrame(strip, fg_color="transparent")
            inner.pack(fill="x", padx=22, pady=18)
            for label, value in [("EARLIEST ENTRY", data["earliest"]),
                                 ("LATEST ENTRY", data["latest"]),
                                 ("INVALID ENTRIES", data["invalid_entries"]),
                                 ("SOURCE FILE", Path(data["file"]).name)]:
                cell = ctk.CTkFrame(inner, fg_color="transparent")
                cell.pack(side="left", expand=True, fill="x")
                ctk.CTkLabel(cell, text=label, font=(FONT, 10, "bold"),
                             text_color=MUTED).pack(anchor="w")
                ctk.CTkLabel(cell, text=str(value), font=(FONT, 13, "bold"),
                             text_color=WHITE).pack(anchor="w", pady=(3, 0))

    def greeting(self):
        hour = datetime.now().hour
        part = "GOOD MORNING" if hour < 12 else "GOOD AFTERNOON" if hour < 18 else "GOOD EVENING"
        return f"{part}  •  WORKSPACE READY"

    def kpi_card(self, parent, row, col, title, value, color, sub):
        pad = (0 if col == 0 else 7, 0 if col == 3 else 7)
        card = ctk.CTkFrame(parent, fg_color=PANEL, corner_radius=16, border_width=1,
                            border_color=BORDER)
        card.grid(row=row, column=col, sticky="nsew", padx=pad)
        ctk.CTkFrame(card, height=3, fg_color=color, corner_radius=2).pack(
            fill="x", padx=22, pady=(0, 0))
        ctk.CTkLabel(card, text=title, font=(FONT, 11, "bold"),
                     text_color=MUTED).pack(anchor="w", padx=22, pady=(16, 0))
        label = ctk.CTkLabel(card, text="0", font=(FONT, 36, "bold"), text_color=color)
        label.pack(anchor="w", padx=22)
        ctk.CTkLabel(card, text=sub, font=(FONT, 11), text_color=DIM).pack(
            anchor="w", padx=22, pady=(0, 18))
        self.count_up(label, value)

    def count_up(self, label, target, steps=22):
        if not self.animations or target <= 0:
            label.configure(text=f"{target:,}")
            return

        def step(i=1):
            try:
                if not label.winfo_exists():
                    return
                eased = 1 - (1 - i / steps) ** 3
                label.configure(text=f"{int(target * eased):,}")
                if i < steps:
                    self.after(18, lambda: step(i + 1))
            except tk.TclError:
                pass
        step()

    def build_insights(self):
        d = self.analysis_data
        if not d:
            return [("◌", MUTED, "No analysis yet. Load a log file and press Analyze (F5).")]

        out = []
        pct = d["error_percentage"]
        if pct >= 20:
            out.append(("▲", RED, f"Error rate is high at {pct:.1f}%. Investigate the top errors first."))
        elif pct >= 5:
            out.append(("▲", ORANGE, f"Error rate is {pct:.1f}%, worth keeping an eye on."))
        else:
            out.append(("✔", GREEN, f"Error rate is a healthy {pct:.1f}%."))

        if d["common_errors"]:
            msg, count = d["common_errors"].most_common(1)[0]
            short = msg if len(msg) < 48 else msg[:45] + "..."
            out.append(("◆", RED, f"Most frequent error: “{short}” ({count}×)."))

        stats = d["statistics"]
        if stats:
            top = max(stats, key=stats.get)
            out.append(("●", level_color(top), f"{top} dominates the log with {stats[top]:,} entries."))

        if d["invalid_entries"]:
            out.append(("!", ORANGE, f"{d['invalid_entries']:,} lines could not be parsed."))
        return out

    # ---------------- analyze ----------------

    def page_analyze(self):
        self.header("Analyze", "Pick a file, hit Analyze, and watch the engine work.")

        body = ctk.CTkFrame(self.main, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew")
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=1)

        file_card = self.card(body, row=0, column=0, sticky="ew", pady=(0, 16))
        self.card_title(file_card, "SOURCE FILE")

        drop = ctk.CTkFrame(file_card, fg_color=INPUT, corner_radius=14, border_width=2,
                            border_color=BORDER)
        drop.pack(fill="x", padx=22)
        ctk.CTkLabel(drop, text="⇪", font=(FONT, 34), text_color=self.accent).pack(pady=(16, 0))

        self.selected_file_label = ctk.CTkLabel(
            drop, text=Path(self.selected_file).name if self.selected_file else "No file selected",
            font=(FONT, 15, "bold"), text_color=WHITE)
        self.selected_file_label.pack()
        self.selected_path_label = ctk.CTkLabel(
            drop, text=self.selected_file or "Supported formats: .log  •  .txt   (Ctrl+O to browse)",
            font=(FONT, 11), text_color=MUTED)
        self.selected_path_label.pack(pady=(2, 16))

        controls = ctk.CTkFrame(file_card, fg_color="transparent")
        controls.pack(fill="x", padx=22, pady=18)

        ctk.CTkButton(controls, text="Browse…", width=130, height=42, corner_radius=10,
                      fg_color=CARD, hover_color=CARD_HOVER, font=(FONT, 13, "bold"),
                      command=self.browse_file).pack(side="left", padx=(0, 10))

        self.analyze_btn = ctk.CTkButton(
            controls, text="▶  Analyze  (F5)", width=170, height=42, corner_radius=10,
            fg_color=GREEN, hover_color="#16A34A", font=(FONT, 13, "bold"),
            command=self.start_analysis)
        self.analyze_btn.pack(side="left", padx=(0, 10))

        if self.recent_files:
            self.recent_menu = ctk.CTkOptionMenu(
                controls, values=[Path(f).name for f in self.recent_files], width=220, height=42,
                fg_color=CARD, button_color=CARD_HOVER, command=self.pick_recent)
            self.recent_menu.set("Recent files")
            self.recent_menu.pack(side="left")

        self.progress = ctk.CTkProgressBar(file_card, height=6, progress_color=self.accent,
                                           fg_color=TRACK, mode="indeterminate")
        self.progress.pack(fill="x", padx=22, pady=(0, 20))
        self.progress.set(0)

        out_card = self.card(body, row=1, column=0, sticky="nsew")
        out_card.grid_rowconfigure(1, weight=1)
        out_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(out_card, text="ANALYSIS OUTPUT", font=(FONT, 12, "bold"),
                     text_color=self.accent).grid(row=0, column=0, sticky="w", padx=22, pady=(20, 10))

        self.results_box = ctk.CTkTextbox(
            out_card, fg_color=INPUT, text_color=WHITE, border_width=1, border_color=BORDER,
            corner_radius=12, font=("Consolas", 12), wrap="word")
        self.results_box.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        for tag, color in [("h", self.accent), ("ok", GREEN), ("err", RED), ("warn", ORANGE),
                           ("muted", MUTED)]:
            self.results_box.tag_config(tag, foreground=color)

        if self.analysis_data:
            self.display_results(self.analysis_data)
        else:
            self.write_output([
                ("$ log-analyzer --ready\n\n", "ok"),
                ("1. Browse and select a log file\n", None),
                ("2. Press Analyze or F5\n", None),
                ("3. Results stream in here, and the Dashboard fills up\n", None),
            ])

    def write_output(self, chunks):
        box = self.results_box
        box.configure(state="normal")
        box.delete("1.0", "end")
        for text, tag in chunks:
            box.insert("end", text, tag) if tag else box.insert("end", text)
        box.configure(state="disabled")

    def browse_file(self):
        path = filedialog.askopenfilename(
            title="Select a Log File",
            filetypes=[("Log Files", "*.log"), ("Text Files", "*.txt"), ("All Files", "*.*")])
        if path:
            self.set_file(path)

    def pick_recent(self, name):
        for f in self.recent_files:
            if Path(f).name == name:
                self.set_file(f)
                return

    def set_file(self, path):
        self.selected_file = path
        if path in self.recent_files:
            self.recent_files.remove(path)
        self.recent_files.insert(0, path)
        self.recent_files = self.recent_files[:6]
        self.status_file.configure(text=path)
        if self.current_page == "Analyze":
            self.selected_file_label.configure(text=Path(path).name)
            self.selected_path_label.configure(text=path)
        self.toast(f"Loaded {Path(path).name}", "info")

    # ---- analysis runs in a worker thread so the UI never freezes ----

    def start_analysis(self):
        if self.analysing:
            return
        if not self.selected_file:
            self.toast("Select a log file first (Ctrl+O).", "warning")
            return

        self.analysing = True
        self.set_status("Analysing…", ORANGE)
        if hasattr(self, "progress") and self.current_page == "Analyze":
            self.analyze_btn.configure(state="disabled", text="Analysing…")
            self.progress.start()
            self.write_output([("$ analysing ", "h"), (Path(self.selected_file).name + "\n", None),
                               ("reading → parsing → crunching numbers…\n", "muted")])

        path = self.selected_file
        threading.Thread(target=self.analysis_worker, args=(path,), daemon=True).start()

    def analysis_worker(self, path):
        try:
            raw_logs = read_log_file(path)
            if raw_logs is None:
                raise RuntimeError("Unable to read the selected log file.")

            logs, invalid = [], 0
            for entry in raw_logs:
                parsed = parse_log_entry(entry)
                if parsed is not None:
                    logs.append(parsed)
                else:
                    invalid += 1

            if not logs:
                raise RuntimeError("No valid log entries were found.")

            statistics = count_log_levels(logs)
            errors = find_errors(logs)
            common_errors = find_common_errors(errors)
            common_messages = find_common_messages(logs)
            error_percentage = calculate_error_percentage(logs)
            earliest, latest = find_time_range(logs)

            generate_json_report(logs, statistics, errors, common_errors, common_messages,
                                 error_percentage, earliest, latest, invalid)
            generate_csv_report(logs)

            result = {
                "file": path, "logs": logs, "rows": [entry_to_row(e) for e in logs],
                "statistics": statistics, "errors": errors, "common_errors": common_errors,
                "common_messages": common_messages, "error_percentage": error_percentage,
                "earliest": earliest, "latest": latest, "invalid_entries": invalid,
            }
            self.after(0, lambda: self.analysis_done(result, None))
        except Exception as exc:
            self.after(0, lambda e=exc: self.analysis_done(None, e))

    def analysis_done(self, result, error):
        self.analysing = False
        if self.current_page == "Analyze" and hasattr(self, "progress"):
            try:
                self.progress.stop()
                self.progress.set(0)
                self.analyze_btn.configure(state="normal", text="▶  Analyze  (F5)")
            except tk.TclError:
                pass

        if error:
            self.set_status("Analysis failed", RED)
            self.toast(f"Analysis failed: {error}", "error")
            return

        self.analysis_data = result
        self.explorer_level, self.explorer_query = "ALL", ""
        self.set_status("Analysis complete", GREEN)
        self.toast("Analysis complete. JSON and CSV reports generated.", "success")
        if self.current_page == "Analyze":
            self.display_results(result)
        elif self.current_page == "Dashboard":
            self.navigate("Dashboard")

    def display_results(self, d):
        if not hasattr(self, "results_box"):
            return
        chunks = [("========== ANALYSIS SUMMARY ==========\n", "h"),
                  (f"File              {Path(d['file']).name}\n", None),
                  (f"Total entries     {len(d['logs']):,}\n", None),
                  (f"Total errors      {len(d['errors']):,}\n", "err"),
                  (f"Error percentage  {d['error_percentage']:.2f}%\n", "warn"),
                  (f"Invalid entries   {d['invalid_entries']:,}\n\n", None),
                  ("========== LOG LEVELS ==========\n", "h")]

        total = sum(d["statistics"].values()) or 1
        for level, count in d["statistics"].items():
            bar = "█" * int(24 * count / total)
            chunks.append((f"{level:<9}{count:>8,}  {bar}\n", None))

        chunks.append(("\n========== COMMON ERRORS ==========\n", "h"))
        if d["common_errors"]:
            for msg, count in d["common_errors"].most_common(5):
                chunks.append((f"{count:>5}×  {msg}\n", "err"))
        else:
            chunks.append(("No errors found.\n", "ok"))

        chunks.append(("\n========== COMMON MESSAGES ==========\n", "h"))
        for msg, count in d["common_messages"].most_common(5):
            chunks.append((f"{count:>5}×  {msg}\n", None))

        chunks += [("\n========== TIME RANGE ==========\n", "h"),
                   (f"Earliest  {d['earliest']}\n", None), (f"Latest    {d['latest']}\n", None),
                   ("\n========== REPORTS ==========\n", "h"),
                   ("✔ reports/analysis_report.json\n", "ok"), ("✔ reports/analysis_report.csv\n", "ok")]
        self.write_output(chunks)

    # ---------------- explorer ----------------

    def setup_tree_style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Log.Treeview", background=INPUT, fieldbackground=INPUT, foreground=WHITE,
                        rowheight=30, borderwidth=0, font=(FONT, 10))
        style.configure("Log.Treeview.Heading", background=CARD, foreground=CYAN, relief="flat",
                        borderwidth=0, font=(FONT, 10, "bold"), padding=(8, 8))
        style.map("Log.Treeview", background=[("selected", "#1D4ED8")],
                  foreground=[("selected", WHITE)])
        style.map("Log.Treeview.Heading", background=[("active", CARD_HOVER)])
        style.configure("Vertical.TScrollbar", background=CARD, troughcolor=INPUT,
                        bordercolor=INPUT, arrowcolor=MUTED, relief="flat")

    def page_explorer(self):
        self.header("Explorer", "Search, filter and inspect every parsed entry.")

        body = ctk.CTkFrame(self.main, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew")
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=1)

        if not self.analysis_data:
            empty = self.card(body, row=0, column=0, sticky="ew")
            ctk.CTkLabel(empty, text="☰", font=(FONT, 48), text_color=DIM).pack(pady=(40, 6))
            ctk.CTkLabel(empty, text="Nothing to explore yet", font=(FONT, 18, "bold"),
                         text_color=WHITE).pack()
            ctk.CTkLabel(empty, text="Analyze a log file and every entry will be searchable here.",
                         font=(FONT, 12), text_color=MUTED).pack(pady=(4, 18))
            ctk.CTkButton(empty, text="Go to Analyze", height=40, fg_color=self.accent,
                          command=lambda: self.navigate("Analyze")).pack(pady=(0, 40))
            return

        bar = self.card(body, row=0, column=0, sticky="ew", pady=(0, 14))
        inner = ctk.CTkFrame(bar, fg_color="transparent")
        inner.pack(fill="x", padx=18, pady=14)

        self.search_entry = ctk.CTkEntry(inner, placeholder_text="🔍  Search messages…  (Ctrl+F)",
                                         width=340, height=38, corner_radius=10, fg_color=INPUT,
                                         border_color=BORDER)
        self.search_entry.pack(side="left")
        if self.explorer_query:
            self.search_entry.insert(0, self.explorer_query)
        self.search_entry.bind("<KeyRelease>", self.on_search_key)

        levels = ["ALL"] + list(self.analysis_data["statistics"].keys())
        self.level_filter = ctk.CTkSegmentedButton(
            inner, values=levels, command=self.on_level_change, selected_color=self.accent,
            unselected_color=CARD, fg_color=CARD)
        self.level_filter.set(self.explorer_level if self.explorer_level in levels else "ALL")
        self.level_filter.pack(side="left", padx=16)

        ctk.CTkButton(inner, text="⭳  Export view", width=130, height=38, corner_radius=10,
                      fg_color=CARD, hover_color=CARD_HOVER,
                      command=self.export_view).pack(side="right")
        self.count_label = ctk.CTkLabel(inner, text="", font=(FONT, 12), text_color=MUTED)
        self.count_label.pack(side="right", padx=16)

        table_card = self.card(body, row=1, column=0, sticky="nsew")
        table_card.grid_columnconfigure(0, weight=1)
        table_card.grid_rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(table_card, columns=("time", "level", "message"),
                                 show="headings", style="Log.Treeview")
        self.tree.heading("time", text="TIMESTAMP")
        self.tree.heading("level", text="LEVEL")
        self.tree.heading("message", text="MESSAGE")
        self.tree.column("time", width=190, stretch=False)
        self.tree.column("level", width=100, stretch=False, anchor="center")
        self.tree.column("message", width=700)
        for level, color in LEVEL_COLORS.items():
            self.tree.tag_configure(level, foreground=color)

        scroll = ttk.Scrollbar(table_card, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(12, 0), pady=12)
        scroll.grid(row=0, column=1, sticky="ns", padx=(0, 8), pady=12)
        self.tree.bind("<Double-1>", self.show_entry_detail)

        self.refresh_table()

    def focus_explorer_search(self):
        if self.current_page != "Explorer":
            self.navigate("Explorer")
        if hasattr(self, "search_entry"):
            self.search_entry.focus_set()

    def on_search_key(self, _event=None):
        if self.search_job:
            self.after_cancel(self.search_job)
        self.search_job = self.after(220, self.refresh_table)

    def on_level_change(self, value):
        self.explorer_level = value
        self.refresh_table()

    def filtered_rows(self):
        rows = self.analysis_data["rows"]
        query = self.search_entry.get().strip().lower() if hasattr(self, "search_entry") else ""
        self.explorer_query = query
        level = self.explorer_level
        return [r for r in rows
                if (level == "ALL" or r[1] == level) and (not query or query in r[2].lower())]

    def refresh_table(self):
        if not hasattr(self, "tree") or not self.tree.winfo_exists():
            return
        rows = self.filtered_rows()
        self.tree.delete(*self.tree.get_children())
        limit = 3000
        for ts, level, msg in rows[:limit]:
            self.tree.insert("", "end", values=(ts, level, msg), tags=(level,))
        shown = min(len(rows), limit)
        extra = "  (showing first 3,000)" if len(rows) > limit else ""
        self.count_label.configure(text=f"{shown:,} of {len(self.analysis_data['rows']):,} entries{extra}")

    def show_entry_detail(self, _event):
        selected = self.tree.selection()
        if not selected:
            return
        ts, level, msg = self.tree.item(selected[0], "values")

        win = ctk.CTkToplevel(self)
        win.title("Log Entry")
        win.geometry("640x340")
        win.configure(fg_color=PANEL)
        win.after(120, win.lift)
        win.focus_force()

        ctk.CTkLabel(win, text=f"  {level}  ", fg_color=level_color(level), text_color="#0B1120",
                     corner_radius=8, font=(FONT, 12, "bold")).pack(anchor="w", padx=24, pady=(24, 6))
        ctk.CTkLabel(win, text=ts, font=(FONT, 12), text_color=MUTED).pack(anchor="w", padx=24)
        box = ctk.CTkTextbox(win, fg_color=INPUT, font=("Consolas", 13), corner_radius=12,
                             border_width=1, border_color=BORDER, wrap="word")
        box.pack(fill="both", expand=True, padx=24, pady=16)
        box.insert("end", msg)
        box.configure(state="disabled")

        def copy():
            self.clipboard_clear()
            self.clipboard_append(msg)
            self.toast("Message copied to clipboard.", "success")

        ctk.CTkButton(win, text="Copy message", fg_color=self.accent, command=copy).pack(
            anchor="e", padx=24, pady=(0, 20))

    def export_view(self):
        rows = self.filtered_rows()
        if not rows:
            self.toast("No rows to export with the current filters.", "warning")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV", "*.csv")],
            initialdir=str(self.reports_folder), initialfile="filtered_view.csv")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "level", "message"])
            writer.writerows(rows)
        self.toast(f"Exported {len(rows):,} rows.", "success")

    # ---------------- reports ----------------

    def page_reports(self):
        self.header("Reports", "Everything the engine has exported for you.")

        body = ctk.CTkFrame(self.main, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew")
        body.grid_columnconfigure((0, 1), weight=1, uniform="r")
        body.grid_rowconfigure(1, weight=1)

        specs = [("JSON REPORT", "analysis_report.json", "Detailed analysis data, machine readable.", CYAN),
                 ("CSV REPORT", "analysis_report.csv", "Every log entry in spreadsheet-friendly form.", GREEN)]

        for col, (title, filename, desc, color) in enumerate(specs):
            path = self.reports_folder / filename
            exists = path.exists()
            card = self.card(body, row=0, column=col, sticky="nsew",
                             padx=(0 if col == 0 else 8, 8 if col == 0 else 0), pady=(0, 16))
            ctk.CTkLabel(card, text=title, font=(FONT, 15, "bold"), text_color=color).pack(
                anchor="w", padx=22, pady=(20, 2))
            ctk.CTkLabel(card, text=desc, font=(FONT, 12), text_color=MUTED).pack(anchor="w", padx=22)

            if exists:
                st = path.stat()
                meta = f"✔ Generated  •  {st.st_size / 1024:.1f} KB  •  " \
                       f"{datetime.fromtimestamp(st.st_mtime).strftime('%d %b, %H:%M')}"
            else:
                meta = "○ Not generated yet"
            ctk.CTkLabel(card, text=meta, font=(FONT, 11), text_color=GREEN if exists else ORANGE).pack(
                anchor="w", padx=22, pady=10)

            btns = ctk.CTkFrame(card, fg_color="transparent")
            btns.pack(anchor="w", padx=22, pady=(0, 20))
            ctk.CTkButton(btns, text="Open", width=100, height=36, fg_color=self.accent,
                          command=lambda p=path: self.open_report(p)).pack(side="left", padx=(0, 8))
            ctk.CTkButton(btns, text="Preview", width=100, height=36, fg_color=CARD,
                          hover_color=CARD_HOVER,
                          command=lambda p=path: self.preview_report(p)).pack(side="left")

        prev = self.card(body, row=1, column=0, columnspan=2, sticky="nsew")
        prev.grid_rowconfigure(1, weight=1)
        prev.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(prev, text="PREVIEW", font=(FONT, 12, "bold"), text_color=self.accent).grid(
            row=0, column=0, sticky="w", padx=22, pady=(18, 8))
        self.preview_box = ctk.CTkTextbox(prev, fg_color=INPUT, font=("Consolas", 11), corner_radius=12,
                                          border_width=1, border_color=BORDER, wrap="none")
        self.preview_box.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 14))
        self.preview_box.insert("end", "Press Preview on a report to peek inside.")
        self.preview_box.configure(state="disabled")

        ctk.CTkButton(prev, text="📂  Open reports folder", height=38, fg_color=CARD,
                      hover_color=CARD_HOVER,
                      command=lambda: open_path(self.reports_folder)).grid(
            row=2, column=0, sticky="w", padx=20, pady=(0, 18))

    def open_report(self, path):
        if path.exists():
            open_path(path)
        else:
            self.toast("Report not found. Analyze a log file first.", "warning")

    def preview_report(self, path):
        if not path.exists():
            self.toast("Report not found. Analyze a log file first.", "warning")
            return
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            if path.suffix == ".json":
                try:
                    text = json.dumps(json.loads(text), indent=2)
                except ValueError:
                    pass
        except OSError as exc:
            text = f"Could not read file: {exc}"
        self.preview_box.configure(state="normal")
        self.preview_box.delete("1.0", "end")
        self.preview_box.insert("end", text[:12000] + ("\n\n… (truncated)" if len(text) > 12000 else ""))
        self.preview_box.configure(state="disabled")

    # ---------------- settings ----------------

    def page_settings(self):
        self.header("Settings", "Make the workspace yours.")

        body = ctk.CTkScrollableFrame(self.main, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew")
        body.grid_columnconfigure(0, weight=1)

        card = self.card(body, row=0, column=0, sticky="ew", pady=(0, 16))
        self.card_title(card, "ACCENT COLOUR")
        swatches = ctk.CTkFrame(card, fg_color="transparent")
        swatches.pack(anchor="w", padx=22, pady=(0, 22))
        for name, color in ACCENTS.items():
            ctk.CTkButton(swatches, text="✔" if color == self.accent else "", width=46, height=46,
                          corner_radius=23, fg_color=color, hover_color=color,
                          font=(FONT, 16, "bold"),
                          command=lambda c=color: self.set_accent(c)).pack(side="left", padx=(0, 10))

        card2 = self.card(body, row=1, column=0, sticky="ew", pady=(0, 16))
        self.card_title(card2, "INTERFACE")
        ctk.CTkLabel(card2, text="UI scale", font=(FONT, 12), text_color=MUTED).pack(anchor="w", padx=22)
        ctk.CTkOptionMenu(card2, values=["90%", "100%", "110%", "125%"], width=140,
                          command=self.set_scale).pack(anchor="w", padx=22, pady=(4, 14))
        self.anim_switch = ctk.CTkSwitch(card2, text="Animated counters", progress_color=self.accent,
                                         command=self.toggle_anim)
        self.anim_switch.pack(anchor="w", padx=22, pady=(0, 22))
        if self.animations:
            self.anim_switch.select()

        card3 = self.card(body, row=2, column=0, sticky="ew")
        self.card_title(card3, "ABOUT")
        ctk.CTkLabel(card3, text="Log Analyzer Pro  •  v3.0\nBuilt with Python and CustomTkinter\n\n"
                     "Ctrl+O  open file      F5  analyze      Ctrl+K  command palette\n"
                     "Ctrl+F  search entries      Ctrl+B  collapse sidebar",
                     font=(FONT, 12), text_color=WHITE, justify="left").pack(anchor="w", padx=22, pady=(0, 24))

    def set_accent(self, color):
        self.accent = color
        self.navigate("Settings")
        self.toast("Accent updated.", "success")

    def set_scale(self, choice):
        ctk.set_widget_scaling(int(choice.rstrip("%")) / 100)

    def toggle_anim(self):
        self.animations = bool(self.anim_switch.get())

    # ---------------- command palette ----------------

    def open_palette(self):
        commands = [
            ("Go to Dashboard", lambda: self.navigate("Dashboard")),
            ("Go to Analyze", lambda: self.navigate("Analyze")),
            ("Go to Explorer", lambda: self.navigate("Explorer")),
            ("Go to Reports", lambda: self.navigate("Reports")),
            ("Go to Settings", lambda: self.navigate("Settings")),
            ("Browse for a log file", self.browse_file),
            ("Run analysis", self.start_analysis),
            ("Open reports folder", lambda: open_path(self.reports_folder)),
            ("Toggle sidebar", self.toggle_sidebar),
        ]
        win = ctk.CTkToplevel(self)
        win.title("Command Palette")
        win.geometry("520x380")
        win.configure(fg_color=PANEL)
        win.resizable(False, False)
        win.transient(self)
        win.after(120, win.lift)

        entry = ctk.CTkEntry(win, placeholder_text="Type a command…", height=44, corner_radius=10,
                             fg_color=INPUT, border_color=self.accent, font=(FONT, 14))
        entry.pack(fill="x", padx=16, pady=16)
        entry.after(150, entry.focus_set)

        listing = ctk.CTkScrollableFrame(win, fg_color="transparent")
        listing.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        current = []

        def run(action):
            win.destroy()
            self.after(60, action)

        def render(_e=None):
            for w in listing.winfo_children():
                w.destroy()
            q = entry.get().lower().strip()
            current.clear()
            current.extend(c for c in commands if q in c[0].lower())
            for label, action in current:
                ctk.CTkButton(listing, text=f"   {label}", anchor="w", height=38, fg_color="transparent",
                              hover_color=CARD, text_color=WHITE, font=(FONT, 13),
                              command=lambda a=action: run(a)).pack(fill="x", pady=1)

        entry.bind("<KeyRelease>", render)
        entry.bind("<Return>", lambda e: current and run(current[0][1]))
        win.bind("<Escape>", lambda e: win.destroy())
        render()


# ====================== RUN ======================

if __name__ == "__main__":
    app = LogAnalyzerApp()
    app.mainloop()