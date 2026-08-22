# 🖥️ WebDesk — Comprehensive System & CLI Documentation

**WebDesk** is a self-contained, high-performance, encrypted in-browser desktop streaming server for Linux. It allows seamless remote access to a live Linux desktop (`DISPLAY=:0`) or display manager login screen (e.g., LightDM) through any modern web browser without requiring client-side software or browser plugins.

---

## 📑 Table of Contents

1. [Architecture & Technology Stack](#1-architecture--technology-stack)
2. [Network Ports & Directory Structure](#2-network-ports--directory-structure)
3. [Prerequisites & Installation](#3-prerequisites--installation)
4. [Command-Line Interface (CLI) Usage](#4-command-line-interface-cli-usage)
5. [Interactive Terminal Menu & Administration Center](#5-interactive-terminal-menu--administration-center)
6. [Master Password & Security Modes](#6-master-password--security-modes)
7. [Multi-User Web Authentication & Roles (RBAC)](#7-multi-user-web-authentication--roles-rbac)
8. [Session Management & Concurrent Login Protection](#8-session-management--concurrent-login-protection)
9. [Client IP Logging & Security Audit Trail](#9-client-ip-logging--security-audit-trail)
10. [Comprehensive Features Guide](#10-comprehensive-features-guide)
    * [10.1 Performance & Speed/Quality Profiles](#101-performance--speedquality-profiles)
    * [10.2 Dynamic Screen Resolution Matching](#102-dynamic-screen-resolution-matching)
    * [10.3 Hardened View-Only / Guest Input Lock](#103-hardened-view-only--guest-input-lock)
    * [10.4 Low-Latency Remote Audio Streaming](#104-low-latency-remote-audio-streaming)
    * [10.5 Drag-and-Drop File Transfers](#105-drag-and-drop-file-transfers)
    * [10.6 Special Key Forwarder & Desktop Shortcuts](#106-special-key-forwarder--desktop-shortcuts)
    * [10.7 Remote Session & Power Controls](#107-remote-session--power-controls)
    * [10.8 24/7 System Service & Login Screen Streaming](#108-247-system-service--login-screen-streaming)
    * [10.9 Native GTK Control Panel (`webdesk_gui.py`)](#109-native-gtk-control-panel-webdesk_guipy)
    * [10.10 Dual-Protocol Server: Windows Native RDP (XRDP / Port 3389)](#1010-dual-protocol-server-windows-native-rdp-xrdp--port-3389)
11. [Configuration Files & Database](#11-configuration-files--database)
12. [Troubleshooting & FAQs](#12-troubleshooting--faqs)

---

## 1. Architecture & Technology Stack

WebDesk unites lightweight Linux desktop technologies into a unified multi-protocol pipeline:

```
[ Web Browser Client ]                 [ Windows Remote Desktop Client (mstsc.exe) ]
        │  (HTTPS / WSS on Port 6080)                          │  (TLS RDP on Port 3389)
        ▼                                                      ▼
[ Websockify + noVNC Web Engine ]                      [ XRDP Server Engine ]
        │  (Raw RFB Loopback 127.0.0.1:5900)                   │  (Mode 1: Mirror :0 / Mode 2: Xorg)
        ▼                                                      ▼
[ x11vnc Engine ] ────────────────────────► [ X11 Server (DISPLAY=:0) ] ◄── [ Desktop / Login Manager ]
        ▲
        │  (REST API HTTPS on Port 6085)
        ├──────────────────────────────────────────► [ Auth DB (users.json) ]
        │                                          ► [ Master Auth (master_auth.json) ]
        │                                          ► [ Active Sessions (active_sessions.json) ]
        │                                          ► [ Audit Trail (login_audit.log) ]
[ WebDesk API Server (api_server.py) ]
        ▲
        │  (WebSocket Audio Stream on Port 6086)
[ WebDesk Audio Server (audio_server.py) ] ◄── [ PulseAudio / PipeWire Monitor ]
```

* **Display Engines**: `x11vnc` for in-browser RFB streaming + `xrdp` for Windows native RDP client connections.
* **Transport Protocols**: Encrypted WebSocket (`wss://`) on port 6080 and TLS RDP on port 3389.
* **Web Client**: Custom glassmorphic `noVNC` web portal with Floating Action Hub.
* **Backend API**: Python 3 HTTPS REST API handling multi-user auth, single-session enforcement, IP audit logging, resolution switching, power commands, and file downloads.
* **Audio Engine**: PulseAudio/PipeWire monitor source streamed as raw PCM / Web Audio API.

---

## 2. Network Ports & Directory Structure

### Default Port Allocations

| Port | Protocol | Service | Description |
| :--- | :--- | :--- | :--- |
| **`6080`** | `HTTPS` / `WSS` | Web Portal & noVNC | Primary web interface and encrypted VNC WebSocket |
| **`3389`** | `TLS RDP` | Windows XRDP Server | Native Windows Remote Desktop Connection (`mstsc.exe`) |
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

All persistent runtime assets, databases, logs, and configurations are deployed to `~/.local/share/webdesk/`:

```
~/.local/share/webdesk/
├── api_server.py          # REST API & RBAC Controller
├── audio_server.py        # Live PulseAudio/PipeWire WebSocket streamer
├── user_auth.py           # User authentication & security module
├── config.env             # Global profile & environment configuration
├── master_auth.json       # Master password mode & salted PBKDF2 hash (0600)
├── active_sessions.json   # Single active session registry per user account (0600)
├── login_audit.log        # Plain-text client IP & login audit log (0600)
├── login_audit.json       # Structured JSON login audit history (0600)
├── revoked_tokens.json    # Revocation list for terminated sessions (0600)
├── secret.key             # HMAC-SHA256 session token signing key (0600)
├── users.json             # Salted PBKDF2 user database & saved preferences (0600)
├── webdesk.crt            # TLS/SSL Public Certificate
├── webdesk.key            # TLS/SSL Private Key
├── webdesk.pem            # Unified PEM certificate for websockify
├── webdesk.log            # System & runtime service logs
└── root/                  # Self-contained bundled runtime dependencies
    ├── usr/bin/           # x11vnc, websockify, xdotool, etc.
    └── usr/share/novnc/   # HTML5 web client (vnc.html, login.html, styles)
```

---

---

## 3. Prerequisites, Apps & Libraries

WebDesk is designed to be **completely self-contained**. It runs entirely in user-space without requiring external Python `pip` packages or root permissions for standard execution.

### 3.1 Host System Prerequisites & Libraries

The following core packages are needed on the host system:

| Package | Component | Purpose |
| :--- | :--- | :--- |
| **`python3`** (3.8+) | Runtime Engine | Runs the REST API (`api_server.py`), Audio Streamer (`audio_server.py`), and Auth Module (`user_auth.py`). **Zero `pip` packages required** (uses standard library modules: `ssl`, `http.server`, `urllib.parse`, `hashlib`, `hmac`, `json`, `subprocess`, `threading`, `secrets`, `socket`, `struct`, `base64`, `shutil`, `re`, `time`). |
| **`openssl`** | Cryptography | Automatically creates 2048-bit self-signed SSL/TLS certificates (`webdesk.pem`, `webdesk.crt`, `webdesk.key`) for HTTPS & WSS encryption. |
| **`x11-xserver-utils`** / **`xrandr`** | Display Control | Manages remote client resolution auto-matching and dynamic display scaling. |
| **`pulseaudio-utils`** (`parec`) or **`pipewire`** (`pw-record`) | Sound Engine | Captures real-time raw desktop audio output for in-browser PCM streaming on port 6086. |
| **`systemd`** / **`loginctl`** | Session Manager | Handles background system service daemonization (`webdesk.service`) and power actions (Lock, Switch User, Logout, Suspend, Reboot). |
| **`curl`** & **`dpkg`** | Installer Utilities | Downloads and unpacks standalone components into `~/.local/share/webdesk/root/`. |

#### Single-Command Host Prerequisites Installation (Debian / Ubuntu / Mint / Kali / Pop!_OS):
```bash
sudo apt update && sudo apt install -y python3 openssl x11-xserver-utils pulseaudio-utils curl dpkg
```

---

### 3.2 Standalone Packages (Automatically Downloaded by `webdesk.sh`)

During installation (`./webdesk.sh install`), WebDesk uses `apt-get download` and `dpkg -x` to extract these standalone binaries directly into `~/.local/share/webdesk/root/` (**No `sudo` or system-wide modifications required**):

| Package | Bundled Binaries & Libraries | Description |
| :--- | :--- | :--- |
| **`x11vnc`** | `x11vnc` | High-performance VNC server connecting to active X11 display `DISPLAY=:0`. |
| **`libvncserver1`** / **`libvncclient1`** | `libvncserver.so`, `libvncclient.so` | Core VNC protocol and encoding library. |
| **`novnc`** | `vnc.html`, `app/`, `core/`, `vendor/` | HTML5 canvas web client and RFB protocol engine. |
| **`websockify`** / **`python3-websockify`** | `websockify` | High-speed proxy converting WebSockets (port 6080) to TCP VNC stream (port 5900). |
| **`xdotool`** / **`libxdo3`** | `xdotool`, `libxdo.so.3` | Synthetic keyboard and mouse input injection for X11. |
| **`xclip`** / **`libxmu6`** | `xclip`, `libXmu.so.6` | Bidirectional X11 clipboard synchronization. |

---

### 3.3 Optional Dependencies

* **Native GTK Desktop GUI (`webdesk_gui.py`)**:
  ```bash
  sudo apt install -y python3-gi gir1.2-gtk-3.0
  ```
* **Supported Display Managers (for 24/7 Login Screen Streaming)**:
  - **LightDM** (`lightdm` / `dm-tool`) — *Recommended for instant cold-boot remote login*
  - **GDM3** (`gdm3` / `gdmflexiserver`)
  - **SDDM** (`sddm`)
* **Supported Desktop Environments**:
  - XFCE, LXDE, LXQt, MATE, Cinnamon, GNOME (X11), KDE Plasma (X11).

---

### 3.4 Installation Steps

#### ⚡ 1-Line Quick Installation
```bash
curl -fsSL https://raw.githubusercontent.com/sandipkc7/Webdesk/main/webdesk.sh -o webdesk.sh && chmod +x webdesk.sh && ./webdesk.sh install
```

#### Manual Installation Steps
1. Make the script executable:
   ```bash
   chmod +x webdesk.sh
   ```
2. Run the automated installer:
   ```bash
   ./webdesk.sh install
   ```
3. The installer will:
   * Download and unpack standalone dependencies into `~/.local/share/webdesk/root/`.
   * Generate 2048-bit self-signed SSL/TLS certificates (`webdesk.pem`).
   * Initialize the salted user database (`users.json`) with default credentials.
   * Prompt to configure your preferred Master Security Mode (Custom Password or Dynamic Daily Rule).
   * Generate cryptographically secure HMAC session signing keys (`secret.key`).

#### Complete Uninstallation
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

`webdesk.sh` (or the shortcut `webdesk`) supports direct non-interactive CLI commands for automation, scripting, and system administration:

```bash
webdesk [COMMAND] [ARGUMENTS]
```

### Supported Subcommands

| Subcommand | Arguments | Description |
| :--- | :--- | :--- |
| `start` | — | Starts WebDesk server in background mode. |
| `stop` | — | Stops all running WebDesk background processes. |
| `restart` | — | Restarts WebDesk user-session or systemd service. |
| `status` | — | Displays live process status, active PID list, and access URLs. |
| `admin` *(or `administration`)* | — | **Opens the Administration Menu** (Master Password required). |
| `audit` *(or `audit-logs`)* | — | **Opens the Client Login & IP Address Audit Log Viewer**. |
| `users` *(or `user-accounts`)* | — | **Opens Web User Management** (Add/Edit/Suspend/Kick/Delete). |
| `master-password` | — | **Configures Master Password mode** (Custom Password vs. Dynamic Rule). |
| `logs` *(or `log`)* | — | Streams real-time live server logs (`tail -f webdesk.log`). |
| `menu` *(or no args)* | — | Launches the interactive Main Menu. |
| `install` | — | Deploys binaries, certificates, and default database. |
| `remove` *(or `uninstall`)* | `[-y]` | **Completely uninstalls WebDesk** from the host. |
| `export` *(or `export-config`)* | `[file.json]` | **Exports unified configuration** (users, master auth, settings, theme). |
| `import` *(or `import-config`)* | `<file.json>` | **Imports unified configuration** into WebDesk. |
| `reset-users` | — | **Factory resets user accounts** (`admin:admin123`, `user:user123`, `guest:guest123`). |
| `profile` | `[profile_name]` | Sets performance profile: `ultra_fast`, `balanced`, `high_quality`, `low_bandwidth`. |
| `resolution` | `[WxH]` | Sets remote resolution (e.g. `1920x1080`, `1600x900`, `1280x720`). |
| `install-service` | — | Configures & installs 24/7 `systemd` background service (`webdesk.service`). |
| `uninstall-service`| — | Removes the `systemd` background service. |
| `renew-cert` | — | Regenerates fresh SSL/TLS certificates. |
| `enable-autostart` | — | Enables automatic startup on desktop user login. |
| `disable-autostart`| — | Disables desktop login autostart. |

---

## 5. Interactive Terminal Menu & Administration Center

Running `webdesk` without arguments launches the streamlined Main Menu:

```
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
  5) 🛡️  Administration (Master Password Required)
  6) 🖥️  Manage Login Screen Service (24/7)
  7) 🖥️  Launch Native GUI Control Panel
  8) 📜 View Live Service Logs
  0) 🚪 Exit
```

### 🛡️ Administration & Security Submenu (Option 5)

All sensitive administrative actions are consolidated behind Master Password verification:

```
  WebDesk Administration & Security Center (Master Protected)
  ==============================================================

  1) 👥 Web User Accounts & Access Control
  2) 📜 Client Login & IP Address Audit Logs
  3) 🔑 Master Password Settings (Custom Password / Dynamic Rule)
  4) 🔄 Reset All Web Users to Factory Defaults
  5) 🔒 Renew / Reissue TLS/SSL Certificate
  6) 📤 Export Configuration & User Accounts (.json)
  7) 📥 Import Configuration & User Accounts (.json)
  8) 🗑️  Completely Uninstall WebDesk
  0) ↩  Back to Main Menu
```

---

## 6. Master Password & Security Modes

WebDesk supports two Master Security modes:

### Mode 1: Custom Master Password
- Administrators can set a persistent, custom master password ($\ge 6$ characters).
- Stored securely in `~/.local/share/webdesk/master_auth.json` with PBKDF2-HMAC-SHA256 salted hashing (100,000 iterations) and `0600` permissions.

### Mode 2: Dynamic Daily Rule (Default)
- Changes dynamically each day according to the host calendar date:
  $$\text{Pass@} + \text{3-letter Day of Week} + \text{Day of Month}$$
  *Example:* Saturday, August 22nd $\rightarrow$ **`Pass@Sat22`**

### Switching Modes
Access **Administration** $\rightarrow$ **Option 3 (`🔑 Master Password Settings`)** or run `webdesk master-password`:
```text
--- Master Password Configuration ---

Current Mode : Custom Master Password (or Dynamic Daily Rule)
==============================================================

  1) ✍️   Set Custom Master Password
  2) 🔄  Revert to Default Dynamic Rule (Pass@<Day><Date>)
  3) ℹ️   View Dynamic Daily Rule Details
  0) ↩   Back to Administration Menu
```

---

## 7. Multi-User Web Authentication & Roles (RBAC)

WebDesk features a web login portal (`login.html`) with role-based access control (RBAC):

### 7.1 Default Credentials

| Username | Password | Role | Permissions & Capabilities |
| :--- | :--- | :--- | :--- |
| **`admin`** | **`admin123`** | `admin` | **Full Control**: Mouse & keyboard interaction, resolution changes, file upload/download, change all passwords, add/suspend/delete users, view connected viewers & audit logs, reboot/poweroff system. |
| **`user`** | **`user123`** | `user` | **Interactive User**: Full desktop interaction, audio, file upload/download, can change **own** password. Power actions and account management hidden. |
| **`guest`** | **`guest123`** | `viewer` | **View-Only Stream**: Real-time screen and audio streaming. **100% Input Locked** (all mouse clicks, movement, and keystrokes are intercepted and dropped). File transfers and power actions disabled. |

### 7.2 Managing User Accounts

Access user management via `webdesk users` or **Administration** $\rightarrow$ **Option 1**:

* **`1) 📋 List All Web Users`**: Displays usernames, roles, saved display profiles, active status, and creation timestamps.
* **`2) ➕ Add New Web User`**: Prompts for username, password, and role (`admin`, `user`, `viewer`).
* **`3) 🔑 Change User Password`**: Updates password for any account.
* **`4) ⏸️  Suspend / Unsuspend User`**: Instantly blocks account from signing in and revokes active tokens.
* **`5) ⚡ Terminate Active Session`**: Kicks a connected user immediately.
---

## 8. Session Management & Concurrent Login Protection

To prevent conflicting control and unauthorized concurrent access, WebDesk enforces **Single Active Session per User Account**:

1. **New Session Invalidation**:
   - When a user logs in from **Browser B**, a new cryptographic session nonce is registered in `active_sessions.json`.
   - Any prior session tokens for that username on **Browser A** are superseded.

2. **Real-Time Heartbeat Enforcement**:
   - The web client sends periodic heartbeats to `/api/auth/heartbeat`.
   - On detecting a superseded session, **Browser A** immediately severs the RFB desktop stream and wipes local credentials.

3. **In-Page Blurred Disconnect Overlay**:
   - Rather than abruptly redirecting, **Browser A** presents a dark frosted glass overlay (`backdrop-filter: blur(18px)`) over the desktop canvas:
     > ⚠️ **Session Disconnected**  
     > *New session started in another browser.*
   - Clicking **"Go to Login Screen ➔"** takes the user to `login.html` where an alert banner explains the logout reason.

---

## 9. Client IP Logging & Security Audit Trail

WebDesk logs client IP addresses for all connection attempts:

* **Header Forwarding**: The internal WebSocket proxy forwards `X-Forwarded-For` and `X-Real-IP` headers to the API daemon.
* **Audit Storage**:
  - `~/.local/share/webdesk/login_audit.log`: Plain-text timestamped log.
  - `~/.local/share/webdesk/login_audit.json`: Structured JSON containing the last 500 login events (timestamp, username, role, client IP, status `SUCCESS`/`FAILED`, reason, user-agent).

### Viewing Audit Logs
Run `webdesk audit` or select **Option 2** under the **Administration Menu**:

```text
--- Client Login & Connected IP Audit Logs ---

TIMESTAMP               STATUS     USERNAME        ROLE       IP ADDRESS          DETAILS
----------------------------------------------------------------------------------------------------------
2026-08-22 11:07:21     SUCCESS    guest           viewer     192.168.1.100       
2026-08-22 11:05:40     FAILED     admin           -          192.168.1.45        Incorrect password
2026-08-22 10:48:12     SUCCESS    admin           admin      127.0.0.1           

==========================================================================================================
1) 🔄 Refresh Logs
2) 📜 Live Stream Login Logs (tail -f)
3) 🗑️  Clear Login Audit Logs
0) ↩  Back to Administration Menu
```

---

## 10. Comprehensive Features Guide

### 10.1 Performance & Speed/Quality Profiles

WebDesk provides fine-tuned compression and frame rate profiles for various network conditions:

| Profile | Frame Rate | Quality (0–9) | Compression (0–9) | Recommended Use Case |
| :--- | :---: | :---: | :---: | :--- |
| ⚡ **Fast / Low Bandwidth** | 30–60 FPS | `3` | `7` | Mobile data, slow Wi-Fi, high network latency |
| ⚖️ **Balanced (Default)** | 30–45 FPS | `6` | `2` | Standard LAN/WAN, fluid desktop work |
| 🎨 **High Quality** | 30 FPS | `9` | `0` | Photo/video editing, pixel-perfect text clarity |
| 🛠️ **Custom** | Adjustable | `0–9` | `0–9` | Fine-tuned via the Floating Hub Settings modal |

> **User Preference Preservation**: When a user selects a profile in the Floating Hub (`⚙️ Display`) and clicks **💾 Save & Apply Preferences**, their settings are saved to `users.json` and automatically loaded whenever they log in from any browser.

### 10.2 Dynamic Screen Resolution Matching & Match Res

* **One-Click `🎯 Match Res`**: Clicking **Match Res** on the floating menu dynamically calculates the browser window's inner canvas dimensions and Device Pixel Ratio ($DPR$), immediately sending a request to the WebDesk API (`/set-resolution`) to resize the host X11 display.
* **Auto-Match on Login (`auto`)**: When a user logs in with resolution set to `auto`, WebDesk measures the client viewport and configures the host desktop to match the client window without letterboxing or black bars.
* **Automatic Display Output Detection**: Automatically discovers connected physical and virtual display outputs (e.g. `Virtual1`, `eDP-1`, `HDMI-1`) and generates on-the-fly modelines with `cvt` for non-standard aspect ratios.
* **Standard Resolution Presets**: Supports `2560x1440` (2K), `1920x1080` (Full HD), `1600x900`, `1440x900`, `1366x768`, `1280x720` (720p), `1024x768` (4:3), and custom user modes.
* **Fullscreen Sync**: Automatically triggers resolution re-synchronization when toggling browser fullscreen mode (`F11`).

---

### 10.3 Hardened View-Only / Guest Input Lock

To guarantee security when sharing desktop streams with untrusted or guest viewers, WebDesk enforces a **3-Layer Input Lock**:

1. **Hardware / DOM Layout Engine Layer**:
   Applies `pointer-events: none !important;` to the canvas and screen viewport. The browser's layout engine directly drops 100% of mouse clicks, drags, right-clicks, and wheel scrolls before JavaScript receives them.
2. **Capture-Phase Event Interceptor**:
   Registers capture-phase event listeners on `window` for `keydown`, `keyup`, and `keypress`. Any input events originating from a guest session are destroyed immediately (`stopImmediatePropagation()`).
3. **RFB Protocol Engine Layer**:
   Sets `UI.rfb.viewOnly = true` directly within the noVNC transport engine.

---

### 10.4 Low-Latency Remote Audio Streaming

* **Source**: Captures audio from the default PulseAudio/PipeWire monitor source (`.monitor`).
* **Transport**: Streams over dedicated WebSocket on port `6086`.
* **Playback**: Decoded and scheduled via the browser **Web Audio API** (`AudioContext`) with jitter buffering for synchronized, low-latency audio.
* **Toggle**: Can be muted or unmuted directly from the Floating Action Hub (`🔊 Audio`).

---

### 10.5 Drag-and-Drop File Transfers

* **Uploads**: Drag and drop any file directly onto the browser window. Files are securely transferred via `POST /api/upload` and saved directly into `~/Downloads/`.
* **Downloads**: Click **📁 Files** in the Floating Hub to browse files in `~/Downloads/` and download them back to the client computer with one click.
* **Permissions**: Blocked automatically for Guest / Viewer accounts.

---

### 10.6 Special Key Forwarder & Dedicated Linux Shortcuts

The Floating Action Hub features a dedicated **Linux Shortcuts & Modifiers** toolbar that transmits raw X11 keysyms directly through the encrypted RFB stream:

* **Sticky Key Latches**: `Ctrl`, `Alt`, `Shift`, `Win` (latches modifier down on the server so you can press single keys sequentially).
* **Linux Dedicated Shortcuts**:
  - `🪟 Start`: Opens application menu / dashboard launcher (`Super_L`).
  - `🔀 Alt+Tab`: Cycles through active application windows (`Alt + Tab`).
  - `💻 Terminal`: Launches default Linux terminal emulator (`Ctrl + Alt + T`).
  - `🖥️ Desktop`: Minimizes all windows to reveal the desktop (`Super + D`).
  - `⚡ Run`: Opens application run command dialog (`Alt + F2`).
  - `❌ Close`: Closes currently focused window (`Alt + F4`).
  - `📋 Term Paste`: Pastes clipboard text directly into terminal (`Ctrl + Shift + V`).
  - `⌨️ CAD`: Sends system interrupt / task manager signal (`Ctrl + Alt + Del`).

---

### 10.7 Remote Session & Power Controls

Interactive users (`admin` and `user`) can perform system-level session actions from the **🔒 Power** modal (with safety confirmation dialogs):
* **🔒 Lock Screen**: Locks the active desktop session (`loginctl lock-sessions` / `dm-tool lock`).
* **👥 Switch User**: Switches the active seat to the display manager login greeter without terminating running background user sessions (`dm-tool switch-to-greeter`).
* **🚪 Log Out**: Safely logs out the active user session (`loginctl terminate-user`).
* **🌙 Sleep / Suspend**: Puts the host computer into system sleep/suspend (`systemctl suspend`).
* **🔄 Reboot System**: Reboots the Linux system (`systemctl reboot`).

---

### 10.8 24/7 System Service & Login Screen Streaming

WebDesk can run as a persistent `systemd` service (`webdesk.service`):
* **LightDM / Display Manager Streaming**: Allows logging into Linux from a cold boot via browser before any user logs in physically.
* **Fast Multi-User Switching**: Dynamically tracks active virtual terminals (`/sys/class/tty/tty0/active`) and active sessions (`loginctl show-seat seat0`), seamlessly transferring the stream between active user sessions (`:0`, `:1`, etc.) and the login greeter when users switch without logging out.
* **Automatic Recovery**: Service automatically restarts if the X server resets or user logs out.
* **Installation**: Run `./webdesk.sh install-service` or select Menu Option `6`.

---

### 10.9 Native GTK Control Panel (`webdesk_gui.py`)

A modern desktop GUI application is included for graphical control:
* Run with: `python3 webdesk_gui.py` or Menu Option `8`.
* Features live start/stop toggles, profile switcher, resolution picker, visual user account manager with suspension/kick buttons, and theme toggling (Dark / Light / System).

---

### 10.10 Dual-Protocol Server: Windows Native RDP (XRDP / Port 3389)

WebDesk supports **Microsoft Remote Desktop Protocol (RDP)**, allowing native Windows clients (`mstsc.exe`) to connect directly to the Linux desktop alongside the in-browser WebDesk client.

#### 🔀 The 3 Configurable RDP Session Modes

| Mode | Name | Description |
| :--- | :--- | :--- |
| **Mode 1** | **🪞 Live Desktop Mirror (`:0`)** | Connects Windows directly to the active physical monitor / WebDesk web client (`127.0.0.1:5900`). You see and control the exact same live screen. |
| **Mode 2** | **🖥️ Dedicated Virtual Session** | Opens an independent, high-speed virtual X11 desktop for your existing Linux user account with access to all your personal `/home` files. |
| **Mode 3** | **👥 Multi-User Simultaneous Workstation** | Allows a secondary Linux user (e.g. `remoteuser`) to log in and work simultaneously without interfering with the local user. |

#### 🛠️ RDP CLI Commands
```bash
webdesk rdp-enable          # Installs, configures, and starts XRDP on port 3389
webdesk rdp-disable         # Stops and disables the XRDP service
webdesk rdp-mode <1|2|3>    # Switches between Mode 1 (Mirror), Mode 2 (Virtual), and Mode 3 (Multi-User)
webdesk rdp-status          # Displays active RDP listening port, mode, and connected Windows sessions
webdesk rdp-port <PORT>     # Changes the default listening port (e.g. 3389 -> custom)
webdesk rdp-user            # Interactive wizard to create a secondary Linux account for Mode 3
webdesk rdp-menu            # Opens the interactive RDP configuration menu (under Administration)
```

#### 🪟 How to Connect from Windows:
1. Press <kbd>Win</kbd> + <kbd>R</kbd>, type `mstsc`, and press **Enter**.
2. In the **Computer** field, enter your Linux IP address and port: `192.168.1.25:3389`.
3. Click **Connect**.
4. At the login prompt, enter your standard Linux username (e.g., `sandeep` or secondary user) and system password.

---

## 11. Configuration Files & Database

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

WebDesk allows merging and bundling the entire configuration (user accounts, password hashes, salts, roles, display/speed preferences, master security mode, server profiles, and theme preferences) into a single portable `.json` file for backup, replication, or migration:

* **Exporting Configuration**:
  ```bash
  webdesk export [destination_file.json]
  ```

* **Importing Configuration**:
  ```bash
  webdesk import <source_backup.json>
  ```

* **GUI Import & Export**:
  Open `webdesk_gui.py`, click **`👥 Web Accounts`**, and use the **`📤 Export Config`** or **`📥 Import Config`** buttons.

---

## 12. Troubleshooting & FAQs

### Q1: Browser displays "Your connection isn't private" or certificate warning
> **Explanation**: WebDesk uses self-signed SSL/TLS certificates to encrypt the stream.
> **Fix**: Click **Advanced** → **Proceed to site (unsafe)** in your browser. This only needs to be accepted once.

### Q2: API connection blocked on Port 6085 during login
> **Fix**: When logging in for the first time from a new device, your browser may require accepting the certificate for port 6085. Click the link shown on the login error alert: `👉 Click here to Accept Certificate on Port 6085`, click Advanced → Proceed, then return and sign in.

### Q3: Forgotten admin password
> **Fix**: Open terminal on the host and run:
> ```bash
> webdesk reset-users
> ```
> This immediately restores `admin` (`admin123`), `user` (`user123`), and `guest` (`guest123`).

### Q4: Remote resolution does not change
> **Fix**: Ensure your X display driver supports `xrandr` virtual modes. If running on a physical monitor, resolution is constrained by the monitor's supported EDID modes. In virtual machines (QEMU/KVM/VirtualBox), install guest additions for unrestricted resolutions.

### Q5: How to check live logs for debugging
> **Fix**: Run:
> ```bash
> webdesk logs
> ```
> or inspect the log file directly:
> ```bash
> tail -f ~/.local/share/webdesk/webdesk.log
> ```

---

*WebDesk Documentation — Maintained for WebDesk v2.3.1+*
