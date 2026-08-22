# 🖥️ WebDesk — Dual-Protocol In-Browser & Windows RDP Remote Desktop Suite

**WebDesk** is a self-contained, high-performance, encrypted remote desktop suite for Linux. It combines **in-browser streaming (`https://<IP>:6080/`)** and **native Windows Remote Desktop (`<IP>:3389`)** into a unified pipeline, allowing seamless access to live Linux desktops (`DISPLAY=:0`) or 24/7 login screens (LightDM, GDM3, SDDM).

---

## ⚡ Quick Start

### 🚀 1-Line Automated Installation
```bash
curl -fsSL https://raw.githubusercontent.com/sandipkc7/Webdesk/main/webdesk.sh -o webdesk.sh && chmod +x webdesk.sh && ./webdesk.sh install
```

### 🌐 Accessing Your Linux Desktop

| Client Type | Endpoint | Credentials | Details |
| :--- | :--- | :--- | :--- |
| **🌐 Any Web Browser** (Chrome/Edge/Safari/Firefox) | `https://<Linux_IP>:6080/` | WebDesk Users (`admin:admin123`, `user:user123`, `guest:guest123`) | Glassmorphic portal with Floating Action Hub, audio, file transfers & Linux shortcuts. |
| **🪟 Windows Remote Desktop** (`mstsc.exe`) | `<Linux_IP>:3389` | Linux System User (`remotelinuxuser` + Linux Password) | Native Windows RDP client with 3 session modes (Mirror `:0`, Virtual Session, or Multi-User). |

---

## 📑 Table of Contents

1. [Architecture & Protocol Pipeline](#1-architecture--protocol-pipeline)
2. [Prerequisites, Apps & Libraries](#2-prerequisites-apps--libraries)
3. [Command-Line Interface (CLI) Quick Reference](#3-command-line-interface-cli-quick-reference)
4. [Interactive Terminal Menu & Administration Center](#4-interactive-terminal-menu--administration-center)
5. [Master Password & Security Modes](#5-master-password--security-modes)
6. [Multi-User Web Authentication & Roles (RBAC)](#6-multi-user-web-authentication--roles-rbac)
7. [Client IP Logging & Security Audit Trail](#7-client-ip-logging--security-audit-trail)
8. [Windows Native RDP Server (XRDP / Port 3389)](#8-windows-native-rdp-server-xrdp--port-3389)
9. [Comprehensive Features Deep-Dive](#9-comprehensive-features-deep-dive)
10. [Configuration Files, Export & Import](#10-configuration-files-export--import)
11. [Troubleshooting & FAQs](#11-troubleshooting--faqs)

---

## 1. Architecture & Protocol Pipeline

WebDesk provides a unified dual-protocol engine serving both web and native desktop clients:

<details>
<summary><b>🔍 View Full Architecture Diagram & Network Port Allocation</b></summary>

```text
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

### Network Ports

| Port | Protocol | Service | Description |
| :--- | :--- | :--- | :--- |
| **`6080`** | `HTTPS` / `WSS` | Web Portal & noVNC | Primary web interface and encrypted VNC WebSocket stream |
| **`3389`** | `TLS RDP` | Windows XRDP Server | Native Windows Remote Desktop Connection endpoint (`mstsc.exe`) |
| **`6085`** | `HTTPS` | WebDesk API | Multi-user authentication, file transfers, and system control |
| **`6086`** | `WSS` | Audio Streamer | Low-latency live desktop audio stream via Web Audio API |
| **`5900`** | `TCP` (Internal) | x11vnc RFB | Local loopback stream (`127.0.0.1` only, blocked from WAN) |

### Runtime Directory Layout (`~/.local/share/webdesk/`)
```text
~/.local/share/webdesk/
├── api_server.py          # REST API & RBAC Controller (Port 6085)
├── audio_server.py        # Live PulseAudio/PipeWire WebSocket streamer (Port 6086)
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
└── root/                  # Standalone bundled runtime dependencies (x11vnc, novnc, etc.)
```

</details>

---

## 2. Prerequisites, Apps & Libraries

WebDesk is **completely self-contained**. It requires **zero external `pip` packages** and runs entirely in user-space.

<details>
<summary><b>📦 View Host Dependencies, Standalone Packages & Compatibility Matrix</b></summary>

### 2.1 Host System Prerequisites
```bash
sudo apt update && sudo apt install -y python3 openssl x11-xserver-utils pulseaudio-utils curl dpkg
```

* **`python3` (3.8+)**: Uses standard library modules (`ssl`, `http.server`, `hashlib`, `hmac`, `json`, `subprocess`, `threading`, `secrets`, `socket`, `base64`, `shutil`, `re`).
* **`openssl`**: Creates 2048-bit self-signed SSL/TLS certificates (`webdesk.pem`, `webdesk.crt`, `webdesk.key`).
* **`x11-xserver-utils` (`xrandr`)**: Manages dynamic client resolution auto-matching.
* **`pulseaudio-utils` (`parec`) / `pipewire` (`pw-record`)**: Captures real-time desktop audio.
* **`systemd` / `loginctl`**: Daemon management (`webdesk.service`) and remote power/session actions.

### 2.2 Standalone Packages (Auto-Downloaded by `webdesk.sh`)
* **`x11vnc` & `libvncserver1`**: High-performance VNC server for `DISPLAY=:0`.
* **`novnc`**: HTML5 canvas web client.
* **`websockify`**: TLS/SSL WebSocket proxy.
* **`xdotool` & `xclip`**: Synthetic input injection and clipboard synchronization.

### 2.3 Compatibility Matrix
* **Desktop Environments**: XFCE, Cinnamon, MATE, LXDE, LXQt, GNOME (X11), KDE Plasma (X11).
* **Display Managers (24/7 Login Screen)**: LightDM (`lightdm`), GDM3 (`gdm3`), SDDM (`sddm`).

### 2.4 Complete Uninstallation
```bash
./webdesk.sh remove -y
```

</details>

---

## 3. Command-Line Interface (CLI) Quick Reference

Run `webdesk [COMMAND]` from anywhere in your terminal:

```bash
webdesk start                 # Starts WebDesk server
webdesk stop                  # Stops WebDesk server
webdesk restart               # Restarts WebDesk server / systemd service
webdesk status                # Displays live server status, ports, and URLs
webdesk menu                  # Launches the interactive terminal control menu
```

<details>
<summary><b>⚙️ View Full CLI Subcommands Table (Administration, RDP, Display & Profiles)</b></summary>

| Command | Arguments | Description |
| :--- | :--- | :--- |
| **`admin`** | — | Opens the Administration Menu (Master Password required). |
| **`audit`** | — | Opens the Client Login & IP Address Audit Log Viewer. |
| **`users`** | — | Opens Web User Management (Add/Edit/Suspend/Kick/Delete). |
| **`master-password`** | — | Configures Master Password mode (Custom Password vs. Dynamic Rule). |
| **`rdp-enable`** | — | Installs, configures, and starts the XRDP server on port 3389. |
| **`rdp-disable`** | — | Stops and disables the XRDP server. |
| **`rdp-mode`** | `[1|2|3]` | Switches RDP mode: `1` (Mirror :0), `2` (Virtual Session), `3` (Multi-User). |
| **`rdp-status`** | — | Displays active RDP listening port, mode, and connected Windows sessions. |
| **`rdp-port`** | `[PORT]` | Changes the default listening port (default: 3389). |
| **`rdp-user`** | — | Interactive wizard to create a secondary Linux account for Mode 3. |
| **`profile`** | `[name]` | Sets speed profile: `ultra_fast`, `balanced`, `high_quality`, `low_bandwidth`. |
| **`resolution`** | `[WxH]` | Sets remote resolution (e.g. `1920x1080`, `1600x900`, `1280x720`). |
| **`export`** | `[file.json]` | Exports full configuration backup (users, master auth, settings). |
| **`import`** | `<file.json>` | Imports configuration backup JSON. |
| **`reset-users`** | — | Factory resets user database to defaults (`admin`, `user`, `guest`). |
| **`install-service`** | — | Installs 24/7 background systemd service (`webdesk.service`). |
| **`uninstall-service`** | — | Removes 24/7 background systemd service. |
| **`logs`** | — | Streams real-time live server logs (`tail -f webdesk.log`). |
| **`renew-cert`** | — | Regenerates fresh SSL/TLS certificates. |

</details>

---

## 4. Interactive Terminal Menu & Administration Center

Launch the interactive console menu by running `webdesk` (or `./webdesk.sh`):

```text
  WebDesk Server v2.3.1 - Encrypted Remote Desktop Suite
  ==============================================================
  Status     : ● RUNNING (24/7 System Service / Login Screen Active)
  Profile    : Balanced (Recommended / 30-45 FPS)
  Resolution : 1920x1080
  Web Port   : 6080 (HTTPS/WSS) | RDP Port: 3389 (Active - Mode 1: Mirror :0)
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

<details>
<summary><b>🛡️ View Administration & Security Center Details (Option 5)</b></summary>

All sensitive actions are consolidated behind Master Password protection:

```text
  WebDesk Administration & Security Center (Master Protected)
  ==============================================================

  1) 👥 Web User Accounts & Access Control
  2) 📜 Client Login & IP Address Audit Logs
  3) 🔑 Master Password Settings (Custom Password / Dynamic Rule)
  4) 🖥️  Windows Remote Desktop Protocol (XRDP Server)
  5) 🔄 Reset All Web Users to Factory Defaults
  6) 🔒 Renew / Reissue TLS/SSL Certificate
  7) 📤 Export Configuration & User Accounts (.json)
  8) 📥 Import Configuration & User Accounts (.json)
  9) 🗑️  Completely Uninstall WebDesk
  0) ↩  Back to Main Menu
```

</details>

---

## 5. Master Password & Security Modes

WebDesk secures administrative terminal functions behind a Master Password with two modes:

* **Mode 1: Custom Master Password** (Recommended) — Set a persistent, custom master password stored with PBKDF2-HMAC-SHA256 hashing (100,000 iterations).
* **Mode 2: Dynamic Daily Rule** (Default) — Formatted as `Pass@<Day><Date>` (e.g. `Pass@Sat22`).

<details>
<summary><b>🔑 View How to Configure Master Password</b></summary>

Run `webdesk master-password` or choose **Administration $\rightarrow$ Option 3**:
```text
--- Master Password Configuration ---
Current Mode : Custom Master Password (or Dynamic Daily Rule)
==============================================================
  1) ✍️   Set Custom Master Password
  2) 🔄  Revert to Default Dynamic Rule (Pass@<Day><Date>)
  3) ℹ️   View Dynamic Daily Rule Details
  0) ↩   Back to Administration Menu
```

</details>

---

## 6. Multi-User Web Authentication & Roles (RBAC)

The Web Portal (`login.html`) provides role-based access control (RBAC):

| Role | Default Login | Permissions & Capabilities |
| :--- | :--- | :--- |
| **`admin`** | `admin` / `admin123` | **Full Administrative Control**: Interactive session, resolution control, file transfer, password management, user management, audit logs, power actions. |
| **`user`** | `user` / `user123` | **Interactive User**: Full desktop interaction, audio streaming, file upload/download, change own password, power actions. |
| **`viewer`** | `guest` / `guest123` | **100% Locked View-Only**: Real-time screen and audio stream. All mouse clicks, movement, and keystrokes are intercepted and dropped. |

<details>
<summary><b>🔒 View Single Active Session Protection & In-Page Disconnect Overlay</b></summary>

WebDesk enforces a **Single Active Session per User Account**:
1. When a user signs in from **Browser B**, any existing session for that username on **Browser A** is superseded.
2. **Browser A** detects this via real-time heartbeat, severs the stream, and displays a dark frosted glass overlay (`backdrop-filter: blur(18px)`):
   > ⚠️ **Session Disconnected**  
   > *New session started in another browser.*

</details>

---

## 7. Client IP Logging & Security Audit Trail

WebDesk logs client IP addresses for all connection attempts:

* **Plain-text log**: `~/.local/share/webdesk/login_audit.log`
* **Structured JSON**: `~/.local/share/webdesk/login_audit.json`

<details>
<summary><b>📜 View Sample Audit Log Output</b></summary>

Run `webdesk audit` or select **Option 2** under Administration:
```text
TIMESTAMP               STATUS     USERNAME        ROLE       IP ADDRESS          DETAILS
----------------------------------------------------------------------------------------------------------
2026-08-22 12:15:21     SUCCESS    admin           admin      192.168.1.45        
2026-08-22 12:10:40     FAILED     admin           -          192.168.1.102       Incorrect password
2026-08-22 11:48:12     SUCCESS    guest           viewer     100.125.6.113       
```

</details>

---

## 8. Windows Native RDP Server (XRDP / Port 3389)

Connect directly from Windows using the built-in **Remote Desktop Connection (`mstsc.exe`)** app over port `3389`.

### 🔀 The 3 RDP Session Modes

| Mode | Name | How It Works & Best Use Case |
| :--- | :--- | :--- |
| **Mode 1** | **🪞 Live Desktop Mirror (`:0`)** | Connects Windows directly to the active physical monitor / WebDesk web client (`127.0.0.1:5900`). You see and control the exact same live screen. |
| **Mode 2** | **🖥️ Dedicated Virtual Session** | Opens an independent, high-speed virtual X11 desktop for your existing Linux user account (`remotelinuxuser`) with full access to personal `/home` files. |
| **Mode 3** | **👥 Multi-User Simultaneous Workstation** | Allows a secondary Linux user (e.g. `remoteuser`) to work simultaneously without sharing the mouse with the local user. |

<details>
<summary><b>🪟 View Windows Connection Walkthrough & Management Commands</b></summary>

#### How to Connect from Windows:
1. Press <kbd>Win</kbd> + <kbd>R</kbd>, type `mstsc`, and press **Enter**.
2. In the **Computer** field, enter your Linux IP and port (e.g. `192.168.1.25:3389`).
3. Click **Connect**.
4. Enter your Linux username (`remotelinuxuser`) and system password.

#### RDP CLI Commands:
```bash
webdesk rdp-enable          # Installs and starts XRDP on port 3389
webdesk rdp-disable         # Stops and disables the XRDP service
webdesk rdp-mode <1|2|3>    # Switches between Mode 1 (Mirror), Mode 2 (Virtual), and Mode 3 (Multi-User)
webdesk rdp-status          # Displays active RDP listening port, mode, and connected Windows sessions
webdesk rdp-port <PORT>     # Changes the default listening port (default: 3389)
webdesk rdp-user            # Wizard to create a secondary Linux user for Mode 3
webdesk rdp-menu            # Opens the interactive RDP configuration menu
```

</details>

---

## 9. Comprehensive Features Deep-Dive

<details>
<summary><b>⚡ 9.1 Performance & Speed/Quality Profiles</b></summary>

| Profile | Frame Rate | Quality (0–9) | Compression (0–9) | Recommended Use Case |
| :--- | :---: | :---: | :---: | :--- |
| ⚡ **Fast / Low Bandwidth** | 30–60 FPS | `3` | `7` | Mobile data, slow Wi-Fi, high network latency |
| ⚖️ **Balanced (Default)** | 30–45 FPS | `6` | `2` | Standard LAN/WAN, fluid desktop work |
| 🎨 **High Quality** | 30 FPS | `9` | `0` | Photo/video editing, pixel-perfect text clarity |
| 🛠️ **Custom** | Adjustable | `0–9` | `0–9` | Fine-tuned via the Floating Hub Settings modal |

</details>

<details>
<summary><b>📐 9.2 Dynamic Screen Resolution Matching</b></summary>

* **One-Click `🎯 Match Res`**: Dynamically calculates the browser window dimensions and Device Pixel Ratio ($DPR$) to resize the host X11 display instantly.
* **Auto-Match on Login (`auto`)**: Automatically measures the client viewport upon login to eliminate letterboxing or black bars.
* **Standard Presets**: Supports `2560x1440` (2K), `1920x1080` (Full HD), `1600x900`, `1440x900`, `1366x768`, `1280x720` (720p), and custom user modes.

</details>

<details>
<summary><b>🛡️ 9.3 Hardened View-Only / Guest Input Lock</b></summary>

WebDesk enforces a **3-Layer Input Lock** for guest viewers:
1. **DOM Layout Layer**: Applies `pointer-events: none !important;` so the browser drops 100% of mouse clicks and drags.
2. **Event Interceptor Layer**: Destroys all `keydown`, `keyup`, and `keypress` events during the capture phase (`stopImmediatePropagation()`).
3. **RFB Protocol Layer**: Enforces `UI.rfb.viewOnly = true` directly within the noVNC transport engine.

</details>

<details>
<summary><b>🔊 9.4 Low-Latency Remote Audio Streaming</b></summary>

* **Source**: Captures audio from the default PulseAudio/PipeWire monitor source.
* **Transport**: Streams over dedicated WebSocket on port `6086`.
* **Playback**: Decoded and scheduled via the browser **Web Audio API** (`AudioContext`) with jitter buffering for synchronized, low-latency playback.

</details>

<details>
<summary><b>📁 9.5 Drag-and-Drop File Transfers</b></summary>

* **Uploads**: Drag and drop any file directly onto the browser window. Files are saved directly into `~/Downloads/`.
* **Downloads**: Click **📁 Files** in the Floating Hub to browse `~/Downloads/` and download files back to the client computer.

</details>

<details>
<summary><b>⌨️ 9.6 Special Key Forwarder & Dedicated Linux Shortcuts</b></summary>

The Floating Action Hub features a dedicated **Linux Shortcuts** toolbar sending raw X11 keysyms directly through the RFB WebSocket pipeline:
* **Sticky Key Latches**: `Ctrl`, `Alt`, `Shift`, `Win`
* **Linux Dedicated Shortcuts**:
  - `🪟 Start`: Opens application launcher (`Super_L`).
  - `🔀 Alt+Tab`: Cycles through active application windows (`Alt + Tab`).
  - `💻 Terminal`: Launches default terminal emulator (`Ctrl + Alt + T`).
  - `🖥️ Desktop`: Minimizes all windows to reveal desktop (`Super + D`).
  - `⚡ Run`: Opens application run dialog (`Alt + F2`).
  - `❌ Close`: Closes currently focused window (`Alt + F4`).
  - `📋 Term Paste`: Pastes clipboard text directly into terminal (`Ctrl + Shift + V`).
  - `⌨️ CAD`: Sends system interrupt / task manager signal (`Ctrl + Alt + Del`).

</details>

<details>
<summary><b>🔒 9.7 Remote Session & Power Controls</b></summary>

Interactive users (`admin` and `user`) can perform system-level session actions from the **🔒 Power** modal (with safety confirmation dialogs):
* **🔒 Lock Screen**: Locks the active desktop session (`loginctl lock-sessions` / `dm-tool lock`).
* **👥 Switch User**: Switches the active seat to the login greeter without terminating background sessions (`dm-tool switch-to-greeter`).
* **🚪 Log Out**: Safely logs out the active user session (`loginctl terminate-user`).
* **🌙 Sleep / Suspend**: Puts the host computer into system sleep/suspend (`systemctl suspend`).
* **🔄 Reboot System**: Reboots the Linux system (`systemctl reboot`).

</details>

<details>
<summary><b>🖥️ 9.8 24/7 System Service & Native GTK Control Panel</b></summary>

* **24/7 System Service (`webdesk.service`)**: Allows logging into Linux from a cold boot via browser before any user logs in physically.
* **Native GTK Desktop GUI (`webdesk_gui.py`)**: PyGObject (GTK3) application with live start/stop toggles, profile switcher, resolution picker, and visual user account manager.

</details>

---

## 10. Configuration Files, Export & Import

<details>
<summary><b>💾 View Configuration File Formats & JSON Backup/Restore</b></summary>

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
RDP_PORT=3389
RDP_MODE=1
RDP_ENABLED=true
```

### 📦 Unified Configuration Export & Import (.json)
* **Export Configuration**:
  ```bash
  webdesk export [destination_file.json]
  ```
* **Import Configuration**:
  ```bash
  webdesk import <source_backup.json>
  ```

</details>

---

## 11. Troubleshooting & FAQs

<details>
<summary><b>❓ Q1: Browser displays "Your connection isn't private" or certificate warning</b></summary>

> **Explanation**: WebDesk uses self-signed SSL/TLS certificates to encrypt the stream.  
> **Fix**: Click **Advanced** → **Proceed to site (unsafe)** in your browser. This only needs to be accepted once.

</details>

<details>
<summary><b>❓ Q2: API connection blocked on Port 6085 during login</b></summary>

> **Fix**: When logging in for the first time from a new device, click the link shown on the login error alert: `👉 Click here to Accept Certificate on Port 6085`, click Advanced → Proceed, then return and sign in.

</details>

<details>
<summary><b>❓ Q3: Forgotten admin password</b></summary>

> **Fix**: Run `webdesk reset-users` on the host terminal to restore `admin` (`admin123`), `user` (`user123`), and `guest` (`guest123`).

</details>

<details>
<summary><b>❓ Q4: Remote resolution does not change</b></summary>

> **Fix**: Ensure your X display driver supports `xrandr` virtual modes. In virtual machines (QEMU/KVM/VirtualBox), install guest additions for unrestricted resolutions.

</details>

<details>
<summary><b>❓ Q5: How to check live logs for debugging</b></summary>

> **Fix**: Run `webdesk logs` or inspect `tail -f ~/.local/share/webdesk/webdesk.log`.

</details>

---

*WebDesk Documentation — Maintained for WebDesk v2.3.1+*
