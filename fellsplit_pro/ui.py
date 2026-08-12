from __future__ import annotations

import ctypes
import os
import queue
import subprocess
import sys
import traceback
from datetime import datetime
from pathlib import Path
from tkinter import BooleanVar, StringVar, messagebox

import customtkinter as ctk

from . import __version__
from .config_store import error_log_path, load_config, save_config
from .controller import ControllerStatus, GameWindowController, RunState
from .hotkey import GlobalHotkeyManager, HotkeySpec, KEY_CODES
from .layout import calculate_layout
from .models import (
    GAME_SIDE_LEFT,
    GAME_SIDE_RIGHT,
    LAYOUT_AUTOMATIC,
    LAYOUT_CUSTOM,
    LAYOUT_EQUAL_HALVES,
    LAYOUT_GAME_16_9,
    AppConfig,
    MonitorInfo,
    TargetRect,
    WindowInfo,
    window_matches,
)
from .startup import sync_windows_startup
from .tray import TrayManager
from . import win32_api as win32


COLORS = {
    "bg": "#080D16",
    "sidebar": "#0B1220",
    "card": "#111A2B",
    "card_alt": "#0E1726",
    "line": "#22304A",
    "text": "#F4F7FC",
    "muted": "#8EA0BA",
    "accent": "#38BDF8",
    "accent_hover": "#0EA5E9",
    "accent_dark": "#082F49",
    "green": "#34D399",
    "amber": "#FBBF24",
    "red": "#FB7185",
}

LAYOUT_LABELS = {
    LAYOUT_AUTOMATIC: "Automatisch passend",
    LAYOUT_EQUAL_HALVES: "50/50 - beide Zonen gleich gross",
    LAYOUT_GAME_16_9: "Spiel 16:9 + Restflaeche",
    LAYOUT_CUSTOM: "Benutzerdefiniert (Pixel)",
}
LAYOUT_MODES_BY_LABEL = {label: mode for mode, label in LAYOUT_LABELS.items()}
GAME_SIDE_LABELS = {
    GAME_SIDE_LEFT: "Spiel links",
    GAME_SIDE_RIGHT: "Spiel rechts",
}
GAME_SIDES_BY_LABEL = {label: side for side, label in GAME_SIDE_LABELS.items()}
PRIMARY_MONITOR_LABEL = "Hauptmonitor automatisch erkennen"


class FellSplitProApp(ctk.CTk):
    TICK_MS = 120

    def __init__(self, single_instance=None) -> None:
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        super().__init__(fg_color=COLORS["bg"])

        self.title(f"FellSplit Pro {__version__}")
        try:
            bundle_root = Path(
                getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1])
            )
            self.iconbitmap(str(bundle_root / "assets" / "FellSplitPro.ico"))
        except Exception:
            # A missing icon must never prevent the safety tool from starting.
            pass
        self.geometry("1080x740")
        self.minsize(980, 680)
        self.protocol("WM_DELETE_WINDOW", self._on_window_close)
        self.bind("<Unmap>", self._on_unmap)

        self.config_data = load_config()
        self._persisted_config = self.config_data
        self.controller = GameWindowController()
        self.app_events: queue.Queue[str] = queue.Queue()
        self.hotkey = GlobalHotkeyManager(self.app_events)
        self.tray = TrayManager(
            self.app_events,
            lambda: self.controller.desired_active,
            version=__version__,
        )
        self.window_items: dict[str, WindowInfo] = {}
        self.monitor_items: dict[str, MonitorInfo | None] = {}
        self.selected_hwnd = 0
        self.selected_secondary_hwnd = 0
        self._last_status_key = ""
        self._closing = False
        self._tray_notice_shown = False
        self._start_hidden = "--minimized" in sys.argv
        self._single_instance = single_instance
        if self._start_hidden:
            self.withdraw()

        self._create_variables()
        self._build_layout()
        self._show_page("Start")
        self._refresh_monitors(show_errors=False)
        self._apply_config_to_ui(self.config_data)
        self._configure_tray()
        self._configure_hotkey(show_dialog=False)
        self._refresh_summary()
        self._display_status(self.controller.status)
        self._log(
            f"FellSplit Pro {__version__} gestartet aus "
            f"{Path(__file__).resolve().parents[1]}. "
            "Windows-Pixelmodus ist aktiv."
        )
        try:
            startup_message = sync_windows_startup(
                self.config_data.start_with_windows,
                self.config_data.start_minimized,
            )
            if self.config_data.start_with_windows:
                self._log(startup_message)
        except (OSError, RuntimeError, ValueError) as exc:
            self._log(f"Autostart konnte nicht synchronisiert werden: {exc}")

        if self.config_data.activate_on_launch:
            self.master_switch.select()
            try:
                self._display_status(self.controller.activate(self.config_data))
            except (ValueError, RuntimeError) as exc:
                self.master_switch.deselect()
                self._log(f"Automatischer Start fehlgeschlagen: {exc}")

        self.after(100, self._refresh_windows)
        self.after(180, self._apply_startup_visibility)
        self.after(self.TICK_MS, self._background_tick)

    def _create_variables(self) -> None:
        cfg = self.config_data
        self.master_enabled = BooleanVar(value=False)
        self.process_var = StringVar(value=cfg.process_name)
        self.title_var = StringVar(value=cfg.title_contains)
        self.auto_detect_var = BooleanVar(value=cfg.auto_detect_games)
        self.auto_exclusions_var = StringVar(value=cfg.auto_excluded_processes)
        self.layout_mode_var = StringVar(
            value=LAYOUT_LABELS.get(cfg.layout_mode, LAYOUT_LABELS[LAYOUT_AUTOMATIC])
        )
        self.monitor_select_var = StringVar(value=PRIMARY_MONITOR_LABEL)
        self.game_side_var = StringVar(
            value=GAME_SIDE_LABELS.get(cfg.game_side, GAME_SIDE_LABELS[GAME_SIDE_LEFT])
        )
        self.x_var = StringVar(value=str(cfg.target_rect.x))
        self.y_var = StringVar(value=str(cfg.target_rect.y))
        self.width_var = StringVar(value=str(cfg.target_rect.width))
        self.height_var = StringVar(value=str(cfg.target_rect.height))
        self.secondary_enabled_var = BooleanVar(value=cfg.secondary_enabled)
        self.secondary_process_var = StringVar(value=cfg.secondary_process_name)
        self.secondary_title_var = StringVar(value=cfg.secondary_title_contains)
        self.secondary_x_var = StringVar(value=str(cfg.secondary_target_rect.x))
        self.secondary_y_var = StringVar(value=str(cfg.secondary_target_rect.y))
        self.secondary_width_var = StringVar(value=str(cfg.secondary_target_rect.width))
        self.secondary_height_var = StringVar(value=str(cfg.secondary_target_rect.height))
        self.secondary_borderless_var = BooleanVar(
            value=cfg.secondary_remove_borders
        )
        self.secondary_focus_frame_var = BooleanVar(
            value=cfg.secondary_show_frame_when_focused
        )
        self.borderless_var = BooleanVar(value=cfg.remove_borders)
        self.cursor_var = BooleanVar(value=cfg.lock_cursor)
        self.restore_var = BooleanVar(value=cfg.restore_window)
        self.keep_position_var = BooleanVar(value=cfg.keep_position)
        self.foreground_var = BooleanVar(value=cfg.foreground_only)
        self.hide_taskbar_var = BooleanVar(
            value=cfg.hide_taskbar_while_game_focused
        )
        self.topmost_var = BooleanVar(value=cfg.always_on_top)
        self.hotkey_enabled_var = BooleanVar(value=cfg.hotkey_enabled)
        self.hotkey_ctrl_var = BooleanVar(value=cfg.hotkey_ctrl)
        self.hotkey_alt_var = BooleanVar(value=cfg.hotkey_alt)
        self.hotkey_shift_var = BooleanVar(value=cfg.hotkey_shift)
        self.hotkey_key_var = StringVar(value=cfg.hotkey_key)
        self.tray_enabled_var = BooleanVar(value=cfg.tray_enabled)
        self.close_to_tray_var = BooleanVar(value=cfg.close_to_tray)
        self.minimize_to_tray_var = BooleanVar(value=cfg.minimize_to_tray)
        self.start_with_windows_var = BooleanVar(value=cfg.start_with_windows)
        self.start_minimized_var = BooleanVar(value=cfg.start_minimized)
        self.activate_on_launch_var = BooleanVar(value=cfg.activate_on_launch)
        self.window_select_var = StringVar(value="Fensterliste wird geladen ...")
        self.secondary_window_select_var = StringVar(
            value="Fensterliste wird geladen ..."
        )

    def _build_layout(self) -> None:
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self.sidebar = ctk.CTkFrame(
            self,
            width=220,
            corner_radius=0,
            fg_color=COLORS["sidebar"],
            border_width=0,
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_rowconfigure(7, weight=1)

        brand = ctk.CTkLabel(
            self.sidebar,
            text="FELLSPLIT PRO",
            font=ctk.CTkFont("Segoe UI", 25, weight="bold"),
            text_color=COLORS["text"],
        )
        brand.grid(row=0, column=0, padx=24, pady=(30, 0), sticky="w")
        ctk.CTkLabel(
            self.sidebar,
            text="ULTRAWIDE DUAL-ZONE",
            font=ctk.CTkFont("Segoe UI", 10, weight="bold"),
            text_color=COLORS["accent"],
        ).grid(row=1, column=0, padx=25, pady=(1, 32), sticky="w")

        self.nav_buttons: dict[str, ctk.CTkButton] = {}
        for row, name in enumerate(("Start", "Einstellungen", "Protokoll"), start=2):
            button = ctk.CTkButton(
                self.sidebar,
                text=name,
                height=46,
                corner_radius=10,
                anchor="w",
                font=ctk.CTkFont("Segoe UI", 14, weight="bold"),
                fg_color="transparent",
                hover_color=COLORS["card"],
                text_color=COLORS["muted"],
                command=lambda page=name: self._show_page(page),
            )
            button.grid(row=row, column=0, padx=16, pady=4, sticky="ew")
            self.nav_buttons[name] = button

        admin_text = "Administrator" if win32.is_admin() else "Standardrechte"
        admin_color = COLORS["green"] if win32.is_admin() else COLORS["amber"]
        ctk.CTkLabel(
            self.sidebar,
            text=f"●  {admin_text}",
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=admin_color,
        ).grid(row=8, column=0, padx=24, pady=(0, 5), sticky="w")
        ctk.CTkLabel(
            self.sidebar,
            text=f"Version {__version__}",
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=COLORS["muted"],
        ).grid(row=9, column=0, padx=24, pady=(0, 24), sticky="w")

        self.content = ctk.CTkFrame(self, fg_color=COLORS["bg"], corner_radius=0)
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

        self.pages: dict[str, ctk.CTkFrame] = {}
        self.pages["Start"] = self._build_home_page()
        self.pages["Einstellungen"] = self._build_settings_page()
        self.pages["Protokoll"] = self._build_log_page()

    def _build_home_page(self) -> ctk.CTkFrame:
        page = ctk.CTkFrame(self.content, fg_color=COLORS["bg"], corner_radius=0)
        page.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            page,
            text="Spielen in deiner Zone. Arbeiten daneben.",
            font=ctk.CTkFont("Segoe UI", 30, weight="bold"),
            text_color=COLORS["text"],
        ).grid(row=0, column=0, padx=36, pady=(32, 0), sticky="w")
        ctk.CTkLabel(
            page,
            text="Flexible Dual-Zone-Layouts fuer 32:9, 21:9 und eigene Aufloesungen.",
            font=ctk.CTkFont("Segoe UI", 13),
            text_color=COLORS["muted"],
        ).grid(row=1, column=0, padx=37, pady=(5, 24), sticky="w")

        hero = ctk.CTkFrame(
            page,
            height=210,
            corner_radius=18,
            fg_color=COLORS["card"],
            border_width=1,
            border_color=COLORS["line"],
        )
        hero.grid(row=2, column=0, padx=36, pady=(0, 18), sticky="ew")
        hero.grid_columnconfigure(0, weight=1)
        hero.grid_propagate(False)

        self.hero_status = ctk.CTkLabel(
            hero,
            text="●  AUSGESCHALTET",
            font=ctk.CTkFont("Segoe UI", 12, weight="bold"),
            text_color=COLORS["muted"],
        )
        self.hero_status.grid(row=0, column=0, padx=28, pady=(26, 0), sticky="w")
        self.hero_title = ctk.CTkLabel(
            hero,
            text="FellSplit Pro aktivieren",
            font=ctk.CTkFont("Segoe UI", 24, weight="bold"),
            text_color=COLORS["text"],
        )
        self.hero_title.grid(row=1, column=0, padx=28, pady=(11, 0), sticky="w")
        self.hero_message = ctk.CTkLabel(
            hero,
            text="Das Spiel wird automatisch gesucht und in die berechnete Spielzone gesetzt.",
            font=ctk.CTkFont("Segoe UI", 12),
            text_color=COLORS["muted"],
            wraplength=570,
            justify="left",
        )
        self.hero_message.grid(row=2, column=0, padx=28, pady=(4, 0), sticky="w")

        self.master_switch = ctk.CTkSwitch(
            hero,
            text="",
            variable=self.master_enabled,
            command=self._handle_master_switch,
            width=98,
            height=46,
            switch_width=92,
            switch_height=42,
            corner_radius=21,
            button_color="#FFFFFF",
            button_hover_color="#E2E8F0",
            fg_color="#334155",
            progress_color=COLORS["accent"],
        )
        self.master_switch.grid(row=0, column=1, rowspan=3, padx=34, pady=(42, 0), sticky="e")
        self.hotkey_hint = ctk.CTkLabel(
            hero,
            text="Hotkey: Strg+Alt+F10",
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=COLORS["muted"],
        )
        self.hotkey_hint.grid(row=3, column=0, columnspan=2, padx=28, pady=(20, 22), sticky="w")

        info = ctk.CTkFrame(
            page,
            corner_radius=18,
            fg_color=COLORS["card_alt"],
            border_width=1,
            border_color=COLORS["line"],
        )
        info.grid(row=3, column=0, padx=36, pady=(0, 18), sticky="ew")
        info.grid_columnconfigure((0, 1), weight=1)

        self.summary_target = self._summary_item(info, 0, 0, "ZIELFENSTER", "Wow.exe")
        self.summary_area = self._summary_item(info, 0, 1, "BEREICH", "2560 x 1440 @ 0, 0")
        self.summary_mouse = self._summary_item(info, 1, 0, "MAUS-LOCK", "Aktiv")
        self.summary_mode = self._summary_item(info, 1, 1, "FENSTERMODUS", "Borderless")

        safety = ctk.CTkFrame(page, fg_color=COLORS["accent_dark"], corner_radius=12)
        safety.grid(row=4, column=0, padx=36, pady=(0, 25), sticky="ew")
        ctk.CTkLabel(
            safety,
            text="Sicherheits-Hinweis",
            font=ctk.CTkFont("Segoe UI", 12, weight="bold"),
            text_color=COLORS["accent"],
        ).grid(row=0, column=0, padx=18, pady=(13, 0), sticky="w")
        ctk.CTkLabel(
            safety,
            text="Mit dem globalen Hotkey kannst du die Maus jederzeit freigeben - auch ohne Alt+Tab.",
            font=ctk.CTkFont("Segoe UI", 11),
            text_color="#BAE6FD",
        ).grid(row=1, column=0, padx=18, pady=(2, 13), sticky="w")
        return page

    def _build_settings_page(self) -> ctk.CTkFrame:
        page = ctk.CTkFrame(self.content, fg_color=COLORS["bg"], corner_radius=0)
        page.grid_rowconfigure(1, weight=1)
        page.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            page,
            text="Einstellungen",
            font=ctk.CTkFont("Segoe UI", 30, weight="bold"),
            text_color=COLORS["text"],
        ).grid(row=0, column=0, padx=36, pady=(30, 14), sticky="w")

        scroll = ctk.CTkScrollableFrame(
            page,
            fg_color="transparent",
            scrollbar_button_color=COLORS["line"],
            scrollbar_button_hover_color=COLORS["accent_hover"],
        )
        scroll.grid(row=1, column=0, sticky="nsew", padx=(25, 18), pady=(0, 12))
        scroll.grid_columnconfigure(0, weight=1)

        target = self._settings_card(scroll, 0, "1  Spielfenster")
        target.grid_columnconfigure(0, weight=1)
        target.grid_columnconfigure(1, weight=0)
        auto_line = ctk.CTkFrame(target, fg_color=COLORS["accent_dark"], corner_radius=10)
        auto_line.grid(row=1, column=0, columnspan=2, padx=20, pady=(9, 12), sticky="ew")
        auto_line.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            auto_line,
            text="Spiele automatisch erkennen",
            font=ctk.CTkFont("Segoe UI", 12, weight="bold"),
            text_color=COLORS["text"],
        ).grid(row=0, column=0, padx=14, pady=(11, 0), sticky="w")
        ctk.CTkLabel(
            auto_line,
            text="Erkennt ein grosses Vordergrundfenster nach kurzer Pruefung; OBS, Browser und Launcher sind ausgeschlossen.",
            font=ctk.CTkFont("Segoe UI", 9),
            text_color="#BAE6FD",
        ).grid(row=1, column=0, padx=14, pady=(0, 11), sticky="w")
        ctk.CTkSwitch(
            auto_line,
            text="",
            variable=self.auto_detect_var,
            width=50,
            switch_width=46,
            switch_height=25,
            progress_color=COLORS["accent"],
        ).grid(row=0, column=1, rowspan=2, padx=14)

        self._field_label(target, "Aktuell geoeffnete Fenster").grid(
            row=2, column=0, padx=20, pady=(0, 5), sticky="w"
        )
        self.window_combo = ctk.CTkComboBox(
            target,
            variable=self.window_select_var,
            values=["Fensterliste wird geladen ..."],
            command=self._on_window_selected,
            height=38,
            corner_radius=8,
            fg_color=COLORS["bg"],
            border_color=COLORS["line"],
            button_color=COLORS["line"],
            button_hover_color=COLORS["accent_hover"],
            dropdown_fg_color=COLORS["card"],
            dropdown_hover_color=COLORS["line"],
            text_color=COLORS["text"],
        )
        self.window_combo.grid(row=3, column=0, padx=(20, 10), pady=(0, 10), sticky="ew")
        ctk.CTkButton(
            target,
            text="Aktualisieren",
            width=116,
            height=38,
            corner_radius=8,
            fg_color=COLORS["line"],
            hover_color=COLORS["accent_hover"],
            command=self._refresh_windows,
        ).grid(row=3, column=1, padx=(0, 20), pady=(0, 10))

        fields = ctk.CTkFrame(target, fg_color="transparent")
        fields.grid(row=4, column=0, columnspan=2, padx=20, pady=(0, 7), sticky="ew")
        fields.grid_columnconfigure((0, 1), weight=1)
        self._labeled_entry(
            fields,
            0,
            "Prozessname (exakt)",
            self.process_var,
            "z. B. Wow.exe",
        )
        self._labeled_entry(
            fields,
            1,
            "Fenstertitel enthaelt (optional)",
            self.title_var,
            "z. B. World of Warcraft",
        )
        ctk.CTkLabel(
            target,
            text="Wenn beide Felder gesetzt sind, muessen beide passen. Keine Regex noetig: Wow.exe statt wow\\.exe.",
            font=ctk.CTkFont("Segoe UI", 10),
            text_color=COLORS["muted"],
        ).grid(row=5, column=0, columnspan=2, padx=20, pady=(0, 8), sticky="w")
        self._field_label(target, "Zusaetzlich nie automatisch auswaehlen (optional, kommagetrennt)").grid(
            row=6, column=0, columnspan=2, padx=20, pady=(0, 4), sticky="w"
        )
        ctk.CTkEntry(
            target,
            textvariable=self.auto_exclusions_var,
            placeholder_text="z. B. Photoshop.exe, Teams.exe",
            height=36,
            corner_radius=8,
            fg_color=COLORS["bg"],
            border_color=COLORS["line"],
            text_color=COLORS["text"],
        ).grid(row=7, column=0, columnspan=2, padx=20, pady=(0, 18), sticky="ew")

        geometry = self._settings_card(scroll, 1, "2  Monitor und Layout")
        geometry.grid_columnconfigure(0, weight=1)

        layout_controls = ctk.CTkFrame(geometry, fg_color="transparent")
        layout_controls.grid(row=1, column=0, padx=20, pady=(8, 12), sticky="ew")
        layout_controls.grid_columnconfigure(0, weight=2)
        layout_controls.grid_columnconfigure(1, weight=3)
        layout_controls.grid_columnconfigure(2, weight=1)

        self._field_label(layout_controls, "Layoutmodus").grid(
            row=0, column=0, padx=(0, 7), pady=(0, 4), sticky="w"
        )
        self._field_label(layout_controls, "Monitor").grid(
            row=0, column=1, padx=7, pady=(0, 4), sticky="w"
        )
        self._field_label(layout_controls, "Spielseite").grid(
            row=0, column=2, padx=(7, 0), pady=(0, 4), sticky="w"
        )
        self.layout_mode_combo = ctk.CTkComboBox(
            layout_controls,
            variable=self.layout_mode_var,
            values=list(LAYOUT_LABELS.values()),
            command=self._on_layout_controls_changed,
            height=38,
            corner_radius=8,
            fg_color=COLORS["bg"],
            border_color=COLORS["line"],
            button_color=COLORS["line"],
            button_hover_color=COLORS["accent_hover"],
            dropdown_fg_color=COLORS["card"],
            dropdown_hover_color=COLORS["line"],
            text_color=COLORS["text"],
            state="readonly",
        )
        self.layout_mode_combo.grid(row=1, column=0, padx=(0, 7), sticky="ew")
        self.monitor_combo = ctk.CTkComboBox(
            layout_controls,
            variable=self.monitor_select_var,
            values=[PRIMARY_MONITOR_LABEL],
            command=self._on_layout_controls_changed,
            height=38,
            corner_radius=8,
            fg_color=COLORS["bg"],
            border_color=COLORS["line"],
            button_color=COLORS["line"],
            button_hover_color=COLORS["accent_hover"],
            dropdown_fg_color=COLORS["card"],
            dropdown_hover_color=COLORS["line"],
            text_color=COLORS["text"],
            state="readonly",
        )
        self.monitor_combo.grid(row=1, column=1, padx=7, sticky="ew")
        self.game_side_combo = ctk.CTkComboBox(
            layout_controls,
            variable=self.game_side_var,
            values=list(GAME_SIDE_LABELS.values()),
            command=self._on_layout_controls_changed,
            height=38,
            corner_radius=8,
            fg_color=COLORS["bg"],
            border_color=COLORS["line"],
            button_color=COLORS["line"],
            button_hover_color=COLORS["accent_hover"],
            dropdown_fg_color=COLORS["card"],
            dropdown_hover_color=COLORS["line"],
            text_color=COLORS["text"],
            state="readonly",
        )
        self.game_side_combo.grid(row=1, column=2, padx=(7, 0), sticky="ew")

        monitor_actions = ctk.CTkFrame(geometry, fg_color="transparent")
        monitor_actions.grid(row=2, column=0, padx=20, pady=(0, 10), sticky="e")
        ctk.CTkButton(
            monitor_actions,
            text="Monitore neu erkennen",
            height=32,
            corner_radius=8,
            fg_color=COLORS["line"],
            hover_color=COLORS["accent_hover"],
            command=self._refresh_monitors,
        ).grid(row=0, column=0)

        self.layout_preview = ctk.CTkFrame(
            geometry,
            height=112,
            fg_color=COLORS["bg"],
            corner_radius=10,
            border_width=1,
            border_color=COLORS["line"],
        )
        self.layout_preview.grid(row=3, column=0, padx=20, pady=(0, 8), sticky="ew")
        self.layout_preview.grid_propagate(False)
        self.preview_game_frame = ctk.CTkFrame(
            self.layout_preview,
            fg_color=COLORS["accent_dark"],
            corner_radius=8,
            border_width=1,
            border_color=COLORS["accent"],
        )
        self.preview_game_label = ctk.CTkLabel(
            self.preview_game_frame,
            text="SPIEL",
            font=ctk.CTkFont("Segoe UI", 11, weight="bold"),
            text_color=COLORS["accent"],
        )
        self.preview_game_label.place(relx=0.5, rely=0.5, anchor="center")
        self.preview_secondary_frame = ctk.CTkFrame(
            self.layout_preview,
            fg_color=COLORS["card"],
            corner_radius=8,
            border_width=1,
            border_color=COLORS["line"],
        )
        self.preview_secondary_label = ctk.CTkLabel(
            self.preview_secondary_frame,
            text="2. FENSTER",
            font=ctk.CTkFont("Segoe UI", 11, weight="bold"),
            text_color=COLORS["text"],
        )
        self.preview_secondary_label.place(relx=0.5, rely=0.5, anchor="center")
        self.layout_preview_text = ctk.CTkLabel(
            geometry,
            text="Layout wird berechnet ...",
            font=ctk.CTkFont("Segoe UI", 10),
            text_color=COLORS["muted"],
            justify="left",
        )
        self.layout_preview_text.grid(row=4, column=0, padx=20, pady=(0, 10), sticky="w")

        self._field_label(
            geometry,
            "Zielbereich des Spiels in echten Pixeln (im manuellen Modus editierbar)",
        ).grid(row=5, column=0, padx=20, pady=(0, 4), sticky="w")
        coord_frame = ctk.CTkFrame(geometry, fg_color="transparent")
        coord_frame.grid(row=6, column=0, padx=20, pady=(0, 12), sticky="ew")
        coord_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)
        self.geometry_entries = []
        for col, (label, variable) in enumerate(
            (("X", self.x_var), ("Y", self.y_var), ("Breite", self.width_var), ("Hoehe", self.height_var))
        ):
            self.geometry_entries.append(
                self._labeled_entry(coord_frame, col, label, variable, label)
            )
        ctk.CTkLabel(
            geometry,
            text=(
                "WICHTIG: Im Spiel normalen Fenstermodus waehlen, nicht den "
                "spieleigenen randlosen Vollbildmodus. FellSplit Pro entfernt den Rahmen."
            ),
            font=ctk.CTkFont("Segoe UI", 10, weight="bold"),
            text_color=COLORS["amber"],
            wraplength=720,
            justify="left",
        ).grid(row=7, column=0, padx=20, pady=(0, 16), sticky="w")

        secondary = self._settings_card(scroll, 2, "3  Zweite Zone / OBS")
        secondary.grid_columnconfigure(0, weight=1)
        secondary.grid_columnconfigure(1, weight=0)
        secondary_line = ctk.CTkFrame(
            secondary,
            fg_color=COLORS["accent_dark"],
            corner_radius=10,
        )
        secondary_line.grid(
            row=1,
            column=0,
            columnspan=2,
            padx=20,
            pady=(9, 12),
            sticky="ew",
        )
        secondary_line.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            secondary_line,
            text="Dual-Zone aktivieren",
            font=ctk.CTkFont("Segoe UI", 12, weight="bold"),
            text_color=COLORS["text"],
        ).grid(row=0, column=0, padx=14, pady=(11, 0), sticky="w")
        ctk.CTkLabel(
            secondary_line,
            text=(
                "Setzt ein zweites Fenster rahmenlos in die freie Zone. "
                "Desktopaufloesung, HDR und Bildwiederholrate bleiben unveraendert."
            ),
            font=ctk.CTkFont("Segoe UI", 9),
            text_color="#BAE6FD",
        ).grid(row=1, column=0, padx=14, pady=(0, 11), sticky="w")
        ctk.CTkSwitch(
            secondary_line,
            text="",
            variable=self.secondary_enabled_var,
            width=50,
            switch_width=46,
            switch_height=25,
            progress_color=COLORS["accent"],
        ).grid(row=0, column=1, rowspan=2, padx=14)

        self._field_label(secondary, "Zweites geoeffnetes Fenster").grid(
            row=2,
            column=0,
            padx=20,
            pady=(0, 5),
            sticky="w",
        )
        self.secondary_window_combo = ctk.CTkComboBox(
            secondary,
            variable=self.secondary_window_select_var,
            values=["Fensterliste wird geladen ..."],
            command=self._on_secondary_window_selected,
            height=38,
            corner_radius=8,
            fg_color=COLORS["bg"],
            border_color=COLORS["line"],
            button_color=COLORS["line"],
            button_hover_color=COLORS["accent_hover"],
            dropdown_fg_color=COLORS["card"],
            dropdown_hover_color=COLORS["line"],
            text_color=COLORS["text"],
        )
        self.secondary_window_combo.grid(
            row=3,
            column=0,
            padx=(20, 10),
            pady=(0, 10),
            sticky="ew",
        )
        ctk.CTkButton(
            secondary,
            text="Aktualisieren",
            width=116,
            height=38,
            corner_radius=8,
            fg_color=COLORS["line"],
            hover_color=COLORS["accent_hover"],
            command=self._refresh_windows,
        ).grid(row=3, column=1, padx=(0, 20), pady=(0, 10))

        secondary_fields = ctk.CTkFrame(secondary, fg_color="transparent")
        secondary_fields.grid(
            row=4,
            column=0,
            columnspan=2,
            padx=20,
            pady=(0, 9),
            sticky="ew",
        )
        secondary_fields.grid_columnconfigure((0, 1), weight=1)
        self._labeled_entry(
            secondary_fields,
            0,
            "Prozessname (exakt)",
            self.secondary_process_var,
            "z. B. obs64.exe",
        )
        self._labeled_entry(
            secondary_fields,
            1,
            "Fenstertitel enthaelt (optional)",
            self.secondary_title_var,
            "z. B. OBS",
        )

        secondary_coords = ctk.CTkFrame(secondary, fg_color="transparent")
        secondary_coords.grid(
            row=5,
            column=0,
            columnspan=2,
            padx=20,
            pady=(0, 10),
            sticky="ew",
        )
        secondary_coords.grid_columnconfigure((0, 1, 2, 3), weight=1)
        self.secondary_geometry_entries = []
        for col, (label, variable) in enumerate(
            (
                ("X", self.secondary_x_var),
                ("Y", self.secondary_y_var),
                ("Breite", self.secondary_width_var),
                ("Hoehe", self.secondary_height_var),
            )
        ):
            self.secondary_geometry_entries.append(
                self._labeled_entry(
                    secondary_coords,
                    col,
                    label,
                    variable,
                    label,
                )
            )

        secondary_actions = ctk.CTkFrame(secondary, fg_color="transparent")
        secondary_actions.grid(
            row=6,
            column=0,
            columnspan=2,
            padx=20,
            pady=(0, 8),
            sticky="w",
        )
        ctk.CTkButton(
            secondary_actions,
            text="Layout neu berechnen",
            height=34,
            corner_radius=8,
            fg_color=COLORS["line"],
            hover_color=COLORS["accent_hover"],
            command=self._on_layout_controls_changed,
        ).grid(row=0, column=0, padx=(0, 8))
        ctk.CTkLabel(
            secondary_actions,
            text="Spiel: normaler Fenstermodus | OBS: automatisch in die freie Zone",
            font=ctk.CTkFont("Segoe UI", 9),
            text_color=COLORS["muted"],
        ).grid(row=0, column=1, padx=8)
        self._option_switch(
            secondary,
            7,
            0,
            "OBS-Rahmen entfernen",
            "Fuellt die zweite Zone ohne Titelleiste.",
            self.secondary_borderless_var,
        )
        self._option_switch(
            secondary,
            7,
            1,
            "Fensterleiste bei OBS-Fokus zeigen",
            "Alt+Tab zu OBS blendet Minimieren, Maximieren und X ein.",
            self.secondary_focus_frame_var,
        )

        behavior = self._settings_card(scroll, 3, "4  Verhalten")
        behavior.grid_columnconfigure((0, 1), weight=1)
        self._option_switch(
            behavior,
            1,
            0,
            "Rahmen und Titelleiste entfernen",
            "Erzwingt echtes Borderless Window.",
            self.borderless_var,
        )
        self._option_switch(
            behavior,
            1,
            1,
            "Maus im Zielbereich sperren",
            "ClipCursor auf den eingestellten Bereich.",
            self.cursor_var,
        )
        self._option_switch(
            behavior,
            2,
            0,
            "Beim Ausschalten wiederherstellen",
            "Stil, Position und Fensterstatus zuruecksetzen.",
            self.restore_var,
        )
        self._option_switch(
            behavior,
            2,
            1,
            "Position automatisch halten",
            "Korrigiert Spiele, die sich selbst verschieben.",
            self.keep_position_var,
        )
        self._option_switch(
            behavior,
            3,
            0,
            "Alt+Tab-sicherer Maus-Lock",
            "Maus sofort frei, sobald das Spiel den Fokus verliert.",
            self.foreground_var,
        )
        self._option_switch(
            behavior,
            3,
            1,
            "Fenster immer im Vordergrund",
            "Wird bei Alt+Tab automatisch temporaer geloest.",
            self.topmost_var,
        )
        self._option_switch(
            behavior,
            4,
            0,
            "Taskleiste beim Spielen verstecken",
            "Bleibt auch am unteren Rand zu; Alt+Tab stellt sie wieder her.",
            self.hide_taskbar_var,
        )

        hotkey = self._settings_card(scroll, 4, "5  Globaler Sicherheits-Hotkey")
        hotkey.grid_columnconfigure(0, weight=1)
        hotkey_line = ctk.CTkFrame(hotkey, fg_color="transparent")
        hotkey_line.grid(row=1, column=0, padx=20, pady=(8, 17), sticky="ew")
        ctk.CTkSwitch(
            hotkey_line,
            text="Hotkey aktiv",
            variable=self.hotkey_enabled_var,
            progress_color=COLORS["accent"],
        ).grid(row=0, column=0, padx=(0, 18))
        for col, (text, variable) in enumerate(
            (("Strg", self.hotkey_ctrl_var), ("Alt", self.hotkey_alt_var), ("Umschalt", self.hotkey_shift_var)),
            start=1,
        ):
            ctk.CTkCheckBox(
                hotkey_line,
                text=text,
                variable=variable,
                width=78,
                fg_color=COLORS["accent"],
                hover_color=COLORS["accent_hover"],
                border_color=COLORS["line"],
            ).grid(row=0, column=col, padx=4)
        self.hotkey_key_combo = ctk.CTkComboBox(
            hotkey_line,
            variable=self.hotkey_key_var,
            values=list(KEY_CODES.keys()),
            width=105,
            height=34,
            fg_color=COLORS["bg"],
            border_color=COLORS["line"],
            button_color=COLORS["line"],
            dropdown_fg_color=COLORS["card"],
        )
        self.hotkey_key_combo.grid(row=0, column=5, padx=(12, 0))

        integration = self._settings_card(scroll, 5, "6  System-Tray und Windows-Start")
        integration.grid_columnconfigure((0, 1), weight=1)
        self._option_switch(
            integration,
            1,
            0,
            "System-Tray aktivieren",
            "Steuerung ueber das Symbol neben der Uhr.",
            self.tray_enabled_var,
        )
        self._option_switch(
            integration,
            1,
            1,
            "Schliessen minimiert in Tray",
            "Das X beendet die Automatik nicht.",
            self.close_to_tray_var,
        )
        self._option_switch(
            integration,
            2,
            0,
            "Minimieren blendet Fenster aus",
            "Nur das Tray-Symbol bleibt sichtbar.",
            self.minimize_to_tray_var,
        )
        self._option_switch(
            integration,
            2,
            1,
            "Mit Windows starten",
            "Autostart nur fuer deinen Benutzeraccount.",
            self.start_with_windows_var,
        )
        self._option_switch(
            integration,
            3,
            0,
            "Bei Windows-Start minimiert",
            "Startet unsichtbar direkt im Tray.",
            self.start_minimized_var,
        )
        self._option_switch(
            integration,
            3,
            1,
            "Automatik beim App-Start aktiv",
            "Wartet ohne weiteren Klick auf ein Spiel.",
            self.activate_on_launch_var,
        )

        actions = ctk.CTkFrame(scroll, fg_color="transparent")
        actions.grid(row=6, column=0, padx=8, pady=(4, 24), sticky="ew")
        actions.grid_columnconfigure(0, weight=1)
        self.settings_feedback = ctk.CTkLabel(
            actions,
            text="",
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=COLORS["green"],
        )
        self.settings_feedback.grid(row=0, column=0, sticky="w")
        if not win32.is_admin():
            ctk.CTkButton(
                actions,
                text="Als Administrator neu starten",
                height=40,
                corner_radius=9,
                fg_color=COLORS["line"],
                hover_color="#334155",
                command=self._restart_as_admin,
            ).grid(row=0, column=1, padx=(8, 10))
        ctk.CTkButton(
            actions,
            text="Einstellungen speichern",
            height=40,
            corner_radius=9,
            fg_color=COLORS["accent_hover"],
            hover_color=COLORS["accent"],
            text_color="#FFFFFF",
            font=ctk.CTkFont("Segoe UI", 12, weight="bold"),
            command=self._save_settings,
        ).grid(row=0, column=2)
        return page

    def _build_log_page(self) -> ctk.CTkFrame:
        page = ctk.CTkFrame(self.content, fg_color=COLORS["bg"], corner_radius=0)
        page.grid_rowconfigure(2, weight=1)
        page.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            page,
            text="Protokoll",
            font=ctk.CTkFont("Segoe UI", 30, weight="bold"),
            text_color=COLORS["text"],
        ).grid(row=0, column=0, padx=36, pady=(30, 0), sticky="w")
        ctk.CTkLabel(
            page,
            text="Nur diese Programmsitzung; es werden keine Spieldaten gespeichert.",
            font=ctk.CTkFont("Segoe UI", 12),
            text_color=COLORS["muted"],
        ).grid(row=1, column=0, padx=37, pady=(5, 18), sticky="w")
        self.log_box = ctk.CTkTextbox(
            page,
            corner_radius=14,
            fg_color=COLORS["card_alt"],
            border_width=1,
            border_color=COLORS["line"],
            text_color="#CBD5E1",
            font=ctk.CTkFont("Cascadia Mono", 11),
            wrap="word",
        )
        self.log_box.grid(row=2, column=0, padx=36, pady=(0, 18), sticky="nsew")
        self.log_box.configure(state="disabled")
        ctk.CTkButton(
            page,
            text="Protokoll leeren",
            width=140,
            height=36,
            fg_color=COLORS["line"],
            hover_color="#334155",
            command=self._clear_log,
        ).grid(row=3, column=0, padx=36, pady=(0, 28), sticky="e")
        return page

    def _summary_item(
        self,
        parent: ctk.CTkFrame,
        row: int,
        column: int,
        label: str,
        value: str,
    ) -> ctk.CTkLabel:
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=row, column=column, padx=25, pady=16, sticky="ew")
        ctk.CTkLabel(
            frame,
            text=label,
            font=ctk.CTkFont("Segoe UI", 9, weight="bold"),
            text_color=COLORS["accent"],
        ).grid(row=0, column=0, sticky="w")
        value_label = ctk.CTkLabel(
            frame,
            text=value,
            font=ctk.CTkFont("Segoe UI", 13, weight="bold"),
            text_color=COLORS["text"],
        )
        value_label.grid(row=1, column=0, pady=(2, 0), sticky="w")
        return value_label

    def _settings_card(self, parent: ctk.CTkFrame, row: int, title: str) -> ctk.CTkFrame:
        card = ctk.CTkFrame(
            parent,
            fg_color=COLORS["card_alt"],
            corner_radius=14,
            border_width=1,
            border_color=COLORS["line"],
        )
        card.grid(row=row, column=0, padx=8, pady=(0, 14), sticky="ew")
        ctk.CTkLabel(
            card,
            text=title,
            font=ctk.CTkFont("Segoe UI", 15, weight="bold"),
            text_color=COLORS["text"],
        ).grid(row=0, column=0, columnspan=2, padx=20, pady=(17, 4), sticky="w")
        return card

    def _field_label(self, parent: ctk.CTkFrame, text: str) -> ctk.CTkLabel:
        return ctk.CTkLabel(
            parent,
            text=text,
            font=ctk.CTkFont("Segoe UI", 11, weight="bold"),
            text_color=COLORS["muted"],
        )

    def _labeled_entry(
        self,
        parent: ctk.CTkFrame,
        column: int,
        label: str,
        variable: StringVar,
        placeholder: str,
    ) -> ctk.CTkEntry:
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=0, column=column, padx=(0 if column == 0 else 6, 6), sticky="ew")
        self._field_label(frame, label).grid(row=0, column=0, pady=(0, 4), sticky="w")
        entry = ctk.CTkEntry(
            frame,
            textvariable=variable,
            placeholder_text=placeholder,
            height=38,
            corner_radius=8,
            fg_color=COLORS["bg"],
            border_color=COLORS["line"],
            text_color=COLORS["text"],
        )
        entry.grid(row=1, column=0, sticky="ew")
        frame.grid_columnconfigure(0, weight=1)
        return entry

    def _option_switch(
        self,
        parent: ctk.CTkFrame,
        row: int,
        column: int,
        title: str,
        description: str,
        variable: BooleanVar,
    ) -> None:
        frame = ctk.CTkFrame(parent, fg_color=COLORS["card"], corner_radius=10)
        frame.grid(row=row, column=column, padx=(20 if column == 0 else 7, 20 if column == 1 else 7), pady=7, sticky="ew")
        frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            frame,
            text=title,
            font=ctk.CTkFont("Segoe UI", 11, weight="bold"),
            text_color=COLORS["text"],
        ).grid(row=0, column=0, padx=(14, 5), pady=(12, 0), sticky="w")
        ctk.CTkLabel(
            frame,
            text=description,
            font=ctk.CTkFont("Segoe UI", 9),
            text_color=COLORS["muted"],
        ).grid(row=1, column=0, padx=(14, 5), pady=(0, 12), sticky="w")
        ctk.CTkSwitch(
            frame,
            text="",
            variable=variable,
            width=48,
            switch_width=44,
            switch_height=24,
            progress_color=COLORS["accent"],
        ).grid(row=0, column=1, rowspan=2, padx=12)

    def _show_page(self, page_name: str) -> None:
        for name, page in self.pages.items():
            if name == page_name:
                page.grid(row=0, column=0, sticky="nsew")
            else:
                page.grid_forget()
        for name, button in self.nav_buttons.items():
            selected = name == page_name
            button.configure(
                fg_color=COLORS["card"] if selected else "transparent",
                text_color=COLORS["text"] if selected else COLORS["muted"],
            )

    def _apply_config_to_ui(self, config: AppConfig) -> None:
        self.selected_hwnd = config.selected_hwnd
        self.selected_secondary_hwnd = config.secondary_selected_hwnd
        self.process_var.set(config.process_name)
        self.title_var.set(config.title_contains)
        self.auto_detect_var.set(config.auto_detect_games)
        self.auto_exclusions_var.set(config.auto_excluded_processes)
        self.layout_mode_var.set(
            LAYOUT_LABELS.get(config.layout_mode, LAYOUT_LABELS[LAYOUT_AUTOMATIC])
        )
        self.game_side_var.set(
            GAME_SIDE_LABELS.get(config.game_side, GAME_SIDE_LABELS[GAME_SIDE_LEFT])
        )
        self._select_monitor_in_ui(config.monitor_id)
        self.x_var.set(str(config.target_rect.x))
        self.y_var.set(str(config.target_rect.y))
        self.width_var.set(str(config.target_rect.width))
        self.height_var.set(str(config.target_rect.height))
        self.secondary_enabled_var.set(config.secondary_enabled)
        self.secondary_process_var.set(config.secondary_process_name)
        self.secondary_title_var.set(config.secondary_title_contains)
        self.secondary_x_var.set(str(config.secondary_target_rect.x))
        self.secondary_y_var.set(str(config.secondary_target_rect.y))
        self.secondary_width_var.set(str(config.secondary_target_rect.width))
        self.secondary_height_var.set(str(config.secondary_target_rect.height))
        self.secondary_borderless_var.set(config.secondary_remove_borders)
        self.secondary_focus_frame_var.set(
            config.secondary_show_frame_when_focused
        )
        self.borderless_var.set(config.remove_borders)
        self.cursor_var.set(config.lock_cursor)
        self.restore_var.set(config.restore_window)
        self.keep_position_var.set(config.keep_position)
        self.foreground_var.set(config.foreground_only)
        self.hide_taskbar_var.set(config.hide_taskbar_while_game_focused)
        self.topmost_var.set(config.always_on_top)
        self.hotkey_enabled_var.set(config.hotkey_enabled)
        self.hotkey_ctrl_var.set(config.hotkey_ctrl)
        self.hotkey_alt_var.set(config.hotkey_alt)
        self.hotkey_shift_var.set(config.hotkey_shift)
        self.hotkey_key_var.set(config.hotkey_key)
        self.tray_enabled_var.set(config.tray_enabled)
        self.close_to_tray_var.set(config.close_to_tray)
        self.minimize_to_tray_var.set(config.minimize_to_tray)
        self.start_with_windows_var.set(config.start_with_windows)
        self.start_minimized_var.set(config.start_minimized)
        self.activate_on_launch_var.set(config.activate_on_launch)
        self._on_layout_controls_changed(show_feedback=False)

    def _refresh_monitors(self, show_errors: bool = True) -> None:
        preferred_id = (
            self._monitor_id_from_ui()
            if self.monitor_items
            else self.config_data.monitor_id
        )
        self.monitor_items = {PRIMARY_MONITOR_LABEL: None}
        try:
            for monitor in win32.enumerate_monitors():
                label = monitor.display_name
                if label in self.monitor_items:
                    label = f"{label} ({monitor.identifier})"
                self.monitor_items[label] = monitor
            self.monitor_combo.configure(values=list(self.monitor_items.keys()))
            found = self._select_monitor_in_ui(preferred_id)
            self._on_layout_controls_changed(show_feedback=False)
            if show_errors:
                note = "Monitore neu erkannt."
                if not found and preferred_id != "primary":
                    note += " Der zuvor gewaehlte Monitor fehlt; Hauptmonitor wird verwendet."
                self.settings_feedback.configure(
                    text=note,
                    text_color=COLORS["accent"],
                )
        except Exception as exc:
            self.monitor_combo.configure(values=[PRIMARY_MONITOR_LABEL])
            self.monitor_select_var.set(PRIMARY_MONITOR_LABEL)
            if show_errors:
                messagebox.showerror(
                    "Monitore konnten nicht erkannt werden",
                    str(exc),
                    parent=self,
                )

    def _select_monitor_in_ui(self, monitor_id: str) -> bool:
        if not monitor_id or monitor_id.casefold() == "primary":
            self.monitor_select_var.set(PRIMARY_MONITOR_LABEL)
            return True
        query = monitor_id.casefold()
        for label, monitor in self.monitor_items.items():
            if monitor is not None and monitor.identifier.casefold() == query:
                self.monitor_select_var.set(label)
                return True
        self.monitor_select_var.set(PRIMARY_MONITOR_LABEL)
        return False

    def _monitor_id_from_ui(self) -> str:
        monitor = self.monitor_items.get(self.monitor_select_var.get())
        return monitor.identifier if monitor is not None else "primary"

    def _selected_monitor(self) -> MonitorInfo:
        selected = self.monitor_items.get(self.monitor_select_var.get())
        if selected is not None:
            return selected
        return win32.get_monitor_by_id("primary")

    def _on_layout_controls_changed(
        self,
        _selected_value: str | None = None,
        *,
        show_feedback: bool = True,
    ) -> None:
        mode = LAYOUT_MODES_BY_LABEL.get(
            self.layout_mode_var.get(),
            LAYOUT_AUTOMATIC,
        )
        custom = mode == LAYOUT_CUSTOM
        entry_state = "normal" if custom else "disabled"
        for entry in (*self.geometry_entries, *self.secondary_geometry_entries):
            entry.configure(state=entry_state)

        try:
            if custom:
                game, secondary = self._read_rects_from_ui()
                self._render_layout_preview(
                    game,
                    secondary,
                    "Benutzerdefiniertes Pixel-Layout",
                )
                feedback = "Manuelle Pixelwerte sind freigeschaltet."
            else:
                monitor = self._selected_monitor()
                side = GAME_SIDES_BY_LABEL.get(
                    self.game_side_var.get(),
                    GAME_SIDE_LEFT,
                )
                layout = calculate_layout(monitor.rect, mode, side)
                self._write_layout_rects(layout.game, layout.secondary)
                effective = LAYOUT_LABELS.get(
                    layout.effective_mode,
                    layout.effective_mode,
                )
                title = (
                    f"Automatik -> {effective}"
                    if mode == LAYOUT_AUTOMATIC
                    else effective
                )
                self._render_layout_preview(layout.game, layout.secondary, title)
                feedback = (
                    f"{monitor.rect.width} x {monitor.rect.height}: Spiel "
                    f"{layout.game.width} x {layout.game.height}, zweite Zone "
                    f"{layout.secondary.width} x {layout.secondary.height}."
                )
            if show_feedback and hasattr(self, "settings_feedback"):
                self.settings_feedback.configure(
                    text=feedback,
                    text_color=COLORS["accent"],
                )
        except (ValueError, RuntimeError) as exc:
            self.layout_preview_text.configure(
                text=f"Layout kann nicht berechnet werden: {exc}",
                text_color=COLORS["red"],
            )
            if show_feedback and hasattr(self, "settings_feedback"):
                self.settings_feedback.configure(
                    text=str(exc),
                    text_color=COLORS["red"],
                )

    def _read_rects_from_ui(self) -> tuple[TargetRect, TargetRect]:
        try:
            game = TargetRect(
                x=int(self.x_var.get().strip()),
                y=int(self.y_var.get().strip()),
                width=int(self.width_var.get().strip()),
                height=int(self.height_var.get().strip()),
            )
            secondary = TargetRect(
                x=int(self.secondary_x_var.get().strip()),
                y=int(self.secondary_y_var.get().strip()),
                width=int(self.secondary_width_var.get().strip()),
                height=int(self.secondary_height_var.get().strip()),
            )
        except ValueError as exc:
            raise ValueError(
                "X, Y, Breite und Hoehe beider Zonen muessen ganze Zahlen sein."
            ) from exc
        game.validate()
        secondary.validate()
        return game, secondary

    def _write_layout_rects(self, game: TargetRect, secondary: TargetRect) -> None:
        self.x_var.set(str(game.x))
        self.y_var.set(str(game.y))
        self.width_var.set(str(game.width))
        self.height_var.set(str(game.height))
        self.secondary_x_var.set(str(secondary.x))
        self.secondary_y_var.set(str(secondary.y))
        self.secondary_width_var.set(str(secondary.width))
        self.secondary_height_var.set(str(secondary.height))

    def _render_layout_preview(
        self,
        game: TargetRect,
        secondary: TargetRect,
        title: str,
    ) -> None:
        combined_width = max(1, game.width + secondary.width)
        game_fraction = game.width / combined_width
        secondary_fraction = secondary.width / combined_width
        game_first = game.x <= secondary.x
        game_x = 0.0 if game_first else secondary_fraction
        secondary_x = game_fraction if game_first else 0.0
        self.preview_game_frame.place(
            relx=game_x,
            rely=0.05,
            relwidth=game_fraction,
            relheight=0.9,
        )
        self.preview_secondary_frame.place(
            relx=secondary_x,
            rely=0.05,
            relwidth=secondary_fraction,
            relheight=0.9,
        )
        self.preview_game_label.configure(
            text=f"SPIEL\n{game.width} x {game.height}"
        )
        self.preview_secondary_label.configure(
            text=f"2. FENSTER\n{secondary.width} x {secondary.height}"
        )
        self.layout_preview_text.configure(
            text=(
                f"{title} | Spiel bei ({game.x}, {game.y}) | "
                f"zweite Zone bei ({secondary.x}, {secondary.y})"
            ),
            text_color=COLORS["muted"],
        )

    def _config_from_ui(self) -> AppConfig:
        rect, secondary_rect = self._read_rects_from_ui()
        layout_mode = LAYOUT_MODES_BY_LABEL.get(
            self.layout_mode_var.get(),
            LAYOUT_AUTOMATIC,
        )
        game_side = GAME_SIDES_BY_LABEL.get(
            self.game_side_var.get(),
            GAME_SIDE_LEFT,
        )
        monitor_id = self._monitor_id_from_ui()
        if layout_mode != LAYOUT_CUSTOM:
            monitor = self._selected_monitor()
            layout = calculate_layout(monitor.rect, layout_mode, game_side)
            rect = layout.game
            secondary_rect = layout.secondary
            self._write_layout_rects(rect, secondary_rect)

        virtual_screen = win32.get_virtual_screen_rect()
        is_outside = (
            rect.right <= virtual_screen.x
            or rect.x >= virtual_screen.right
            or rect.bottom <= virtual_screen.y
            or rect.y >= virtual_screen.bottom
        )
        if is_outside:
            raise ValueError(
                "Der Zielbereich liegt vollstaendig ausserhalb des aktuellen Windows-Desktops."
            )
        secondary_is_outside = (
            secondary_rect.right <= virtual_screen.x
            or secondary_rect.x >= virtual_screen.right
            or secondary_rect.bottom <= virtual_screen.y
            or secondary_rect.y >= virtual_screen.bottom
        )
        if self.secondary_enabled_var.get() and secondary_is_outside:
            raise ValueError(
                "Die zweite Zone liegt vollstaendig ausserhalb des aktuellen Windows-Desktops."
            )

        process = self.process_var.get().strip().strip('"').replace("\\.", ".")
        process = process.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]
        secondary_process = (
            self.secondary_process_var.get()
            .strip()
            .strip('"')
            .replace("\\.", ".")
        )
        secondary_process = secondary_process.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]

        selected_hwnd = self.selected_hwnd
        selected_info = next(
            (item for item in self.window_items.values() if item.hwnd == selected_hwnd),
            None,
        )
        if selected_info is None or not window_matches(
            selected_info,
            process,
            self.title_var.get().strip(),
        ):
            selected_hwnd = 0

        secondary_selected_hwnd = self.selected_secondary_hwnd
        secondary_selected_info = next(
            (
                item
                for item in self.window_items.values()
                if item.hwnd == secondary_selected_hwnd
            ),
            None,
        )
        if secondary_selected_info is None or not window_matches(
            secondary_selected_info,
            secondary_process,
            self.secondary_title_var.get().strip(),
        ):
            secondary_selected_hwnd = 0

        config = AppConfig(
            process_name=process,
            title_contains=self.title_var.get().strip(),
            selected_hwnd=selected_hwnd,
            auto_detect_games=self.auto_detect_var.get(),
            auto_excluded_processes=self.auto_exclusions_var.get().strip(),
            layout_mode=layout_mode,
            monitor_id=monitor_id,
            game_side=game_side,
            target_rect=rect,
            secondary_enabled=self.secondary_enabled_var.get(),
            secondary_process_name=secondary_process,
            secondary_title_contains=self.secondary_title_var.get().strip(),
            secondary_selected_hwnd=secondary_selected_hwnd,
            secondary_target_rect=secondary_rect,
            secondary_remove_borders=self.secondary_borderless_var.get(),
            secondary_show_frame_when_focused=(
                self.secondary_focus_frame_var.get()
            ),
            remove_borders=self.borderless_var.get(),
            lock_cursor=self.cursor_var.get(),
            restore_window=self.restore_var.get(),
            keep_position=self.keep_position_var.get(),
            foreground_only=self.foreground_var.get(),
            hide_taskbar_while_game_focused=self.hide_taskbar_var.get(),
            always_on_top=self.topmost_var.get(),
            hotkey_enabled=self.hotkey_enabled_var.get(),
            hotkey_ctrl=self.hotkey_ctrl_var.get(),
            hotkey_alt=self.hotkey_alt_var.get(),
            hotkey_shift=self.hotkey_shift_var.get(),
            hotkey_key=self.hotkey_key_var.get().upper(),
            tray_enabled=self.tray_enabled_var.get(),
            close_to_tray=self.close_to_tray_var.get(),
            minimize_to_tray=self.minimize_to_tray_var.get(),
            start_with_windows=self.start_with_windows_var.get(),
            start_minimized=self.start_minimized_var.get(),
            activate_on_launch=self.activate_on_launch_var.get(),
        )
        if (
            not config.auto_detect_games
            and not config.process_name
            and not config.title_contains
            and not config.selected_hwnd
        ):
            raise ValueError(
                "Bitte ein Zielfenster angeben oder die automatische Spiel-Erkennung aktivieren."
            )
        if config.secondary_enabled and not (
            config.secondary_process_name
            or config.secondary_title_contains
            or config.secondary_selected_hwnd
        ):
            raise ValueError("Bitte ein zweites Fenster fuer die zweite Zone angeben.")
        if (
            config.secondary_enabled
            and config.selected_hwnd
            and config.selected_hwnd == config.secondary_selected_hwnd
        ):
            raise ValueError("Spiel und zweite Zone duerfen nicht dasselbe Fenster sein.")
        zones_overlap = (
            config.target_rect.x < config.secondary_target_rect.right
            and config.target_rect.right > config.secondary_target_rect.x
            and config.target_rect.y < config.secondary_target_rect.bottom
            and config.target_rect.bottom > config.secondary_target_rect.y
        )
        if config.secondary_enabled and zones_overlap:
            raise ValueError("Spiel- und zweite Zielzone duerfen sich nicht ueberlappen.")
        if (config.close_to_tray or config.minimize_to_tray or config.start_minimized) and not config.tray_enabled:
            raise ValueError(
                "Schliessen/Minimieren in den Tray setzt ein aktiviertes System-Tray voraus."
            )
        if config.hotkey_enabled:
            self._hotkey_spec(config).validate()
        return config

    def _save_settings(
        self,
        show_dialog: bool = True,
        *,
        apply_controller: bool = True,
    ) -> bool:
        try:
            config = self._config_from_ui()
            save_config(config)
            startup_message = ""
            if (
                apply_controller
                or config.start_with_windows
                or self._persisted_config.start_with_windows
            ):
                startup_message = sync_windows_startup(
                    config.start_with_windows,
                    config.start_minimized,
                )
            self.config_data = config
            self._persisted_config = config
            status = (
                self.controller.reconfigure(config)
                if apply_controller
                else self.controller.status
            )
            tray_ok = self._configure_tray()
            hotkey_ok = self._configure_hotkey(show_dialog=False)
            self._refresh_summary()
            self._display_status(status)
            feedback = "Einstellungen gespeichert."
            if startup_message:
                feedback += f" {startup_message}"
            if not hotkey_ok and config.hotkey_enabled:
                feedback += " Hotkey ist belegt oder nicht verfuegbar."
            if not tray_ok and config.tray_enabled:
                feedback += " System-Tray konnte nicht gestartet werden."
            self.settings_feedback.configure(
                text=feedback,
                text_color=(
                    COLORS["green"]
                    if (hotkey_ok or not config.hotkey_enabled)
                    and (tray_ok or not config.tray_enabled)
                    else COLORS["amber"]
                ),
            )
            self._log(feedback)
            return True
        except (ValueError, OSError, RuntimeError) as exc:
            self.settings_feedback.configure(text=str(exc), text_color=COLORS["red"])
            if show_dialog:
                messagebox.showerror("Einstellungen pruefen", str(exc), parent=self)
            return False

    def _handle_master_switch(self) -> None:
        if self.master_enabled.get():
            if not self._save_settings(show_dialog=True, apply_controller=False):
                self.master_switch.deselect()
                return
            try:
                status = self.controller.activate(self.config_data)
            except (ValueError, RuntimeError) as exc:
                self.master_switch.deselect()
                messagebox.showerror(
                    "FellSplit Pro konnte nicht starten",
                    str(exc),
                    parent=self,
                )
                self._log(f"Aktivierung abgebrochen: {exc}")
                return
        else:
            status = self.controller.deactivate()
        self._display_status(status)

    def _background_tick(self) -> None:
        if self._closing:
            return
        if (
            self._single_instance is not None
            and self._single_instance.consume_show_request()
        ):
            self._show_window()
        try:
            while True:
                event = self.app_events.get_nowait()
                if event == "toggle":
                    if self.master_enabled.get():
                        self.master_switch.deselect()
                    else:
                        self.master_switch.select()
                    self._handle_master_switch()
                elif event == "show":
                    self._show_window()
                elif event == "exit":
                    self._exit_app()
        except queue.Empty:
            pass

        if self.controller.desired_active:
            status = self.controller.tick()
            self._display_status(status)
        self.after(self.TICK_MS, self._background_tick)

    def _display_status(self, status: ControllerStatus) -> None:
        state_style = {
            RunState.OFF: (
                "●  AUSGESCHALTET",
                COLORS["muted"],
                "FellSplit Pro aktivieren",
            ),
            RunState.WAITING: ("●  WARTET AUF SPIEL", COLORS["amber"], "Automatik ist bereit"),
            RunState.POSITIONING: (
                "●  FENSTER WIRD ANGEPASST",
                COLORS["amber"],
                "Maus bleibt vorerst frei",
            ),
            RunState.ACTIVE: ("●  AKTIV", COLORS["green"], "Spielbereich ist gesperrt"),
            RunState.ERROR: ("●  FEHLER", COLORS["red"], "Eingriff nicht moeglich"),
        }
        label, color, title = state_style[status.state]
        self.hero_status.configure(text=label, text_color=color)
        self.hero_title.configure(text=title)
        self.hero_message.configure(text=status.message)

        key = f"{status.state.value}|{status.message}"
        if key != self._last_status_key:
            self._last_status_key = key
            self._log(status.message)
            self.tray.update(status.message)

    def _refresh_summary(self) -> None:
        cfg = self.config_data
        game_rect = cfg.target_rect
        secondary_rect = cfg.secondary_target_rect
        layout_text = LAYOUT_LABELS.get(cfg.layout_mode, "Benutzerdefiniert")
        if cfg.layout_mode != LAYOUT_CUSTOM:
            try:
                monitor = win32.get_monitor_by_id(cfg.monitor_id)
                layout = calculate_layout(
                    monitor.rect,
                    cfg.layout_mode,
                    cfg.game_side,
                )
                game_rect = layout.game
                secondary_rect = layout.secondary
                if cfg.layout_mode == LAYOUT_AUTOMATIC:
                    layout_text = (
                        "Auto -> "
                        + LAYOUT_LABELS.get(
                            layout.effective_mode,
                            layout.effective_mode,
                        )
                    )
            except Exception:
                pass
        target = cfg.process_name or cfg.title_contains
        if cfg.auto_detect_games:
            target = f"Automatisch ({target})" if target else "Automatische Erkennung"
        elif not target:
            target = "Nicht festgelegt"
        self.summary_target.configure(text=target)
        self.summary_area.configure(
            text=(
                f"{game_rect.width} x {game_rect.height} @ "
                f"{game_rect.x}, {game_rect.y}"
            )
        )
        mouse_text = "Aktiv"
        if not cfg.lock_cursor:
            mouse_text = "Aus"
        elif cfg.foreground_only:
            mouse_text = "Nur bei Spiel-Fokus"
        self.summary_mouse.configure(text=mouse_text)
        if cfg.secondary_enabled:
            secondary = cfg.secondary_process_name or cfg.secondary_title_contains
            side = "links" if secondary_rect.right <= game_rect.x else "rechts"
            self.summary_mode.configure(
                text=f"{layout_text} | {secondary or side}"
            )
        else:
            self.summary_mode.configure(
                text=(
                    f"{layout_text} | "
                    + ("Borderless" if cfg.remove_borders else "Nur positionieren")
                )
            )

        spec = self._hotkey_spec(cfg)
        if not cfg.hotkey_enabled:
            self.hotkey_hint.configure(text="Globaler Hotkey: aus", text_color=COLORS["muted"])
        elif self.hotkey.registered:
            self.hotkey_hint.configure(text=f"Hotkey: {spec.label}", text_color=COLORS["muted"])
        else:
            self.hotkey_hint.configure(
                text=f"Hotkey nicht aktiv: {spec.label} ist vermutlich belegt",
                text_color=COLORS["red"],
            )

    def _refresh_windows(self) -> None:
        try:
            windows = win32.enumerate_windows(exclude_pid=os.getpid())
            self.window_items.clear()
            for item in windows:
                base = item.display_name
                label = base
                if label in self.window_items:
                    label = f"{base}  (0x{item.hwnd:X})"
                self.window_items[label] = item
            values = list(self.window_items.keys())
            if not values:
                values = ["Keine passenden sichtbaren Fenster gefunden"]
            self.window_combo.configure(values=values)
            self.secondary_window_combo.configure(values=values)
            selected_label = next(
                (
                    label
                    for label, item in self.window_items.items()
                    if item.hwnd == self.selected_hwnd
                ),
                values[0],
            )
            self.window_select_var.set(selected_label)
            secondary_selected_label = next(
                (
                    label
                    for label, item in self.window_items.items()
                    if item.hwnd == self.selected_secondary_hwnd
                ),
                values[0],
            )
            self.secondary_window_select_var.set(secondary_selected_label)
        except Exception as exc:
            self.window_combo.configure(values=["Fensterliste konnte nicht geladen werden"])
            self.window_select_var.set("Fensterliste konnte nicht geladen werden")
            self.secondary_window_combo.configure(
                values=["Fensterliste konnte nicht geladen werden"]
            )
            self.secondary_window_select_var.set(
                "Fensterliste konnte nicht geladen werden"
            )
            self._log(f"Fensterliste: {exc}")

    def _on_window_selected(self, label: str) -> None:
        item = self.window_items.get(label)
        if item is None:
            return
        self.selected_hwnd = item.hwnd
        if item.process_name:
            self.process_var.set(item.process_name)
            self.title_var.set("")
        elif item.title and item.title != "<Fenster ohne Titel>":
            self.process_var.set("")
            self.title_var.set(item.title)
        self.settings_feedback.configure(
            text=f"Ausgewaehlt: {item.process_name or item.title}",
            text_color=COLORS["accent"],
        )

    def _on_secondary_window_selected(self, label: str) -> None:
        item = self.window_items.get(label)
        if item is None:
            return
        self.selected_secondary_hwnd = item.hwnd
        if item.process_name:
            self.secondary_process_var.set(item.process_name)
            self.secondary_title_var.set("")
        elif item.title and item.title != "<Fenster ohne Titel>":
            self.secondary_process_var.set("")
            self.secondary_title_var.set(item.title)
        self.settings_feedback.configure(
            text=f"Zweite Zone: {item.process_name or item.title}",
            text_color=COLORS["accent"],
        )

    def _configure_hotkey(self, show_dialog: bool) -> bool:
        self.hotkey.stop()
        if not self.config_data.hotkey_enabled:
            return True
        try:
            ok, message = self.hotkey.start(self._hotkey_spec(self.config_data))
        except ValueError as exc:
            ok, message = False, str(exc)
        self._log(message)
        if not ok and show_dialog:
            messagebox.showwarning("Globaler Hotkey", message, parent=self)
        return ok

    def _configure_tray(self) -> bool:
        if not self.config_data.tray_enabled:
            self.tray.stop()
            return True
        ok, message = self.tray.start()
        self._log(message)
        return ok

    def _apply_startup_visibility(self) -> None:
        if self._start_hidden and self.config_data.tray_enabled and self.tray.available:
            self.withdraw()
            self._log("Minimiert im System-Tray gestartet.")
        elif self._start_hidden:
            self._log("Minimierter Start nicht moeglich: System-Tray ist nicht verfuegbar.")
            self._show_window()
        else:
            # The normal constructor already shows the window. Avoid stealing
            # focus a second time while another app/game is opening.
            self.deiconify()

    def _show_window(self) -> None:
        if self._closing:
            return
        self.deiconify()
        self.state("normal")
        self.lift()
        try:
            self.focus_force()
        except Exception:
            pass

    def _hide_to_tray(self) -> None:
        if not self.config_data.tray_enabled or not self.tray.available:
            return
        self.withdraw()
        if not self._tray_notice_shown:
            self._tray_notice_shown = True
            self.tray.notify(
                "FellSplit Pro laeuft im Hintergrund weiter. Doppelklick auf das Tray-Symbol oeffnet die App.",
                "FellSplit Pro bleibt aktiv",
            )

    def _on_window_close(self) -> None:
        if (
            self.config_data.tray_enabled
            and self.config_data.close_to_tray
            and self.tray.available
        ):
            self._hide_to_tray()
            return
        self._exit_app()

    def _on_unmap(self, _event=None) -> None:
        if self._closing or not self.config_data.minimize_to_tray:
            return
        if self.state() == "iconic" and self.tray.available:
            self.after(50, self._hide_to_tray)

    @staticmethod
    def _hotkey_spec(config: AppConfig) -> HotkeySpec:
        return HotkeySpec(
            ctrl=config.hotkey_ctrl,
            alt=config.hotkey_alt,
            shift=config.hotkey_shift,
            key=config.hotkey_key,
        )

    def _log(self, message: str) -> None:
        if not hasattr(self, "log_box"):
            return
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"[{timestamp}] {message}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _clear_log(self) -> None:
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")
        self._log("Protokoll geleert.")

    def _restart_as_admin(self) -> None:
        try:
            executable = sys.executable
            if getattr(sys, "frozen", False):
                parameters = subprocess.list2cmdline(sys.argv[1:])
            else:
                script = str(Path(sys.argv[0]).resolve())
                parameters = subprocess.list2cmdline([script, *sys.argv[1:]])
            result = ctypes.windll.shell32.ShellExecuteW(
                None,
                "runas",
                executable,
                parameters,
                str(Path.cwd()),
                1,
            )
            if result <= 32:
                raise OSError(f"ShellExecuteW-Code {result}")
            self._exit_app()
        except OSError as exc:
            messagebox.showerror(
                "Neustart nicht moeglich",
                f"Windows konnte FellSplit Pro nicht als Administrator starten: {exc}",
                parent=self,
            )

    def _exit_app(self) -> None:
        if self._closing:
            return
        self._closing = True
        try:
            self.controller.emergency_release()
        finally:
            self.hotkey.stop()
            self.tray.stop()
            self.destroy()

    def report_callback_exception(self, exc_type, exc_value, exc_traceback) -> None:
        """Tk callback safety net: release input before reporting an unexpected error."""

        try:
            self.controller.emergency_release()
            self.master_switch.deselect()
        except Exception:
            pass
        details = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        self._log(f"Unerwarteter GUI-Fehler: {exc_value}")
        try:
            error_log = error_log_path()
            error_log.parent.mkdir(parents=True, exist_ok=True)
            error_log.write_text(details, encoding="utf-8")
            note = f"\n\nDetails: {error_log}"
        except OSError:
            note = ""
        messagebox.showerror(
            "FellSplit Pro - unerwarteter Fehler",
            f"Die Maus wurde vorsorglich freigegeben.\n\n{exc_value}{note}",
            parent=self,
        )
