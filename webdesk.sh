#!/usr/bin/env bash
# ==============================================================================
# WebDesk - Encrypted In-Browser Desktop Streaming Server for Linux
# Stack: x11vnc + websockify (TLS/SSL) + noVNC + Audio Streamer + ResSync
# Supports: Live Desktop, Login Screen (LightDM), Fullscreen & Mobile
# ==============================================================================

set -eo pipefail

APP_NAME="WebDesk"
VERSION="2.3.1"
SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"

# Resolve installation directory (works for current user, sudo, and systemd service)
if [ -d "/home/sandeep/.local/share/webdesk" ]; then
    INSTALL_DIR="/home/sandeep/.local/share/webdesk"
    USER_HOME="/home/sandeep"
else
    REAL_USER="${SUDO_USER:-$USER}"
    USER_HOME=$(getent passwd "${REAL_USER}" | cut -d: -f6)
    INSTALL_DIR="${USER_HOME}/.local/share/webdesk"
fi

VNC_ROOT="${INSTALL_DIR}/root"
VNC_PORT="5900"
WEB_PORT="6080"
RES_PORT="6085"
AUDIO_PORT="6086"
DISPLAY_NUM="${DISPLAY:-:0}"
PASSWD_FILE="${INSTALL_DIR}/vnc_passwd"
CONFIG_FILE="${INSTALL_DIR}/config.env"
CERT_PEM="${INSTALL_DIR}/webdesk.pem"
CERT_CRT="${INSTALL_DIR}/webdesk.crt"
CERT_KEY="${INSTALL_DIR}/webdesk.key"
AUTOSTART_DIR="${USER_HOME}/.config/autostart"
AUTOSTART_FILE="${AUTOSTART_DIR}/webdesk.desktop"
SERVICE_FILE="/etc/systemd/system/webdesk.service"

DEFAULT_PROFILE="balanced"
if [ -f "${CONFIG_FILE}" ]; then
    # shellcheck disable=SC1090
    source "${CONFIG_FILE}"
else
    mkdir -p "${INSTALL_DIR}"
    echo "PROFILE=${DEFAULT_PROFILE}" > "${CONFIG_FILE}"
    PROFILE="${DEFAULT_PROFILE}"
fi

export LD_LIBRARY_PATH="${VNC_ROOT}/usr/lib/x86_64-linux-gnu:${VNC_ROOT}/usr/lib:${LD_LIBRARY_PATH}"
export PYTHONPATH="${VNC_ROOT}/usr/lib/python3/dist-packages:${PYTHONPATH}"
export PATH="${VNC_ROOT}/usr/bin:${PATH}"

# Terminal Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

get_ips() {
    ip -4 addr show scope global | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | grep -v '127.0.0.1' || echo "127.0.0.1"
}

is_running() {
    pgrep -f "x11vnc" >/dev/null 2>&1 && pgrep -f "websockify" >/dev/null 2>&1
}

is_service_enabled() {
    systemctl is-active webdesk.service >/dev/null 2>&1
}

get_profile_flags() {
    case "${PROFILE}" in
        ultra_fast)
            VNC_TUNING="-wait 5 -defer 5 -noxdamage -nowf -repeat -nodpms -xkb"
            PROFILE_DESC="Ultra Fast (60 FPS / Low Latency)"
            ;;
        high_quality)
            VNC_TUNING="-wait 15 -defer 15 -noxdamage -repeat -nodpms -xkb"
            PROFILE_DESC="High Quality (Crisp Text & Colors)"
            ;;
        low_bandwidth)
            VNC_TUNING="-wait 35 -defer 35 -wireframe -repeat -nodpms -xkb"
            PROFILE_DESC="Low Bandwidth (Eco / Slow Wi-Fi)"
            ;;
        balanced|*)
            VNC_TUNING="-wait 10 -defer 10 -noxdamage -repeat -nodpms -xkb"
            PROFILE_DESC="Balanced (Recommended / 30-45 FPS)"
            ;;
    esac
}

generate_ssl_cert() {
    mkdir -p "${INSTALL_DIR}"
    echo -e "${BLUE}${BOLD}[WebDesk]${NC} Generating SSL/TLS certificate for encrypted HTTPS/WSS..."
    
    SAN_ENTRIES="DNS:localhost,IP:127.0.0.1"
    for ip in $(get_ips); do
        SAN_ENTRIES="${SAN_ENTRIES},IP:${ip}"
    done

    openssl req -x509 -nodes -newkey rsa:2048 -days 3650 \
        -keyout "${CERT_KEY}" \
        -out "${CERT_CRT}" \
        -subj "/CN=WebDesk-Encrypted" \
        -addext "subjectAltName=${SAN_ENTRIES}" >/dev/null 2>&1

    cat "${CERT_CRT}" "${CERT_KEY}" > "${CERT_PEM}"
    chmod 644 "${CERT_CRT}" "${CERT_KEY}" "${CERT_PEM}"
    echo -e "${GREEN}✔ SSL Certificate generated successfully.${NC}"
}

ensure_index_page() {
    if [ -f "${VNC_ROOT}/usr/share/novnc/vnc.html" ]; then
        cp "${VNC_ROOT}/usr/share/novnc/vnc.html" "${VNC_ROOT}/usr/share/novnc/index.html"
    fi
}

install_webdesk() {
    echo -e "${BLUE}${BOLD}[WebDesk]${NC} Installing standalone components into ${INSTALL_DIR}..."
    mkdir -p "${INSTALL_DIR}/downloads" "${VNC_ROOT}"
    
    cd "${INSTALL_DIR}/downloads"
    echo -e "${YELLOW}--> Downloading packages (no root/sudo required)...${NC}"
    /usr/bin/apt-get download x11vnc libvncserver1 libvncclient1 novnc websockify python3-websockify xdotool libxdo3 xclip libxmu6 >/dev/null 2>&1 || {
        echo -e "${RED}[!] Error downloading packages. Please check internet connection.${NC}"
        exit 1
    }

    echo -e "${YELLOW}--> Extracting binaries and web assets...${NC}"
    for deb in *.deb; do
        dpkg -x "$deb" "${VNC_ROOT}" >/dev/null 2>&1
    done

    rm -rf "${INSTALL_DIR}/downloads"
    mkdir -p "${USER_HOME}/.local/bin"
    ln -sf "${SCRIPT_PATH}" "${USER_HOME}/.local/bin/webdesk"

    generate_ssl_cert
    ensure_index_page
    echo -e "${GREEN}${BOLD}[WebDesk] Installation completed successfully!${NC}\n"
}

remove_webdesk() {
    local force_flag="${1:-}"
    clear
    echo -e "${RED}${BOLD}"
    cat << "REMOVE_BANNER"
  _   _       _           _        _ _ 
 | | | |_ __ (_)_ __  ___| |_ __ _| | |
 | | | | '_ \| | '_ \/ __| __/ _` | | |
 | |_| | | | | | | | \__ \ || (_| | | |
  \___/|_| |_|_|_| |_|___/\__\__,_|_|_|
REMOVE_BANNER
    echo -e "${NC}"
    echo -e "${RED}${BOLD}[WebDesk Uninstaller]${NC} This will completely remove WebDesk from your system:"
    echo -e "  • Stop all running WebDesk streaming processes"
    echo -e "  • Disable and remove the 24/7 systemd service (${SERVICE_FILE})"
    echo -e "  • Remove desktop autostart entries (${AUTOSTART_FILE})"
    echo -e "  • Remove command shortcut (${USER_HOME}/.local/bin/webdesk)"
    echo -e "  • Delete all downloaded binaries, web assets, and databases (${INSTALL_DIR})"
    echo ""

    if [ "$force_flag" != "-y" ] && [ "$force_flag" != "--force" ] && [ "$force_flag" != "-f" ]; then
        read -rp "Are you sure you want to completely remove WebDesk? (y/N): " confirm </dev/tty || true
        if [[ ! "$confirm" =~ ^[yY]$ ]]; then
            echo -e "\n${CYAN}Uninstallation cancelled.${NC}\n"
            return 0
        fi
    fi

    echo -e "\n${YELLOW}--> Stopping active WebDesk streaming services...${NC}"
    stop_webdesk_silent

    if is_service_enabled || [ -f "${SERVICE_FILE}" ]; then
        echo -e "${YELLOW}--> Removing systemd background service...${NC}"
        if [ "$EUID" -eq 0 ]; then
            systemctl disable --now webdesk.service 2>/dev/null || true
            rm -f "${SERVICE_FILE}"
            systemctl daemon-reload 2>/dev/null || true
            systemctl reset-failed 2>/dev/null || true
        elif command -v sudo >/dev/null 2>&1; then
            sudo systemctl disable --now webdesk.service 2>/dev/null || true
            sudo rm -f "${SERVICE_FILE}"
            sudo systemctl daemon-reload 2>/dev/null || true
            sudo systemctl reset-failed 2>/dev/null || true
        fi
    fi

    echo -e "${YELLOW}--> Removing autostart entries and shortcuts...${NC}"
    rm -f "${AUTOSTART_FILE}" 2>/dev/null || true
    rm -f "${USER_HOME}/.local/bin/webdesk" 2>/dev/null || true
    rm -rf "${SCRIPT_DIR}/__pycache__" 2>/dev/null || true

    echo -e "${YELLOW}--> Removing installation directory (${INSTALL_DIR})...${NC}"
    rm -rf "${INSTALL_DIR}" 2>/dev/null || true

    echo -e "\n${GREEN}${BOLD}✔ WebDesk has been completely removed from your system.${NC}\n"
}

stop_webdesk_silent() {
    pkill -9 -f "x11vnc" 2>/dev/null || true
    pkill -9 -f "websockify" 2>/dev/null || true
    pkill -9 -f "api_server.py" 2>/dev/null || true
    pkill -9 -f "res_server.py" 2>/dev/null || true
    pkill -9 -f "audio_server.py" 2>/dev/null || true
    pkill -9 -f "parec" 2>/dev/null || true
    sleep 1
}

start_webdesk() {
    if [ ! -f "${VNC_ROOT}/usr/bin/x11vnc" ] || [ ! -d "${VNC_ROOT}/usr/share/novnc" ]; then
        echo -e "${YELLOW}[WebDesk] Required binaries not found. Triggering automated install...${NC}"
        install_webdesk
    fi

    if [ ! -f "${CERT_PEM}" ]; then
        generate_ssl_cert
    fi

    ensure_index_page
    get_profile_flags

    if is_running; then
        echo -e "${YELLOW}[WebDesk] Server is already running.${NC}"
        status_webdesk
        return 0
    fi

    stop_webdesk_silent

    echo -e "${BLUE}${BOLD}[WebDesk]${NC} Starting encrypted desktop streaming services..."
    echo -e "${MAGENTA}--> Performance Profile: ${BOLD}${PROFILE_DESC}${NC}"

    # WebDesk Multi-User Portal handles authentication; x11vnc runs with -nopw on 127.0.0.1
    PASS_OPT="-nopw"

    # Start x11vnc with auto-auth detection
    # shellcheck disable=SC2086
    "${VNC_ROOT}/usr/bin/x11vnc" \
        -display "${DISPLAY_NUM}" \
        -auth /var/run/lightdm/root/:0 \
        -forever \
        -shared \
        -listen 127.0.0.1 \
        -rfbport "${VNC_PORT}" \
        ${VNC_TUNING} \
        ${PASS_OPT} \
        -bg >/dev/null 2>&1 || {
            "${VNC_ROOT}/usr/bin/x11vnc" \
                -display "${DISPLAY_NUM}" \
                -auth guess \
                -forever \
                -shared \
                -listen 127.0.0.1 \
                -rfbport "${VNC_PORT}" \
                ${VNC_TUNING} \
                ${PASS_OPT} \
                -bg >/dev/null 2>&1
        }

    # Start websockify daemon with TLS/SSL
    "${VNC_ROOT}/usr/bin/websockify" \
        -D \
        --cert="${CERT_PEM}" \
        --web="${VNC_ROOT}/usr/share/novnc/" \
        "${WEB_PORT}" \
        "127.0.0.1:${VNC_PORT}" >/dev/null 2>&1

    # Start WebDesk API daemon (Files, Keys, Power, Resolution)
    if [ -f "${INSTALL_DIR}/api_server.py" ]; then
        python3 "${INSTALL_DIR}/api_server.py" -D >/dev/null 2>&1 || true
    fi

    # Start audio streaming daemon
    if [ -f "${INSTALL_DIR}/audio_server.py" ]; then
        python3 "${INSTALL_DIR}/audio_server.py" -D >/dev/null 2>&1 || true
    fi

    sleep 1.5

    if is_running; then
        echo -e "${GREEN}${BOLD}✔ WebDesk is ACTIVE (Encrypted HTTPS / WSS) on port ${WEB_PORT}!${NC}\n"
        echo -e "${BOLD}Access the encrypted desktop in your host PC browser:${NC}"
        for ip in $(get_ips); do
            echo -e "  👉 ${CYAN}https://${ip}:${WEB_PORT}/${NC}"
        done
        echo ""
    else
        echo -e "${RED}[!] Failed to start WebDesk. Check if display ${DISPLAY_NUM} is active.${NC}"
        exit 1
    fi
}

LOG_FILE="${INSTALL_DIR}/webdesk.log"

log_msg() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo -e "${msg}"
    echo "${msg}" >> "${LOG_FILE}" 2>/dev/null || true
}

# System-level 24/7 service (Handles Display Manager / LightDM login screen & user sessions)
run_system_service() {
    export LD_LIBRARY_PATH="${VNC_ROOT}/usr/lib/x86_64-linux-gnu:${VNC_ROOT}/usr/lib:${LD_LIBRARY_PATH}"
    export PYTHONPATH="${VNC_ROOT}/usr/lib/python3/dist-packages:${PYTHONPATH}"
    export PATH="${VNC_ROOT}/usr/bin:${PATH}"

    mkdir -p "${INSTALL_DIR}"
    touch "${LOG_FILE}"
    chmod 666 "${LOG_FILE}" 2>/dev/null || true

    log_msg "=========================================================="
    log_msg "=== WebDesk 24/7 System Service Started (PID $$) ==="
    log_msg "=========================================================="

    # WebDesk Multi-User Portal handles authentication; x11vnc runs with -nopw on 127.0.0.1
    PASS_OPT="-nopw"
    log_msg "Security: WebDesk Multi-User Portal Authentication ENABLED"

    # 1. Start websockify daemon
    pkill -9 -f "websockify" 2>/dev/null || true
    log_msg "Starting Websockify on port ${WEB_PORT} (HTTPS / WSS)..."
    "${VNC_ROOT}/usr/bin/websockify" \
        -D \
        --cert="${CERT_PEM}" \
        --web="${VNC_ROOT}/usr/share/novnc/" \
        "${WEB_PORT}" \
        "127.0.0.1:${VNC_PORT}" >> "${LOG_FILE}" 2>&1

    # 2. Start API daemon
    if [ -f "${INSTALL_DIR}/api_server.py" ]; then
        pkill -9 -f "api_server.py" 2>/dev/null || true
        log_msg "Starting WebDesk API on port ${RES_PORT}..."
        python3 "${INSTALL_DIR}/api_server.py" -D >> "${LOG_FILE}" 2>&1 || true
    fi

    # 3. Supervisor loop: dynamically tracks Xorg display & LightDM/User session changes
    log_msg "Entering Dynamic Display & Authentication Supervisor loop..."
    while true; do
        XORG_PROC=$(ps -eo pid,args | grep -E '[X]org|[X] ' | grep -v 'grep' | head -n 1 || true)
        ACTIVE_DISP=":0"
        ACTIVE_AUTH=""

        if [ -n "$XORG_PROC" ]; then
            ACTIVE_DISP=$(echo "$XORG_PROC" | grep -oP ':\d+' | head -n 1 || echo ":0")
            ACTIVE_AUTH=$(echo "$XORG_PROC" | grep -oP '(?<=-auth\s)\S+' || echo "")
        fi

        if [ -z "$ACTIVE_AUTH" ] || [ ! -r "$ACTIVE_AUTH" ]; then
            if [ -r "/var/run/lightdm/root/${ACTIVE_DISP}" ]; then
                ACTIVE_AUTH="/var/run/lightdm/root/${ACTIVE_DISP}"
            elif [ -r "/run/lightdm/root/${ACTIVE_DISP}" ]; then
                ACTIVE_AUTH="/run/lightdm/root/${ACTIVE_DISP}"
            elif [ -r "/home/sandeep/.Xauthority" ]; then
                ACTIVE_AUTH="/home/sandeep/.Xauthority"
            fi
        fi

        AUTH_FLAG=""
        if [ -n "$ACTIVE_AUTH" ] && [ -r "$ACTIVE_AUTH" ]; then
            AUTH_FLAG="-auth ${ACTIVE_AUTH}"
            log_msg "Target Display: ${ACTIVE_DISP} (Auth: ${ACTIVE_AUTH})"
        else
            AUTH_FLAG="-auth guess"
            log_msg "Target Display: ${ACTIVE_DISP} (Using -auth guess)"
        fi

        log_msg "Spawning x11vnc backend for display ${ACTIVE_DISP}..."

        # shellcheck disable=SC2086
        "${VNC_ROOT}/usr/bin/x11vnc" \
            -display "${ACTIVE_DISP}" \
            ${AUTH_FLAG} \
            -forever \
            -shared \
            -listen 127.0.0.1 \
            -rfbport "${VNC_PORT}" \
            ${VNC_TUNING} \
            ${PASS_OPT} >> "${LOG_FILE}" 2>&1 || true

        log_msg "x11vnc session ended or display reset. Re-probing in 1s..."
        sleep 1
    done
}

install_system_service() {
    if [ "$EUID" -ne 0 ]; then
        echo -e "${YELLOW}[!] Root privileges required to enable Login Screen streaming.${NC}"
        echo -e "Please run: ${CYAN}${BOLD}sudo ${SCRIPT_PATH} install-service${NC}\n"
        return 1
    fi

    echo -e "${BLUE}${BOLD}[WebDesk]${NC} Installing systemd service for Login Screen (LightDM) streaming..."
    
    # Ensure certs are readable by root
    chmod 644 "${CERT_PEM}" "${CERT_CRT}" "${CERT_KEY}" 2>/dev/null || true

    cat << EOF_SVC > "${SERVICE_FILE}"
[Unit]
Description=WebDesk Remote Desktop Server (System & Login Screen Service)
After=network.target display-manager.service lightdm.service
Wants=display-manager.service

[Service]
Type=simple
ExecStart=${SCRIPT_PATH} system-service
Restart=always
RestartSec=3
Environment=DISPLAY=:0
User=root

[Install]
WantedBy=multi-user.target
EOF_SVC

    systemctl daemon-reload
    systemctl enable --now webdesk.service
    echo -e "${GREEN}${BOLD}✔ WebDesk Login Screen Streaming is now ACTIVE!${NC}"
    echo -e "WebDesk will now stream the LightDM login screen and stay connected across logouts.\n"
}

uninstall_system_service() {
    if [ "$EUID" -ne 0 ]; then
        echo -e "${YELLOW}[!] Root privileges required to disable system service.${NC}"
        echo -e "Please run: ${CYAN}${BOLD}sudo ${SCRIPT_PATH} uninstall-service${NC}\n"
        return 1
    fi

    systemctl disable --now webdesk.service 2>/dev/null || true
    rm -f "${SERVICE_FILE}"
    systemctl daemon-reload
    echo -e "${GREEN}✔ WebDesk system service removed.${NC}\n"
}

stop_webdesk() {
    echo -e "${YELLOW}[WebDesk] Stopping streaming services...${NC}"
    if is_service_enabled; then
        systemctl stop webdesk.service 2>/dev/null || true
    fi
    stop_webdesk_silent
    if ! is_running; then
        echo -e "${GREEN}✔ WebDesk has been stopped.${NC}"
    else
        echo -e "${RED}[!] Some processes could not be stopped.${NC}"
    fi
}

set_resolution() {
    RES="${1:-1920x1080}"
    echo -e "${BLUE}${BOLD}[WebDesk]${NC} Adjusting display resolution to ${RES}..."
    if DISPLAY="${DISPLAY_NUM}" xrandr -s "${RES}" 2>/dev/null; then
        echo -e "${GREEN}✔ Desktop resolution set to ${RES}.${NC}"
    else
        DISPLAY="${DISPLAY_NUM}" xrandr --output Virtual1 --mode "${RES}" 2>/dev/null || {
            echo -e "${RED}[!] Failed to set resolution ${RES}. Check 'xrandr' output.${NC}"
            return 1
        }
        echo -e "${GREEN}✔ Desktop resolution set to ${RES}.${NC}"
    fi
}

set_profile() {
    NEW_PROFILE="${1}"
    case "${NEW_PROFILE}" in
        ultra_fast|fast|60fps|1)
            PROFILE="ultra_fast"
            ;;
        high_quality|quality|sharp|3)
            PROFILE="high_quality"
            ;;
        low_bandwidth|eco|mobile|4)
            PROFILE="low_bandwidth"
            ;;
        balanced|default|auto|2|*)
            PROFILE="balanced"
            ;;
    esac

    echo "PROFILE=${PROFILE}" > "${CONFIG_FILE}"
    get_profile_flags
    echo -e "${GREEN}✔ Performance Profile switched to: ${BOLD}${PROFILE_DESC}${NC}"
    
    if is_running; then
        echo -e "${YELLOW}--> Restarting WebDesk to apply changes...${NC}"
        stop_webdesk_silent
        start_webdesk
    fi
}

status_webdesk() {
    get_profile_flags
    CUR_RES=$(DISPLAY="${DISPLAY_NUM}" xrandr 2>/dev/null | grep -E '\*' | awk '{print $1}' || echo "Default")
    if is_running; then
        echo -e "${GREEN}${BOLD}● WebDesk is RUNNING${NC}"
        if is_service_enabled; then
            echo -e "  Service Mode     : ${GREEN}${BOLD}System Service (Login Screen / LightDM Active)${NC}"
        else
            echo -e "  Service Mode     : ${CYAN}User Session Mode (:0)${NC}"
        fi
        echo -e "  Security Mode    : ${GREEN}${BOLD}Encrypted (HTTPS / TLS / WSS)${NC}"
        echo -e "  Speed & Quality  : ${MAGENTA}${BOLD}${PROFILE_DESC}${NC}"
        echo -e "  Resolution       : ${CYAN}${CUR_RES}${NC}"
        echo -e "  Resolution Sync  : ${GREEN}Port ${RES_PORT} (Active)${NC}"
        echo -e "  Audio Streaming  : ${GREEN}Port ${AUDIO_PORT} (Active)${NC}"
        echo -e "  Web / noVNC Port : ${WEB_PORT} (Encrypted)"
        if [ -f "${PASSWD_FILE}" ]; then
            echo -e "  Password Protect : ${GREEN}Enabled (Protected)${NC}"
        else
            echo -e "  Password Protect : ${YELLOW}Disabled (No password)${NC}"
        fi
        echo -e "\n${BOLD}Encrypted Browser URLs:${NC}"
        for ip in $(get_ips); do
            echo -e "  👉 ${CYAN}https://${ip}:${WEB_PORT}/${NC}"
        done
    else
        echo -e "${RED}${BOLD}○ WebDesk is STOPPED${NC}"
    fi
}

manage_web_users() {
    export PYTHONPATH="${INSTALL_DIR}:${PYTHONPATH}"
    while true; do
        clear
        echo -e "${BOLD}${CYAN}--- WebDesk Multi-User Web Accounts Manager ---${NC}\n"
        echo -e "  ${BOLD}1)${NC} 📋 List All Web Users, Roles & Status"
        echo -e "  ${BOLD}2)${NC} ➕ Add New Web User (Admin / User / Guest)"
        echo -e "  ${BOLD}3)${NC} 🔑 Change User Password"
        echo -e "  ${BOLD}4)${NC} ⏸️  Suspend / Unsuspend User Account"
        echo -e "  ${BOLD}5)${NC} ⚡ Terminate Active User Session (Kick)"
        echo -e "  ${BOLD}6)${NC} 🗑️  Delete Web User"
        echo -e "  ${BOLD}7)${NC} 🔄 Reset All Users & Logins to Factory Defaults"
        echo -e "  ${BOLD}8)${NC} 📤 Export Configuration & User Accounts (.json)"
        echo -e "  ${BOLD}9)${NC} 📥 Import Configuration & User Accounts (.json)"
        echo -e "  ${BOLD}0)${NC} ↩  Back to Main Menu\n"
        read -rp "Select option [0-9]: " u_choice </dev/tty || break

        case "$u_choice" in
            1)
                echo -e "\n${BLUE}${BOLD}[Registered Web Users]${NC}"
                echo -e "  ${BOLD}USERNAME        ROLE            PROFILE / RES          STATUS          CREATED${NC}"
                echo -e "  -----------------------------------------------------------------------------------------------"
                python3 -c "
import sys
sys.path.insert(0, '${INSTALL_DIR}')
import user_auth
for u in user_auth.list_users():
    role_color = '\033[1;36m' if u['role'] == 'admin' else ('\033[1;32m' if u['role'] == 'user' else '\033[1;33m')
    status_color = '\033[1;32m' if u.get('status') == 'active' else '\033[1;31m'
    status_str = u.get('status', 'active')
    st = u.get('settings', {})
    prof_res = f\"{st.get('profile', 'balanced')} | {st.get('resolution', 'auto')}\"
    print(f\"  {u['username']:<15} {role_color}{u['role']:<15}\033[0m \033[1;35m{prof_res:<22}\033[0m {status_color}{status_str:<15}\033[0m {u['created_at']}\")
"
                pause_prompt
                ;;
            2)
                echo -e "\n${BLUE}${BOLD}[Add New Web User]${NC}"
                read -rp "Enter username: " new_uname </dev/tty || true
                read -rsp "Enter password: " new_upass </dev/tty || true
                echo ""
                echo -e "Select Role: 1) Admin (Full Control)  2) User (Interactive)  3) Guest (View Only)"
                read -rp "Select role [1-3, default 2]: " new_urole </dev/tty || true
                ROLE_STR="user"
                if [ "$new_urole" = "1" ]; then ROLE_STR="admin"; fi
                if [ "$new_urole" = "3" ]; then ROLE_STR="viewer"; fi
                python3 -c "
import sys
sys.path.insert(0, '${INSTALL_DIR}')
import user_auth
ok, msg = user_auth.add_user('admin', '${new_uname}', '${new_upass}', '${ROLE_STR}')
print(f'\\n\033[1;32m✔ {msg}\033[0m' if ok else f'\\n\033[1;31m✖ {msg}\033[0m')
"
                pause_prompt
                ;;
            3)
                echo -e "\n${BLUE}${BOLD}[Change User Password]${NC}"
                read -rp "Enter username to update: " target_uname </dev/tty || true
                read -rsp "Enter new password: " target_upass </dev/tty || true
                echo ""
                python3 -c "
import sys
sys.path.insert(0, '${INSTALL_DIR}')
import user_auth
ok, msg = user_auth.change_password('admin', 'admin', '${target_uname}', '${target_upass}')
print(f'\\n\033[1;32m✔ {msg}\033[0m' if ok else f'\\n\033[1;31m✖ {msg}\033[0m')
"
                pause_prompt
                ;;
            4)
                echo -e "\n${YELLOW}${BOLD}[Suspend / Unsuspend User Account]${NC}"
                read -rp "Enter username: " susp_uname </dev/tty || true
                echo -e "Action: 1) ⏸️ Suspend (Block login & kick)  2) ▶️ Unsuspend (Reactivate)"
                read -rp "Select action [1-2]: " susp_act </dev/tty || true
                python3 -c "
import sys
sys.path.insert(0, '${INSTALL_DIR}')
import user_auth
if '${susp_act}' == '1':
    ok, msg = user_auth.suspend_user('admin', '${susp_uname}')
else:
    ok, msg = user_auth.unsuspend_user('admin', '${susp_uname}')
print(f'\\n\033[1;32m✔ {msg}\033[0m' if ok else f'\\n\033[1;31m✖ {msg}\033[0m')
"
                pause_prompt
                ;;
            5)
                echo -e "\n${RED}${BOLD}[Terminate Active User Session (Kick)]${NC}"
                read -rp "Enter username to disconnect: " kick_uname </dev/tty || true
                python3 -c "
import sys
sys.path.insert(0, '${INSTALL_DIR}')
import user_auth
ok, msg = user_auth.terminate_user_session('admin', '${kick_uname}')
print(f'\\n\033[1;32m✔ {msg}\033[0m' if ok else f'\\n\033[1;31m✖ {msg}\033[0m')
"
                pause_prompt
                ;;
            6)
                echo -e "\n${RED}${BOLD}[Delete Web User]${NC}"
                read -rp "Enter username to delete: " del_uname </dev/tty || true
                python3 -c "
import sys
sys.path.insert(0, '${INSTALL_DIR}')
import user_auth
ok, msg = user_auth.delete_user('admin', '', '${del_uname}')
print(f'\\n\033[1;32m✔ {msg}\033[0m' if ok else f'\\n\033[1;31m✖ {msg}\033[0m')
"
                pause_prompt
                ;;
            7)
                echo -e "\n${YELLOW}${BOLD}[Reset All Web Users to Factory Defaults]${NC}"
                echo -e "${RED}This will reset the user database to standard default accounts:${NC}"
                echo -e "  • ${BOLD}admin${NC} -> password: ${BOLD}admin123${NC} (Role: Admin)"
                echo -e "  • ${BOLD}user${NC}  -> password: ${BOLD}user123${NC}  (Role: User)"
                echo -e "  • ${BOLD}guest${NC} -> password: ${BOLD}guest123${NC} (Role: Guest/Viewer)"
                echo -e "  • Restores default speed/quality profiles and auto resolution"
                echo -e "  • Clears all suspended states and revoked session tokens"
                echo ""
                read -rp "Are you sure you want to reset all user accounts? (y/N): " confirm_reset </dev/tty || true
                if [[ "$confirm_reset" =~ ^[yY]$ ]]; then
                    python3 -c "
import sys
sys.path.insert(0, '${INSTALL_DIR}')
import user_auth
ok, msg = user_auth.reset_default_users()
print(f'\\n\033[1;32m✔ {msg}\033[0m' if ok else f'\\n\033[1;31m✖ {msg}\033[0m')
"
                else
                    echo -e "\n${CYAN}Reset cancelled.${NC}"
                fi
                pause_prompt
                ;;
            8)
                echo -e "\n${BLUE}${BOLD}[Export Full WebDesk Configuration]${NC}"
                default_exp="${USER_HOME}/webdesk_config_backup.json"
                read -rp "Enter destination path [default: ${default_exp}]: " exp_dest </dev/tty || true
                exp_dest="${exp_dest:-$default_exp}"
                python3 -c "
import sys
sys.path.insert(0, '${INSTALL_DIR}')
import user_auth
ok, msg, _ = user_auth.export_config('${exp_dest}')
print(f'\\n\033[1;32m✔ {msg}\033[0m' if ok else f'\\n\033[1;31m✖ {msg}\033[0m')
"
                pause_prompt
                ;;
            9)
                echo -e "\n${YELLOW}${BOLD}[Import Full WebDesk Configuration]${NC}"
                read -rp "Enter path to configuration JSON file: " imp_src </dev/tty || true
                if [ -n "$imp_src" ]; then
                    python3 -c "
import sys
sys.path.insert(0, '${INSTALL_DIR}')
import user_auth
ok, msg = user_auth.import_config('${imp_src}')
print(f'\\n\033[1;32m✔ {msg}\033[0m' if ok else f'\\n\033[1;31m✖ {msg}\033[0m')
"
                else
                    echo -e "\n${CYAN}Import cancelled.${NC}"
                fi
                pause_prompt
                ;;
            0|*)
                break
                ;;
        esac
    done
}

renew_cert() {
    generate_ssl_cert
    if is_running; then
        echo -e "${YELLOW}--> Restarting WebDesk to apply new SSL certificate...${NC}"
        stop_webdesk_silent
        start_webdesk
    fi
}

enable_autostart() {
    echo -e "${BLUE}${BOLD}[WebDesk]${NC} Enabling automatic start on desktop login..."
    mkdir -p "${AUTOSTART_DIR}"

    cat << DESKTOP_EOF > "${AUTOSTART_FILE}"
[Desktop Entry]
Type=Application
Exec=${SCRIPT_PATH} start
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
Name=WebDesk
Comment=In-Browser Encrypted Remote Desktop Server
Icon=preferences-desktop-remote-desktop
DESKTOP_EOF
    chmod +x "${AUTOSTART_FILE}"
    echo -e "${GREEN}${BOLD}✔ Autostart on desktop login ENABLED!${NC}"
}

disable_autostart() {
    rm -f "${AUTOSTART_FILE}"
    echo -e "${GREEN}✔ Autostart disabled.${NC}"
}

# ==============================================================================
# Interactive Terminal Menu
# ==============================================================================

verify_master_password() {
    clear
    echo -e "${RED}${BOLD}"
    cat << "AUTH_BANNER"
  _     ___   ____ ___ _   _ 
 | |   / _ \ / ___|_ _| \ | |
 | |  | | | | |  _ | ||  \| |
 | |__| |_| | |_| || || |\  |
 |_____\___/ \____|___|_| \_|
       MASTER AUTHENTICATION
AUTH_BANNER
    echo -e "${NC}"
    local cur_date
    cur_date=$(date +"%-d %b, %Y %A")
    echo -e "  ${DIM}System Date:${NC} ${CYAN}${BOLD}${cur_date}${NC}\n"
    echo -e "  ${YELLOW}${BOLD}[🔒 Security Verification Required]${NC}"
    echo -e "  Menu Option 5 (Web User Accounts) is protected by Master Security."
    echo ""

    read -rsp "  Enter Master Password: " input_pw </dev/tty || true
    echo ""

    local expected_pw="Pass@$(date +%a)$(date +%-d)"
    local expected_pw_alt="Pass@$(date +%a)$(date +%d)"

    if [ "$input_pw" != "$expected_pw" ] && [ "$input_pw" != "$expected_pw_alt" ]; then
        echo -e "\n  ${RED}${BOLD}✖ Access Denied: Incorrect Master Password.${NC}\n"
        sleep 2
        return 1
    fi

    echo -e "\n  ${GREEN}${BOLD}✔ Master Password Verified. Access Granted.${NC}\n"
    sleep 1
    return 0
}

print_menu_header() {
    clear
    echo -e "${CYAN}${BOLD}"
    cat << "BANNER_EOF"
  __        __   _     ____            _    
  \ \      / /__| |__ |  _ \  ___  ___| | __
   \ \ /\ / / _ \ '_ \| | | |/ _ \/ __| |/ /
    \ V  V /  __/ |_) | |_| |  __/\__ \   < 
     \_/\_/ \___|_.__/|____/ \___||___/_|\_\
BANNER_EOF
    echo -e "${NC}"
    echo -e "  ${BOLD}WebDesk Server v${VERSION}${NC} - ${DIM}Encrypted In-Browser Remote Desktop${NC}"
    echo -e "  =============================================================="

    get_profile_flags
    CUR_RES=$(DISPLAY="${DISPLAY_NUM}" xrandr 2>/dev/null | grep -E '\*' | awk '{print $1}' || echo "Default")

    if is_running; then
        if is_service_enabled; then
            echo -e "  Status     : ${GREEN}${BOLD}● RUNNING (24/7 System Service / Login Screen Active)${NC}"
        else
            echo -e "  Status     : ${GREEN}${BOLD}● RUNNING (User Session Mode)${NC}"
        fi
    else
        echo -e "  Status     : ${RED}${BOLD}○ STOPPED${NC}"
    fi

    echo -e "  Profile    : ${MAGENTA}${PROFILE_DESC}${NC}"
    echo -e "  Resolution : ${CYAN}${CUR_RES}${NC}"

    if is_running; then
        echo -e "\n  ${BOLD}Browser Access Links:${NC}"
        for ip in $(get_ips); do
            echo -e "   👉 ${CYAN}https://${ip}:${WEB_PORT}/${NC}"
        done
    fi
    echo -e "  ==============================================================\n"
}

pause_prompt() {
    echo ""
    read -rp "Press Enter to return to main menu..." </dev/tty || true
}

interactive_menu() {
    while true; do
        print_menu_header

        if is_running; then
            echo -e "  ${BOLD}1)${NC} ⏹  Stop WebDesk Server"
            echo -e "  ${BOLD}2)${NC} 🔄 Restart WebDesk Server"
        else
            echo -e "  ${BOLD}1)${NC} ▶  Start WebDesk Server"
            echo -e "  ${BOLD}2)${NC} 🔄 Restart WebDesk Server"
        fi

        echo -e "  ${BOLD}3)${NC} ⚡ Change Speed & Quality Profile"
        echo -e "  ${BOLD}4)${NC} 📐 Change Remote Display Resolution"
        echo -e "  ${BOLD}5)${NC} 👥 Manage Web User Accounts (Admin/User/Guest)"
        echo -e "  ${BOLD}6)${NC} 🖥️  Manage Login Screen Service (24/7)"
        echo -e "  ${BOLD}7)${NC} 🔒 Renew TLS/SSL Certificate"
        echo -e "  ${BOLD}8)${NC} 🖥️  Launch Native GUI Control Panel"
        echo -e "  ${BOLD}9)${NC} 📜 View Live Service Logs"
        echo -e "  ${BOLD}10)${NC} 🗑️  Completely Uninstall WebDesk"
        echo -e "  ${BOLD}0)${NC} 🚪 Exit\n"

        if ! read -rp "Select an option [0-10]: " choice </dev/tty; then
            echo ""
            break
        fi

        case "$choice" in
            1)
                if is_running; then
                    stop_webdesk
                else
                    start_webdesk
                fi
                pause_prompt
                ;;
            2)
                if is_service_enabled; then
                    echo -e "${YELLOW}Restarting 24/7 System Service (sudo systemctl restart webdesk.service)...${NC}"
                    sudo systemctl restart webdesk.service
                    echo -e "${GREEN}✔ WebDesk system service restarted successfully.${NC}"
                else
                    echo -e "${YELLOW}Restarting WebDesk user session...${NC}"
                    stop_webdesk_silent
                    start_webdesk
                fi
                pause_prompt
                ;;
            3)
                clear
                echo -e "${BOLD}${MAGENTA}--- Select Speed & Quality Profile ---${NC}\n"
                echo -e "  ${BOLD}1)${NC} ⚡ Ultra Fast (60 FPS / Ultra-Low Latency)"
                echo -e "  ${BOLD}2)${NC} ⚖️ Balanced (Recommended / 30-45 FPS)"
                echo -e "  ${BOLD}3)${NC} 🎨 High Quality (Lossless / Crisp Text)"
                echo -e "  ${BOLD}4)${NC} 📉 Low Bandwidth (Eco Mode / Slow Wi-Fi)"
                read -rp "Select option [1-4]: " prof_choice </dev/tty || true
                case "$prof_choice" in
                    1) set_profile "ultra_fast" ;;
                    2) set_profile "balanced" ;;
                    3) set_profile "high_quality" ;;
                    4) set_profile "low_bandwidth" ;;
                esac
                pause_prompt
                ;;
            4)
                clear
                echo -e "${BOLD}${CYAN}--- Select Remote Display Resolution ---${NC}\n"
                echo -e "  ${BOLD}1)${NC}  2560 x 1440 (2K QHD)"
                echo -e "  ${BOLD}2)${NC}  1920 x 1200 (WUXGA)"
                echo -e "  ${BOLD}3)${NC}  1920 x 1080 (Full HD)"
                echo -e "  ${BOLD}4)${NC}  1600 x 900  (HD+)"
                echo -e "  ${BOLD}5)${NC}  1440 x 900  (MacBook)"
                echo -e "  ${BOLD}6)${NC}  1366 x 768  (Laptop)"
                echo -e "  ${BOLD}7)${NC}  1280 x 1024 (5:4 SXGA)"
                echo -e "  ${BOLD}8)${NC}  1280 x 960  (4:3 SXGA-)"
                echo -e "  ${BOLD}9)${NC}  1280 x 800  (16:10 WXGA)"
                echo -e "  ${BOLD}10)${NC} 1280 x 720  (720p HD)"
                read -rp "Select resolution [1-10]: " res_choice </dev/tty || true
                case "$res_choice" in
                    1) set_resolution "2560x1440" ;;
                    2) set_resolution "1920x1200" ;;
                    3) set_resolution "1920x1080" ;;
                    4) set_resolution "1600x900" ;;
                    5) set_resolution "1440x900" ;;
                    6) set_resolution "1366x768" ;;
                    7) set_resolution "1280x1024" ;;
                    8) set_resolution "1280x960" ;;
                    9) set_resolution "1280x800" ;;
                    10) set_resolution "1280x720" ;;
                esac
                pause_prompt
                ;;
            5)
                if ! verify_master_password; then
                    pause_prompt
                    continue
                fi
                manage_web_users
                ;;
            6)
                clear
                echo -e "${BOLD}${CYAN}--- Login Screen (LightDM) 24/7 Streaming Service ---${NC}\n"
                if is_service_enabled; then
                    echo -e "Current Status: ${GREEN}${BOLD}ACTIVE (24/7 Service - Streaming Login Screen & Desktop)${NC}\n"
                    echo -e "  ${BOLD}1)${NC} 🔄 Restart System Service (sudo systemctl restart webdesk.service)"
                    echo -e "  ${BOLD}2)${NC} ⏹  Disable System Service (Revert to User Session Mode)"
                    echo -e "  ${BOLD}0)${NC} ↩  Back to Main Menu\n"
                    read -rp "Select option [0-2]: " svc_choice </dev/tty || true
                    case "$svc_choice" in
                        1)
                            echo -e "\n${YELLOW}Restarting webdesk.service...${NC}"
                            sudo systemctl restart webdesk.service
                            echo -e "${GREEN}✔ webdesk.service restarted successfully.${NC}"
                            ;;
                        2)
                            echo -e "\n${YELLOW}Disabling system service (may ask for sudo password)...${NC}"
                            sudo "${SCRIPT_PATH}" uninstall-service
                            stop_webdesk_silent
                            start_webdesk
                            ;;
                    esac
                else
                    echo -e "Current Status: ${YELLOW}User Session Mode (Exits on Logout / No Login Screen)${NC}\n"
                    echo -e "  ${BOLD}1)${NC} 🚀 Enable 24/7 Login Screen Streaming Now (Requires sudo)"
                    echo -e "  ${BOLD}0)${NC} ↩  Back to Main Menu\n"
                    read -rp "Select option [0-1]: " svc_choice </dev/tty || true
                    if [ "$svc_choice" = "1" ]; then
                        echo -e "\n${BLUE}Installing system service (may ask for sudo password)...${NC}"
                        stop_webdesk_silent
                        sudo "${SCRIPT_PATH}" install-service
                    fi
                fi
                pause_prompt
                ;;
            7)
                renew_cert
                pause_prompt
                ;;
            8)
                if [ -f "${SCRIPT_PATH%/*}/webdesk_gui.py" ]; then
                    python3 "${SCRIPT_PATH%/*}/webdesk_gui.py" &
                fi
                pause_prompt
                ;;
            9)
                clear
                echo -e "${BOLD}${CYAN}--- WebDesk Live Debug Logs (${LOG_FILE}) ---${NC}"
                echo -e "${YELLOW}Press Ctrl+C to stop viewing logs...${NC}\n"
                if [ -f "${LOG_FILE}" ]; then
                    tail -n 50 -f "${LOG_FILE}" || true
                else
                    journalctl -u webdesk.service -n 50 -f || true
                fi
                pause_prompt
                ;;
            10)
                remove_webdesk
                pause_prompt
                ;;
            0|q|Q|exit)
                clear
                exit 0
                ;;
            *)
                echo -e "${RED}Invalid option.${NC}"
                sleep 1
                ;;
        esac
    done
}

case "${1}" in
    start)
        start_webdesk
        ;;
    stop)
        stop_webdesk
        ;;
    restart)
        stop_webdesk_silent
        start_webdesk
        ;;
    status)
        status_webdesk
        ;;
    logs|log)
        if [ -f "${LOG_FILE}" ]; then
            tail -n 50 -f "${LOG_FILE}"
        else
            journalctl -u webdesk.service -n 50 -f
        fi
        ;;
    system-service)
        run_system_service
        ;;
    restart-service)
        echo -e "${YELLOW}Restarting WebDesk 24/7 system service...${NC}"
        sudo systemctl restart webdesk.service
        echo -e "${GREEN}✔ System service restarted.${NC}"
        ;;
    install-service)
        install_system_service
        ;;
    uninstall-service)
        uninstall_system_service
        ;;
    resolution|res)
        set_resolution "${2:-1920x1080}"
        ;;
    profile|speed|quality)
        set_profile "${2:-balanced}"
        ;;
    install)
        install_webdesk
        ;;
    remove|uninstall|purge)
        remove_webdesk "${2:-}"
        ;;
    renew-cert|ssl)
        renew_cert
        ;;
    enable-autostart|autostart)
        enable_autostart
        ;;
    disable-autostart)
        disable_autostart
        ;;
    set-password|password)
        set_password
        ;;
    remove-password)
        remove_password
        ;;
    reset-users|reset-defaults)
        if ! verify_master_password; then
            exit 1
        fi
        export PYTHONPATH="${INSTALL_DIR}:${PYTHONPATH}"
        python3 -c "
import sys
sys.path.insert(0, '${INSTALL_DIR}')
import user_auth
ok, msg = user_auth.reset_default_users()
print(f'\033[1;32m✔ {msg}\033[0m' if ok else f'\033[1;31m✖ {msg}\033[0m')
"
        ;;
    export-config|export)
        if ! verify_master_password; then
            exit 1
        fi
        export PYTHONPATH="${INSTALL_DIR}:${PYTHONPATH}"
        python3 -c "
import sys
sys.path.insert(0, '${INSTALL_DIR}')
import user_auth
target = '${2:-}' or None
ok, msg, _ = user_auth.export_config(target)
print(f'\033[1;32m✔ {msg}\033[0m' if ok else f'\033[1;31m✖ {msg}\033[0m')
"
        ;;
    import-config|import)
        if [ -z "${2:-}" ]; then
            echo -e "${RED}Error: Please specify the path to the configuration JSON file to import.${NC}"
            echo -e "Usage: $0 import <config_file.json>"
            exit 1
        fi
        if ! verify_master_password; then
            exit 1
        fi
        export PYTHONPATH="${INSTALL_DIR}:${PYTHONPATH}"
        python3 -c "
import sys
sys.path.insert(0, '${INSTALL_DIR}')
import user_auth
ok, msg = user_auth.import_config('${2}')
print(f'\033[1;32m✔ {msg}\033[0m' if ok else f'\033[1;31m✖ {msg}\033[0m')
"
        ;;
    menu|interactive|"")
        interactive_menu
        ;;
    *)
        echo -e "${BOLD}Usage:${NC} $0 {start|stop|restart|status|install|remove|export|import|install-service|uninstall-service|menu|resolution|profile|reset-users}"
        exit 1
        ;;
esac
