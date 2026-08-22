#!/usr/bin/env bash
# ==============================================================================
# WebDesk - Encrypted In-Browser Desktop Streaming Server for Linux
# Stack: x11vnc + websockify (TLS/SSL) + noVNC + Audio Streamer + ResSync
# Supports: Live Desktop, Login Screen (LightDM), Fullscreen & Mobile
# ==============================================================================

set -eo pipefail

APP_NAME="WebDesk"
VERSION="2.3.1"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_NAME="$(basename "${BASH_SOURCE[0]}")"
SCRIPT_PATH="${SCRIPT_DIR}/${SCRIPT_NAME}"

# Resolve real user and installation directory (works for current user, sudo, and systemd service)
SCRIPT_OWNER=$(stat -c '%U' "${SCRIPT_PATH}" 2>/dev/null || echo "")
if [ -n "${SUDO_USER}" ]; then
    REAL_USER="${SUDO_USER}"
elif [ "${USER}" = "root" ] && [ -n "${SCRIPT_OWNER}" ] && [ "${SCRIPT_OWNER}" != "root" ]; then
    REAL_USER="${SCRIPT_OWNER}"
else
    REAL_USER="${USER:-$SCRIPT_OWNER}"
fi
[ -z "${REAL_USER}" ] && REAL_USER="root"
USER_HOME=$(getent passwd "${REAL_USER}" 2>/dev/null | cut -d: -f6 || echo "${HOME}")
INSTALL_DIR="${USER_HOME}/.local/share/webdesk"

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
    source "${CONFIG_FILE}" 2>/dev/null || true
else
    mkdir -p "${INSTALL_DIR}"
    echo "PROFILE=${DEFAULT_PROFILE}" > "${CONFIG_FILE}"
    PROFILE="${DEFAULT_PROFILE}"
fi

RDP_PORT="${RDP_PORT:-3389}"
RDP_MODE="${RDP_MODE:-1}"
RDP_ENABLED="${RDP_ENABLED:-false}"
RDP_DESKTOP="${RDP_DESKTOP:-auto}"

export LD_LIBRARY_PATH="${VNC_ROOT}/usr/lib/x86_64-linux-gnu:${VNC_ROOT}/usr/lib:${LD_LIBRARY_PATH}"
export PYTHONPATH="${INSTALL_DIR}:${SCRIPT_DIR}:${VNC_ROOT}/usr/lib/python3/dist-packages:${PYTHONPATH}"
export PATH="${VNC_ROOT}/usr/bin:${PATH}"
export WEBDESK_INSTALL_DIR="${INSTALL_DIR}"

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

is_service_installed() {
    [ -f "${SERVICE_FILE}" ] || systemctl is-enabled webdesk.service >/dev/null 2>&1
}

is_service_active() {
    systemctl is-active webdesk.service >/dev/null 2>&1
}

is_service_enabled() {
    is_service_installed
}

ensure_runtime_files() {
    mkdir -p "${INSTALL_DIR}" "${VNC_ROOT}/usr/share/novnc/app/styles"
    local GITHUB_RAW="https://raw.githubusercontent.com/sandipkc7/WebDesk/main"

    # 1. Sync / fetch Python backend modules
    for py_file in user_auth.py api_server.py audio_server.py webdesk_gui.py; do
        if [ -f "${SCRIPT_DIR}/src/${py_file}" ]; then
            cp -u "${SCRIPT_DIR}/src/${py_file}" "${INSTALL_DIR}/" 2>/dev/null || cp "${SCRIPT_DIR}/src/${py_file}" "${INSTALL_DIR}/" 2>/dev/null || true
        elif [ -f "${SCRIPT_DIR}/${py_file}" ]; then
            cp -u "${SCRIPT_DIR}/${py_file}" "${INSTALL_DIR}/" 2>/dev/null || cp "${SCRIPT_DIR}/${py_file}" "${INSTALL_DIR}/" 2>/dev/null || true
        elif [ ! -f "${INSTALL_DIR}/${py_file}" ]; then
            curl -fsSL "${GITHUB_RAW}/src/${py_file}" -o "${INSTALL_DIR}/${py_file}" 2>/dev/null || \
            curl -fsSL "${GITHUB_RAW}/${py_file}" -o "${INSTALL_DIR}/${py_file}" 2>/dev/null || true
        fi
    done

    # 2. Sync / fetch Web Client assets
    if [ -d "${VNC_ROOT}/usr/share/novnc" ]; then
        # vnc.html & index.html
        if [ -f "${SCRIPT_DIR}/src/web/vnc.html" ]; then
            cp -u "${SCRIPT_DIR}/src/web/vnc.html" "${VNC_ROOT}/usr/share/novnc/vnc.html" 2>/dev/null || cp "${SCRIPT_DIR}/src/web/vnc.html" "${VNC_ROOT}/usr/share/novnc/vnc.html" 2>/dev/null || true
            cp "${VNC_ROOT}/usr/share/novnc/vnc.html" "${VNC_ROOT}/usr/share/novnc/index.html" 2>/dev/null || true
        elif [ -f "${SCRIPT_DIR}/vnc.html" ]; then
            cp -u "${SCRIPT_DIR}/vnc.html" "${VNC_ROOT}/usr/share/novnc/vnc.html" 2>/dev/null || cp "${SCRIPT_DIR}/vnc.html" "${VNC_ROOT}/usr/share/novnc/vnc.html" 2>/dev/null || true
            cp "${VNC_ROOT}/usr/share/novnc/vnc.html" "${VNC_ROOT}/usr/share/novnc/index.html" 2>/dev/null || true
        elif [ ! -f "${VNC_ROOT}/usr/share/novnc/vnc.html" ] || ! grep -q "webdesk_hub" "${VNC_ROOT}/usr/share/novnc/vnc.html" 2>/dev/null; then
            curl -fsSL "${GITHUB_RAW}/src/web/vnc.html" -o "${VNC_ROOT}/usr/share/novnc/vnc.html" 2>/dev/null || true
            cp "${VNC_ROOT}/usr/share/novnc/vnc.html" "${VNC_ROOT}/usr/share/novnc/index.html" 2>/dev/null || true
        fi

        # login.html
        if [ -f "${SCRIPT_DIR}/src/web/login.html" ]; then
            cp -u "${SCRIPT_DIR}/src/web/login.html" "${VNC_ROOT}/usr/share/novnc/login.html" 2>/dev/null || cp "${SCRIPT_DIR}/src/web/login.html" "${VNC_ROOT}/usr/share/novnc/login.html" 2>/dev/null || true
        elif [ -f "${SCRIPT_DIR}/login.html" ]; then
            cp -u "${SCRIPT_DIR}/login.html" "${VNC_ROOT}/usr/share/novnc/login.html" 2>/dev/null || cp "${SCRIPT_DIR}/login.html" "${VNC_ROOT}/usr/share/novnc/login.html" 2>/dev/null || true
        elif [ ! -f "${VNC_ROOT}/usr/share/novnc/login.html" ]; then
            curl -fsSL "${GITHUB_RAW}/src/web/login.html" -o "${VNC_ROOT}/usr/share/novnc/login.html" 2>/dev/null || true
        fi

        # webdesk.css
        if [ -f "${SCRIPT_DIR}/src/web/app/styles/webdesk.css" ]; then
            cp -u "${SCRIPT_DIR}/src/web/app/styles/webdesk.css" "${VNC_ROOT}/usr/share/novnc/app/styles/webdesk.css" 2>/dev/null || cp "${SCRIPT_DIR}/src/web/app/styles/webdesk.css" "${VNC_ROOT}/usr/share/novnc/app/styles/webdesk.css" 2>/dev/null || true
        elif [ -f "${SCRIPT_DIR}/app/styles/webdesk.css" ]; then
            cp -u "${SCRIPT_DIR}/app/styles/webdesk.css" "${VNC_ROOT}/usr/share/novnc/app/styles/webdesk.css" 2>/dev/null || cp "${SCRIPT_DIR}/app/styles/webdesk.css" "${VNC_ROOT}/usr/share/novnc/app/styles/webdesk.css" 2>/dev/null || true
        elif [ ! -f "${VNC_ROOT}/usr/share/novnc/app/styles/webdesk.css" ]; then
            curl -fsSL "${GITHUB_RAW}/src/web/app/styles/webdesk.css" -o "${VNC_ROOT}/usr/share/novnc/app/styles/webdesk.css" 2>/dev/null || true
        fi
    fi

    export PYTHONPATH="${INSTALL_DIR}:${SCRIPT_DIR}/src:${SCRIPT_DIR}:${PYTHONPATH}"
    python3 -c "
import sys
sys.path.insert(0, '${INSTALL_DIR}')
sys.path.insert(0, '${SCRIPT_DIR}/src')
sys.path.insert(0, '${SCRIPT_DIR}')
try:
    import user_auth
    user_auth.ensure_initialized()
except Exception:
    pass
" 2>/dev/null || true
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

    ensure_runtime_files
    generate_ssl_cert
    ensure_index_page

    # Master Security Initialization
    echo -e "\n${CYAN}==============================================================${NC}"
    echo -e "  ${BOLD}[🔒 Master Security Setup]${NC}"
    echo -e "  WebDesk protects administrative operations with a Master Password."
    echo -e "  Choose your preferred Master Password mode:\n"
    echo -e "    ${BOLD}1)${NC} ✍️  Set your own Custom Master Password (Recommended)"
    echo -e "    ${BOLD}2)${NC} 🔄 Use Default Dynamic Daily Rule (Pass@<Day><Date>, e.g. Pass@$(date +%a)$(date +%-d))"
    echo -e "${CYAN}==============================================================${NC}"
    read -rp "Select mode [1-2, default 1]: " init_mp_choice </dev/tty || init_mp_choice="1"

    if [ "$init_mp_choice" = "2" ]; then
        python3 -c "
import sys
sys.path.insert(0, '${INSTALL_DIR}')
sys.path.insert(0, '${SCRIPT_DIR}/src')
sys.path.insert(0, '${SCRIPT_DIR}')
import user_auth
user_auth.reset_master_password_to_rule()
" 2>/dev/null || true
        echo -e "${GREEN}✔ Configured with Dynamic Rule (Today's password: Pass@$(date +%a)$(date +%-d))${NC}\n"
    else
        while true; do
            read -rsp "Enter custom Master Password (min 6 characters): " init_pw </dev/tty || true
            echo ""
            if [ ${#init_pw} -lt 6 ]; then
                echo -e "${RED}Password must be at least 6 characters long. Try again.${NC}"
                continue
            fi
            read -rsp "Confirm custom Master Password: " init_pw_conf </dev/tty || true
            echo ""
            if [ "$init_pw" != "$init_pw_conf" ]; then
                echo -e "${RED}Passwords do not match. Try again.${NC}"
                continue
            fi
            python3 -c "
import sys
sys.path.insert(0, sys.argv[1])
sys.path.insert(0, sys.argv[2] + '/src')
sys.path.insert(0, sys.argv[2])
import user_auth
user_auth.set_custom_master_password(sys.argv[3])
" "${INSTALL_DIR}" "${SCRIPT_DIR}" "${init_pw}" 2>/dev/null || true
            echo -e "${GREEN}✔ Custom Master Password saved successfully.${NC}\n"
            break
        done
    fi

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
    if is_service_installed && [ "${1:-}" != "--user-only" ]; then
        echo -e "${BLUE}${BOLD}[WebDesk]${NC} Starting 24/7 systemd background service..."
        if [ "$EUID" -eq 0 ]; then
            systemctl start webdesk.service 2>/dev/null || true
        elif command -v sudo >/dev/null 2>&1; then
            sudo systemctl start webdesk.service 2>/dev/null || true
        fi
        sleep 1.5
        if is_running; then
            echo -e "${GREEN}${BOLD}✔ WebDesk system service is ACTIVE (Encrypted HTTPS / WSS) on port ${WEB_PORT}!${NC}\n"
            echo -e "${BOLD}Access the encrypted desktop in your host PC browser:${NC}"
            for ip in $(get_ips); do
                echo -e "  👉 ${CYAN}https://${ip}:${WEB_PORT}/${NC}"
            done
            echo ""
            return 0
        fi
    fi

    if [ ! -f "${VNC_ROOT}/usr/bin/x11vnc" ] || [ ! -d "${VNC_ROOT}/usr/share/novnc" ]; then
        echo -e "${YELLOW}[WebDesk] Required binaries not found. Triggering automated install...${NC}"
        install_webdesk
    fi

    ensure_runtime_files

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
    DISP_INFO=$(get_active_display_and_auth)
    DETECTED_DISP=$(echo "$DISP_INFO" | cut -d'|' -f1)
    DETECTED_AUTH=$(echo "$DISP_INFO" | cut -d'|' -f2)
    [ -n "$DETECTED_DISP" ] && DISPLAY_NUM="${DISPLAY:-$DETECTED_DISP}"

    AUTH_FLAG=""
    if [ -n "$DETECTED_AUTH" ] && [ -r "$DETECTED_AUTH" ]; then
        AUTH_FLAG="-auth ${DETECTED_AUTH}"
    else
        AUTH_FLAG="-auth guess"
    fi

    # shellcheck disable=SC2086
    "${VNC_ROOT}/usr/bin/x11vnc" \
        -display "${DISPLAY_NUM}" \
        ${AUTH_FLAG} \
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

get_active_display_and_auth() {
    local active_disp=""
    local active_auth=""
    local active_vt=""

    # 1. Read active console VT (e.g. tty7, tty8) from sysfs
    if [ -r "/sys/class/tty/tty0/active" ]; then
        active_vt=$(cat /sys/class/tty/tty0/active 2>/dev/null || true)
    fi

    # 2. Check systemd-logind active session on seat0
    if command -v loginctl >/dev/null 2>&1; then
        local active_session
        active_session=$(loginctl show-seat seat0 -p ActiveSession --value 2>/dev/null || true)
        if [ -n "$active_session" ]; then
            active_disp=$(loginctl show-session "$active_session" -p Display --value 2>/dev/null || true)
            if [ -z "$active_vt" ]; then
                local vtnr
                vtnr=$(loginctl show-session "$active_session" -p VTNr --value 2>/dev/null || true)
                [ -n "$vtnr" ] && active_vt="tty${vtnr}"
            fi
        fi
    fi

    # 3. Match running Xorg process with the active VT or display
    local xorg_match=""
    if [ -n "$active_vt" ]; then
        xorg_match=$(ps -eo pid,args | grep -E '[X]org|[X] ' | grep -w "$active_vt" | head -n 1 || true)
        if [ -z "$xorg_match" ]; then
            xorg_match=$(ps -eo pid,args | grep -E '[X]org|[X] ' | grep "$active_vt" | head -n 1 || true)
        fi
    fi
    if [ -z "$xorg_match" ] && [ -n "$active_disp" ]; then
        xorg_match=$(ps -eo pid,args | grep -E '[X]org|[X] ' | grep -w "$active_disp" | head -n 1 || true)
    fi
    if [ -z "$xorg_match" ]; then
        xorg_match=$(ps -eo pid,args | grep -E '[X]org|[X] ' | grep -v 'grep' | tail -n 1 || true)
    fi

    if [ -n "$xorg_match" ]; then
        [ -z "$active_disp" ] && active_disp=$(echo "$xorg_match" | grep -oP ':\d+' | head -n 1 || echo ":0")
        active_auth=$(echo "$xorg_match" | grep -oP '(?<=-auth\s)\S+' || echo "")
    fi

    [ -z "$active_disp" ] && active_disp=":0"

    # 4. Fallback auth file locations
    if [ -z "$active_auth" ] || [ ! -r "$active_auth" ]; then
        if [ -r "/var/run/lightdm/root/${active_disp}" ]; then
            active_auth="/var/run/lightdm/root/${active_disp}"
        elif [ -r "/run/lightdm/root/${active_disp}" ]; then
            active_auth="/run/lightdm/root/${active_disp}"
        elif [ -r "/run/lightdm/${REAL_USER}/xauthority" ]; then
            active_auth="/run/lightdm/${REAL_USER}/xauthority"
        elif [ -r "${USER_HOME}/.Xauthority" ]; then
            active_auth="${USER_HOME}/.Xauthority"
        fi
    fi

    echo "${active_disp}|${active_auth}"
}

# System-level 24/7 service (Handles Display Manager / LightDM login screen, switch-user & user sessions)
run_system_service() {
    export WEBDESK_INSTALL_DIR="${INSTALL_DIR}"
    export HOME="${USER_HOME}"
    export LD_LIBRARY_PATH="${VNC_ROOT}/usr/lib/x86_64-linux-gnu:${VNC_ROOT}/usr/lib:${LD_LIBRARY_PATH}"
    export PYTHONPATH="${INSTALL_DIR}:${SCRIPT_DIR}:${VNC_ROOT}/usr/lib/python3/dist-packages:${PYTHONPATH}"
    export PATH="${VNC_ROOT}/usr/bin:${PATH}"

    mkdir -p "${INSTALL_DIR}"
    touch "${LOG_FILE}"
    chmod 666 "${LOG_FILE}" 2>/dev/null || true

    log_msg "=========================================================="
    log_msg "=== WebDesk 24/7 System Service Started (PID $$) ==="
    log_msg "=========================================================="

    PASS_OPT="-nopw"
    get_profile_flags
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

    # 3. Dynamic Display & Switch-User Supervisor Loop
    log_msg "Entering Dynamic Display & Authentication Supervisor loop..."
    while true; do
        get_profile_flags
        DISP_INFO=$(get_active_display_and_auth)
        ACTIVE_DISP=$(echo "$DISP_INFO" | cut -d'|' -f1)
        ACTIVE_AUTH=$(echo "$DISP_INFO" | cut -d'|' -f2)

        AUTH_FLAG=""
        if [ -n "$ACTIVE_AUTH" ] && [ -r "$ACTIVE_AUTH" ]; then
            AUTH_FLAG="-auth ${ACTIVE_AUTH}"
            log_msg "Target Display: ${ACTIVE_DISP} (Auth: ${ACTIVE_AUTH})"
        else
            AUTH_FLAG="-auth guess"
            log_msg "Target Display: ${ACTIVE_DISP} (Using -auth guess)"
        fi

        log_msg "Spawning x11vnc backend for display ${ACTIVE_DISP}..."

        # Launch x11vnc in background
        # shellcheck disable=SC2086
        "${VNC_ROOT}/usr/bin/x11vnc" \
            -display "${ACTIVE_DISP}" \
            ${AUTH_FLAG} \
            -forever \
            -shared \
            -listen 127.0.0.1 \
            -rfbport "${VNC_PORT}" \
            ${VNC_TUNING} \
            ${PASS_OPT} >> "${LOG_FILE}" 2>&1 &
        VNC_PID=$!

        # Watch for display/VT switch or process exit
        while kill -0 "$VNC_PID" 2>/dev/null; do
            sleep 1.5
            NEW_DISP_INFO=$(get_active_display_and_auth)
            NEW_DISP=$(echo "$NEW_DISP_INFO" | cut -d'|' -f1)
            NEW_AUTH=$(echo "$NEW_DISP_INFO" | cut -d'|' -f2)

            # If active display or auth changes (e.g. switch user to greeter on :1 or back to :0)
            if [ "$NEW_DISP" != "$ACTIVE_DISP" ] || ([ -n "$NEW_AUTH" ] && [ "$NEW_AUTH" != "$ACTIVE_AUTH" ] && [ -r "$NEW_AUTH" ]); then
                log_msg "Active session/display switched: ${ACTIVE_DISP} -> ${NEW_DISP}. Restarting x11vnc..."
                kill -TERM "$VNC_PID" 2>/dev/null || true
                sleep 0.5
                kill -9 "$VNC_PID" 2>/dev/null || true
                break
            fi
        done

        wait "$VNC_PID" 2>/dev/null || true
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
    if is_service_installed; then
        if [ "$EUID" -eq 0 ]; then
            systemctl stop webdesk.service 2>/dev/null || true
        elif command -v sudo >/dev/null 2>&1; then
            sudo systemctl stop webdesk.service 2>/dev/null || true
        fi
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
        if is_service_installed; then
            if [ "$EUID" -eq 0 ]; then
                systemctl restart webdesk.service 2>/dev/null || true
            elif command -v sudo >/dev/null 2>&1; then
                sudo systemctl restart webdesk.service 2>/dev/null || true
            fi
        else
            stop_webdesk_silent
            start_webdesk
        fi
    fi
}

status_webdesk() {
    get_profile_flags
    CUR_RES=$(DISPLAY="${DISPLAY_NUM}" xrandr 2>/dev/null | grep -E '\*' | awk '{print $1}' || echo "Default")
    if is_running; then
        echo -e "${GREEN}${BOLD}● WebDesk is RUNNING${NC}"
        if is_service_installed; then
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
        if is_rdp_active; then
            local rdp_mode_desc="Mode 1: Live Mirror (:0)"
            [ "${RDP_MODE}" = "2" ] && rdp_mode_desc="Mode 2: Dedicated Virtual Session (${REAL_USER})"
            [ "${RDP_MODE}" = "3" ] && rdp_mode_desc="Mode 3: Multi-User Simultaneous Workstation"
            echo -e "  Windows RDP Port : ${GREEN}${BOLD}${RDP_PORT} (${rdp_mode_desc})${NC}"
        else
            echo -e "  Windows RDP Port : ${DIM}Inactive (Configurable in Admin -> XRDP Menu)${NC}"
        fi
        echo -e "\n${BOLD}Encrypted Browser URLs:${NC}"
        for ip in $(get_ips); do
            echo -e "  👉 ${CYAN}https://${ip}:${WEB_PORT}/${NC}"
        done
        if is_rdp_active; then
            echo -e "\n${BOLD}Windows RDP Connection Endpoint (mstsc.exe):${NC}"
            for ip in $(get_ips); do
                echo -e "  👉 ${MAGENTA}${ip}:${RDP_PORT}${NC}"
            done
        fi
    else
        if is_service_installed; then
            echo -e "${RED}${BOLD}○ WebDesk is STOPPED (24/7 System Service Inactive)${NC}"
        else
            echo -e "${RED}${BOLD}○ WebDesk is STOPPED${NC}"
        fi
    fi
}

manage_web_users() {
    set +e
    ensure_runtime_files
    export PYTHONPATH="${INSTALL_DIR}:${SCRIPT_DIR}/src:${SCRIPT_DIR}:${PYTHONPATH}"

    while true; do
        clear
        echo -e "${BOLD}${CYAN}--- WebDesk Web User Accounts & Access Control ---${NC}\n"
        echo -e "  ${BOLD}1)${NC} 📋 List All Web Users, Roles & Status"
        echo -e "  ${BOLD}2)${NC} ➕ Add New Web User (Admin / User / Guest)"
        echo -e "  ${BOLD}3)${NC} 🔑 Change User Password"
        echo -e "  ${BOLD}4)${NC} ⏸️  Suspend / Unsuspend User Account"
        echo -e "  ${BOLD}5)${NC} ⚡ Terminate Active User Session (Kick)"
        echo -e "  ${BOLD}6)${NC} 🗑️  Delete Web User"
        echo -e "  ${BOLD}0)${NC} ↩  Back to Administration Menu\n"
        read -rp "Select option [0-6]: " u_choice </dev/tty || break

        case "$u_choice" in
            1)
                echo -e "\n${BLUE}${BOLD}[Registered Web Users]${NC}"
                echo -e "  ${BOLD}USERNAME        ROLE            PROFILE / RES          STATUS          CREATED${NC}"
                echo -e "  -----------------------------------------------------------------------------------------------"
                python3 -c "
import sys
sys.path.insert(0, '${INSTALL_DIR}')
sys.path.insert(0, '${SCRIPT_DIR}/src')
sys.path.insert(0, '${SCRIPT_DIR}')
try:
    import user_auth
    user_auth.ensure_initialized()
    users = user_auth.list_users()
    for u in users:
        role_color = '\033[1;36m' if u['role'] == 'admin' else ('\033[1;32m' if u['role'] == 'user' else '\033[1;33m')
        status_color = '\033[1;32m' if u.get('status') == 'active' else '\033[1;31m'
        status_str = u.get('status', 'active')
        st = u.get('settings', {})
        prof_res = f\"{st.get('profile', 'balanced')} | {st.get('resolution', 'auto')}\"
        print(f\"  {u['username']:<15} {role_color}{u['role']:<15}\033[0m \033[1;35m{prof_res:<22}\033[0m {status_color}{status_str:<15}\033[0m {u.get('created_at', '')}\")
except Exception as e:
    print(f'  Error loading user database: {e}')
" 2>&1 || true
                pause_prompt "Press Enter to return to user menu..."
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
sys.path.insert(0, sys.argv[1])
sys.path.insert(0, sys.argv[2] + '/src')
sys.path.insert(0, sys.argv[2])
try:
    import user_auth
    ok, msg = user_auth.add_user('admin', sys.argv[3], sys.argv[4], sys.argv[5])
    print(f'\\n\033[1;32m✔ {msg}\033[0m' if ok else f'\\n\033[1;31m✖ {msg}\033[0m')
except Exception as e:
    print(f'\\n\033[1;31m✖ Error: {e}\033[0m')
" "${INSTALL_DIR}" "${SCRIPT_DIR}" "${new_uname}" "${new_upass}" "${ROLE_STR}" 2>&1 || true
                pause_prompt "Press Enter to return to user menu..."
                ;;
            3)
                echo -e "\n${BLUE}${BOLD}[Change User Password]${NC}"
                read -rp "Enter username to update: " target_uname </dev/tty || true
                read -rsp "Enter new password: " target_upass </dev/tty || true
                echo ""
                python3 -c "
import sys
sys.path.insert(0, sys.argv[1])
sys.path.insert(0, sys.argv[2] + '/src')
sys.path.insert(0, sys.argv[2])
try:
    import user_auth
    ok, msg = user_auth.change_password('admin', 'admin', sys.argv[3], sys.argv[4])
    print(f'\\n\033[1;32m✔ {msg}\033[0m' if ok else f'\\n\033[1;31m✖ {msg}\033[0m')
except Exception as e:
    print(f'\\n\033[1;31m✖ Error: {e}\033[0m')
" "${INSTALL_DIR}" "${SCRIPT_DIR}" "${target_uname}" "${target_upass}" 2>&1 || true
                pause_prompt "Press Enter to return to user menu..."
                ;;
            4)
                echo -e "\n${YELLOW}${BOLD}[Suspend / Unsuspend User Account]${NC}"
                read -rp "Enter username: " susp_uname </dev/tty || true
                echo -e "Action: 1) ⏸️ Suspend (Block login & kick)  2) ▶️ Unsuspend (Reactivate)"
                read -rp "Select action [1-2]: " susp_act </dev/tty || true
                python3 -c "
import sys
sys.path.insert(0, sys.argv[1])
sys.path.insert(0, sys.argv[2] + '/src')
sys.path.insert(0, sys.argv[2])
try:
    import user_auth
    if sys.argv[3] == '1':
        ok, msg = user_auth.suspend_user('admin', sys.argv[4])
    else:
        ok, msg = user_auth.unsuspend_user('admin', sys.argv[4])
    print(f'\\n\033[1;32m✔ {msg}\033[0m' if ok else f'\\n\033[1;31m✖ {msg}\033[0m')
except Exception as e:
    print(f'\\n\033[1;31m✖ Error: {e}\033[0m')
" "${INSTALL_DIR}" "${SCRIPT_DIR}" "${susp_act}" "${susp_uname}" 2>&1 || true
                pause_prompt "Press Enter to return to user menu..."
                ;;
            5)
                echo -e "\n${RED}${BOLD}[Terminate Active User Session (Kick)]${NC}"
                read -rp "Enter username to disconnect: " kick_uname </dev/tty || true
                python3 -c "
import sys
sys.path.insert(0, sys.argv[1])
sys.path.insert(0, sys.argv[2] + '/src')
sys.path.insert(0, sys.argv[2])
try:
    import user_auth
    ok, msg = user_auth.terminate_user_session('admin', sys.argv[3])
    print(f'\\n\033[1;32m✔ {msg}\033[0m' if ok else f'\\n\033[1;31m✖ {msg}\033[0m')
except Exception as e:
    print(f'\\n\033[1;31m✖ Error: {e}\033[0m')
" "${INSTALL_DIR}" "${SCRIPT_DIR}" "${kick_uname}" 2>&1 || true
                pause_prompt "Press Enter to return to user menu..."
                ;;
            6)
                echo -e "\n${RED}${BOLD}[Delete Web User]${NC}"
                read -rp "Enter username to delete: " del_uname </dev/tty || true
                python3 -c "
import sys
sys.path.insert(0, sys.argv[1])
sys.path.insert(0, sys.argv[2] + '/src')
sys.path.insert(0, sys.argv[2])
try:
    import user_auth
    ok, msg = user_auth.delete_user('admin', '', sys.argv[3])
    print(f'\\n\033[1;32m✔ {msg}\033[0m' if ok else f'\\n\033[1;31m✖ {msg}\033[0m')
except Exception as e:
    print(f'\\n\033[1;31m✖ Error: {e}\033[0m')
" "${INSTALL_DIR}" "${SCRIPT_DIR}" "${del_uname}" 2>&1 || true
                pause_prompt "Press Enter to return to user menu..."
                ;;
            0|*)
                break
                ;;
        esac
    done
}

view_login_audit_logs() {
    set +e
    ensure_runtime_files
    export PYTHONPATH="${INSTALL_DIR}:${SCRIPT_DIR}/src:${SCRIPT_DIR}:${PYTHONPATH}"

    while true; do
        clear
        echo -e "${BOLD}${CYAN}--- Client Login & Connected IP Audit Logs ---${NC}\n"
        echo -e "  ${BOLD}TIMESTAMP               STATUS     USERNAME        ROLE       IP ADDRESS          DETAILS${NC}"
        echo -e "  ----------------------------------------------------------------------------------------------------------"
        python3 -c "
import sys
sys.path.insert(0, '${INSTALL_DIR}')
sys.path.insert(0, '${SCRIPT_DIR}/src')
sys.path.insert(0, '${SCRIPT_DIR}')
try:
    import user_auth
    logs = user_auth.get_login_audit_logs(limit=40)
    if not logs:
        print('  \033[2mNo login records found yet.\033[0m')
    for item in reversed(logs):
        status = item.get('status', 'SUCCESS')
        st_color = '\033[1;32m' if status == 'SUCCESS' else '\033[1;31m'
        u_role = item.get('role', '-')
        role_color = '\033[1;36m' if u_role == 'admin' else ('\033[1;32m' if u_role == 'user' else '\033[1;33m')
        ts = item.get('timestamp', '')
        uname = item.get('username', '')
        ip = item.get('ip', '127.0.0.1')
        reason = item.get('reason', '')
        print(f\"  {ts:<23} {st_color}{status:<10}\033[0m {uname:<15} {role_color}{u_role:<10}\033[0m \033[1;37m{ip:<19}\033[0m {reason}\")
except Exception as e:
    print(f'  Error loading audit logs: {e}')
" 2>&1 || true

        echo -e "\n  =========================================================================================================="
        echo -e "  ${BOLD}1)${NC} 🔄 Refresh Logs"
        echo -e "  ${BOLD}2)${NC} 📜 Live Stream Login Logs (tail -f)"
        echo -e "  ${BOLD}3)${NC} 🗑️  Clear Login Audit Logs"
        echo -e "  ${BOLD}0)${NC} ↩  Back to Administration Menu\n"
        read -rp "Select option [0-3]: " log_choice </dev/tty || break

        case "$log_choice" in
            1)
                continue
                ;;
            2)
                clear
                echo -e "${BOLD}${CYAN}--- Live Stream Login Audit Logs ---${NC}"
                echo -e "${YELLOW}Press Ctrl+C to stop stream...${NC}\n"
                local audit_file="${INSTALL_DIR}/login_audit.log"
                touch "${audit_file}"
                tail -n 40 -f "${audit_file}" || true
                pause_prompt "Press Enter to return to audit log menu..."
                ;;
            3)
                read -rp "Are you sure you want to clear all login audit logs? (y/N): " c_confirm </dev/tty || true
                if [[ "$c_confirm" =~ ^[yY]$ ]]; then
                    python3 -c "
import sys
sys.path.insert(0, '${INSTALL_DIR}')
sys.path.insert(0, '${SCRIPT_DIR}/src')
sys.path.insert(0, '${SCRIPT_DIR}')
try:
    import user_auth
    user_auth.clear_login_audit_logs()
    print('\033[1;32m✔ Login audit logs cleared successfully.\033[0m')
except Exception as e:
    print(f'\033[1;31m✖ Error: {e}\033[0m')
" 2>&1 || true
                fi
                pause_prompt "Press Enter to return to audit log menu..."
                ;;
            0|*)
                break
                ;;
        esac
    done
}

configure_master_password() {
    set +e
    ensure_runtime_files
    export PYTHONPATH="${INSTALL_DIR}:${SCRIPT_DIR}/src:${SCRIPT_DIR}:${PYTHONPATH}"

    while true; do
        clear
        local cur_mode
        cur_mode=$(python3 -c "
import sys
sys.path.insert(0, '${INSTALL_DIR}')
sys.path.insert(0, '${SCRIPT_DIR}/src')
sys.path.insert(0, '${SCRIPT_DIR}')
try:
    import user_auth
    cfg = user_auth.get_master_auth_config()
    print(cfg.get('mode', 'dynamic_rule'))
except Exception:
    print('dynamic_rule')
" 2>/dev/null || echo "dynamic_rule")

        echo -e "${BOLD}${CYAN}--- Master Password Configuration ---${NC}\n"
        if [ "$cur_mode" = "custom" ]; then
            echo -e "  Current Mode : ${GREEN}${BOLD}Custom Master Password${NC}"
        else
            local cur_date
            cur_date=$(date +"Pass@%a%-d")
            echo -e "  Current Mode : ${YELLOW}${BOLD}Dynamic Daily Rule (Pass@<Day><Date>)${NC}"
            echo -e "  Today's Pass : ${CYAN}${BOLD}${cur_date}${NC}"
        fi
        echo -e "  ==============================================================\n"
        echo -e "  ${BOLD}1)${NC} ✍️   Set Custom Master Password"
        echo -e "  ${BOLD}2)${NC} 🔄  Revert to Default Dynamic Rule (Pass@<Day><Date>)"
        echo -e "  ${BOLD}3)${NC} ℹ️   View Dynamic Daily Rule Details"
        echo -e "  ${BOLD}0)${NC} ↩   Back to Administration Menu\n"

        read -rp "Select an option [0-3]: " mp_choice </dev/tty || break

        case "$mp_choice" in
            1)
                echo -e "\n${BLUE}${BOLD}[Set Custom Master Password]${NC}"
                read -rsp "Enter new Master Password (min 6 characters): " new_mp </dev/tty || true
                echo ""
                if [ ${#new_mp} -lt 6 ]; then
                    echo -e "${RED}✖ Error: Password must be at least 6 characters long.${NC}"
                    pause_prompt "Press Enter to continue..."
                    continue
                fi
                read -rsp "Confirm new Master Password: " new_mp_confirm </dev/tty || true
                echo ""
                if [ "$new_mp" != "$new_mp_confirm" ]; then
                    echo -e "${RED}✖ Error: Passwords do not match.${NC}"
                    pause_prompt "Press Enter to continue..."
                    continue
                fi

                python3 -c "
import sys
sys.path.insert(0, sys.argv[1])
sys.path.insert(0, sys.argv[2] + '/src')
sys.path.insert(0, sys.argv[2])
try:
    import user_auth
    ok, msg = user_auth.set_custom_master_password(sys.argv[3])
    print(f'\\n\033[1;32m✔ {msg}\033[0m' if ok else f'\\n\033[1;31m✖ {msg}\033[0m')
except Exception as e:
    print(f'\\n\033[1;31m✖ Error: {e}\033[0m')
" "${INSTALL_DIR}" "${SCRIPT_DIR}" "${new_mp}" 2>&1 || true
                pause_prompt "Press Enter to continue..."
                ;;
            2)
                echo -e "\n${YELLOW}${BOLD}[Revert to Default Dynamic Daily Rule]${NC}"
                echo -e "This will set the master password to the standard daily formula:"
                echo -e "  Format: ${BOLD}Pass@<Day><Date>${NC} (e.g. ${CYAN}Pass@$(date +%a)$(date +%-d)${NC})"
                read -rp "Revert to dynamic rule? (y/N): " conf_rule </dev/tty || true
                if [[ "$conf_rule" =~ ^[yY]$ ]]; then
                    python3 -c "
import sys
sys.path.insert(0, '${INSTALL_DIR}')
sys.path.insert(0, '${SCRIPT_DIR}/src')
sys.path.insert(0, '${SCRIPT_DIR}')
try:
    import user_auth
    ok, msg = user_auth.reset_master_password_to_rule()
    print(f'\\n\033[1;32m✔ {msg}\033[0m' if ok else f'\\n\033[1;31m✖ {msg}\033[0m')
except Exception as e:
    print(f'\\n\033[1;31m✖ Error: {e}\033[0m')
" 2>&1 || true
                fi
                pause_prompt "Press Enter to continue..."
                ;;
            3)
                clear
                echo -e "${BOLD}${CYAN}--- Dynamic Master Password Rule Details ---${NC}\n"
                echo -e "The dynamic master password changes automatically each calendar day."
                echo -e "Formula: ${BOLD}Pass@<Day><Date>${NC}\n"
                echo -e "Examples:"
                echo -e "  • Saturday August 22nd -> ${GREEN}${BOLD}Pass@Sat22${NC}"
                echo -e "  • Sunday August 23rd   -> ${GREEN}${BOLD}Pass@Sun23${NC}"
                echo -e "  • Monday August 3rd    -> ${GREEN}${BOLD}Pass@Mon3${NC} (or ${GREEN}${BOLD}Pass@Mon03${NC})"
                echo ""
                echo -e "Today's Active Dynamic Password: ${YELLOW}${BOLD}Pass@$(date +%a)$(date +%-d)${NC}"
                pause_prompt "Press Enter to continue..."
                ;;
            0|*)
                break
                ;;
        esac
    done
}

administration_menu() {
    set +e
    ensure_runtime_files
    if ! verify_master_password; then
        pause_prompt
        return
    fi

    while true; do
        clear
        echo -e "${CYAN}${BOLD}"
        cat << "ADMIN_BANNER"
    _       _           _       _     _             _   _             
   / \   __| |_ __ ___ (_)_ __ (_)___| |_ _ __ __ _| |_(_) ___  _ __  
  / _ \ / _` | '_ ` _ \| | '_ \| / __| __| '__/ _` | __| |/ _ \| '_ \ 
 / ___ \ (_| | | | | | | | | | | \__ \ |_| | | (_| | |_| | (_) | | | |
/_/   \_\__,_|_| |_| |_|_|_| |_|_|___/\__|_|  \__,_|\__|_|\___/|_| |_|
ADMIN_BANNER
        echo -e "${NC}"
        echo -e "  ${BOLD}WebDesk Administration & Security Center${NC} ${DIM}(Master Protected)${NC}"
        echo -e "  ==============================================================\n"
        echo -e "  ${BOLD}1)${NC} 👥 Web User Accounts & Access Control"
        echo -e "  ${BOLD}2)${NC} 📜 Client Login & IP Address Audit Logs"
        echo -e "  ${BOLD}3)${NC} 🔑 Master Password Settings (Custom Password / Dynamic Rule)"
        echo -e "  ${BOLD}4)${NC} 🖥️  Windows Remote Desktop Protocol (XRDP Server)"
        echo -e "  ${BOLD}5)${NC} 🔄 Reset All Web Users to Factory Defaults"
        echo -e "  ${BOLD}6)${NC} 🔒 Renew / Reissue TLS/SSL Certificate"
        echo -e "  ${BOLD}7)${NC} 📤 Export Configuration & User Accounts (.json)"
        echo -e "  ${BOLD}8)${NC} 📥 Import Configuration & User Accounts (.json)"
        echo -e "  ${BOLD}9)${NC} 🗑️  Completely Uninstall WebDesk"
        echo -e "  ${BOLD}0)${NC} ↩  Back to Main Menu\n"

        read -rp "Select an option [0-9]: " adm_choice </dev/tty || break

        case "$adm_choice" in
            1)
                manage_web_users
                ;;
            2)
                view_login_audit_logs
                ;;
            3)
                configure_master_password
                ;;
            4)
                rdp_administration_menu
                ;;
            5)
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
sys.path.insert(0, '${SCRIPT_DIR}/src')
sys.path.insert(0, '${SCRIPT_DIR}')
try:
    import user_auth
    ok, msg = user_auth.reset_default_users()
    print(f'\\n\033[1;32m✔ {msg}\033[0m' if ok else f'\\n\033[1;31m✖ {msg}\033[0m')
except Exception as e:
    print(f'\\n\033[1;31m✖ Error: {e}\033[0m')
" 2>&1 || true
                else
                    echo -e "\n${CYAN}Reset cancelled.${NC}"
                fi
                pause_prompt "Press Enter to return to administration menu..."
                ;;
            6)
                renew_cert
                pause_prompt "Press Enter to return to administration menu..."
                ;;
            7)
                echo -e "\n${BLUE}${BOLD}[Export Full WebDesk Configuration]${NC}"
                default_exp="${USER_HOME}/webdesk_config_backup.json"
                read -rp "Enter destination path [default: ${default_exp}]: " exp_dest </dev/tty || true
                exp_dest="${exp_dest:-$default_exp}"
                python3 -c "
import sys
sys.path.insert(0, sys.argv[1])
sys.path.insert(0, sys.argv[2] + '/src')
sys.path.insert(0, sys.argv[2])
try:
    import user_auth
    ok, msg, _ = user_auth.export_config(sys.argv[3])
    print(f'\\n\033[1;32m✔ {msg}\033[0m' if ok else f'\\n\033[1;31m✖ {msg}\033[0m')
except Exception as e:
    print(f'\\n\033[1;31m✖ Error: {e}\033[0m')
" "${INSTALL_DIR}" "${SCRIPT_DIR}" "${exp_dest}" 2>&1 || true
                pause_prompt "Press Enter to return to administration menu..."
                ;;
            8)
                echo -e "\n${YELLOW}${BOLD}[Import Full WebDesk Configuration]${NC}"
                read -rp "Enter path to configuration JSON file: " imp_src </dev/tty || true
                if [ -n "$imp_src" ]; then
                    python3 -c "
import sys
sys.path.insert(0, sys.argv[1])
sys.path.insert(0, sys.argv[2] + '/src')
sys.path.insert(0, sys.argv[2])
try:
    import user_auth
    ok, msg = user_auth.import_config(sys.argv[3])
    print(f'\\n\033[1;32m✔ {msg}\033[0m' if ok else f'\\n\033[1;31m✖ {msg}\033[0m')
except Exception as e:
    print(f'\\n\033[1;31m✖ Error: {e}\033[0m')
" "${INSTALL_DIR}" "${SCRIPT_DIR}" "${imp_src}" 2>&1 || true
                else
                    echo -e "\n${CYAN}Import cancelled.${NC}"
                fi
                pause_prompt "Press Enter to return to administration menu..."
                ;;
            9)
                remove_webdesk
                pause_prompt "Press Enter to return to administration menu..."
                ;;
            0|*)
                break
                ;;
        esac
    done
}

# ==============================================================================
# Windows Remote Desktop Protocol (XRDP) Module
# ==============================================================================

is_rdp_installed() {
    command -v xrdp >/dev/null 2>&1 && command -v xrdp-sesman >/dev/null 2>&1
}

is_rdp_active() {
    systemctl is-active xrdp >/dev/null 2>&1 || pgrep -x xrdp >/dev/null 2>&1
}

detect_desktop_session() {
    # Check active session first
    if [ -n "$DESKTOP_SESSION" ]; then
        case "$(echo "$DESKTOP_SESSION" | tr '[:upper:]' '[:lower:]')" in
            *mate*) echo "mate-session" ; return ;;
            *cinnamon*) echo "cinnamon-session" ; return ;;
            *xfce*) echo "xfce4-session" ; return ;;
            *lxde*) echo "startlxde" ; return ;;
            *lxqt*) echo "startlxqt" ; return ;;
            *gnome*) echo "gnome-session" ; return ;;
        esac
    fi
    if command -v mate-session >/dev/null 2>&1; then
        echo "mate-session"
    elif command -v cinnamon-session >/dev/null 2>&1; then
        echo "cinnamon-session"
    elif command -v xfce4-session >/dev/null 2>&1; then
        echo "xfce4-session"
    elif command -v startlxde >/dev/null 2>&1; then
        echo "startlxde"
    elif command -v startlxqt >/dev/null 2>&1; then
        echo "startlxqt"
    elif command -v gnome-session >/dev/null 2>&1; then
        echo "gnome-session"
    else
        echo "x-session-manager"
    fi
}

ensure_user_xsession() {
    local target_u="${1:-$REAL_USER}"
    local u_home
    u_home=$(getent passwd "${target_u}" 2>/dev/null | cut -d: -f6 || echo "${USER_HOME}")
    local sess
    sess=$(detect_desktop_session)
    local xdg_desk="MATE"
    local desk_sess="mate"

    case "${sess}" in
        mate-session)
            xdg_desk="MATE"
            desk_sess="mate"
            ;;
        cinnamon-session)
            xdg_desk="X-Cinnamon"
            desk_sess="cinnamon"
            ;;
        xfce4-session)
            xdg_desk="XFCE"
            desk_sess="xfce"
            ;;
        startlxde)
            xdg_desk="LXDE"
            desk_sess="LXDE"
            ;;
        startlxqt)
            xdg_desk="LXQt"
            desk_sess="lxqt"
            ;;
        gnome-session)
            xdg_desk="GNOME"
            desk_sess="gnome"
            ;;
    esac

    if [ -d "${u_home}" ]; then
        cat << EOF > "${u_home}/.xsessionrc"
unset DBUS_SESSION_BUS_ADDRESS
unset XDG_RUNTIME_DIR
export XDG_CURRENT_DESKTOP=${xdg_desk}
export DESKTOP_SESSION=${desk_sess}
EOF
        chmod +x "${u_home}/.xsessionrc"
        chown "${target_u}:${target_u}" "${u_home}/.xsessionrc" 2>/dev/null || true

        cat << EOF > "${u_home}/.xsession"
#!/bin/sh
unset DBUS_SESSION_BUS_ADDRESS
unset XDG_RUNTIME_DIR
export XDG_CURRENT_DESKTOP=${xdg_desk}
export DESKTOP_SESSION=${desk_sess}
exec ${sess}
EOF
        chmod +x "${u_home}/.xsession"
        chown "${target_u}:${target_u}" "${u_home}/.xsession" 2>/dev/null || true
    fi
}

select_rdp_desktop() {
    local target_desk="${1:-}"
    if [ -z "${target_desk}" ]; then
        clear
        echo -e "${BOLD}${CYAN}--- Select RDP Virtual Desktop Environment ---${NC}\n"
        
        local mate_status="[Available]"
        command -v mate-session >/dev/null 2>&1 && mate_status="${GREEN}[Installed]${NC}"
        local xfce_status="[Available]"
        command -v xfce4-session >/dev/null 2>&1 && xfce_status="${GREEN}[Installed]${NC}"
        local cinn_status="[Available]"
        command -v cinnamon-session >/dev/null 2>&1 && cinn_status="${GREEN}[Installed]${NC}"
        local lxde_status="[Available]"
        command -v startlxde >/dev/null 2>&1 && lxde_status="${GREEN}[Installed]${NC}"
        local gnome_status="[Available]"
        command -v gnome-session >/dev/null 2>&1 && gnome_status="${GREEN}[Installed]${NC}"

        echo -e "  ${BOLD}1)${NC} 🧉 MATE Desktop       ${mate_status}"
        echo -e "  ${BOLD}2)${NC} 🐭 XFCE Desktop       ${xfce_status}"
        echo -e "  ${BOLD}3)${NC} 🌿 Cinnamon Desktop   ${cinn_status}"
        echo -e "  ${BOLD}4)${NC} 🪶 LXDE Desktop       ${lxde_status}"
        echo -e "  ${BOLD}5)${NC} 🖥️  GNOME Desktop      ${gnome_status}"
        echo -e "  ${BOLD}6)${NC} 🔍 Auto-Detect Active Session"
        echo -e "  ${BOLD}0)${NC} ↩ Back\n"

        read -rp "Select desktop environment [0-6]: " d_choice </dev/tty || return 0
        case "$d_choice" in
            1) target_desk="mate" ;;
            2) target_desk="xfce" ;;
            3) target_desk="cinnamon" ;;
            4) target_desk="lxde" ;;
            5) target_desk="gnome" ;;
            6) target_desk="auto" ;;
            0|*) return 0 ;;
        esac
    fi

    local sess_cmd="mate-session"
    local xdg_desk="MATE"
    local desk_sess="mate"
    local pkg_name=""

    case "${target_desk}" in
        mate)
            sess_cmd="mate-session"
            xdg_desk="MATE"
            desk_sess="mate"
            pkg_name="mate-desktop-environment-core mate-session-manager"
            ;;
        xfce)
            sess_cmd="xfce4-session"
            xdg_desk="XFCE"
            desk_sess="xfce"
            pkg_name="xfce4 xfce4-goodies"
            ;;
        cinnamon)
            sess_cmd="cinnamon-session"
            xdg_desk="X-Cinnamon"
            desk_sess="cinnamon"
            pkg_name="cinnamon-core"
            ;;
        lxde)
            sess_cmd="startlxde"
            xdg_desk="LXDE"
            desk_sess="LXDE"
            pkg_name="lxde-core"
            ;;
        gnome)
            sess_cmd="gnome-session"
            xdg_desk="GNOME"
            desk_sess="gnome"
            pkg_name="gnome-session"
            ;;
        auto|*)
            sess_cmd=$(detect_desktop_session)
            case "${sess_cmd}" in
                mate-session) xdg_desk="MATE"; desk_sess="mate" ;;
                xfce4-session) xdg_desk="XFCE"; desk_sess="xfce" ;;
                cinnamon-session) xdg_desk="X-Cinnamon"; desk_sess="cinnamon" ;;
                startlxde) xdg_desk="LXDE"; desk_sess="LXDE" ;;
                gnome-session) xdg_desk="GNOME"; desk_sess="gnome" ;;
            esac
            ;;
    esac

    if ! command -v "${sess_cmd}" >/dev/null 2>&1 && [ -n "${pkg_name}" ]; then
        echo -e "\n${YELLOW}[!] '${sess_cmd}' is not currently installed.${NC}"
        read -rp "Would you like to install '${pkg_name}' via apt now? (y/N): " install_now </dev/tty || true
        if [[ "$install_now" =~ ^[yY]$ ]]; then
            echo -e "${BLUE}Installing ${pkg_name}...${NC}"
            if [ "$EUID" -eq 0 ]; then
                apt-get update -qq && apt-get install -y ${pkg_name}
            else
                sudo apt-get update -qq && sudo apt-get install -y ${pkg_name}
            fi
        else
            echo -e "${RED}Desktop environment was not installed. Cancelled.${NC}"
            return 1
        fi
    fi

    local u_home="${USER_HOME}"
    cat << EOF > "${u_home}/.xsessionrc"
unset DBUS_SESSION_BUS_ADDRESS
unset XDG_RUNTIME_DIR
export XDG_CURRENT_DESKTOP=${xdg_desk}
export DESKTOP_SESSION=${desk_sess}
EOF
    chmod +x "${u_home}/.xsessionrc"
    chown "${REAL_USER}:${REAL_USER}" "${u_home}/.xsessionrc" 2>/dev/null || true

    cat << EOF > "${u_home}/.xsession"
#!/bin/sh
unset DBUS_SESSION_BUS_ADDRESS
unset XDG_RUNTIME_DIR
export XDG_CURRENT_DESKTOP=${xdg_desk}
export DESKTOP_SESSION=${desk_sess}
exec ${sess_cmd}
EOF
    chmod +x "${u_home}/.xsession"
    chown "${REAL_USER}:${REAL_USER}" "${u_home}/.xsession" 2>/dev/null || true

    RDP_DESKTOP="${target_desk}"
    save_config_var "RDP_DESKTOP" "${RDP_DESKTOP}"
    echo -e "\n${GREEN}${BOLD}✔ RDP Desktop Environment set to: ${xdg_desk} (${sess_cmd})${NC}"
}

apply_rdp_config() {
    local mode="${1:-$RDP_MODE}"
    local port="${2:-$RDP_PORT}"

    if [ ! -f /etc/xrdp/xrdp.ini ]; then
        return 0
    fi

    echo -e "${YELLOW}Configuring XRDP server for Mode ${mode} on port ${port}...${NC}"

    local cmd="
import re, sys

ini_path = '/etc/xrdp/xrdp.ini'
mode = '${mode}'
port = '${port}'

try:
    with open(ini_path, 'r') as f:
        content = f.read()

    # Update port
    content = re.sub(r'^port=\d+', f'port={port}', content, flags=re.MULTILINE)

    # Trim legacy sections after [Channels]
    channels_idx = content.find('[Channels]')
    if channels_idx != -1:
        next_sec = re.search(r'\n\[(Live-Desktop-Mirror|Xorg|Xvnc|vnc-any|neutrinordp-any)\]', content[channels_idx:])
        if next_sec:
            base_content = content[:channels_idx + next_sec.start() + 1]
        else:
            base_content = content
    else:
        base_content = content

    mirror_block = '''[Live-Desktop-Mirror]
name=Live Desktop Mirror (:0)
lib=libvnc.so
ip=127.0.0.1
port=5900
username=ask
password=ask
pamusername=asksame
pampassword=asksame
pamsessionmng=127.0.0.1
'''

    xorg_block = '''[Xorg]
name=Xorg Virtual Session
lib=libxup.so
username=ask
password=ask
ip=127.0.0.1
port=-1
code=20
'''

    if mode == '1':
        sections = mirror_block + '\n' + xorg_block
    else:
        sections = xorg_block + '\n' + mirror_block

    final_content = base_content.rstrip() + '\n\n' + sections + '\n'

    with open(ini_path, 'w') as f:
        f.write(final_content)
except Exception as e:
    print(f'Error updating xrdp.ini: {e}', file=sys.stderr)
"
    if [ "$EUID" -eq 0 ]; then
        python3 -c "$cmd" 2>/dev/null || true
    else
        sudo python3 -c "$cmd" 2>/dev/null || true
    fi

    RDP_MODE="${mode}"
    RDP_PORT="${port}"
    save_config_var "RDP_MODE" "${RDP_MODE}"
    save_config_var "RDP_PORT" "${RDP_PORT}"
    save_config_var "RDP_ENABLED" "true"
}

save_config_var() {
    local var_name="${1}"
    local var_val="${2}"
    mkdir -p "${INSTALL_DIR}"
    if [ -f "${CONFIG_FILE}" ]; then
        if grep -q "^${var_name}=" "${CONFIG_FILE}"; then
            sed -i "s/^${var_name}=.*/${var_name}=\"${var_val}\"/" "${CONFIG_FILE}"
        else
            echo "${var_name}=\"${var_val}\"" >> "${CONFIG_FILE}"
        fi
    else
        echo "${var_name}=\"${var_val}\"" > "${CONFIG_FILE}"
    fi
}

enable_rdp_server() {
    echo -e "\n${BLUE}${BOLD}[Enable Windows RDP Protocol Server (XRDP)]${NC}"

    if ! is_rdp_installed; then
        echo -e "${YELLOW}--> XRDP server package is not yet installed on host.${NC}"
        echo -e "${YELLOW}--> Installing xrdp and xorgxrdp via apt (sudo password may be required)...${NC}"
        if [ "$EUID" -eq 0 ]; then
            apt-get update -qq && apt-get install -y -qq xrdp xorgxrdp
        else
            sudo apt-get update -qq && sudo apt-get install -y -qq xrdp xorgxrdp
        fi
    fi

    if [ "$EUID" -eq 0 ]; then
        adduser xrdp ssl-cert 2>/dev/null || true
    else
        sudo adduser xrdp ssl-cert 2>/dev/null || true
    fi

    ensure_user_xsession "${REAL_USER}"
    apply_rdp_config "${RDP_MODE}" "${RDP_PORT}"

    echo -e "${YELLOW}--> Enabling and starting xrdp system service...${NC}"
    if [ "$EUID" -eq 0 ]; then
        systemctl enable xrdp --now 2>/dev/null || true
        systemctl restart xrdp 2>/dev/null || true
    else
        sudo systemctl enable xrdp --now 2>/dev/null || true
        sudo systemctl restart xrdp 2>/dev/null || true
    fi

    sleep 1
    if is_rdp_active; then
        echo -e "${GREEN}${BOLD}✔ Windows RDP Server is now ACTIVE on port ${RDP_PORT}!${NC}"
        local rdp_mode_desc="Mode 1: Live Mirror (:0)"
        [ "${RDP_MODE}" = "2" ] && rdp_mode_desc="Mode 2: Dedicated Virtual Session (${REAL_USER})"
        [ "${RDP_MODE}" = "3" ] && rdp_mode_desc="Mode 3: Multi-User Simultaneous Workstation"
        echo -e "  Active Mode : ${CYAN}${rdp_mode_desc}${NC}"
        echo -e "\n${BOLD}Windows Client Connection Instructions:${NC}"
        echo -e "  1. On Windows, press ${CYAN}Win + R${NC}, type ${CYAN}mstsc${NC}, and press Enter."
        for ip in $(get_ips); do
            echo -e "  2. Connect to: ${CYAN}${ip}:${RDP_PORT}${NC}"
        done
        echo -e "  3. Log in with your Linux username (${BOLD}${REAL_USER}${NC}) and your system password."
    else
        echo -e "${RED}[!] Failed to start XRDP. Please check systemctl status xrdp.${NC}"
    fi
}

disable_rdp_server() {
    echo -e "\n${YELLOW}${BOLD}[Disabling Windows RDP Server]${NC}"
    if [ "$EUID" -eq 0 ]; then
        systemctl disable xrdp --now 2>/dev/null || true
    else
        sudo systemctl disable xrdp --now 2>/dev/null || true
    fi
    save_config_var "RDP_ENABLED" "false"
    echo -e "${GREEN}✔ Windows RDP service stopped and disabled.${NC}"
}

set_rdp_mode() {
    local target_mode="${1:-}"
    if [ -z "${target_mode}" ]; then
        clear
        echo -e "${BOLD}${MAGENTA}--- Select Windows RDP Session Mode ---${NC}\n"
        echo -e "  ${BOLD}1)${NC} 🪞 Mode 1: Live Desktop Mirror (:0)"
        echo -e "      ${DIM}View & control the exact same live screen as physical monitor / WebDesk web client.${NC}"
        echo -e "  ${BOLD}2)${NC} 🖥️ Mode 2: Dedicated Virtual Session"
        echo -e "      ${DIM}Independent high-speed virtual desktop session for existing user (${REAL_USER}).${NC}"
        echo -e "  ${BOLD}3)${NC} 👥 Mode 3: Multi-User Simultaneous Workstation"
        echo -e "      ${DIM}Dedicated remote user account so 2 people can work simultaneously on this PC.${NC}"
        echo -e "  ${BOLD}0)${NC} ↩ Back\n"
        read -rp "Select mode [0-3]: " target_mode </dev/tty || return 0
    fi

    case "${target_mode}" in
        1)
            RDP_MODE="1"
            apply_rdp_config "1" "${RDP_PORT}"
            echo -e "\n${GREEN}✔ RDP set to Mode 1: Live Desktop Mirror (:0).${NC}"
            ;;
        2)
            RDP_MODE="2"
            ensure_user_xsession "${REAL_USER}"
            apply_rdp_config "2" "${RDP_PORT}"
            echo -e "\n${GREEN}✔ RDP set to Mode 2: Dedicated Virtual Session (${REAL_USER}).${NC}"
            ;;
        3)
            RDP_MODE="3"
            apply_rdp_config "3" "${RDP_PORT}"
            echo -e "\n${GREEN}✔ RDP set to Mode 3: Multi-User Simultaneous Workstation.${NC}"
            ;;
        0|*)
            return 0
            ;;
    esac

    if is_rdp_active; then
        echo -e "${YELLOW}Restarting XRDP service to apply new mode...${NC}"
        if [ "$EUID" -eq 0 ]; then
            systemctl restart xrdp 2>/dev/null || true
        else
            sudo systemctl restart xrdp 2>/dev/null || true
        fi
        echo -e "${GREEN}✔ XRDP service reloaded.${NC}"
    fi
}

create_rdp_secondary_user() {
    echo -e "\n${BLUE}${BOLD}[Create Secondary Linux User for Multi-User Simultaneous Mode]${NC}"
    echo -e "${DIM}This allows a remote user to connect via Windows RDP simultaneously without interfering with your session.${NC}\n"
    read -rp "Enter new Linux username (e.g. remoteuser): " new_u </dev/tty || return 0
    new_u=$(echo "$new_u" | tr -dc 'a-zA-Z0-9_-')

    if [ -z "$new_u" ]; then
        echo -e "${RED}Invalid username.${NC}"
        return 1
    fi

    if id "$new_u" >/dev/null 2>&1; then
        echo -e "${YELLOW}User '$new_u' already exists on this system.${NC}"
    else
        read -rsp "Enter password for '$new_u': " new_p </dev/tty || return 0
        echo ""
        read -rsp "Confirm password: " new_p2 </dev/tty || return 0
        echo ""

        if [ "$new_p" != "$new_p2" ] || [ -z "$new_p" ]; then
            echo -e "${RED}Passwords do not match or are empty.${NC}"
            return 1
        fi

        echo -e "${YELLOW}Creating user account '$new_u'...${NC}"
        if [ "$EUID" -eq 0 ]; then
            useradd -m -s /bin/bash -G audio,video,plugdev,netdev "${new_u}"
            echo "${new_u}:${new_p}" | chpasswd
        else
            sudo useradd -m -s /bin/bash -G audio,video,plugdev,netdev "${new_u}"
            echo "${new_u}:${new_p}" | sudo chpasswd
        fi
        echo -e "${GREEN}✔ User '$new_u' created successfully.${NC}"
    fi

    ensure_user_xsession "${new_u}"
    echo -e "${GREEN}✔ Desktop session configured for '$new_u'.${NC}"
    echo -e "\n${BOLD}Remote Login Details:${NC}"
    echo -e "  • Username : ${CYAN}${new_u}${NC}"
    echo -e "  • RDP Host : ${CYAN}<IP>:${RDP_PORT}${NC}"
}

show_rdp_status() {
    echo -e "\n${BOLD}${CYAN}--- Windows RDP Protocol Server Status ---${NC}"
    if is_rdp_active; then
        echo -e "  Service Status   : ${GREEN}${BOLD}● ACTIVE & LISTENING${NC}"
        local rdp_mode_desc="Mode 1: Live Mirror (:0)"
        [ "${RDP_MODE}" = "2" ] && rdp_mode_desc="Mode 2: Dedicated Virtual Session (${REAL_USER})"
        [ "${RDP_MODE}" = "3" ] && rdp_mode_desc="Mode 3: Multi-User Simultaneous Workstation"
        echo -e "  Active Mode      : ${MAGENTA}${BOLD}${rdp_mode_desc}${NC}"
        echo -e "  Listening Port   : ${CYAN}${RDP_PORT}${NC}"

        echo -e "\n${BOLD}Active Windows RDP Client Connections:${NC}"
        local conn
        conn=$(ss -tnp "( sport = :${RDP_PORT} )" 2>/dev/null | grep -v "State" || true)
        if [ -n "$conn" ]; then
            echo -e "${GREEN}${conn}${NC}"
        else
            echo -e "  ${DIM}No active client connections at this moment.${NC}"
        fi

        echo -e "\n${BOLD}Active Logged-In User Sessions (loginctl):${NC}"
        loginctl list-sessions 2>/dev/null || true
    else
        if is_rdp_installed; then
            echo -e "  Service Status   : ${RED}○ STOPPED / INACTIVE${NC}"
        else
            echo -e "  Service Status   : ${YELLOW}○ NOT INSTALLED (Run Option 1 to install)${NC}"
        fi
    fi
}

rdp_administration_menu() {
    while true; do
        clear
        echo -e "${BOLD}${MAGENTA}"
        cat << 'RDP_BANNER'
  ____  ____  ____    ____                                 
 |  _ \|  _ \|  _ \  / ___|  ___ _ ____   _____ _ __       
 | |_) | | | | |_) | \___ \ / _ \ '__\ \ / / _ \ '__|      
 |  _ <| |_| |  __/   ___) |  __/ |   \ V /  __/ |         
 |_| \_\____/|_|     |____/ \___|_|    \_/ \___|_|         
RDP_BANNER
        echo -e "${NC}"
        echo -e "  ${BOLD}Windows Remote Desktop Protocol (XRDP) Center${NC}"
        echo -e "  ==============================================================\n"

        if is_rdp_active; then
            local rdp_mode_desc="Mode 1: Live Mirror (:0)"
            [ "${RDP_MODE}" = "2" ] && rdp_mode_desc="Mode 2: Dedicated Virtual Session (${REAL_USER})"
            [ "${RDP_MODE}" = "3" ] && rdp_mode_desc="Mode 3: Multi-User Simultaneous"
            echo -e "  Status: ${GREEN}${BOLD}● ACTIVE${NC} | Port: ${CYAN}${RDP_PORT}${NC} | Mode: ${MAGENTA}${rdp_mode_desc}${NC}\n"
        else
            echo -e "  Status: ${RED}○ INACTIVE / DISABLED${NC}\n"
        fi

        echo -e "  ${BOLD}1)${NC} 🟢 Enable & Start Windows RDP Server (Port ${RDP_PORT})"
        echo -e "  ${BOLD}2)${NC} 🔴 Disable & Stop Windows RDP Server"
        echo -e "  ${BOLD}3)${NC} 🔀 Select RDP Session Mode (Mirror / Virtual / Multi-User)"
        echo -e "  ${BOLD}4)${NC} 🪟 Select Desktop Environment (MATE / XFCE / Cinnamon / LXDE / GNOME)"
        echo -e "  ${BOLD}5)${NC} 👥 Create Secondary Linux User for Simultaneous Mode"
        echo -e "  ${BOLD}6)${NC} ⚙️  Configure RDP Listening Port (Current: ${RDP_PORT})"
        echo -e "  ${BOLD}7)${NC} 📜 View RDP Service & Connected Client Sessions"
        echo -e "  ${BOLD}8)${NC} ℹ️  Windows Connection Walkthrough (mstsc.exe)"
        echo -e "  ${BOLD}0)${NC} ↩  Back to Administration Menu\n"

        read -rp "Select an option [0-8]: " rdp_choice </dev/tty || break

        case "$rdp_choice" in
            1)
                enable_rdp_server
                pause_prompt "Press Enter to return to RDP menu..."
                ;;
            2)
                disable_rdp_server
                pause_prompt "Press Enter to return to RDP menu..."
                ;;
            3)
                set_rdp_mode
                pause_prompt "Press Enter to return to RDP menu..."
                ;;
            4)
                select_rdp_desktop
                pause_prompt "Press Enter to return to RDP menu..."
                ;;
            5)
                create_rdp_secondary_user
                pause_prompt "Press Enter to return to RDP menu..."
                ;;
            6)
                echo -e "\n${BLUE}${BOLD}[Configure RDP Listening Port]${NC}"
                read -rp "Enter port number [default: 3389]: " new_port </dev/tty || true
                new_port="${new_port:-3389}"
                if [[ "$new_port" =~ ^[0-9]+$ ]] && [ "$new_port" -ge 1 ] && [ "$new_port" -le 65535 ]; then
                    RDP_PORT="${new_port}"
                    apply_rdp_config "${RDP_MODE}" "${RDP_PORT}"
                    echo -e "${GREEN}✔ RDP port updated to ${RDP_PORT}.${NC}"
                else
                    echo -e "${RED}Invalid port number.${NC}"
                fi
                pause_prompt "Press Enter to return to RDP menu..."
                ;;
            7)
                show_rdp_status
                pause_prompt "Press Enter to return to RDP menu..."
                ;;
            8)
                clear
                echo -e "${BOLD}${CYAN}--- How to Connect from Windows via RDP ---${NC}\n"
                echo -e "1. On your Windows PC, press ${CYAN}Win + R${NC}, type ${CYAN}mstsc${NC}, and hit ${BOLD}Enter${NC}."
                echo -e "2. In the ${BOLD}Computer${NC} field, enter your Linux IP address and port:"
                for ip in $(get_ips); do
                    echo -e "   👉 ${BOLD}${ip}:${RDP_PORT}${NC}"
                done
                echo -e "\n3. Click ${BOLD}Connect${NC}."
                echo -e "4. When the login screen appears, enter your Linux credentials:"
                echo -e "   • Username: ${BOLD}${REAL_USER}${NC} (or secondary username if Mode 3)"
                echo -e "   • Password: ${BOLD}<Your Linux Password>${NC}"
                echo -e "\n${YELLOW}Mode Behaviors:${NC}"
                echo -e "  • ${BOLD}Mode 1 (Mirror :0)${NC}      : Mirrors live physical desktop screen."
                echo -e "  • ${BOLD}Mode 2 (Virtual)${NC}        : Standalone full-speed virtual desktop."
                echo -e "  • ${BOLD}Mode 3 (Multi-User)${NC}     : Independent simultaneous user workspace."
                echo ""
                pause_prompt "Press Enter to return to RDP menu..."
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

    local cur_mode
    cur_mode=$(python3 -c "
import sys
sys.path.insert(0, '${INSTALL_DIR}')
sys.path.insert(0, '${SCRIPT_DIR}/src')
sys.path.insert(0, '${SCRIPT_DIR}')
try:
    import user_auth
    cfg = user_auth.get_master_auth_config()
    print(cfg.get('mode', 'dynamic_rule'))
except Exception:
    print('dynamic_rule')
" 2>/dev/null || echo "dynamic_rule")

    if [ "$cur_mode" = "custom" ]; then
        echo -e "  ${YELLOW}${BOLD}[🔒 Security Verification Required]${NC}"
        echo -e "  Protected by ${GREEN}${BOLD}Custom Master Password${NC}."
    else
        echo -e "  ${YELLOW}${BOLD}[🔒 Security Verification Required]${NC}"
        echo -e "  Protected by ${YELLOW}${BOLD}Dynamic Daily Master Rule${NC} (Pass@<Day><Date>)."
    fi
    echo ""

    read -rsp "  Enter Master Password: " input_pw </dev/tty || true
    echo ""

    local auth_result
    auth_result=$(python3 -c "
import sys
sys.path.insert(0, sys.argv[1])
sys.path.insert(0, sys.argv[2] + '/src')
sys.path.insert(0, sys.argv[2])
try:
    import user_auth
    ok, mode_or_err = user_auth.verify_master_password(sys.argv[3])
    print('OK' if ok else 'FAIL')
except Exception:
    print('FAIL')
" "${INSTALL_DIR}" "${SCRIPT_DIR}" "${input_pw}" 2>/dev/null || echo "FAIL")

    if [ "$auth_result" != "OK" ]; then
        echo -e "\n  ${RED}${BOLD}✖ Access Denied: Incorrect Master Password.${NC}\n"
        sleep 2
        return 1
    fi

    echo -e "\n  ${GREEN}${BOLD}✔ Master Password Verified. Access Granted.${NC}\n"
    sleep 0.8
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
    local prompt_msg="${1:-Press Enter to return to main menu...}"
    echo ""
    read -rp "${prompt_msg}" </dev/tty || true
}

interactive_menu() {
    set +e
    ensure_runtime_files
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
        echo -e "  ${BOLD}5)${NC} 🛡️  Administration (Master Password Required)"
        echo -e "  ${BOLD}6)${NC} 🖥️  Manage Login Screen Service (24/7)"
        echo -e "  ${BOLD}7)${NC} 🖥️  Launch Native GUI Control Panel"
        echo -e "  ${BOLD}8)${NC} 📜 View Live Service Logs"
        echo -e "  ${BOLD}0)${NC} 🚪 Exit\n"

        if ! read -rp "Select an option [0-8]: " choice </dev/tty; then
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
                if is_service_installed; then
                    echo -e "${YELLOW}Restarting 24/7 System Service (sudo systemctl restart webdesk.service)...${NC}"
                    if [ "$EUID" -eq 0 ]; then
                        systemctl restart webdesk.service 2>/dev/null || true
                    elif command -v sudo >/dev/null 2>&1; then
                        sudo systemctl restart webdesk.service 2>/dev/null || true
                    fi
                    sleep 1.5
                    if is_running; then
                        echo -e "${GREEN}✔ WebDesk system service restarted successfully.${NC}"
                    else
                        echo -e "${RED}[!] Failed to restart service. Check logs in Option 8.${NC}"
                    fi
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
                administration_menu
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
                if [ -f "${SCRIPT_DIR}/webdesk_gui.py" ]; then
                    python3 "${SCRIPT_DIR}/webdesk_gui.py" &
                elif [ -f "${INSTALL_DIR}/webdesk_gui.py" ]; then
                    python3 "${INSTALL_DIR}/webdesk_gui.py" &
                fi
                pause_prompt
                ;;
            8)
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

ensure_runtime_files

case "${1}" in
    start)
        start_webdesk
        ;;
    stop)
        stop_webdesk
        ;;
    restart|restart-service)
        if is_service_installed; then
            echo -e "${YELLOW}Restarting WebDesk 24/7 system service...${NC}"
            if [ "$EUID" -eq 0 ]; then
                systemctl restart webdesk.service 2>/dev/null || true
            elif command -v sudo >/dev/null 2>&1; then
                sudo systemctl restart webdesk.service 2>/dev/null || true
            fi
            sleep 1.5
            if is_running; then
                echo -e "${GREEN}✔ System service restarted successfully.${NC}"
            else
                echo -e "${RED}[!] Failed to restart service. Check logs: ./webdesk.sh logs${NC}"
            fi
        else
            echo -e "${YELLOW}Restarting WebDesk user session...${NC}"
            stop_webdesk_silent
            start_webdesk
        fi
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
    reset-users|reset-defaults)
        if ! verify_master_password; then
            exit 1
        fi
        python3 -c "
import sys
sys.path.insert(0, '${INSTALL_DIR}')
sys.path.insert(0, '${SCRIPT_DIR}')
import user_auth
ok, msg = user_auth.reset_default_users()
print(f'\033[1;32m✔ {msg}\033[0m' if ok else f'\033[1;31m✖ {msg}\033[0m')
"
        ;;
    export-config|export)
        if ! verify_master_password; then
            exit 1
        fi
        python3 -c "
import sys
sys.path.insert(0, sys.argv[1])
sys.path.insert(0, sys.argv[2])
import user_auth
target = sys.argv[3] or None
ok, msg, _ = user_auth.export_config(target)
print(f'\033[1;32m✔ {msg}\033[0m' if ok else f'\033[1;31m✖ {msg}\033[0m')
" "${INSTALL_DIR}" "${SCRIPT_DIR}" "${2:-}"
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
        python3 -c "
import sys
sys.path.insert(0, sys.argv[1])
sys.path.insert(0, sys.argv[2])
import user_auth
ok, msg = user_auth.import_config(sys.argv[3])
print(f'\033[1;32m✔ {msg}\033[0m' if ok else f'\033[1;31m✖ {msg}\033[0m')
" "${INSTALL_DIR}" "${SCRIPT_DIR}" "${2}"
        ;;
    admin|administration)
        administration_menu
        ;;
    audit-logs|audit|login-logs)
        if verify_master_password; then
            view_login_audit_logs
        fi
        ;;
    users|user-accounts)
        if verify_master_password; then
            manage_web_users
        fi
        ;;
    master-password|set-master-password)
        if verify_master_password; then
            configure_master_password
        fi
        ;;
    rdp|rdp-menu)
        if verify_master_password; then
            rdp_administration_menu
        fi
        ;;
    rdp-enable|rdp-start)
        if verify_master_password; then
            enable_rdp_server
        fi
        ;;
    rdp-disable|rdp-stop)
        if verify_master_password; then
            disable_rdp_server
        fi
        ;;
    rdp-restart)
        if verify_master_password; then
            if [ "$EUID" -eq 0 ]; then
                systemctl restart xrdp 2>/dev/null || true
            else
                sudo systemctl restart xrdp 2>/dev/null || true
            fi
            echo -e "${GREEN}✔ XRDP service restarted.${NC}"
        fi
        ;;
    rdp-status)
        show_rdp_status
        ;;
    rdp-mode)
        if verify_master_password; then
            set_rdp_mode "${2:-}"
        fi
        ;;
    rdp-port)
        if verify_master_password; then
            new_port="${2:-3389}"
            apply_rdp_config "${RDP_MODE}" "${new_port}"
            echo -e "${GREEN}✔ RDP port updated to ${new_port}.${NC}"
        fi
        ;;
    rdp-user|rdp-create-user)
        if verify_master_password; then
            create_rdp_secondary_user
        fi
        ;;
    rdp-desktop)
        if verify_master_password; then
            select_rdp_desktop "${2:-}"
        fi
        ;;
    menu|interactive|"")
        interactive_menu
        ;;
    *)
        echo -e "${BOLD}Usage:${NC} $0 {start|stop|restart|status|admin|audit|users|master-password|rdp|rdp-enable|rdp-disable|rdp-status|rdp-mode|rdp-desktop|rdp-port|rdp-user|install|remove|export|import|install-service|uninstall-service|menu|resolution|profile|reset-users}"
        exit 1
        ;;
esac
