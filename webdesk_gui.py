#!/usr/bin/env python3
"""
WebDesk Control Panel - Modern Sidebar Desktop GUI
Built with PyGObject (GTK 3.0) for Linux Desktops
Sidebar navigation with dedicated views for all WebDesk features without emoticons/smileys.
"""

import os
import sys
import json
import subprocess
import re
import datetime

INSTALL_DIR = os.path.expanduser("~/.local/share/webdesk")

# Ensure environment has active display and authority before GTK initializes
if "DISPLAY" not in os.environ or not os.environ["DISPLAY"]:
    act_disp = os.path.join(INSTALL_DIR, "active_display")
    if os.path.exists(act_disp):
        try:
            with open(act_disp) as f:
                d = f.read().strip()
                if d:
                    os.environ["DISPLAY"] = d
        except Exception:
            pass

if "XAUTHORITY" not in os.environ or not os.environ["XAUTHORITY"]:
    act_auth = os.path.join(INSTALL_DIR, "active_auth")
    if os.path.exists(act_auth):
        try:
            with open(act_auth) as f:
                a = f.read().strip()
                if a and os.path.exists(a):
                    os.environ["XAUTHORITY"] = a
        except Exception:
            pass

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib, Pango

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WEBDESK_SH = os.path.join(SCRIPT_DIR, "webdesk.sh")
SRC_DIR = os.path.join(SCRIPT_DIR, "src")
sys.path.insert(0, SRC_DIR)
sys.path.insert(0, SCRIPT_DIR)
sys.path.insert(0, INSTALL_DIR)

CONFIG_FILE = os.path.join(INSTALL_DIR, "config.env")
PASSWD_FILE = os.path.join(INSTALL_DIR, "vnc_passwd")
AUTOSTART_FILE = os.path.expanduser("~/.config/autostart/webdesk.desktop")
THEME_FILE = os.path.join(INSTALL_DIR, "theme_pref.json")
LOG_FILE = os.path.join(INSTALL_DIR, "webdesk.log")
AUDIT_LOG_FILE = os.path.join(INSTALL_DIR, "login_audit.log")
DOWNLOADS_DIR = os.path.expanduser("~/Downloads")

PROFILES = {
    "ultra_fast": ("Ultra Fast", "60 FPS / Ultra-Low Latency (Video &amp; Gaming)"),
    "balanced":   ("Balanced",   "30-45 FPS / Sharp Text (Recommended)"),
    "high_quality": ("High Quality", "Maximum Fidelity (Crisp Text &amp; Lossless Colors)"),
    "low_bandwidth": ("Low Bandwidth", "Eco Mode (Slow Wi-Fi / Low Data Usage)")
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
    background-color: #0f172a;
    color: #f1f5f9;
}

/* Sidebar Styling */
.sidebar-box {
    background-color: #0b1120;
    border-right: 1px solid rgba(255, 255, 255, 0.08);
}

.sidebar-header {
    padding: 16px 14px 12px 14px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.sidebar-list {
    background: transparent;
    border: none;
}

.sidebar-list row {
    background: transparent;
    border: none;
    padding: 9px 14px;
    border-radius: 6px;
    margin: 2px 8px;
    color: #94a3b8;
    font-weight: 600;
    font-size: 11.5px;
    transition: all 120ms ease;
}

.sidebar-list row:hover {
    background-color: rgba(255, 255, 255, 0.06);
    color: #f8fafc;
}

.sidebar-list row:selected {
    background-color: #0284c7;
    color: #ffffff;
}

/* Content Container & Panels */
.content-pane {
    background-color: #0f172a;
    padding: 14px 18px;
}

viewport, scrolledwindow {
    background-color: transparent;
}

.card-panel {
    background-color: #1e293b;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    padding: 14px 16px;
    margin-bottom: 12px;
}

.card-header-lbl {
    font-size: 11px;
    font-weight: bold;
    color: #94a3b8;
    letter-spacing: 0.5px;
}

/* Badges */
.badge-running {
    background-color: rgba(34, 197, 94, 0.22);
    color: #4ade80;
    border: 1px solid rgba(34, 197, 94, 0.45);
    border-radius: 4px;
    padding: 3px 8px;
    font-weight: bold;
    font-size: 10px;
}

.badge-stopped {
    background-color: rgba(239, 68, 68, 0.22);
    color: #f87171;
    border: 1px solid rgba(239, 68, 68, 0.45);
    border-radius: 4px;
    padding: 3px 8px;
    font-weight: bold;
    font-size: 10px;
}

.badge-info {
    background-color: rgba(56, 189, 248, 0.18);
    color: #38bdf8;
    border: 1px solid rgba(56, 189, 248, 0.4);
    border-radius: 4px;
    padding: 3px 6px;
    font-weight: bold;
    font-size: 10px;
}

/* Base Buttons */
button {
    background-color: #334155;
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 6px;
    color: #f8fafc;
    font-size: 11px;
    font-weight: 600;
    padding: 5px 12px;
    min-height: 28px;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.25);
    transition: all 120ms ease;
}

button:hover {
    background-color: #475569;
    border-color: rgba(255, 255, 255, 0.25);
    color: #ffffff;
}

button:active {
    background-color: #1e293b;
    box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.4);
}

/* Primary Action Button (Blue) */
.btn-primary {
    background-color: #0284c7;
    border: 1px solid #38bdf8;
    color: #ffffff;
    font-weight: bold;
}

.btn-primary:hover {
    background-color: #0369a1;
    border-color: #7dd3fc;
    color: #ffffff;
}

.btn-primary:active {
    background-color: #075985;
}

/* Danger / Stop Button (Red) */
.btn-danger {
    background-color: #b91c1c;
    border: 1px solid #f87171;
    color: #ffffff;
    font-weight: bold;
}

.btn-danger:hover {
    background-color: #dc2626;
    border-color: #fca5a5;
    color: #ffffff;
}

.btn-danger:active {
    background-color: #991b1b;
}

/* Secondary Button (Neutral Slate) */
.btn-secondary {
    background-color: #334155;
    border: 1px solid rgba(255, 255, 255, 0.15);
    color: #f8fafc;
}

.btn-secondary:hover {
    background-color: #475569;
    border-color: rgba(255, 255, 255, 0.28);
    color: #ffffff;
}

.btn-secondary:active {
    background-color: #1e293b;
}

/* Success / Activate Button (Green) */
.btn-success {
    background-color: #15803d;
    border: 1px solid #4ade80;
    color: #ffffff;
    font-weight: bold;
}

.btn-success:hover {
    background-color: #16a34a;
    border-color: #86efac;
    color: #ffffff;
}

.btn-success:active {
    background-color: #14532d;
}

/* URL and Info Box */
.url-box {
    background-color: #0b1120;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 6px;
    padding: 6px 12px;
    margin: 3px 0;
}

.url-text {
    color: #38bdf8;
    font-family: monospace;
    font-size: 11px;
    font-weight: bold;
}

/* ListBox & Tables (Web Users & Navigation) */
list, listbox, .users-list-box {
    background-color: #0b1120;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 6px;
    color: #f1f5f9;
}

.users-list-box row {
    background-color: #161f30;
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 6px;
    margin: 3px 6px;
    padding: 6px 10px;
    color: #f1f5f9;
}

.users-list-box row:hover {
    background-color: #1e293b;
    border-color: rgba(255, 255, 255, 0.12);
}

/* Dropdown ComboBox & Popup Menus */
combobox {
    background-color: #161f30;
    border: 1px solid rgba(255, 255, 255, 0.16);
    border-radius: 6px;
    color: #f8fafc;
    font-size: 11.5px;
    padding: 3px 8px;
    min-height: 28px;
}

combobox:hover {
    border-color: rgba(255, 255, 255, 0.28);
}

combobox:focus {
    border-color: #38bdf8;
}

combobox button, combobox button.combo {
    background: transparent;
    border: none;
    box-shadow: none;
    color: #f8fafc;
}

combobox cellview, combobox cellview label {
    color: #f8fafc;
    background-color: transparent;
}

combobox window.popup, window.popup {
    background-color: #161f30;
    color: #f8fafc;
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 6px;
}

menu, .menu, window.popup menu {
    background-color: #161f30;
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 6px;
    padding: 4px;
    color: #f8fafc;
}

menu menuitem, .menu menuitem, window.popup menu menuitem {
    background-color: transparent;
    color: #f8fafc;
    padding: 6px 12px;
    border-radius: 4px;
    font-size: 11.5px;
}

menu menuitem:hover, .menu menuitem:hover, window.popup menu menuitem:hover {
    background-color: #0284c7;
    color: #ffffff;
}

menu menuitem label, .menu menuitem label, window.popup menu menuitem label {
    color: #f8fafc;
}

menu menuitem:hover label, .menu menuitem:hover label, window.popup menu menuitem:hover label {
    color: #ffffff;
}

/* Text Inputs */
entry {
    background-color: #0b1120;
    border: 1px solid rgba(255, 255, 255, 0.16);
    border-radius: 6px;
    color: #ffffff;
    font-size: 11.5px;
    padding: 4px 8px;
    min-height: 28px;
}

entry:focus {
    border-color: #38bdf8;
    box-shadow: 0 0 0 1px #38bdf8;
}

/* Textview (Logs & Audit) */
textview {
    background-color: #0b1120;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 6px;
}

textview text {
    background-color: #0b1120;
    color: #cbd5e1;
    font-family: monospace;
    font-size: 10.5px;
    padding: 6px;
}

/* Radio & Checkboxes */
radiobutton, checkbutton {
    color: #f1f5f9;
}

radiobutton label, checkbutton label {
    color: #f1f5f9;
    font-size: 11.5px;
}

/* Switch */
switch {
    background-color: #334155;
    border-radius: 12px;
}

switch:checked {
    background-color: #0284c7;
}

switch slider {
    background-color: #ffffff;
    border-radius: 12px;
}

/* Dialogs */
dialog, messagedialog, window.dialog {
    background-color: #0f172a;
    color: #f1f5f9;
}

dialog box, messagedialog box {
    background-color: transparent;
    color: #f1f5f9;
}

dialog label, messagedialog label {
    color: #f1f5f9;
}
"""

THEME_CSS_LIGHT = """
window {
    background-color: #f8fafc;
    color: #0f172a;
}

.sidebar-box {
    background-color: #f1f5f9;
    border-right: 1px solid #e2e8f0;
}

.sidebar-header {
    padding: 16px 14px 12px 14px;
    border-bottom: 1px solid #e2e8f0;
}

.sidebar-list {
    background: transparent;
    border: none;
}

.sidebar-list row {
    background: transparent;
    border: none;
    padding: 9px 14px;
    border-radius: 6px;
    margin: 2px 8px;
    color: #475569;
    font-weight: 600;
    font-size: 11.5px;
    transition: all 120ms ease;
}

.sidebar-list row:hover {
    background-color: #e2e8f0;
    color: #0f172a;
}

.sidebar-list row:selected {
    background-color: #0284c7;
    color: #ffffff;
}

.content-pane {
    background-color: #f8fafc;
    padding: 14px 18px;
}

viewport, scrolledwindow {
    background-color: transparent;
}

.card-panel {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 14px 16px;
    margin-bottom: 12px;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
}

.card-header-lbl {
    font-size: 11px;
    font-weight: bold;
    color: #64748b;
    letter-spacing: 0.5px;
}

.badge-running {
    background-color: rgba(34, 197, 94, 0.15);
    color: #16a34a;
    border: 1px solid rgba(34, 197, 94, 0.35);
    border-radius: 4px;
    padding: 3px 8px;
    font-weight: bold;
    font-size: 10px;
}

.badge-stopped {
    background-color: rgba(239, 68, 68, 0.15);
    color: #dc2626;
    border: 1px solid rgba(239, 68, 68, 0.35);
    border-radius: 4px;
    padding: 3px 8px;
    font-weight: bold;
    font-size: 10px;
}

.badge-info {
    background-color: rgba(2, 132, 199, 0.1);
    color: #0284c7;
    border: 1px solid rgba(2, 132, 199, 0.25);
    border-radius: 4px;
    padding: 3px 6px;
    font-weight: bold;
    font-size: 10px;
}

list, listbox, .users-list-box {
    background-color: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    color: #0f172a;
}

.users-list-box row {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    padding: 6px 10px;
    margin: 3px 6px;
    color: #0f172a;
}

.users-list-box row:hover {
    background-color: #f1f5f9;
    color: #0f172a;
}

button {
    background-color: #f1f5f9;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    color: #1e293b;
    font-size: 11px;
    font-weight: 600;
    padding: 5px 12px;
    min-height: 28px;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}

button:hover {
    background-color: #e2e8f0;
    color: #0f172a;
}

.btn-primary {
    background-color: #0284c7;
    border: 1px solid #0369a1;
    color: #ffffff;
    font-weight: bold;
}

.btn-primary:hover {
    background-color: #0369a1;
    color: #ffffff;
}

.btn-danger {
    background-color: #dc2626;
    border: 1px solid #b91c1c;
    color: #ffffff;
    font-weight: bold;
}

.btn-danger:hover {
    background-color: #b91c1c;
    color: #ffffff;
}

.btn-secondary {
    background-color: #f1f5f9;
    border: 1px solid #cbd5e1;
    color: #1e293b;
}

.btn-secondary:hover {
    background-color: #e2e8f0;
}

.btn-success {
    background-color: #16a34a;
    border: 1px solid #15803d;
    color: #ffffff;
    font-weight: bold;
}

.btn-success:hover {
    background-color: #15803d;
    color: #ffffff;
}

.url-box {
    background-color: #f1f5f9;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    padding: 6px 12px;
    margin: 3px 0;
}

.url-text {
    color: #0284c7;
    font-family: monospace;
    font-size: 11px;
    font-weight: bold;
}

combobox {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    color: #0f172a;
    font-size: 11.5px;
    padding: 3px 8px;
    min-height: 28px;
}

combobox button, combobox button.combo {
    background: transparent;
    border: none;
    color: #0f172a;
}

combobox cellview, combobox cellview label {
    color: #0f172a;
    background-color: transparent;
}

menu, .menu, window.popup menu {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 4px;
    color: #0f172a;
}

menu menuitem, .menu menuitem, window.popup menu menuitem {
    background-color: transparent;
    color: #0f172a;
    padding: 6px 12px;
    border-radius: 4px;
    font-size: 11.5px;
}

menu menuitem:hover, .menu menuitem:hover, window.popup menu menuitem:hover {
    background-color: #0284c7;
    color: #ffffff;
}

menu menuitem label, .menu menuitem label, window.popup menu menuitem label {
    color: #0f172a;
}

menu menuitem:hover label, .menu menuitem:hover label, window.popup menu menuitem:hover label {
    color: #ffffff;
}

entry {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    color: #0f172a;
    font-size: 11.5px;
    padding: 4px 8px;
    min-height: 28px;
}

textview text {
    background-color: #ffffff;
    color: #334155;
    font-family: monospace;
    font-size: 10.5px;
    padding: 6px;
}
"""


class WebDeskApp(Gtk.Window):
    def __init__(self):
        super().__init__(title="WebDesk Control Panel")
        self.set_default_size(880, 580)
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
            except Exception:
                pass
        return "dark"

    def save_theme_pref(self, theme_name):
        try:
            with open(THEME_FILE, 'w') as f:
                json.dump({"theme": theme_name}, f)
        except Exception:
            pass

    def apply_theme(self, theme_name):
        self.current_theme = theme_name
        self.save_theme_pref(theme_name)

        if theme_name == "light":
            css_data = THEME_CSS_LIGHT
        elif theme_name == "dark":
            css_data = THEME_CSS_DARK
        else:  # System
            settings = Gtk.Settings.get_default()
            is_dark = settings.get_property("gtk-application-prefer-dark-theme") if settings else True
            css_data = THEME_CSS_DARK if is_dark else THEME_CSS_LIGHT

        try:
            self.css_provider.load_from_data(css_data.encode('utf-8'))
        except Exception as e:
            print(f"[WebDesk GUI] CSS error: {e}", file=sys.stderr)

    def run_cmd(self, action, arg=""):
        try:
            cmd = [WEBDESK_SH, action]
            if arg:
                cmd.append(arg)
            res = subprocess.run(cmd, capture_output=True, text=True)
            return res.returncode == 0, res.stdout.strip()
        except Exception as e:
            return False, str(e)

    def get_config_var(self, key, default=""):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith(f"{key}="):
                            return line.split("=", 1)[1].strip().strip('"')
            except Exception:
                pass
        return default

    def get_active_display(self):
        act_file = os.path.join(INSTALL_DIR, "active_display")
        if os.path.exists(act_file):
            try:
                with open(act_file, 'r') as f:
                    v = f.read().strip()
                    if v:
                        return v
            except Exception:
                pass
        return os.environ.get("DISPLAY", ":0")

    def get_current_resolution(self):
        try:
            disp = self.get_active_display()
            env = dict(os.environ, DISPLAY=disp)
            auth_file = os.path.join(INSTALL_DIR, "active_auth")
            if os.path.exists(auth_file):
                try:
                    with open(auth_file, 'r') as f:
                        a = f.read().strip()
                        if a and os.path.exists(a):
                            env["XAUTHORITY"] = a
                except Exception:
                    pass
            out = subprocess.run(["xrandr"], env=env, capture_output=True, text=True).stdout
            for line in out.splitlines():
                if '*' in line:
                    return line.strip().split()[0]
        except Exception:
            pass
        return "1920x1080"

    def is_running(self):
        try:
            p1 = subprocess.run(["pgrep", "-f", "x11vnc"], capture_output=True)
            p2 = subprocess.run(["pgrep", "-f", "websockify"], capture_output=True)
            return p1.returncode == 0 and p2.returncode == 0
        except Exception:
            return False

    def is_audio_running(self):
        try:
            p = subprocess.run(["pgrep", "-f", "audio_server.py"], capture_output=True)
            return p.returncode == 0
        except Exception:
            return False

    def is_service_installed(self):
        return os.path.exists("/etc/systemd/system/webdesk.service")

    def is_service_active(self):
        try:
            return subprocess.run(["systemctl", "is-active", "webdesk.service"], capture_output=True).returncode == 0
        except Exception:
            return False

    def get_ips(self):
        ips = []
        try:
            out = subprocess.run(["ip", "-4", "addr", "show", "scope", "global"], capture_output=True, text=True).stdout
            for match in re.finditer(r'inet\s+(\d+\.\d+\.\d+\.\d+)', out):
                ip = match.group(1)
                if not ip.startswith('127.'):
                    ips.append(ip)
        except Exception:
            pass
        return ips or ["127.0.0.1"]

    def build_ui(self):
        root_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.add(root_box)

        # ----------------------------------------------------
        # 1. Left Sidebar Navigation
        # ----------------------------------------------------
        sidebar_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        sidebar_box.set_size_request(210, -1)
        sidebar_box.get_style_context().add_class("sidebar-box")

        # Sidebar Header / Brand
        header_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        header_box.get_style_context().add_class("sidebar-header")

        brand_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        brand_icon = Gtk.Image.new_from_icon_name("preferences-desktop-remote-desktop", Gtk.IconSize.DND)
        brand_row.pack_start(brand_icon, False, False, 0)

        brand_lbl = Gtk.Label(xalign=0)
        brand_lbl.set_markup("<b><span size='medium' color='#38bdf8'>WebDesk</span></b>\n<span size='small' color='#94a3b8'>Server v3.5.0</span>")
        brand_row.pack_start(brand_lbl, True, True, 0)
        header_box.pack_start(brand_row, False, False, 0)

        self.sidebar_status_badge = Gtk.Label(xalign=0)
        self.sidebar_status_badge.set_margin_top(6)
        header_box.pack_start(self.sidebar_status_badge, False, False, 0)
        sidebar_box.pack_start(header_box, False, False, 0)

        # Navigation Menu List
        self.nav_list = Gtk.ListBox()
        self.nav_list.get_style_context().add_class("sidebar-list")
        self.nav_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.nav_list.connect("row-selected", self.on_nav_row_selected)

        nav_items = [
            ("dashboard", "Dashboard"),
            ("display",   "Display & Screen"),
            ("profiles",  "Speed & Quality"),
            ("users",     "Web Accounts"),
            ("admin",     "Security & Master"),
            ("system",    "System Service"),
            ("rdp",       "Windows RDP"),
            ("logs",      "Logs & Diagnostics")
        ]

        for nav_id, nav_label in nav_items:
            row = Gtk.ListBoxRow()
            row.nav_id = nav_id
            lbl = Gtk.Label(label=nav_label, xalign=0)
            row.add(lbl)
            self.nav_list.add(row)

        sidebar_scroll = Gtk.ScrolledWindow()
        sidebar_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sidebar_scroll.add(self.nav_list)
        sidebar_box.pack_start(sidebar_scroll, True, True, 4)

        # Sidebar Footer: Theme Switcher
        sidebar_footer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        sidebar_footer.set_margin_start(10)
        sidebar_footer.set_margin_end(10)
        sidebar_footer.set_margin_bottom(12)

        theme_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        theme_lbl = Gtk.Label(label="Theme:", xalign=0)
        theme_lbl.get_style_context().add_class("card-header-lbl")
        theme_box.pack_start(theme_lbl, False, False, 0)

        self.theme_combo = Gtk.ComboBoxText()
        self.theme_combo.append("dark", "Dark")
        self.theme_combo.append("light", "Light")
        self.theme_combo.append("system", "Auto")
        self.theme_combo.set_active_id(self.current_theme)
        self.theme_combo.connect("changed", self.on_theme_changed)
        theme_box.pack_end(self.theme_combo, True, True, 0)
        sidebar_footer.pack_start(theme_box, False, False, 0)

        sidebar_box.pack_end(sidebar_footer, False, False, 0)
        root_box.pack_start(sidebar_box, False, False, 0)

        # ----------------------------------------------------
        # 2. Right Content Stack
        # ----------------------------------------------------
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack.set_transition_duration(150)

        # Build each view page
        self.stack.add_named(self.build_dashboard_page(), "dashboard")
        self.stack.add_named(self.build_display_page(), "display")
        self.stack.add_named(self.build_profiles_page(), "profiles")
        self.stack.add_named(self.build_users_page(), "users")
        self.stack.add_named(self.build_admin_page(), "admin")
        self.stack.add_named(self.build_system_page(), "system")
        self.stack.add_named(self.build_rdp_page(), "rdp")
        self.stack.add_named(self.build_logs_page(), "logs")

        # Container scroll for right pane
        content_scroll = Gtk.ScrolledWindow()
        content_scroll.get_style_context().add_class("content-pane")
        content_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        content_scroll.add(self.stack)
        root_box.pack_start(content_scroll, True, True, 0)

        # Select first nav row
        first_row = self.nav_list.get_row_at_index(0)
        if first_row:
            self.nav_list.select_row(first_row)

    def on_nav_row_selected(self, listbox, row):
        if row and hasattr(row, 'nav_id'):
            self.stack.set_visible_child_name(row.nav_id)

    # ------------------------------------------------------------------
    # View 1: Dashboard Page
    # ------------------------------------------------------------------
    def build_dashboard_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

        # Overview Card
        card_status = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card_status.get_style_context().add_class("card-panel")

        top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        title_lbl = Gtk.Label(xalign=0)
        title_lbl.set_markup("<b>SERVER STATUS &amp; CONTROLS</b>")
        title_lbl.get_style_context().add_class("card-header-lbl")
        top_row.pack_start(title_lbl, True, True, 0)

        self.dash_status_badge = Gtk.Label()
        top_row.pack_end(self.dash_status_badge, False, False, 0)
        card_status.pack_start(top_row, False, False, 0)

        # Server Control Buttons
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.btn_start = Gtk.Button(label="Start Server")
        self.btn_start.get_style_context().add_class("btn-primary")
        self.btn_start.connect("clicked", self.on_start_clicked)
        btn_box.pack_start(self.btn_start, True, True, 0)

        self.btn_stop = Gtk.Button(label="Stop Server")
        self.btn_stop.get_style_context().add_class("btn-danger")
        self.btn_stop.connect("clicked", self.on_stop_clicked)
        btn_box.pack_start(self.btn_stop, True, True, 0)

        self.btn_restart = Gtk.Button(label="Restart Server")
        self.btn_restart.get_style_context().add_class("btn-secondary")
        self.btn_restart.connect("clicked", self.on_restart_clicked)
        btn_box.pack_start(self.btn_restart, True, True, 0)
        card_status.pack_start(btn_box, False, False, 2)

        # Overview Metadata Grid
        meta_grid = Gtk.Grid()
        meta_grid.set_column_spacing(16)
        meta_grid.set_row_spacing(6)
        meta_grid.set_margin_top(4)

        meta_grid.attach(Gtk.Label(label="Active Display:", xalign=0), 0, 0, 1, 1)
        self.dash_disp_lbl = Gtk.Label(xalign=0)
        meta_grid.attach(self.dash_disp_lbl, 1, 0, 1, 1)

        meta_grid.attach(Gtk.Label(label="Active Profile:", xalign=0), 2, 0, 1, 1)
        self.dash_prof_lbl = Gtk.Label(xalign=0)
        meta_grid.attach(self.dash_prof_lbl, 3, 0, 1, 1)

        meta_grid.attach(Gtk.Label(label="Resolution:", xalign=0), 0, 1, 1, 1)
        self.dash_res_lbl = Gtk.Label(xalign=0)
        meta_grid.attach(self.dash_res_lbl, 1, 1, 1, 1)

        meta_grid.attach(Gtk.Label(label="Service Mode:", xalign=0), 2, 1, 1, 1)
        self.dash_svc_lbl = Gtk.Label(xalign=0)
        meta_grid.attach(self.dash_svc_lbl, 3, 1, 1, 1)

        card_status.pack_start(meta_grid, False, False, 0)
        page.pack_start(card_status, False, False, 0)

        # In-Browser Access URLs Card
        card_urls = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        card_urls.get_style_context().add_class("card-panel")

        url_hdr = Gtk.Label(label="ENCRYPTED BROWSER ACCESS LINKS (HTTPS)", xalign=0)
        url_hdr.get_style_context().add_class("card-header-lbl")
        card_urls.pack_start(url_hdr, False, False, 0)

        self.url_list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        card_urls.pack_start(self.url_list_box, False, False, 0)
        page.pack_start(card_urls, False, False, 0)

        # Port Summary Card
        card_ports = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        card_ports.get_style_context().add_class("card-panel")

        port_info = [
            ("Web / HTTPS", "6080"),
            ("Audio Stream", "6086"),
            ("API Daemon", "6085"),
            ("Windows RDP", "3389")
        ]
        for name, port in port_info:
            pbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            lbl_n = Gtk.Label(label=name, xalign=0.5)
            lbl_n.get_style_context().add_class("card-header-lbl")
            lbl_p = Gtk.Label(xalign=0.5)
            lbl_p.set_markup(f"<span font_weight='bold' color='#38bdf8'>Port {port}</span>")
            pbox.pack_start(lbl_n, False, False, 0)
            pbox.pack_start(lbl_p, False, False, 0)
            card_ports.pack_start(pbox, True, True, 0)

        page.pack_start(card_ports, False, False, 0)
        return page

    # ------------------------------------------------------------------
    # View 2: Display & Screen Page
    # ------------------------------------------------------------------
    def build_display_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

        # Target Display Card
        card_disp = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card_disp.get_style_context().add_class("card-panel")

        hdr_disp = Gtk.Label(label="TARGET DESKTOP DISPLAY / SESSION CAPTURE", xalign=0)
        hdr_disp.get_style_context().add_class("card-header-lbl")
        card_disp.pack_start(hdr_disp, False, False, 0)

        desc_disp = Gtk.Label(
            label="Select the X11 display that WebDesk will capture and stream to browsers and Windows RDP Mode 1.",
            xalign=0
        )
        desc_disp.set_line_wrap(True)
        card_disp.pack_start(desc_disp, False, False, 0)

        grid_d = Gtk.Grid()
        grid_d.set_column_spacing(10)
        grid_d.set_row_spacing(8)
        grid_d.set_margin_top(4)

        grid_d.attach(Gtk.Label(label="Current Target Setting:", xalign=0), 0, 0, 1, 1)
        self.disp_target_val_lbl = Gtk.Label(xalign=0)
        grid_d.attach(self.disp_target_val_lbl, 1, 0, 1, 1)

        grid_d.attach(Gtk.Label(label="Live Detected Display:", xalign=0), 0, 1, 1, 1)
        self.disp_detected_val_lbl = Gtk.Label(xalign=0)
        grid_d.attach(self.disp_detected_val_lbl, 1, 1, 1, 1)

        grid_d.attach(Gtk.Label(label="Target Selection:", xalign=0), 0, 2, 1, 1)

        self.disp_selector_combo = Gtk.ComboBoxText()
        self.disp_selector_combo.append("auto", "Auto-Detect (Recommended)")
        self.disp_selector_combo.append(":1001", "NoMachine Session (:1001)")
        self.disp_selector_combo.append(":0", "Physical / Default Console (:0)")
        self.disp_selector_combo.append(":10", "Windows XRDP Session (:10)")
        self.disp_selector_combo.append("custom", "Custom Display Number...")
        self.disp_selector_combo.set_active_id(self.get_config_var("TARGET_DISPLAY", "auto"))
        self.disp_selector_combo.connect("changed", self.on_disp_combo_changed)
        grid_d.attach(self.disp_selector_combo, 1, 2, 1, 1)

        self.custom_disp_entry = Gtk.Entry()
        self.custom_disp_entry.set_placeholder_text("e.g. :1002")
        self.custom_disp_entry.set_no_show_all(True)
        self.custom_disp_entry.hide()
        grid_d.attach(self.custom_disp_entry, 1, 3, 1, 1)

        btn_apply_disp = Gtk.Button(label="Apply Target Display")
        btn_apply_disp.get_style_context().add_class("btn-primary")
        btn_apply_disp.connect("clicked", self.on_apply_disp_clicked)
        grid_d.attach(btn_apply_disp, 1, 4, 1, 1)

        card_disp.pack_start(grid_d, False, False, 0)
        page.pack_start(card_disp, False, False, 0)

        # Resolution Settings Card
        card_res = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card_res.get_style_context().add_class("card-panel")

        hdr_res = Gtk.Label(label="REMOTE DESKTOP RESOLUTION", xalign=0)
        hdr_res.get_style_context().add_class("card-header-lbl")
        card_res.pack_start(hdr_res, False, False, 0)

        grid_r = Gtk.Grid()
        grid_r.set_column_spacing(10)
        grid_r.set_row_spacing(8)

        grid_r.attach(Gtk.Label(label="Resolution Preset:", xalign=0), 0, 0, 1, 1)
        self.res_combo = Gtk.ComboBoxText()
        for res_id, res_label in RESOLUTIONS:
            self.res_combo.append(res_id, res_label)
        cur_res = self.get_current_resolution()
        valid_res = [r[0] for r in RESOLUTIONS]
        self.res_combo.set_active_id(cur_res if cur_res in valid_res else "1920x1080")
        grid_r.attach(self.res_combo, 1, 0, 1, 1)

        btn_apply_res = Gtk.Button(label="Apply Resolution")
        btn_apply_res.get_style_context().add_class("btn-secondary")
        btn_apply_res.connect("clicked", lambda b: self.run_cmd("resolution", self.res_combo.get_active_id() or "1920x1080"))
        grid_r.attach(btn_apply_res, 2, 0, 1, 1)

        btn_match_res = Gtk.Button(label="Auto Match Client")
        btn_match_res.get_style_context().add_class("btn-secondary")
        btn_match_res.connect("clicked", lambda b: self.run_cmd("resolution", "1920x1080"))
        grid_r.attach(btn_match_res, 3, 0, 1, 1)

        card_res.pack_start(grid_r, False, False, 0)
        page.pack_start(card_res, False, False, 0)
        return page

    def on_disp_combo_changed(self, combo):
        c_id = combo.get_active_id()
        if c_id == "custom":
            self.custom_disp_entry.show()
        else:
            self.custom_disp_entry.hide()

    def on_apply_disp_clicked(self, btn):
        sel = self.disp_selector_combo.get_active_id()
        if sel == "custom":
            custom_val = self.custom_disp_entry.get_text().strip()
            if not custom_val.startswith(":"):
                custom_val = f":{custom_val}"
            sel = custom_val
        if sel:
            self.run_cmd("display", sel)
            self.refresh_status()

    # ------------------------------------------------------------------
    # View 3: Speed & Quality (Profiles)
    # ------------------------------------------------------------------
    def build_profiles_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

        card_prof = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card_prof.get_style_context().add_class("card-panel")

        hdr_prof = Gtk.Label(label="STREAMING SPEED &amp; QUALITY PROFILE", xalign=0)
        hdr_prof.get_style_context().add_class("card-header-lbl")
        card_prof.pack_start(hdr_prof, False, False, 0)

        desc_prof = Gtk.Label(
            label="Tune compression, frame rates, and encoding parameters for your network connection.",
            xalign=0
        )
        card_prof.pack_start(desc_prof, False, False, 0)

        self.prof_radio_group = {}
        first_radio = None

        cur_prof = self.get_config_var("PROFILE", "balanced")

        for p_id, (p_title, p_desc) in PROFILES.items():
            rbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            rbox.get_style_context().add_class("url-box")

            radio = Gtk.RadioButton.new_with_label_from_widget(first_radio, p_title)
            if first_radio is None:
                first_radio = radio
            radio.p_id = p_id
            if p_id == cur_prof:
                radio.set_active(True)

            radio.connect("toggled", self.on_profile_radio_toggled)
            rbox.pack_start(radio, False, False, 0)

            sub_lbl = Gtk.Label(xalign=0)
            sub_lbl.set_markup(f"<span size='small' color='#94a3b8'>{p_desc}</span>")
            sub_lbl.set_margin_start(24)
            rbox.pack_start(sub_lbl, False, False, 0)

            card_prof.pack_start(rbox, False, False, 2)
            self.prof_radio_group[p_id] = radio

        page.pack_start(card_prof, False, False, 0)
        return page

    def on_profile_radio_toggled(self, radio):
        if radio.get_active() and hasattr(radio, 'p_id'):
            self.run_cmd("profile", radio.p_id)
            self.refresh_status()

    # ------------------------------------------------------------------
    # View 4: Web Accounts & Roles
    # ------------------------------------------------------------------
    def build_users_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

        card_u = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card_u.get_style_context().add_class("card-panel")

        top_u = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        hdr_u = Gtk.Label(label="WEB USER ACCOUNTS &amp; ACCESS CONTROL", xalign=0)
        hdr_u.get_style_context().add_class("card-header-lbl")
        top_u.pack_start(hdr_u, True, True, 0)

        btn_unlock = Gtk.Button(label="Authenticate / Refresh")
        btn_unlock.get_style_context().add_class("btn-secondary")
        btn_unlock.connect("clicked", lambda b: self.populate_users_table())
        top_u.pack_end(btn_unlock, False, False, 0)
        card_u.pack_start(top_u, False, False, 0)

        self.users_list_box = Gtk.ListBox()
        self.users_list_box.get_style_context().add_class("users-list-box")
        self.users_list_box.set_selection_mode(Gtk.SelectionMode.NONE)

        scroll_u = Gtk.ScrolledWindow()
        scroll_u.set_min_content_height(160)
        scroll_u.add(self.users_list_box)
        card_u.pack_start(scroll_u, True, True, 0)
        page.pack_start(card_u, True, True, 0)

        # Add User Form
        card_add = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        card_add.get_style_context().add_class("card-panel")

        hdr_add = Gtk.Label(label="ADD NEW WEB ACCOUNT", xalign=0)
        hdr_add.get_style_context().add_class("card-header-lbl")
        card_add.pack_start(hdr_add, False, False, 0)

        grid_add = Gtk.Grid()
        grid_add.set_column_spacing(8)
        grid_add.set_row_spacing(6)

        self.entry_new_user = Gtk.Entry()
        self.entry_new_user.set_placeholder_text("Username")
        grid_add.attach(self.entry_new_user, 0, 0, 1, 1)

        self.entry_new_pass = Gtk.Entry()
        self.entry_new_pass.set_placeholder_text("Password")
        self.entry_new_pass.set_visibility(False)
        grid_add.attach(self.entry_new_pass, 1, 0, 1, 1)

        self.combo_new_role = Gtk.ComboBoxText()
        self.combo_new_role.append("user", "User (Interactive)")
        self.combo_new_role.append("viewer", "Guest (Viewer / View Only)")
        self.combo_new_role.append("admin", "Admin (Full Control)")
        self.combo_new_role.set_active_id("user")
        grid_add.attach(self.combo_new_role, 2, 0, 1, 1)

        btn_add_u = Gtk.Button(label="Add Account")
        btn_add_u.get_style_context().add_class("btn-primary")
        btn_add_u.connect("clicked", self.on_add_user_submit)
        grid_add.attach(btn_add_u, 3, 0, 1, 1)

        card_add.pack_start(grid_add, False, False, 0)

        # Backup & Reset Tools Row
        tools_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_export = Gtk.Button(label="Export Config (.json)")
        btn_export.get_style_context().add_class("btn-secondary")
        btn_export.connect("clicked", self.on_export_config_dialog)
        tools_row.pack_start(btn_export, True, True, 0)

        btn_import = Gtk.Button(label="Import Config (.json)")
        btn_import.get_style_context().add_class("btn-secondary")
        btn_import.connect("clicked", self.on_import_config_dialog)
        tools_row.pack_start(btn_import, True, True, 0)

        btn_reset_users = Gtk.Button(label="Reset to Factory Defaults")
        btn_reset_users.get_style_context().add_class("btn-danger")
        btn_reset_users.connect("clicked", self.on_reset_users_dialog)
        tools_row.pack_start(btn_reset_users, True, True, 0)

        card_add.pack_start(tools_row, False, False, 4)
        page.pack_start(card_add, False, False, 0)

        GLib.idle_add(self.populate_users_table)
        return page

    def populate_users_table(self):
        for child in self.users_list_box.get_children():
            self.users_list_box.remove(child)

        try:
            import user_auth
            users = user_auth.list_users()
            for u in users:
                row = Gtk.ListBoxRow()
                hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
                hbox.set_margin_top(4)
                hbox.set_margin_bottom(4)

                role_str = u.get("role", "user").upper()
                is_susp = u.get("status") == "suspended"
                status_lbl = "<span color='#f87171'><b>[ Suspended ]</b></span>" if is_susp else "<span color='#4ade80'><b>[ Active ]</b></span>"

                info_lbl = Gtk.Label(xalign=0)
                info_lbl.set_markup(f"<b><span color='#38bdf8'>{u['username']}</span></b> <span size='small' color='#94a3b8'>({role_str})</span> {status_lbl}")
                hbox.pack_start(info_lbl, True, True, 0)

                btn_pw = Gtk.Button(label="Password")
                btn_pw.get_style_context().add_class("btn-secondary")
                btn_pw.connect("clicked", lambda b, un=u['username']: self.on_change_pw_dialog(un))
                hbox.pack_start(btn_pw, False, False, 0)

                if u['username'] != "admin":
                    if is_susp:
                        btn_susp = Gtk.Button(label="Activate")
                        btn_susp.get_style_context().add_class("btn-success")
                        btn_susp.connect("clicked", lambda b, un=u['username']: self.on_toggle_suspend(un, False))
                    else:
                        btn_susp = Gtk.Button(label="Suspend")
                        btn_susp.get_style_context().add_class("btn-secondary")
                        btn_susp.connect("clicked", lambda b, un=u['username']: self.on_toggle_suspend(un, True))
                    hbox.pack_start(btn_susp, False, False, 0)

                    btn_del = Gtk.Button(label="Delete")
                    btn_del.get_style_context().add_class("btn-danger")
                    btn_del.connect("clicked", lambda b, un=u['username']: self.on_delete_user_dialog(un))
                    hbox.pack_start(btn_del, False, False, 0)

                row.add(hbox)
                self.users_list_box.add(row)
        except Exception as e:
            row = Gtk.ListBoxRow()
            err_lbl = Gtk.Label(label=f"User database notice: {e}", xalign=0)
            row.add(err_lbl)
            self.users_list_box.add(row)

        self.users_list_box.show_all()

    def on_add_user_submit(self, btn):
        u = self.entry_new_user.get_text().strip()
        p = self.entry_new_pass.get_text().strip()
        r = self.combo_new_role.get_active_id() or "user"
        if u and p:
            try:
                import user_auth
                ok, msg = user_auth.add_user("admin", u, p, r)
                if ok:
                    self.entry_new_user.set_text("")
                    self.entry_new_pass.set_text("")
                    self.populate_users_table()
                else:
                    self.show_error_dialog("Add User Error", msg)
            except Exception as e:
                self.show_error_dialog("Add User Error", str(e))

    def on_change_pw_dialog(self, username):
        dialog = Gtk.Dialog(title=f"Change Password: {username}", transient_for=self, flags=0)
        dialog.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "Save", Gtk.ResponseType.OK)
        c = dialog.get_content_area()
        c.set_spacing(6)
        c.set_margin_start(12)
        c.set_margin_end(12)
        c.set_margin_top(12)

        c.pack_start(Gtk.Label(label=f"Enter new password for '{username}':", xalign=0), False, False, 0)
        entry = Gtk.Entry()
        entry.set_visibility(False)
        c.pack_start(entry, False, False, 0)
        dialog.show_all()

        if dialog.run() == Gtk.ResponseType.OK and entry.get_text():
            try:
                import user_auth
                user_auth.change_password("admin", "admin", username, entry.get_text())
                self.populate_users_table()
            except Exception as e:
                self.show_error_dialog("Change Password Error", str(e))
        dialog.destroy()

    def on_toggle_suspend(self, username, suspend=True):
        try:
            import user_auth
            if suspend:
                user_auth.suspend_user("admin", username)
            else:
                user_auth.unsuspend_user("admin", username)
            self.populate_users_table()
        except Exception:
            pass

    def on_delete_user_dialog(self, username):
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            text=f"Delete User Account '{username}'?"
        )
        dialog.format_secondary_text("This action cannot be undone.")
        if dialog.run() == Gtk.ResponseType.OK:
            try:
                import user_auth
                user_auth.delete_user("admin", "", username)
                self.populate_users_table()
            except Exception as e:
                self.show_error_dialog("Delete User Error", str(e))
        dialog.destroy()

    def on_reset_users_dialog(self, btn):
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            text="Reset User Accounts to Factory Defaults?"
        )
        dialog.format_secondary_text(
            "This restores standard logins:\n• admin : admin123\n• user : user123\n• guest : guest123\n\nContinue?"
        )
        if dialog.run() == Gtk.ResponseType.OK:
            try:
                import user_auth
                user_auth.reset_default_users()
                self.populate_users_table()
            except Exception as e:
                self.show_error_dialog("Reset Error", str(e))
        dialog.destroy()

    def on_export_config_dialog(self, btn):
        chooser = Gtk.FileChooserDialog(
            title="Export WebDesk Configuration",
            parent=self,
            action=Gtk.FileChooserAction.SAVE
        )
        chooser.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "Save", Gtk.ResponseType.OK)
        chooser.set_current_name("webdesk_config_backup.json")
        chooser.set_do_overwrite_confirmation(True)
        if chooser.run() == Gtk.ResponseType.OK:
            path = chooser.get_filename()
            chooser.destroy()
            try:
                import user_auth
                ok, msg, _ = user_auth.export_config(path)
                self.show_info_dialog("Export Configuration", msg)
            except Exception as e:
                self.show_error_dialog("Export Error", str(e))
        else:
            chooser.destroy()

    def on_import_config_dialog(self, btn):
        chooser = Gtk.FileChooserDialog(
            title="Import WebDesk Configuration",
            parent=self,
            action=Gtk.FileChooserAction.OPEN
        )
        chooser.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "Open", Gtk.ResponseType.OK)
        f_json = Gtk.FileFilter()
        f_json.set_name("JSON Files")
        f_json.add_pattern("*.json")
        chooser.add_filter(f_json)
        if chooser.run() == Gtk.ResponseType.OK:
            path = chooser.get_filename()
            chooser.destroy()
            try:
                import user_auth
                ok, msg = user_auth.import_config(path)
                self.show_info_dialog("Import Configuration", msg)
                self.populate_users_table()
            except Exception as e:
                self.show_error_dialog("Import Error", str(e))
        else:
            chooser.destroy()

    # ------------------------------------------------------------------
    # View 5: Security & Master Password
    # ------------------------------------------------------------------
    def build_admin_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

        # Master Password Card
        card_mp = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card_mp.get_style_context().add_class("card-panel")

        hdr_mp = Gtk.Label(label="MASTER PASSWORD &amp; TERMINAL SECURITY", xalign=0)
        hdr_mp.get_style_context().add_class("card-header-lbl")
        card_mp.pack_start(hdr_mp, False, False, 0)

        now = datetime.datetime.now()
        today_pass = f"Pass@{now.strftime('%a')}{now.day}"

        rule_info = Gtk.Label(xalign=0)
        rule_info.set_markup(
            f"The Master Password protects CLI admin menus, user database changes, and XRDP settings.\n"
            f"• Dynamic Daily Rule Formula: <b>Pass@&lt;Day&gt;&lt;Date&gt;</b> (Today: <span color='#38bdf8'><b>{today_pass}</b></span>)"
        )
        rule_info.set_line_wrap(True)
        card_mp.pack_start(rule_info, False, False, 0)

        mp_btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_set_custom_mp = Gtk.Button(label="Set Custom Master Password")
        btn_set_custom_mp.get_style_context().add_class("btn-primary")
        btn_set_custom_mp.connect("clicked", self.on_set_custom_mp_dialog)
        mp_btn_row.pack_start(btn_set_custom_mp, True, True, 0)

        btn_reset_rule_mp = Gtk.Button(label="Reset to Dynamic Daily Rule")
        btn_reset_rule_mp.get_style_context().add_class("btn-secondary")
        btn_reset_rule_mp.connect("clicked", self.on_reset_rule_mp)
        mp_btn_row.pack_start(btn_reset_rule_mp, True, True, 0)
        card_mp.pack_start(mp_btn_row, False, False, 2)

        page.pack_start(card_mp, False, False, 0)

        # SSL/TLS Certificate Management Card
        card_ssl = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card_ssl.get_style_context().add_class("card-panel")

        hdr_ssl = Gtk.Label(label="TLS / SSL CERTIFICATE MANAGEMENT", xalign=0)
        hdr_ssl.get_style_context().add_class("card-header-lbl")
        card_ssl.pack_start(hdr_ssl, False, False, 0)

        desc_ssl = Gtk.Label(
            label="WebDesk generates self-signed TLS certificates for end-to-end WSS browser encryption.",
            xalign=0
        )
        card_ssl.pack_start(desc_ssl, False, False, 0)

        ssl_btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_renew_ssl = Gtk.Button(label="Renew / Reissue TLS Certificate")
        btn_renew_ssl.get_style_context().add_class("btn-secondary")
        btn_renew_ssl.connect("clicked", self.on_renew_cert)
        ssl_btn_row.pack_start(btn_renew_ssl, False, False, 0)
        card_ssl.pack_start(ssl_btn_row, False, False, 0)

        page.pack_start(card_ssl, False, False, 0)

        # Audit Logs Preview Card
        card_audit = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        card_audit.get_style_context().add_class("card-panel")

        hdr_audit = Gtk.Label(label="RECENT LOGIN &amp; CLIENT AUDIT LOGS", xalign=0)
        hdr_audit.get_style_context().add_class("card-header-lbl")
        card_audit.pack_start(hdr_audit, False, False, 0)

        self.audit_textview = Gtk.TextView()
        self.audit_textview.set_editable(False)
        self.audit_textview.set_cursor_visible(False)

        audit_scroll = Gtk.ScrolledWindow()
        audit_scroll.set_min_content_height(110)
        audit_scroll.add(self.audit_textview)
        card_audit.pack_start(audit_scroll, True, True, 0)

        page.pack_start(card_audit, True, True, 0)
        GLib.idle_add(self.refresh_audit_logs)
        return page

    def on_set_custom_mp_dialog(self, btn):
        dialog = Gtk.Dialog(title="Set Custom Master Password", transient_for=self, flags=0)
        dialog.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "Set Password", Gtk.ResponseType.OK)
        c = dialog.get_content_area()
        c.set_spacing(6)
        c.set_margin_start(12)
        c.set_margin_end(12)
        c.set_margin_top(12)

        c.pack_start(Gtk.Label(label="Enter new master password (minimum 6 characters):", xalign=0), False, False, 0)
        entry = Gtk.Entry()
        entry.set_visibility(False)
        c.pack_start(entry, False, False, 0)
        dialog.show_all()

        if dialog.run() == Gtk.ResponseType.OK:
            val = entry.get_text().strip()
            if len(val) >= 6:
                try:
                    import user_auth
                    user_auth.set_custom_master_password(val)
                    self.show_info_dialog("Master Password", "Custom Master Password saved successfully.")
                except Exception as e:
                    self.show_error_dialog("Error", str(e))
            else:
                self.show_error_dialog("Error", "Password must be at least 6 characters.")
        dialog.destroy()

    def on_reset_rule_mp(self, btn):
        try:
            import user_auth
            user_auth.reset_master_password_to_rule()
            self.show_info_dialog("Master Password", "Master Password reset to dynamic daily rule.")
        except Exception as e:
            self.show_error_dialog("Error", str(e))

    def refresh_audit_logs(self):
        buf = self.audit_textview.get_buffer()
        if os.path.exists(AUDIT_LOG_FILE):
            try:
                with open(AUDIT_LOG_FILE, 'r') as f:
                    lines = f.readlines()
                    text = "".join(lines[-15:])
                    buf.set_text(text)
                    return
            except Exception:
                pass
        buf.set_text("No login audit records found.")

    # ------------------------------------------------------------------
    # View 6: System & 24/7 Service
    # ------------------------------------------------------------------
    def build_system_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

        # 24/7 System Service Card
        card_svc = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card_svc.get_style_context().add_class("card-panel")

        hdr_svc = Gtk.Label(label="24/7 BACKGROUND STREAMING SERVICE", xalign=0)
        hdr_svc.get_style_context().add_class("card-header-lbl")
        card_svc.pack_start(hdr_svc, False, False, 0)

        desc_svc = Gtk.Label(
            label="The 24/7 system service streams the Display Manager login screen (LightDM / GDM) and survives user logouts.",
            xalign=0
        )
        desc_svc.set_line_wrap(True)
        card_svc.pack_start(desc_svc, False, False, 0)

        svc_status_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        svc_status_row.pack_start(Gtk.Label(label="System Service Status:", xalign=0), False, False, 0)
        self.sys_svc_status_lbl = Gtk.Label(xalign=0)
        svc_status_row.pack_start(self.sys_svc_status_lbl, True, True, 0)
        card_svc.pack_start(svc_status_row, False, False, 0)

        svc_btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_restart_svc = Gtk.Button(label="Restart Service")
        btn_restart_svc.get_style_context().add_class("btn-secondary")
        btn_restart_svc.connect("clicked", lambda b: self.run_cmd("restart-service"))
        svc_btn_row.pack_start(btn_restart_svc, True, True, 0)

        btn_install_svc = Gtk.Button(label="Install / Enable 24/7 Service")
        btn_install_svc.get_style_context().add_class("btn-primary")
        btn_install_svc.connect("clicked", lambda b: self.run_cmd("install-service"))
        svc_btn_row.pack_start(btn_install_svc, True, True, 0)

        btn_uninstall_svc = Gtk.Button(label="Disable Service")
        btn_uninstall_svc.get_style_context().add_class("btn-danger")
        btn_uninstall_svc.connect("clicked", lambda b: self.run_cmd("uninstall-service"))
        svc_btn_row.pack_start(btn_uninstall_svc, True, True, 0)
        card_svc.pack_start(svc_btn_row, False, False, 2)

        page.pack_start(card_svc, False, False, 0)

        # Autostart & Local Tools Card
        card_tools = Gtk.Grid()
        card_tools.set_column_spacing(10)
        card_tools.set_row_spacing(8)
        card_tools.get_style_context().add_class("card-panel")

        card_tools.attach(Gtk.Label(label="Start on Desktop Login:", xalign=0), 0, 0, 1, 1)
        self.auto_switch = Gtk.Switch()
        self.auto_switch.set_valign(Gtk.Align.CENTER)
        self.auto_switch.connect("state-set", self.on_autostart_toggled)
        card_tools.attach(self.auto_switch, 1, 0, 1, 1)

        card_tools.attach(Gtk.Label(label="Remote Audio Streaming:", xalign=0), 0, 1, 1, 1)
        self.sys_audio_status_lbl = Gtk.Label(xalign=0)
        card_tools.attach(self.sys_audio_status_lbl, 1, 1, 1, 1)

        card_tools.attach(Gtk.Label(label="Drag &amp; Drop Downloads Folder:", xalign=0), 0, 2, 1, 1)
        btn_open_dl = Gtk.Button(label="Open ~/Downloads")
        btn_open_dl.get_style_context().add_class("btn-secondary")
        btn_open_dl.connect("clicked", lambda b: subprocess.Popen(["xdg-open", DOWNLOADS_DIR]))
        card_tools.attach(btn_open_dl, 1, 2, 1, 1)

        page.pack_start(card_tools, False, False, 0)
        return page

    # ------------------------------------------------------------------
    # View 7: Windows RDP (XRDP)
    # ------------------------------------------------------------------
    def build_rdp_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

        card_rdp = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card_rdp.get_style_context().add_class("card-panel")

        hdr_rdp = Gtk.Label(label="WINDOWS REMOTE DESKTOP PROTOCOL (XRDP)", xalign=0)
        hdr_rdp.get_style_context().add_class("card-header-lbl")
        card_rdp.pack_start(hdr_rdp, False, False, 0)

        desc_rdp = Gtk.Label(
            label="Connect natively using standard Windows Remote Desktop client (mstsc.exe) on port 3389.",
            xalign=0
        )
        card_rdp.pack_start(desc_rdp, False, False, 0)

        grid_rdp = Gtk.Grid()
        grid_rdp.set_column_spacing(10)
        grid_rdp.set_row_spacing(8)

        grid_rdp.attach(Gtk.Label(label="RDP Server Status:", xalign=0), 0, 0, 1, 1)
        self.rdp_status_val_lbl = Gtk.Label(xalign=0)
        grid_rdp.attach(self.rdp_status_val_lbl, 1, 0, 1, 1)

        grid_rdp.attach(Gtk.Label(label="RDP Session Mode:", xalign=0), 0, 1, 1, 1)
        self.rdp_mode_combo = Gtk.ComboBoxText()
        self.rdp_mode_combo.append("1", "Mode 1: Live Screen Mirror (Current Display)")
        self.rdp_mode_combo.append("2", "Mode 2: Dedicated Virtual Session")
        self.rdp_mode_combo.append("3", "Mode 3: Multi-User Workstation")
        self.rdp_mode_combo.set_active_id(self.get_config_var("RDP_MODE", "1"))
        self.rdp_mode_combo.connect("changed", self.on_rdp_mode_changed)
        grid_rdp.attach(self.rdp_mode_combo, 1, 1, 1, 1)

        grid_rdp.attach(Gtk.Label(label="RDP Port:", xalign=0), 0, 2, 1, 1)
        self.rdp_port_entry = Gtk.Entry()
        self.rdp_port_entry.set_text(self.get_config_var("RDP_PORT", "3389"))
        grid_rdp.attach(self.rdp_port_entry, 1, 2, 1, 1)

        card_rdp.pack_start(grid_rdp, False, False, 0)

        rdp_btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_restart_rdp = Gtk.Button(label="Restart XRDP Server")
        btn_restart_rdp.get_style_context().add_class("btn-secondary")
        btn_restart_rdp.connect("clicked", lambda b: self.run_cmd("rdp-restart"))
        rdp_btn_row.pack_start(btn_restart_rdp, True, True, 0)

        btn_apply_rdp_port = Gtk.Button(label="Apply Port")
        btn_apply_rdp_port.get_style_context().add_class("btn-primary")
        btn_apply_rdp_port.connect("clicked", lambda b: self.run_cmd("rdp-port", self.rdp_port_entry.get_text().strip() or "3389"))
        rdp_btn_row.pack_start(btn_apply_rdp_port, True, True, 0)
        card_rdp.pack_start(rdp_btn_row, False, False, 2)

        page.pack_start(card_rdp, False, False, 0)
        return page

    def on_rdp_mode_changed(self, combo):
        m_id = combo.get_active_id()
        if m_id:
            self.run_cmd("rdp-mode", m_id)

    # ------------------------------------------------------------------
    # View 8: Logs & Diagnostics
    # ------------------------------------------------------------------
    def build_logs_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)

        card_log = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        card_log.get_style_context().add_class("card-panel")

        top_l = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        hdr_log = Gtk.Label(label="LIVE WEBDESK SYSTEM LOGS", xalign=0)
        hdr_log.get_style_context().add_class("card-header-lbl")
        top_l.pack_start(hdr_log, True, True, 0)

        btn_diag = Gtk.Button(label="Run Health Diagnostics")
        btn_diag.get_style_context().add_class("btn-secondary")
        btn_diag.connect("clicked", lambda b: self.run_cmd("healthcheck"))
        top_l.pack_end(btn_diag, False, False, 0)

        btn_ref_log = Gtk.Button(label="Refresh Logs")
        btn_ref_log.get_style_context().add_class("btn-secondary")
        btn_ref_log.connect("clicked", lambda b: self.refresh_logs_view())
        top_l.pack_end(btn_ref_log, False, False, 0)
        card_log.pack_start(top_l, False, False, 0)

        self.logs_textview = Gtk.TextView()
        self.logs_textview.set_editable(False)
        self.logs_textview.set_cursor_visible(False)

        logs_scroll = Gtk.ScrolledWindow()
        logs_scroll.set_min_content_height(320)
        logs_scroll.add(self.logs_textview)
        card_log.pack_start(logs_scroll, True, True, 0)

        page.pack_start(card_log, True, True, 0)
        GLib.idle_add(self.refresh_logs_view)
        return page

    def refresh_logs_view(self):
        buf = self.logs_textview.get_buffer()
        if os.path.exists(LOG_FILE):
            try:
                with open(LOG_FILE, 'r') as f:
                    lines = f.readlines()
                    buf.set_text("".join(lines[-100:]))
                    return
            except Exception:
                pass
        buf.set_text("No log records available yet.")

    # ------------------------------------------------------------------
    # Status Polling & Periodic Refresh
    # ------------------------------------------------------------------
    def refresh_status(self):
        running = self.is_running()
        audio_running = self.is_audio_running()
        active_disp = self.get_active_display()
        active_prof = self.get_config_var("PROFILE", "balanced")
        target_disp = self.get_config_var("TARGET_DISPLAY", "auto")
        cur_res = self.get_current_resolution()

        # Update Sidebar Badge
        self.sidebar_status_badge.get_style_context().remove_class("badge-running")
        self.sidebar_status_badge.get_style_context().remove_class("badge-stopped")
        self.dash_status_badge.get_style_context().remove_class("badge-running")
        self.dash_status_badge.get_style_context().remove_class("badge-stopped")

        if running:
            self.sidebar_status_badge.set_text("[ RUNNING ]")
            self.sidebar_status_badge.get_style_context().add_class("badge-running")
            self.dash_status_badge.set_text("ACTIVE & STREAMING")
            self.dash_status_badge.get_style_context().add_class("badge-running")
            self.btn_start.set_sensitive(False)
            self.btn_stop.set_sensitive(True)
        else:
            self.sidebar_status_badge.set_text("[ STOPPED ]")
            self.sidebar_status_badge.get_style_context().add_class("badge-stopped")
            self.dash_status_badge.set_text("INACTIVE / STOPPED")
            self.dash_status_badge.get_style_context().add_class("badge-stopped")
            self.btn_start.set_sensitive(True)
            self.btn_stop.set_sensitive(False)

        # Update Dashboard Metadata
        self.dash_disp_lbl.set_markup(f"<span font_weight='bold' color='#38bdf8'>{active_disp}</span> <span size='small'>({target_disp})</span>")
        self.dash_prof_lbl.set_markup(f"<b>{active_prof.capitalize()}</b>")
        self.dash_res_lbl.set_markup(f"<b>{cur_res}</b>")

        svc_inst = self.is_service_installed()
        svc_act = self.is_service_active()
        if svc_act:
            self.dash_svc_lbl.set_markup("<span color='#4ade80'>24/7 System Service (Active)</span>")
            self.sys_svc_status_lbl.set_markup("<span color='#4ade80'><b>Active (Login Screen / LightDM Enabled)</b></span>")
        elif svc_inst:
            self.dash_svc_lbl.set_markup("<span color='#f87171'>System Service (Stopped)</span>")
            self.sys_svc_status_lbl.set_markup("<span color='#f87171'><b>Installed (Inactive)</b></span>")
        else:
            self.dash_svc_lbl.set_markup("<span>User Session Mode</span>")
            self.sys_svc_status_lbl.set_markup("<span>User Mode (Exits on logout)</span>")

        # Update Display Page
        self.disp_target_val_lbl.set_markup(f"<span font_weight='bold' color='#38bdf8'>{target_disp}</span>")
        self.disp_detected_val_lbl.set_markup(f"<span font_weight='bold'>{active_disp}</span>")

        # Update Audio Status
        if audio_running:
            self.sys_audio_status_lbl.set_markup("<span color='#4ade80'><b>Active (:6086)</b></span>")
        else:
            self.sys_audio_status_lbl.set_markup("<span color='#94a3b8'>Idle</span>")

        # Update RDP Status
        rdp_active = subprocess.run(["pgrep", "-f", "xrdp"], capture_output=True).returncode == 0
        if rdp_active:
            self.rdp_status_val_lbl.set_markup("<span color='#4ade80'><b>Active (Port 3389)</b></span>")
        else:
            self.rdp_status_val_lbl.set_markup("<span color='#94a3b8'>Inactive</span>")

        # Update URL list
        for child in self.url_list_box.get_children():
            self.url_list_box.remove(child)

        if running:
            ips = self.get_ips()
            for ip in ips:
                url = f"https://{ip}:6080/"
                row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
                row.get_style_context().add_class("url-box")

                lbl = Gtk.Label(xalign=0)
                lbl.set_markup(f"<span font_family='monospace' font_weight='bold' color='#38bdf8'>{url}</span>")
                row.pack_start(lbl, True, True, 0)

                btn_copy = Gtk.Button(label="Copy")
                btn_copy.get_style_context().add_class("btn-secondary")
                btn_copy.connect("clicked", lambda b, u=url: self.copy_to_clipboard(u))
                row.pack_end(btn_copy, False, False, 0)

                btn_open = Gtk.Button(label="Open")
                btn_open.get_style_context().add_class("btn-primary")
                btn_open.connect("clicked", lambda b, u=url: subprocess.Popen(["xdg-open", u]))
                row.pack_end(btn_open, False, False, 0)

                self.url_list_box.pack_start(row, False, False, 0)
        else:
            empty_lbl = Gtk.Label(label="Server is stopped. Click 'Start Server' to generate connection links.", xalign=0)
            self.url_list_box.pack_start(empty_lbl, False, False, 2)

        self.url_list_box.show_all()

        # Update autostart switch
        self.auto_switch.handler_block_by_func(self.on_autostart_toggled)
        self.auto_switch.set_active(os.path.exists(AUTOSTART_FILE))
        self.auto_switch.handler_unblock_by_func(self.on_autostart_toggled)

        return True

    # ------------------------------------------------------------------
    # Actions & Helpers
    # ------------------------------------------------------------------
    def copy_to_clipboard(self, text):
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(text, -1)
        self.show_info_dialog("Link Copied", f"{text}\n\nCopied to clipboard.")

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

    def on_theme_changed(self, combo):
        theme_id = combo.get_active_id()
        if theme_id:
            self.apply_theme(theme_id)

    def on_renew_cert(self, btn):
        self.run_cmd("renew-cert")
        self.refresh_status()
        self.show_info_dialog("TLS Certificate", "A new TLS/SSL certificate was generated for active IP addresses.")

    def show_info_dialog(self, title, msg):
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text=title
        )
        dialog.format_secondary_text(msg)
        dialog.run()
        dialog.destroy()

    def show_error_dialog(self, title, msg):
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=title
        )
        dialog.format_secondary_text(msg)
        dialog.run()
        dialog.destroy()


def main():
    app = WebDeskApp()
    app.connect("destroy", Gtk.main_quit)
    app.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()
