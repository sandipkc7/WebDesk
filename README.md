# 🖥️ WebDesk — Comprehensive System & CLI Documentation

**WebDesk** is a self-contained, high-performance, encrypted in-browser desktop streaming server for Linux. It allows seamless remote access to a live Linux desktop (`DISPLAY=:0`) or display manager login screen (e.g., LightDM) through any modern web browser without requiring client-side software or browser plugins.

---

## 📑 Table of Contents

1. [Architecture & Technology Stack](#1-architecture--technology-stack)
2. [Network Ports & Directory Structure](#2-network-ports--directory-structure)
3. [Prerequisites & Installation](#3-prerequisites--installation)
4. [Command-Line Interface (CLI) Usage](#4-command-line-interface-cli-usage)
5. [Interactive Terminal Menu](#5-interactive-terminal-menu)
6. [Multi-User Web Authentication & Roles (RBAC)](#6-multi-user-web-authentication--roles-rbac)
7. [Comprehensive Features Guide](#7-comprehensive-features-guide)
   * [7.1 Performance & Speed/Quality Profiles](#71-performance--speedquality-profiles)
   * [7.2 Dynamic Screen Resolution Matching](#72-dynamic-screen-resolution-matching)
   * [7.3 Hardened View-Only / Guest Input Lock](#73-hardened-view-only--guest-input-lock)
   * [7.4 Low-Latency Remote Audio Streaming](#74-low-latency-remote-audio-streaming)
   * [7.5 Drag-and-Drop File Transfers](#75-drag-and-drop-file-transfers)
   * [7.6 Special Key Forwarder & Desktop Shortcuts](#76-special-key-forwarder--desktop-shortcuts)
   * [7.7 Remote Session & Power Controls](#77-remote-session--power-controls)
   * [7.8 24/7 System Service & Login Screen Streaming](#78-247-system-service--login-screen-streaming)
   * [7.9 Native GTK Control Panel (`webdesk_gui.py`)](#79-native-gtk-control-panel-webdesk_guipy)
8. [Configuration Files & Database](#8-configuration-files--database)
9. [Troubleshooting & FAQs](#9-troubleshooting--faqs)

---

## 1. Architecture & Technology Stack

WebDesk unites lightweight Linux desktop technologies into a unified pipeline:

```
[ Web Browser Client ]
        │  (HTTPS / WSS on Port 6080)
        ▼
[ Websockify (TLS/SSL Proxy) + noVNC Web Engine ]
        │  (Raw RFB Loopback 127.0.0.1:5900)
        ▼
[ x11vnc Engine ] ──► [ X11 Server (DISPLAY=:0) ] ◄── [ Desktop / Login Manager ]
        ▲
        │  (REST API HTTPS on Port 6085)
[ WebDesk API Server (api_server.py) ] ──► [ Auth DB (users.json) ]
        ▲
        │  (WebSocket Audio Stream on Port 6086)
[ WebDesk Audio Server (audio_server.py) ] ◄── [ PulseAudio / PipeWire Monitor ]
```

* **Display Engine**: `x11vnc` attached directly to physical or virtual `DISPLAY=:0`.
* **Transport Protocol**: Encrypted WebSocket (`wss://`) mediated by `websockify`.
* **Web Client**: Custom glassmorphic `noVNC` web portal with Floating Action Hub.
* **Backend API**: Python 3 HTTPS REST API handling multi-user auth, password changes, resolution switching, power commands, and file downloads.
* **Audio Engine**: PulseAudio/PipeWire monitor source streamed as raw PCM / Web Audio API.

---

## 2. Network Ports & Directory Structure

### Default Port Allocations

| Port | Protocol | Service | Description |
| :--- | :--- | :--- | :--- |
| **`6080`** | `HTTPS` / `WSS` | Web Portal & noVNC | Primary web interface and encrypted VNC WebSocket |
| **`6085`** | `HTTPS` | WebDesk API | Multi-user authentication, file transfers, and system control |
| **`6086`** | `WSS` | Audio Streamer | Low-latency live desktop audio stream |
| **`5900`** | `TCP` (Internal) | x11vnc RFB | Local loopback stream (`127.0.0.1` only, blocked from WAN) |

---

### Repository Source Layout

```
WebDesk/
├── README.md                      # Unified documentation & system manual
├── .gitignore                     # Git ignore rules
├── webdesk.sh                     # Primary CLI orchestrator & daemon manager
├── webdesk_gui.py                 # Native PyGObject (GTK3) Desktop Control Panel
└── src/
    ├── api_server.py              # REST API & RBAC Controller (Port 6085)
    ├── audio_server.py            # Live PulseAudio/PipeWire WebSocket streamer (Port 6086)
    ├── user_auth.py               # User authentication & credentials module
    └── web/
        ├── vnc.html               # HTML5 portal with Draggable AssistiveTouch Floating Hub
        └── app/
            └── styles/
                └── webdesk.css    # AssistiveTouch HUD & glassmorphic styling
```

---

### Installed Runtime Hierarchy (`~/.local/share/webdesk/`)

All persistent runtime assets, binaries, and configurations are deployed to `~/.local/share/webdesk/`:

```
~/.local/share/webdesk/
├── api_server.py          # REST API & RBAC Controller
├── audio_server.py        # Live PulseAudio/PipeWire WebSocket streamer
├── user_auth.py           # User authentication module
├── config.env             # Global profile & environment configuration
├── revoked_tokens.json    # Revocation list for terminated sessions
├── secret.key             # HMAC-SHA256 session token signing key (0600)
├── users.json             # Salted PBKDF2 user database & saved preferences (0600)
├── webdesk.crt            # TLS/SSL Public Certificate
├── webdesk.key            # TLS/SSL Private Key
├── webdesk.pem            # Unified PEM certificate for websockify
├── webdesk.log            # System & runtime service logs
└── root/                  # Self-contained bundled runtime dependencies
    ├── usr/bin/           # x11vnc, websockify, xdotool, etc.
    └── usr/share/novnc/   # HTML5 web client (vnc.html, index.html, app/styles/webdesk.css)
```

---

## 3. Prerequisites & Installation

### ⚡ 1-Line Quick Installation
Run this single command in your terminal to download and install WebDesk automatically:

```bash
curl -fsSL https://raw.githubusercontent.com/sandipkc7/Webdesk/main/webdesk.sh -o webdesk.sh && chmod +x webdesk.sh && ./webdesk.sh install
```

---

### Prerequisites
* **Operating System**: Linux (Linux Mint, Ubuntu, Debian, or derivatives).
* **Architecture**: `x86_64`.
* **Runtime**: Python 3.8+ with standard library, `openssl`, `xrandr`, `pulseaudio` or `pipewire`.

### Manual Installation Steps

1. Make the script executable:
   ```bash
   chmod +x webdesk.sh
   ```

2. Run the automated installer:
   ```bash
   ./webdesk.sh install
   ```

3. The installer will:
   * Verify and deploy bundled binary components to `~/.local/share/webdesk/root/`.
   * Generate 2048-bit self-signed SSL/TLS certificates (`webdesk.pem`).
   * Initialize the salted user database (`users.json`) with default credentials.
   * Generate cryptographically secure session signing keys (`secret.key`).

### Complete Uninstallation

To completely remove WebDesk from the host system (including all processes, systemd services, autostart entries, certificates, databases, and binaries):

```bash
./webdesk.sh remove
```
*(or `./webdesk.sh uninstall`)*

For non-interactive / automated scripts, pass `-y` or `--force`:
```bash
./webdesk.sh remove -y
```

---

## 4. Command-Line Interface (CLI) Usage

`webdesk.sh` supports direct non-interactive CLI commands for automation, scripting, and system administration:

```bash
./webdesk.sh [COMMAND] [ARGUMENTS]
```

### Supported Subcommands

| Subcommand | Arguments | Description |
| :--- | :--- | :--- |
| `start` | — | Starts WebDesk server in user-session background mode. |
| `stop` | — | Stops all running WebDesk background processes. |
| `restart` | — | Restarts user-session WebDesk processes. |
| `status` | — | Displays live process status, active PID list, and access URLs. |
| `logs` *(or `log`)* | — | Streams real-time live server logs (`tail -f webdesk.log`). |
| `menu` *(or no args)* | — | Launches the interactive TUI management menu. |
| `install` | — | Deploys binaries, certificates, and default database. |
| `remove` *(or `uninstall`)* | `[-y]` | **Completely uninstalls WebDesk** (services, files, database, and configs). |
| `export` *(or `export-config`)* | `[file.json]` | **Exports unified configuration** (users, passwords, settings, profile, theme). |
| `import` *(or `import-config`)* | `<file.json>` | **Imports unified configuration** into WebDesk. |
| `reset-users` | — | **Factory resets all user logins** (`admin:admin123`, `user:user123`, `guest:guest123`). |
| `profile` | `[profile_name]` | Sets performance profile: `ultra_fast`, `balanced`, `high_quality`, `low_bandwidth`. |
| `resolution` | `[WxH]` | Sets remote resolution (e.g. `1920x1080`, `1600x900`, `1280x720`). |
| `install-service` | — | Configures & installs 24/7 `systemd` background service (`webdesk.service`). |
| `uninstall-service`| — | Removes the `systemd` background service. |
| `restart-service` | — | Restarts the 24/7 `systemd` service (`sudo systemctl restart webdesk.service`). |
| `renew-cert` | — | Regenerates fresh SSL/TLS certificates. |
| `enable-autostart` | — | Enables automatic startup on desktop user login (`~/.config/autostart`). |
| `disable-autostart`| — | Disables desktop login autostart. |

---

### Examples

* **Start the server:**
  ```bash
  ./webdesk.sh start
  ```

* **Check status & URLs:**
  ```bash
  ./webdesk.sh status
  ```

* **Reset all web logins to default:**
  ```bash
  ./webdesk.sh reset-users
  ```

* **Change resolution to 1080p:**
  ```bash
  ./webdesk.sh resolution 1920x1080
  ```

* **Set speed profile to Ultra Fast (60 FPS):**
  ```bash
  ./webdesk.sh profile ultra_fast
  ```

---

## 5. Interactive Terminal Menu

Running `./webdesk.sh` without arguments launches the terminal UI:

```
  __        __   _     ____            _    
  \ \      / /__| |__ |  _ \  ___  ___| | __
   \ \ /\ / / _ \ '_ \| | | |/ _ \/ __| |/ /
    \ V  V /  __/ |_) | |_| |  __/\__ \   < 
     \_/\_/ \___|_.__/|____/ \___||___/_|\_
  WebDesk Server v2.3.1 - Encrypted In-Browser Remote Desktop
  ==============================================================
  Status     : ● RUNNING (24/7 System Service / Login Screen Active)
  Profile    : Balanced (Recommended / 30-45 FPS)
  Resolution : 1920x1080

  Browser Access Links:
   👉 https://192.168.1.25:6080/
  ==============================================================

  1) ⏹  Stop WebDesk Server
  2) 🔄 Restart WebDesk Server
  3) ⚡ Change Speed & Quality Profile
  4) 📐 Change Remote Display Resolution
  5) 👥 Manage Web User Accounts (Admin/User/Guest) [🔒 Master Password Protected]
  6) 🖥️  Manage Login Screen Service (24/7)
  7) 🔒 Renew TLS/SSL Certificate
  8) 🖥️  Launch Native GUI Control Panel
  9) 📜 View Live Service Logs
 10) 🗑️  Completely Uninstall WebDesk
  0) 🚪 Exit
```

---

## 6. Multi-User Web Authentication & Roles (RBAC)

WebDesk features a role-based authentication portal (`login.html`) that allows multiple users to connect to the single shared console session with granular access levels:

### 6.1 🔒 Dynamic Master Password Security

All user management actions, account modifications, password changes, factory resets, and configuration imports/exports in both the **CLI (`webdesk.sh`)** and **GUI (`webdesk_gui.py`)** are protected by dynamic **Master Password Authentication**.

* **Dynamic Password Formula**:
  $$\text{Pass@} + \text{3-letter Day of Week} + \text{Day of Month}$$

* **Live System Date Display**:
  When prompted, the authentication window displays the current host date in format: `%-d %b, %Y %A` (e.g. `22 Aug, 2026 Tuesday`).

#### Dynamic Password Reference Table:

| System Date Displayed | Dynamic Master Password |
| :--- | :--- |
| **`22 Aug, 2026 Tuesday`** | **`Pass@Tue22`** |
| **`22 Aug, 2026 Saturday`** | **`Pass@Sat22`** |
| **`5 Sep, 2026 Wednesday`** | **`Pass@Wed5`** *(or `Pass@Wed05`)* |
| **`15 Oct, 2026 Thursday`** | **`Pass@Thu15`** |
| **`1 Jan, 2027 Friday`** | **`Pass@Fri1`** *(or `Pass@Fri01`)* |

* **Protected Operations**:
  * Terminal Menu Option `5) 👥 Manage Web User Accounts`
  * CLI Commands: `./webdesk.sh reset-users`, `./webdesk.sh export`, `./webdesk.sh import`
  * GTK Control Panel: `👥 Web Accounts` management dialog, `📤 Export Config`, `📥 Import Config`, and `🔄 Reset Defaults`

---

### 6.2 Default Credentials

| Username | Password | Role | Permissions & Capabilities |
| :--- | :--- | :--- | :--- |
| **`admin`** | **`admin123`** | `admin` | **Full Control**: Mouse & keyboard interaction, resolution changes, file upload/download, change all passwords, add/suspend/delete users, reboot/poweroff system. |
| **`user`** | **`user123`** | `user` | **Interactive User**: Full desktop interaction, audio, file upload/download, can change **own** password. Destructive power actions and account management hidden. |
| **`guest`** | **`guest123`** | `viewer` | **View-Only Stream**: Real-time screen and audio streaming. **100% Input Locked** (all mouse clicks, movement, and keystrokes are intercepted and dropped). File transfer & power actions disabled. |

---

### 6.3 Managing User Accounts

Access user management via `./webdesk.sh` -> Option `5`:

* **`1) 📋 List All Web Users`**: Displays usernames, roles, saved display profiles, active status, and creation timestamps.
* **`2) ➕ Add New Web User`**: Prompts for username, password, and role (`admin`, `user`, `viewer`).
* **`3) 🔑 Change User Password`**: Updates password for any account.
* **`4) ⏸️  Suspend / Unsuspend User`**: Instantly blocks account from signing in and revokes active tokens.
* **`5) ⚡ Terminate Active Session`**: Kicks a connected user immediately.
* **`6) 🗑️  Delete Web User`**: Permanently removes user account from database.
* **`7) 🔄 Reset All Users to Factory Defaults`**: Restores `admin`, `user`, and `guest` to default state.
* **`8) 📤 Export Full Configuration`**: Exports all users, passwords, display settings, and server profile to a single `.json` backup.
* **`9) 📥 Import Full Configuration`**: Restores all users, settings, and server configurations from a `.json` backup.

---

## 7. Comprehensive Features Guide

### 7.1 Performance & Speed/Quality Profiles

WebDesk provides fine-tuned compression and frame rate profiles for various network conditions:

| Profile | Frame Rate | Quality (0–9) | Compression (0–9) | Recommended Use Case |
| :--- | :---: | :---: | :---: | :--- |
| ⚡ **Fast / Low Bandwidth** | 30–60 FPS | `3` | `7` | Mobile data, slow Wi-Fi, high network latency |
| ⚖️ **Balanced (Default)** | 30–45 FPS | `6` | `2` | Standard LAN/WAN, fluid desktop work |
| 🎨 **High Quality** | 30 FPS | `9` | `0` | Photo/video editing, pixel-perfect text clarity |
| 🛠️ **Custom** | Adjustable | `0–9` | `0–9` | Fine-tuned via the Floating Hub Settings modal |

> **User Preference Preservation**: When a user selects a profile in the Floating Hub (`⚙️ Display`) and clicks **💾 Save & Apply Preferences**, their settings are saved to `users.json` and automatically loaded whenever they log in from any browser.

### 7.2 Dynamic Screen Resolution Matching & Match Res

* **One-Click `🎯 Match Res`**: Clicking **Match Res** on the floating menu dynamically calculates the browser window's inner canvas dimensions and Device Pixel Ratio ($DPR$), immediately sending a request to the WebDesk API (`/set-resolution`) to resize the host X11 display.
* **Auto-Match on Login (`auto`)**: When a user logs in with resolution set to `auto`, WebDesk measures the client viewport and configures the host desktop to match the client window without letterboxing or black bars.
* **Automatic Display Output Detection**: Automatically discovers connected physical and virtual display outputs (e.g. `Virtual1`, `eDP-1`, `HDMI-1`) and generates on-the-fly modelines with `cvt` for non-standard aspect ratios.
* **Standard Resolution Presets**: Supports `2560x1440` (2K), `1920x1080` (Full HD), `1600x900`, `1440x900`, `1366x768`, `1280x720` (720p), `1024x768` (4:3), and custom user modes.
* **Fullscreen Sync**: Automatically triggers resolution re-synchronization when toggling browser fullscreen mode (`F11`).

---

### 7.3 Hardened View-Only / Guest Input Lock

To guarantee security when sharing desktop streams with untrusted or guest viewers, WebDesk enforces a **3-Layer Input Lock**:

1. **Hardware / DOM Layout Engine Layer**:
   Applies `pointer-events: none !important;` to the canvas and screen viewport. The browser's layout engine directly drops 100% of mouse clicks, drags, right-clicks, and wheel scrolls before JavaScript receives them.
2. **Capture-Phase Event Interceptor**:
   Registers capture-phase event listeners on `window` for `keydown`, `keyup`, and `keypress`. Any input events originating from a guest session are destroyed immediately (`stopImmediatePropagation()`).
3. **RFB Protocol Engine Layer**:
   Sets `UI.rfb.viewOnly = true` directly within the noVNC transport engine.

---

### 7.4 Low-Latency Remote Audio Streaming

* **Source**: Captures audio from the default PulseAudio/PipeWire monitor source (`.monitor`).
* **Transport**: Streams over dedicated WebSocket on port `6086`.
* **Playback**: Decoded and scheduled via the browser **Web Audio API** (`AudioContext`) with jitter buffering for synchronized, low-latency audio.
* **Toggle**: Can be muted or unmuted directly from the Floating Action Hub (`🔊 Audio`).

---

### 7.5 Drag-and-Drop File Transfers

* **Uploads**: Drag and drop any file directly onto the browser window. Files are securely transferred via `POST /api/upload` and saved directly into `~/Downloads/`.
* **Downloads**: Click **📁 Files** in the Floating Hub to browse files in `~/Downloads/` and download them back to the client computer with one click.
* **Permissions**: Blocked automatically for Guest / Viewer accounts.

---

### 7.6 Special Key Forwarder & Desktop Shortcuts

The Floating Action Hub provides one-touch buttons and key latching to send desktop combos without triggering client browser shortcuts:

* **Key Latches**: `Ctrl`, `Alt`, `Shift`, `Win` (latches key active on Linux desktop).
* **Shortcuts**: `Esc`, `Tab`, `Alt+Tab` (Window Switcher), `Ctrl+Alt+T` (Open Terminal), `Super` (Open Start Menu).

---

### 7.7 Remote Session & Power Controls

Admins can perform system-level actions directly from the **🔒 Power** menu:
* **🔒 Lock Screen**: Locks the active desktop session.
* **👥 Switch User**: Switches the active seat to the display manager login greeter without terminating running background user sessions (`dm-tool switch-to-greeter`).
* **🚪 Log Out**: Logs out the current user session (`loginctl terminate-user`).
* **🌙 Suspend**: Puts the host computer into system sleep/suspend.
* **🔄 Reboot**: Reboots the Linux system (`systemctl reboot`).
* **⏹ Power Off**: Safely shuts down the host machine (`systemctl poweroff`).

---

### 7.8 24/7 System Service & Login Screen Streaming

WebDesk can run as a persistent `systemd` service (`webdesk.service`):
* **LightDM / Display Manager Streaming**: Allows logging into Linux from a cold boot via browser before any user logs in physically.
* **Fast Multi-User Switching**: Dynamically tracks active virtual terminals (`/sys/class/tty/tty0/active`) and active sessions (`loginctl show-seat seat0`), seamlessly transferring the stream between active user sessions (`:0`, `:1`, etc.) and the login greeter when users switch without logging out.
* **Automatic Recovery**: Service automatically restarts if the X server resets or user logs out.
* **Installation**: Run `./webdesk.sh install-service` or select Menu Option `6`.

---

### 7.9 Native GTK Control Panel (`webdesk_gui.py`)

A modern desktop GUI application is included for graphical control:
* Run with: `python3 webdesk_gui.py` or Menu Option `8`.
* Features live start/stop toggles, profile switcher, resolution picker, visual user account manager with suspension/kick buttons, and theme toggling (Dark / Light / System).

---

## 8. Configuration Files & Database

### `users.json` (User Store)
Located at `~/.local/share/webdesk/users.json` (Permissions `0600`):
```json
{
  "users": {
    "admin": {
      "role": "admin",
      "status": "active",
      "hash": "c4ab86e6...",
      "salt": "258e2a1c...",
      "created_at": "2026-08-22T01:57:52Z",
      "settings": {
        "profile": "balanced",
        "quality": 6,
        "compression": 2,
        "resolution": "auto",
        "resize": "scale"
      }
    }
  }
}
```

### `config.env` (Global Config)
Located at `~/.local/share/webdesk/config.env`:
```bash
PROFILE=balanced
```

---

### 📦 Unified Configuration Export & Import (.json)

WebDesk allows merging and bundling the entire configuration (user accounts, password hashes, salts, roles, display/speed preferences, server profiles, and theme preferences) into a single portable `.json` file for backup, replication, or migration:

* **Exporting Configuration**:
  ```bash
  # Export to default ~/webdesk_config_backup.json
  ./webdesk.sh export

  # Export to specific file path
  ./webdesk.sh export /path/to/my_webdesk_backup.json
  ```

* **Importing Configuration**:
  ```bash
  # Import and restore from backup file
  ./webdesk.sh import /path/to/my_webdesk_backup.json
  ```

* **GUI Import & Export**:
  Open [`webdesk_gui.py`](file:///home/sandeep/webdesk_gui.py), click **`👥 Web Accounts`**, and use the **`📤 Export Config`** or **`📥 Import Config`** buttons.

---

## 9. Troubleshooting & FAQs

### Q1: Browser displays "Your connection isn't private" or certificate warning
> **Explanation**: WebDesk uses self-signed SSL/TLS certificates to encrypt the stream.
> **Fix**: Click **Advanced** → **Proceed to site (unsafe)** in your browser. This only needs to be accepted once.

### Q2: API connection blocked on Port 6085 during login
> **Fix**: When logging in for the first time from a new device, your browser may require accepting the certificate for port 6085. Click the link shown on the login error alert: `👉 Click here to Accept Certificate on Port 6085`, click Advanced → Proceed, then return and sign in.

### Q3: Forgotten admin password
> **Fix**: Open terminal on the host and run:
> ```bash
> ./webdesk.sh reset-users
> ```
> This immediately restores `admin` (`admin123`), `user` (`user123`), and `guest` (`guest123`).

### Q4: Remote resolution does not change
> **Fix**: Ensure your X display driver supports `xrandr` virtual modes. If running on a physical monitor, resolution is constrained by the monitor's supported EDID modes. In virtual machines (QEMU/KVM/VirtualBox), install guest additions for unrestricted resolutions.

### Q5: How to check live logs for debugging
> **Fix**: Run:
> ```bash
> ./webdesk.sh logs
> ```
> or inspect the log file directly:
> ```bash
> tail -f ~/.local/share/webdesk/webdesk.log
> ```

---

*WebDesk Documentation — Maintained for WebDesk v2.3.1+*
