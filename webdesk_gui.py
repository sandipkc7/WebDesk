#!/usr/bin/env python3
"""
WebDesk Control Panel - Modern Compact Native GUI
Built with PyGObject (GTK 3.0) for Linux Mint
Ultra-compact layout, modern small pill buttons, dark/light/system theme engine.
"""

import os
import sys
import json
import subprocess
import re
import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WEBDESK_SH = os.path.join(SCRIPT_DIR, "webdesk.sh")
INSTALL_DIR = os.path.expanduser("~/.local/share/webdesk")
CONFIG_FILE = os.path.join(INSTALL_DIR, "config.env")
PASSWD_FILE = os.path.join(INSTALL_DIR, "vnc_passwd")
AUTOSTART_FILE = os.path.expanduser("~/.config/autostart/webdesk.desktop")
THEME_FILE = os.path.join(INSTALL_DIR, "theme_pref.json")
DOWNLOADS_DIR = os.path.expanduser("~/Downloads")

PROFILES = {
    "ultra_fast": ("⚡ Ultra Fast", "60 FPS / Ultra-Low Latency (Video & Gaming)"),
    "balanced":   ("⚖️ Balanced",   "30-45 FPS / Sharp Text (Recommended)"),
    "high_quality": ("🎨 High Quality", "Maximum Fidelity (Crisp Text & Colors)"),
    "low_bandwidth": ("📉 Low Bandwidth", "Eco Mode (Slow Wi-Fi / Low Data)")
}

RESOLUTIONS = [
    ("2560x1440", "2560 x 1440 (16:9 2K QHD)"),
    ("1920x1200", "1920 x 1200 (16:10 WUXGA)"),
    ("1920x1080", "1920 x 1080 (16:9 Full HD)"),
    ("1600x900",  "1600 x 900 (16:9 HD+)"),
    ("1440x900",  "1440 x 900 (16:10 MacBook)"),
    ("1366x768",  "1366 x 768 (16:9 Laptop)"),
    ("1280x1024", "1280 x 1024 (5:4 SXGA)"),
    ("1280x960",  "1280 x 960 (4:3 SXGA-)"),
    ("1280x800",  "1280 x 800 (16:10 WXGA)"),
    ("1280x768",  "1280 x 768 (15:9 WXGA)"),
    ("1280x720",  "1280 x 720 (16:9 720p HD)"),
    ("1024x768",  "1024 x 768 (4:3 XGA)")
]

THEME_CSS_DARK = """
window {
    background-color: #0b0f19;
    color: #f3f4f6;
}

.compact-card {
    background-color: #161f30;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    padding: 10px 14px;
    margin: 4px 10px;
}

.header-card {
    background: #1e293b;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    padding: 10px 14px;
    margin: 6px 10px;
}

.card-title {
    font-size: 11px;
    font-weight: 800;
    color: #94a3b8;
}

.badge-running {
    background-color: rgba(34, 197, 94, 0.2);
    color: #4ade80;
    border: 1px solid rgba(34, 197, 94, 0.4);
    border-radius: 12px;
    padding: 2px 8px;
    font-weight: 800;
    font-size: 10px;
}

.badge-stopped {
    background-color: rgba(239, 68, 68, 0.2);
    color: #f87171;
    border: 1px solid rgba(239, 68, 68, 0.4);
    border-radius: 12px;
    padding: 2px 8px;
    font-weight: 800;
    font-size: 10px;
}

/* Modern Small Pill Buttons */
button {
    border-radius: 6px;
    font-size: 11px;
    font-weight: 600;
    padding: 4px 10px;
    min-height: 24px;
}

.btn-primary {
    background-color: #0284c7;
    color: #ffffff;
    border: none;
}

.btn-primary:hover {
    background-color: #0369a1;
}

.btn-danger {
    background-color: rgba(239, 68, 68, 0.18);
    color: #f87171;
    border: 1px solid rgba(239, 68, 68, 0.35);
}

.btn-danger:hover {
    background-color: #dc2626;
    color: #ffffff;
}

.btn-secondary {
    background-color: rgba(255, 255, 255, 0.07);
    border: 1px solid rgba(255, 255, 255, 0.1);
    color: #f3f4f6;
}

.btn-secondary:hover {
    background-color: rgba(255, 255, 255, 0.14);
}

.url-row {
    background-color: #0b0f19;
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 8px;
    padding: 4px 10px;
    margin: 2px 0;
}

.url-text {
    color: #38bdf8;
    font-family: monospace;
    font-size: 11px;
    font-weight: bold;
}

/* Compact Dropdowns */
combobox {
    background-color: #0f172a;
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 6px;
    color: #ffffff;
    font-size: 11px;
    padding: 2px 6px;
    min-height: 24px;
}

combobox button {
    background-color: transparent;
    border: none;
    color: #ffffff;
    padding: 2px;
}

combobox cellview {
    color: #ffffff;
    font-size: 11px;
}

menu {
    background-color: #1e293b;
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 8px;
    padding: 4px;
}

menu menuitem {
    color: #f3f4f6;
    padding: 5px 10px;
    border-radius: 4px;
    font-size: 11px;
}

menu menuitem:hover {
    background-color: #0284c7;
    color: #ffffff;
}

menu menuitem label {
    color: inherit;
}
"""

THEME_CSS_LIGHT = """
window {
    background-color: #f1f5f9;
    color: #0f172a;
}

.compact-card {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 10px 14px;
    margin: 4px 10px;
}

.header-card {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 12px;
    padding: 10px 14px;
    margin: 6px 10px;
}

.card-title {
    font-size: 11px;
    font-weight: 800;
    color: #64748b;
}

.badge-running {
    background-color: rgba(34, 197, 94, 0.15);
    color: #16a34a;
    border: 1px solid rgba(34, 197, 94, 0.4);
    border-radius: 12px;
    padding: 2px 8px;
    font-weight: 800;
    font-size: 10px;
}

.badge-stopped {
    background-color: rgba(239, 68, 68, 0.15);
    color: #dc2626;
    border: 1px solid rgba(239, 68, 68, 0.4);
    border-radius: 12px;
    padding: 2px 8px;
    font-weight: 800;
    font-size: 10px;
}

/* Modern Small Pill Buttons */
button {
    border-radius: 6px;
    font-size: 11px;
    font-weight: 600;
    padding: 4px 10px;
    min-height: 24px;
}

.btn-primary {
    background-color: #0284c7;
    color: #ffffff;
    border: none;
}

.btn-primary:hover {
    background-color: #0369a1;
}

.btn-danger {
    background-color: #fee2e2;
    color: #dc2626;
    border: 1px solid #fca5a5;
}

.btn-danger:hover {
    background-color: #dc2626;
    color: #ffffff;
}

.btn-secondary {
    background-color: #f8fafc;
    border: 1px solid #cbd5e1;
    color: #1e293b;
}

.btn-secondary:hover {
    background-color: #e2e8f0;
}

.url-row {
    background-color: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 4px 10px;
    margin: 2px 0;
}

.url-text {
    color: #0284c7;
    font-family: monospace;
    font-size: 11px;
    font-weight: bold;
}

/* Compact Dropdowns */
combobox {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    color: #0f172a;
    font-size: 11px;
    padding: 2px 6px;
    min-height: 24px;
}

combobox button {
    background-color: transparent;
    border: none;
    color: #0f172a;
    padding: 2px;
}

combobox cellview {
    color: #0f172a;
    font-size: 11px;
}

menu {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 4px;
}

menu menuitem {
    color: #0f172a;
    padding: 5px 10px;
    border-radius: 4px;
    font-size: 11px;
}

menu menuitem:hover {
    background-color: #0284c7;
    color: #ffffff;
}

menu menuitem label {
    color: inherit;
}
"""

class WebDeskApp(Gtk.Window):
    def __init__(self):
        super().__init__(title="WebDesk Control Panel")
        self.set_default_size(520, 560)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_icon_name("preferences-desktop-remote-desktop")

        self.current_theme = self.load_theme_pref()
        self.css_provider = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            self.css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        self.apply_theme(self.current_theme)

        self.build_ui()
        self.refresh_status()
        GLib.timeout_add_seconds(3, self.refresh_status)

    def load_theme_pref(self):
        if os.path.exists(THEME_FILE):
            try:
                with open(THEME_FILE, 'r') as f:
                    return json.load(f).get("theme", "dark")
            except:
                pass
        return "dark"

    def save_theme_pref(self, theme_name):
        try:
            with open(THEME_FILE, 'w') as f:
                json.dump({"theme": theme_name}, f)
        except:
            pass

    def apply_theme(self, theme_name):
        self.current_theme = theme_name
        self.save_theme_pref(theme_name)

        if theme_name == "light":
            css_data = THEME_CSS_LIGHT
        elif theme_name == "dark":
            css_data = THEME_CSS_DARK
        else: # System
            settings = Gtk.Settings.get_default()
            is_dark = settings.get_property("gtk-application-prefer-dark-theme") if settings else True
            css_data = THEME_CSS_DARK if is_dark else THEME_CSS_LIGHT

        try:
            self.css_provider.load_from_data(css_data.encode('utf-8'))
        except Exception as e:
            print(f"[WebDesk GUI] CSS load notice: {e}", file=sys.stderr)

    def run_cmd(self, action, arg=""):
        try:
            cmd = [WEBDESK_SH, action]
            if arg:
                cmd.append(arg)
            res = subprocess.run(cmd, capture_output=True, text=True)
            return res.returncode == 0, res.stdout.strip()
        except Exception as e:
            return False, str(e)

    def get_current_profile(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    for line in f:
                        if line.startswith("PROFILE="):
                            return line.strip().split("=")[1].strip().strip('"')
            except:
                pass
        return "balanced"

    def get_current_resolution(self):
        try:
            out = subprocess.run(["xrandr"], capture_output=True, text=True).stdout
            for line in out.splitlines():
                if '*' in line:
                    return line.strip().split()[0]
        except:
            pass
        return "1920x1080"

    def is_running(self):
        try:
            p1 = subprocess.run(["pgrep", "-f", "x11vnc"], capture_output=True)
            p2 = subprocess.run(["pgrep", "-f", "websockify"], capture_output=True)
            return p1.returncode == 0 and p2.returncode == 0
        except:
            return False

    def is_audio_running(self):
        try:
            p = subprocess.run(["pgrep", "-f", "audio_server.py"], capture_output=True)
            return p.returncode == 0
        except:
            return False

    def get_ips(self):
        ips = []
        try:
            out = subprocess.run(["ip", "-4", "addr", "show", "scope", "global"], capture_output=True, text=True).stdout
            for match in re.finditer(r'inet\s+(\d+\.\d+\.\d+\.\d+)', out):
                ip = match.group(1)
                if not ip.startswith('127.'):
                    ips.append(ip)
        except:
            pass
        return ips or ["127.0.0.1"]

    def build_ui(self):
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.add(main_box)

        # 1. Compact Header Bar
        header_card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        header_card.get_style_context().add_class("header-card")

        logo = Gtk.Image.new_from_icon_name("preferences-desktop-remote-desktop", Gtk.IconSize.LARGE_TOOLBAR)
        header_card.pack_start(logo, False, False, 0)

        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        title_lbl = Gtk.Label(xalign=0)
        title_lbl.set_markup("<span font_weight='bold' font_size='11000' color='#38bdf8'>🖥️ WebDesk Server</span>")
        subtitle_lbl = Gtk.Label(xalign=0)
        subtitle_lbl.set_markup("<span font_size='8500' color='#94a3b8'>Encrypted Remote Desktop</span>")
        title_box.pack_start(title_lbl, False, False, 0)
        title_box.pack_start(subtitle_lbl, False, False, 0)
        header_card.pack_start(title_box, True, True, 0)

        # Status Badge
        self.status_badge = Gtk.Label()
        header_card.pack_end(self.status_badge, False, False, 0)

        # Theme Switcher
        self.theme_combo = Gtk.ComboBoxText()
        self.theme_combo.append("dark", "🌙 Dark")
        self.theme_combo.append("light", "☀️ Light")
        self.theme_combo.append("system", "💻 Auto")
        self.theme_combo.set_active_id(self.current_theme)
        self.theme_combo.connect("changed", self.on_theme_changed)
        header_card.pack_end(self.theme_combo, False, False, 4)

        main_box.pack_start(header_card, False, False, 0)

        # 2. Server Control Action Buttons Row
        ctrl_card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        ctrl_card.get_style_context().add_class("compact-card")

        self.btn_start = Gtk.Button(label="▶ Start")
        self.btn_start.get_style_context().add_class("btn-primary")
        self.btn_start.connect("clicked", self.on_start_clicked)
        ctrl_card.pack_start(self.btn_start, True, True, 0)

        self.btn_stop = Gtk.Button(label="⏹ Stop")
        self.btn_stop.get_style_context().add_class("btn-danger")
        self.btn_stop.connect("clicked", self.on_stop_clicked)
        ctrl_card.pack_start(self.btn_stop, True, True, 0)

        self.btn_restart = Gtk.Button(label="🔄 Restart")
        self.btn_restart.get_style_context().add_class("btn-secondary")
        self.btn_restart.connect("clicked", self.on_restart_clicked)
        ctrl_card.pack_start(self.btn_restart, True, True, 0)

        main_box.pack_start(ctrl_card, False, False, 0)

        # 3. Display & Streaming Settings Grid (Two Column Compact Layout)
        settings_grid = Gtk.Grid()
        settings_grid.set_column_spacing(8)
        settings_grid.set_row_spacing(6)
        settings_grid.get_style_context().add_class("compact-card")

        # Resolution Row
        res_title = Gtk.Label(xalign=0)
        res_title.set_markup("<b><small>📐 RESOLUTION</small></b>")
        settings_grid.attach(res_title, 0, 0, 1, 1)

        res_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.res_combo = Gtk.ComboBoxText()
        for res_id, res_label in RESOLUTIONS:
            self.res_combo.append(res_id, res_label)
        cur_res = self.get_current_resolution()
        valid_res = [r[0] for r in RESOLUTIONS]
        self.res_combo.set_active_id(cur_res if cur_res in valid_res else "1920x1080")
        self.res_combo.connect("changed", self.on_res_changed)
        res_box.pack_start(self.res_combo, True, True, 0)

        btn_auto_res = Gtk.Button(label="🎯 Match")
        btn_auto_res.get_style_context().add_class("btn-secondary")
        btn_auto_res.set_tooltip_text("Auto-match client display resolution")
        btn_auto_res.connect("clicked", lambda b: self.run_cmd("resolution", "1920x1080"))
        res_box.pack_end(btn_auto_res, False, False, 0)
        settings_grid.attach(res_box, 1, 0, 1, 1)

        # Speed Profile Row
        prof_title = Gtk.Label(xalign=0)
        prof_title.set_markup("<b><small>⚡ SPEED PROFILE</small></b>")
        settings_grid.attach(prof_title, 0, 1, 1, 1)

        self.profile_combo = Gtk.ComboBoxText()
        for prof_k, (prof_title_str, _) in PROFILES.items():
            self.profile_combo.append(prof_k, prof_title_str)
        self.profile_combo.set_active_id(self.get_current_profile())
        self.profile_combo.connect("changed", self.on_profile_changed)
        settings_grid.attach(self.profile_combo, 1, 1, 1, 1)

        main_box.pack_start(settings_grid, False, False, 0)

        # 4. In-Browser URLs Card
        url_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        url_card.get_style_context().add_class("compact-card")

        url_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        url_title = Gtk.Label(xalign=0)
        url_title.set_markup("<b><small>🌐 BROWSER ACCESS LINKS (HTTPS)</small></b>")
        url_header.pack_start(url_title, True, True, 0)
        url_card.pack_start(url_header, False, False, 0)

        self.url_list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        url_card.pack_start(self.url_list_box, False, False, 0)
        main_box.pack_start(url_card, False, False, 0)

        # 5. Quick Tools & Security Grid
        tools_card = Gtk.Grid()
        tools_card.set_column_spacing(8)
        tools_card.set_row_spacing(6)
        tools_card.get_style_context().add_class("compact-card")

        # Audio Stream Status & Action
        audio_lbl = Gtk.Label(label="🎵 Remote Audio Stream:", xalign=0)
        tools_card.attach(audio_lbl, 0, 0, 1, 1)

        self.audio_status_lbl = Gtk.Label(xalign=1)
        tools_card.attach(self.audio_status_lbl, 1, 0, 1, 1)

        # Files Folder
        files_lbl = Gtk.Label(label="📁 Drag & Drop Folder:", xalign=0)
        tools_card.attach(files_lbl, 0, 1, 1, 1)

        btn_open_dl = Gtk.Button(label="Open ~/Downloads")
        btn_open_dl.get_style_context().add_class("btn-secondary")
        btn_open_dl.connect("clicked", lambda b: subprocess.Popen(["xdg-open", DOWNLOADS_DIR]))
        tools_card.attach(btn_open_dl, 1, 1, 1, 1)

        # Web Accounts & Roles
        self.pw_status_lbl = Gtk.Label(xalign=0)
        self.pw_status_lbl.set_markup("👥 <b>Web Accounts & Roles:</b>")
        tools_card.attach(self.pw_status_lbl, 0, 2, 1, 1)

        btn_manage_users = Gtk.Button(label="Manage Web Users")
        btn_manage_users.get_style_context().add_class("btn-secondary")
        btn_manage_users.connect("clicked", self.on_manage_users_dialog)
        tools_card.attach(btn_manage_users, 1, 2, 1, 1)

        # Autostart on Boot Switch
        auto_lbl = Gtk.Label(label="🚀 Start on Desktop Login:", xalign=0)
        tools_card.attach(auto_lbl, 0, 3, 1, 1)

        self.auto_switch = Gtk.Switch()
        self.auto_switch.set_valign(Gtk.Align.CENTER)
        self.auto_switch.connect("state-set", self.on_autostart_toggled)
        tools_card.attach(self.auto_switch, 1, 3, 1, 1)

        # Login Screen (LightDM) Service Status
        svc_lbl = Gtk.Label(label="🖥️ Login Screen (24/7 Service):", xalign=0)
        tools_card.attach(svc_lbl, 0, 4, 1, 1)

        self.svc_status_lbl = Gtk.Label(xalign=1)
        tools_card.attach(self.svc_status_lbl, 1, 4, 1, 1)

        main_box.pack_start(tools_card, False, False, 0)

        # Compact Footer
        footer_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        footer_box.set_margin_start(12)
        footer_box.set_margin_end(12)
        footer_box.set_margin_top(2)
        footer_box.set_margin_bottom(6)

        footer_lbl = Gtk.Label(xalign=0)
        footer_lbl.set_markup("<span font_size='8000' color='#64748b'>Ports: 6080 (Web) • 6086 (Audio) • 6085 (API)</span>")
        footer_box.pack_start(footer_lbl, True, True, 0)

        btn_renew = Gtk.Button(label="🔒 Renew SSL")
        btn_renew.get_style_context().add_class("btn-secondary")
        btn_renew.connect("clicked", self.on_renew_cert)
        footer_box.pack_end(btn_renew, False, False, 0)

        main_box.pack_end(footer_box, False, False, 0)

    def on_theme_changed(self, combo):
        theme_id = combo.get_active_id()
        if theme_id:
            self.apply_theme(theme_id)

    def on_res_changed(self, combo):
        res_key = combo.get_active_id()
        if res_key:
            self.run_cmd("resolution", res_key)

    def on_profile_changed(self, combo):
        prof_key = combo.get_active_id()
        if prof_key:
            self.run_cmd("profile", prof_key)
            self.refresh_status()

    def refresh_status(self):
        running = self.is_running()
        audio_running = self.is_audio_running()

        self.status_badge.get_style_context().remove_class("badge-running")
        self.status_badge.get_style_context().remove_class("badge-stopped")

        if running:
            self.status_badge.set_text("● RUNNING")
            self.status_badge.get_style_context().add_class("badge-running")
            self.btn_start.set_sensitive(False)
            self.btn_stop.set_sensitive(True)
        else:
            self.status_badge.set_text("○ STOPPED")
            self.status_badge.get_style_context().add_class("badge-stopped")
            self.btn_start.set_sensitive(True)
            self.btn_stop.set_sensitive(False)

        if audio_running:
            self.audio_status_lbl.set_markup("<span font_size='9000' color='#22c55e'><b>● Active (:6086)</b></span>")
        else:
            self.audio_status_lbl.set_markup("<span font_size='9000' color='#94a3b8'>Idle</span>")

        try:
            svc_active = subprocess.run(["systemctl", "is-active", "webdesk.service"], capture_output=True).returncode == 0
            if svc_active:
                self.svc_status_lbl.set_markup("<span font_size='9000' color='#22c55e'><b>Active (LightDM)</b></span>")
            else:
                self.svc_status_lbl.set_markup("<span font_size='9000' color='#94a3b8'>Disabled</span>")
        except:
            self.svc_status_lbl.set_markup("<span font_size='9000' color='#94a3b8'>--</span>")

        for child in self.url_list_box.get_children():
            self.url_list_box.remove(child)

        if running:
            ips = self.get_ips()
            for ip in ips:
                url = f"https://{ip}:6080/"
                row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
                row.get_style_context().add_class("url-row")

                lbl = Gtk.Label(xalign=0)
                lbl.set_markup(f"<span font_family='monospace' font_weight='bold' color='#38bdf8'>{url}</span>")
                row.pack_start(lbl, True, True, 0)

                btn_copy = Gtk.Button(label="📋 Copy")
                btn_copy.get_style_context().add_class("btn-secondary")
                btn_copy.connect("clicked", lambda b, u=url: self.copy_to_clipboard(u))
                row.pack_end(btn_copy, False, False, 0)

                self.url_list_box.pack_start(row, False, False, 0)
        else:
            empty_lbl = Gtk.Label(label="Server stopped. Click 'Start' to generate URLs.", xalign=0)
            empty_lbl.set_margin_top(4)
            empty_lbl.set_margin_bottom(4)
            self.url_list_box.pack_start(empty_lbl, False, False, 0)

        self.url_list_box.show_all()

        users_count = 0
        try:
            sys.path.insert(0, INSTALL_DIR)
            import user_auth
            users_count = len(user_auth.list_users())
        except:
            pass
        self.pw_status_lbl.set_markup(f"👥 <b>Web Accounts:</b> <span color='#38bdf8'><b>{users_count} Active</b></span>")

        self.auto_switch.handler_block_by_func(self.on_autostart_toggled)
        self.auto_switch.set_active(os.path.exists(AUTOSTART_FILE))
        self.auto_switch.handler_unblock_by_func(self.on_autostart_toggled)

        cur_prof = self.get_current_profile()
        if self.profile_combo.get_active_id() != cur_prof:
            self.profile_combo.handler_block_by_func(self.on_profile_changed)
            self.profile_combo.set_active_id(cur_prof)
            self.profile_combo.handler_unblock_by_func(self.on_profile_changed)

        return True

    def copy_to_clipboard(self, text):
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(text, -1)
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text="Link Copied!"
        )
        dialog.format_secondary_text(f"{text}\n\nCopied to clipboard.")
        dialog.run()
        dialog.destroy()

    def on_start_clicked(self, btn):
        self.run_cmd("start")
        self.refresh_status()

    def on_stop_clicked(self, btn):
        self.run_cmd("stop")
        self.refresh_status()

    def on_restart_clicked(self, btn):
        self.run_cmd("restart")
        self.refresh_status()

    def on_autostart_toggled(self, switch, state):
        if state:
            self.run_cmd("enable-autostart")
        else:
            self.run_cmd("disable-autostart")
        return False

    def on_renew_cert(self, btn):
        self.run_cmd("renew-cert")
        self.refresh_status()
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text="SSL Certificate Renewed"
        )
        dialog.format_secondary_text("A new TLS/SSL certificate was generated for active IP addresses.")
        dialog.run()
        dialog.destroy()

    def verify_master_password(self):
        import datetime
        now = datetime.datetime.now()
        day_str = f"{now.day} {now.strftime('%b')}, {now.year} {now.strftime('%A')}"
        expected_pw1 = f"Pass@{now.strftime('%a')}{now.day}"
        expected_pw2 = f"Pass@{now.strftime('%a')}{now.strftime('%d')}"

        dialog = Gtk.Dialog(title="🔒 Master Authentication Required", transient_for=self, flags=0)
        dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, "Unlock", Gtk.ResponseType.OK)
        dialog.set_default_size(360, 180)

        content = dialog.get_content_area()
        content.set_spacing(8)
        content.set_margin_start(16)
        content.set_margin_end(16)
        content.set_margin_top(16)
        content.set_margin_bottom(12)

        header_lbl = Gtk.Label(xalign=0)
        header_lbl.set_markup("<b><span size='large'>🔒 Security Verification Required</span></b>")
        content.pack_start(header_lbl, False, False, 0)

        date_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        date_lbl_tag = Gtk.Label(label="System Date:", xalign=0)
        date_lbl_val = Gtk.Label(xalign=0)
        date_lbl_val.set_markup(f"<span color='#38bdf8'><b>{day_str}</b></span>")
        date_box.pack_start(date_lbl_tag, False, False, 0)
        date_box.pack_start(date_lbl_val, False, False, 0)
        content.pack_start(date_box, False, False, 0)

        desc_lbl = Gtk.Label(xalign=0)
        desc_lbl.set_markup("<small>Web User Accounts management is protected by Master Security.</small>")
        content.pack_start(desc_lbl, False, False, 0)

        pw_entry = Gtk.Entry()
        pw_entry.set_placeholder_text("Enter Master Password")
        pw_entry.set_visibility(False)
        pw_entry.set_activates_default(True)
        dialog.set_default_response(Gtk.ResponseType.OK)
        content.pack_start(pw_entry, False, False, 4)

        dialog.show_all()
        response = dialog.run()
        input_text = pw_entry.get_text().strip()
        dialog.destroy()

        if response == Gtk.ResponseType.OK:
            if input_text in [expected_pw1, expected_pw2]:
                return True
            else:
                err_dialog = Gtk.MessageDialog(
                    transient_for=self,
                    flags=0,
                    message_type=Gtk.MessageType.ERROR,
                    buttons=Gtk.ButtonsType.OK,
                    text="Access Denied"
                )
                err_dialog.format_secondary_text("Incorrect Master Password entered.")
                err_dialog.run()
                err_dialog.destroy()
                return False
        return False

    def on_manage_users_dialog(self, btn):
        if not self.verify_master_password():
            return

        dialog = Gtk.Dialog(title="👥 Manage Web Accounts", transient_for=self, flags=0)
        dialog.add_buttons(Gtk.STOCK_CLOSE, Gtk.ResponseType.CLOSE)
        dialog.set_default_size(460, 420)

        content = dialog.get_content_area()
        content.set_spacing(10)
        content.set_margin_start(14)
        content.set_margin_end(14)
        content.set_margin_top(14)

        sys.path.insert(0, INSTALL_DIR)

        # List of users
        list_box = Gtk.ListBox()
        list_box.set_selection_mode(Gtk.SelectionMode.NONE)

        scroll = Gtk.ScrolledWindow()
        scroll.set_min_content_height(180)
        scroll.add(list_box)
        content.pack_start(scroll, True, True, 0)

        # Add user box
        add_frame = Gtk.Frame(label=" + Add New Web User ")
        add_box = Gtk.Grid()
        add_box.set_column_spacing(6)
        add_box.set_row_spacing(4)
        add_box.set_margin_start(8)
        add_box.set_margin_end(8)
        add_box.set_margin_top(8)
        add_box.set_margin_bottom(8)

        e_u = Gtk.Entry()
        e_u.set_placeholder_text("Username")
        add_box.attach(e_u, 0, 0, 1, 1)

        e_p = Gtk.Entry()
        e_p.set_placeholder_text("Password")
        e_p.set_visibility(False)
        add_box.attach(e_p, 1, 0, 1, 1)

        r_combo = Gtk.ComboBoxText()
        r_combo.append("user", "User (Interactive)")
        r_combo.append("viewer", "Guest (View Only)")
        r_combo.append("admin", "Admin (Full Control)")
        r_combo.set_active(0)
        add_box.attach(r_combo, 0, 1, 1, 1)

        btn_add = Gtk.Button(label="➕ Add Account")
        btn_add.connect("clicked", lambda b: self.on_add_user_act(e_u, e_p, r_combo.get_active_id(), list_box, dialog))
        add_box.attach(btn_add, 1, 1, 1, 1)

        add_frame.add(add_box)
        content.pack_start(add_frame, False, False, 0)

        io_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        btn_export = Gtk.Button(label="📤 Export Config (.json)")
        btn_export.connect("clicked", lambda b: self.on_export_config_act(dialog))
        btn_import = Gtk.Button(label="📥 Import Config (.json)")
        btn_import.connect("clicked", lambda b: self.on_import_config_act(list_box, dialog))
        io_box.pack_start(btn_export, True, True, 0)
        io_box.pack_start(btn_import, True, True, 0)
        content.pack_start(io_box, False, False, 2)

        btn_reset = Gtk.Button(label="🔄 Reset All Accounts to Factory Defaults")
        btn_reset.connect("clicked", lambda b: self.on_reset_users_act(list_box, dialog))
        content.pack_start(btn_reset, False, False, 4)

        # Populate users initially
        self.populate_users_list(list_box, dialog)

        dialog.show_all()
        dialog.run()
        dialog.destroy()
        self.refresh_status()

    def populate_users_list(self, list_box, parent_dialog):
        for child in list_box.get_children():
            list_box.remove(child)

        import user_auth
        for u in user_auth.list_users():
            row = Gtk.ListBoxRow()
            hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            hbox.set_margin_top(4)
            hbox.set_margin_bottom(4)

            icon = "👑" if u['role'] == "admin" else ("👤" if u['role'] == "user" else "👁️")
            is_susp = u.get('status') == 'suspended'
            status_tag = "<span color='#f87171'>(Suspended)</span>" if is_susp else "<span color='#4ade80'>(Active)</span>"
            settings = u.get('settings', {})
            prof = settings.get('profile', 'balanced')
            res = settings.get('resolution', 'auto')
            u_lbl = Gtk.Label(xalign=0)
            u_lbl.set_markup(f"<b>{icon} {u['username']}</b> <small>{u['role']} [{prof} | {res}] {status_tag}</small>")
            hbox.pack_start(u_lbl, True, True, 0)

            btn_change = Gtk.Button(label="🔑")
            btn_change.set_tooltip_text("Change Password")
            btn_change.connect("clicked", lambda b, uname=u['username']: self.on_change_user_pw(uname, list_box, parent_dialog))
            hbox.pack_start(btn_change, False, False, 0)

            if u['username'] != "admin":
                if is_susp:
                    btn_susp = Gtk.Button(label="▶️")
                    btn_susp.set_tooltip_text("Reactivate User")
                    btn_susp.connect("clicked", lambda b, uname=u['username']: self.on_unsuspend_user_act(uname, list_box, parent_dialog))
                else:
                    btn_susp = Gtk.Button(label="⏸️")
                    btn_susp.set_tooltip_text("Suspend User (Block & Kick)")
                    btn_susp.connect("clicked", lambda b, uname=u['username']: self.on_suspend_user_act(uname, list_box, parent_dialog))
                hbox.pack_start(btn_susp, False, False, 0)

                btn_kick = Gtk.Button(label="⚡")
                btn_kick.set_tooltip_text("Terminate Active Session")
                btn_kick.connect("clicked", lambda b, uname=u['username']: self.on_kick_user_act(uname, list_box, parent_dialog))
                hbox.pack_start(btn_kick, False, False, 0)

                btn_del = Gtk.Button(label="🗑️")
                btn_del.set_tooltip_text("Delete User")
                btn_del.connect("clicked", lambda b, uname=u['username']: self.on_delete_user_act(uname, list_box, parent_dialog))
                hbox.pack_start(btn_del, False, False, 0)

            row.add(hbox)
            list_box.add(row)

        list_box.show_all()

    def on_export_config_act(self, parent_dialog):
        chooser = Gtk.FileChooserDialog(
            title="Export WebDesk Configuration",
            parent=parent_dialog,
            action=Gtk.FileChooserAction.SAVE
        )
        chooser.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_SAVE, Gtk.ResponseType.OK)
        chooser.set_current_name("webdesk_config_backup.json")
        chooser.set_do_overwrite_confirmation(True)
        if chooser.run() == Gtk.ResponseType.OK:
            path = chooser.get_filename()
            chooser.destroy()
            import user_auth
            ok, msg, _ = user_auth.export_config(path)
            d = Gtk.MessageDialog(
                transient_for=parent_dialog,
                flags=0,
                message_type=Gtk.MessageType.INFO if ok else Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text="Configuration Export"
            )
            d.format_secondary_text(msg)
            d.run()
            d.destroy()
        else:
            chooser.destroy()

    def on_import_config_act(self, list_box, parent_dialog):
        chooser = Gtk.FileChooserDialog(
            title="Import WebDesk Configuration",
            parent=parent_dialog,
            action=Gtk.FileChooserAction.OPEN
        )
        chooser.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OPEN, Gtk.ResponseType.OK)
        filter_json = Gtk.FileFilter()
        filter_json.set_name("JSON Files")
        filter_json.add_pattern("*.json")
        chooser.add_filter(filter_json)
        if chooser.run() == Gtk.ResponseType.OK:
            path = chooser.get_filename()
            chooser.destroy()
            import user_auth
            ok, msg = user_auth.import_config(path)
            d = Gtk.MessageDialog(
                transient_for=parent_dialog,
                flags=0,
                message_type=Gtk.MessageType.INFO if ok else Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text="Configuration Import"
            )
            d.format_secondary_text(msg)
            d.run()
            d.destroy()
            if ok:
                self.populate_users_list(list_box, parent_dialog)
        else:
            chooser.destroy()

    def on_reset_users_act(self, list_box, parent_dialog):
        d = Gtk.MessageDialog(
            transient_for=parent_dialog,
            flags=0,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            text="Reset User Database to Factory Defaults?"
        )
        d.format_secondary_text("This will restore default logins:\n• admin : admin123 (Admin)\n• user : user123 (User)\n• guest : guest123 (Viewer)\n\nAre you sure you want to proceed?")
        res = d.run()
        d.destroy()
        if res == Gtk.ResponseType.OK:
            import user_auth
            user_auth.reset_default_users()
            self.populate_users_list(list_box, parent_dialog)

    def on_change_user_pw(self, username, list_box, parent_dialog):
        d = Gtk.Dialog(title=f"Change Password: {username}", transient_for=parent_dialog, flags=0)
        d.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OK, Gtk.ResponseType.OK)
        c = d.get_content_area()
        c.set_spacing(6)
        c.set_margin_start(10)
        c.set_margin_end(10)
        c.set_margin_top(10)

        c.pack_start(Gtk.Label(label=f"Enter new password for '{username}':", xalign=0), False, False, 0)
        e = Gtk.Entry()
        e.set_visibility(False)
        c.pack_start(e, False, False, 0)
        d.show_all()

        if d.run() == Gtk.ResponseType.OK and e.get_text():
            import user_auth
            ok, msg = user_auth.change_password("admin", "admin", username, e.get_text())
            d.destroy()
            self.populate_users_list(list_box, parent_dialog)
        else:
            d.destroy()

    def on_suspend_user_act(self, username, list_box, parent_dialog):
        import user_auth
        user_auth.suspend_user("admin", username)
        self.populate_users_list(list_box, parent_dialog)

    def on_unsuspend_user_act(self, username, list_box, parent_dialog):
        import user_auth
        user_auth.unsuspend_user("admin", username)
        self.populate_users_list(list_box, parent_dialog)

    def on_kick_user_act(self, username, list_box, parent_dialog):
        import user_auth
        user_auth.terminate_user_session("admin", username)
        self.populate_users_list(list_box, parent_dialog)

    def on_delete_user_act(self, username, list_box, parent_dialog):
        import user_auth
        user_auth.delete_user("admin", "", username)
        self.populate_users_list(list_box, parent_dialog)

    def on_add_user_act(self, e_u, e_p, r, list_box, parent_dialog):
        u = e_u.get_text().strip()
        p = e_p.get_text().strip()
        if u and p:
            import user_auth
            ok, msg = user_auth.add_user("admin", u, p, r or "user")
            if not ok:
                d = Gtk.MessageDialog(
                    transient_for=parent_dialog,
                    flags=0,
                    message_type=Gtk.MessageType.ERROR,
                    buttons=Gtk.ButtonsType.OK,
                    text="Add User Failed"
                )
                d.format_secondary_text(msg)
                d.run()
                d.destroy()
            else:
                e_u.set_text("")
                e_p.set_text("")
                self.populate_users_list(list_box, parent_dialog)

def main():
    app = WebDeskApp()
    app.connect("destroy", Gtk.main_quit)
    app.show_all()
    Gtk.main()

if __name__ == "__main__":
    main()
