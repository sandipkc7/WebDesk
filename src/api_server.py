#!/usr/bin/env python3
"""
WebDesk REST API Server (Port 6085 HTTPS)
Handles user authentication, password changes, dynamic resolution switching,
remote power actions, special keystrokes forwarding, and file transfers.
"""

import os
import sys
import re
import json
import ssl
import time
import threading
import subprocess
import shutil
import cgi
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler

def get_install_dir():
    if "WEBDESK_INSTALL_DIR" in os.environ and os.path.exists(os.environ["WEBDESK_INSTALL_DIR"]):
        return os.environ["WEBDESK_INSTALL_DIR"]
    candidate = os.path.expanduser("~/.local/share/webdesk")
    if os.path.exists(os.path.join(candidate, "users.json")) or os.path.exists(os.path.join(candidate, "webdesk.pem")):
        return candidate
    try:
        for u in sorted(os.listdir("/home")):
            cand = os.path.join("/home", u, ".local/share/webdesk")
            if os.path.exists(cand):
                return cand
    except Exception:
        pass
    return os.path.expanduser("~/.local/share/webdesk")

INSTALL_DIR = get_install_dir()
sys.path.insert(0, INSTALL_DIR)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import user_auth

PORT = 6085
CERT_PEM = os.path.join(INSTALL_DIR, "webdesk.pem")
CERT_CRT = os.path.join(INSTALL_DIR, "webdesk.crt")
CERT_KEY = os.path.join(INSTALL_DIR, "webdesk.key")

def get_downloads_dir():
    cand = os.path.expanduser("~/Downloads")
    if os.path.exists(cand):
        return cand
    try:
        for u in sorted(os.listdir("/home")):
            d = os.path.join("/home", u, "Downloads")
            if os.path.exists(d):
                return d
    except Exception:
        pass
    return cand

DOWNLOADS_DIR = get_downloads_dir()
CONFIG_FILE = os.path.join(INSTALL_DIR, "config.env")
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

# Security Constants
MAX_UPLOAD_SIZE = 500 * 1024 * 1024  # 500 MB max file upload
MAX_FAILED_LOGINS = 5
LOCKOUT_WINDOW_SECONDS = 300  # 5 minute lockout after 5 consecutive failures
RATE_LIMIT_LOCK = threading.Lock()
FAILED_LOGIN_ATTEMPTS = {}  # ip -> list of timestamps

# Active connected viewers tracking: username -> (last_seen_timestamp, role)
ACTIVE_VIEWERS = {}


def get_active_viewers_list():
    now = time.time()
    stale_users = [u for u, (t, r) in ACTIVE_VIEWERS.items() if now - t > 15]
    for u in stale_users:
        ACTIVE_VIEWERS.pop(u, None)
    return [{"username": u, "role": r} for u, (t, r) in ACTIVE_VIEWERS.items()]


class WebDeskAPIHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress noisy standard request logging
        pass

    def send_cors_headers(self):
        origin = self.headers.get("Origin", "")
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Credentials", "true")
        else:
            self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, PUT, DELETE")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, X-Requested-With, X-Filename")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_cors_headers()
        self.end_headers()

    def send_json(self, status_code: int, data: dict):
        response_bytes = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response_bytes)))
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(response_bytes)

    def get_client_ip(self):
        xff = self.headers.get("X-Forwarded-For", "")
        if xff:
            return xff.split(",")[0].strip()
        xri = self.headers.get("X-Real-IP", "")
        if xri:
            return xri.strip()
        if self.client_address:
            return str(self.client_address[0])
        return "127.0.0.1"

    def get_token_user(self):
        auth_header = self.headers.get("Authorization", "")
        token = ""
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
        if not token:
            # Check query params
            parsed = urllib.parse.urlparse(self.path)
            query = urllib.parse.parse_qs(parsed.query)
            token = query.get("token", [""])[0]

        if not token:
            return None, "Missing session token."

        ok, user_or_err = user_auth.verify_token(token)
        if not ok:
            return None, user_or_err
        return user_or_err, None

    def read_json_body(self):
        content_len = int(self.headers.get("Content-Length", 0))
        if content_len <= 0:
            return {}
        raw_body = self.rfile.read(content_len)
        try:
            return json.loads(raw_body.decode("utf-8"))
        except Exception:
            return {}

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # Health & Status check
        if path in ["/api/status", "/status"]:
            self.send_json(200, {
                "ok": True,
                "success": True,
                "status": "running",
                "version": "2.3.1",
                "api_port": PORT
            })
            return

        # View login audit logs
        if path in ["/api/auth/audit-logs", "/api/audit-logs"]:
            user, err = self.get_token_user()
            if not user or user.get("role") != "admin":
                self.send_json(403, {"ok": False, "success": False, "error": "Unauthorized. Admin required."})
                return
            logs = user_auth.get_login_audit_logs(limit=100)
            self.send_json(200, {"ok": True, "success": True, "logs": logs})
            return

        # Current logged in user info
        if path in ["/api/auth/me", "/api/me"]:
            user, err = self.get_token_user()
            if not user:
                self.send_json(401, {"ok": False, "success": False, "error": err, "code": "SESSION_SUPERSEDED"})
                return
            ACTIVE_VIEWERS[user["username"]] = (time.time(), user.get("role", "user"))
            self.send_json(200, {
                "ok": True,
                "success": True,
                "username": user["username"],
                "role": user["role"],
                "status": user.get("status", "active"),
                "settings": user.get("settings", {}),
                "user": user
            })
            return

        # Heartbeat check
        if path in ["/api/auth/heartbeat", "/api/heartbeat"]:
            user, err = self.get_token_user()
            if not user:
                self.send_json(401, {"ok": False, "success": False, "error": err, "code": "SESSION_SUPERSEDED"})
                return
            ACTIVE_VIEWERS[user["username"]] = (time.time(), user.get("role", "user"))
            self.send_json(200, {"ok": True, "success": True, "status": "active"})
            return

        # Connected viewers count and list
        if path in ["/api/auth/viewers", "/api/viewers"]:
            user, err = self.get_token_user()
            if not user:
                self.send_json(401, {"ok": False, "success": False, "error": err, "code": "SESSION_SUPERSEDED"})
                return
            viewers = get_active_viewers_list()
            self.send_json(200, {
                "ok": True,
                "success": True,
                "count": max(1, len(viewers)),
                "viewers": viewers if viewers else [{"username": "user", "role": "user"}]
            })
            return

        # List all web users (Admin or authenticated user)
        if path in ["/api/auth/users", "/api/users"]:
            user, err = self.get_token_user()
            if not user:
                self.send_json(401, {"ok": False, "success": False, "error": err})
                return
            user_list = user_auth.list_users()
            self.send_json(200, {
                "ok": True,
                "success": True,
                "users": user_list
            })
            return

        # List files in ~/Downloads (Authenticated non-viewer only)
        if path in ["/api/files", "/files"]:
            user, err = self.get_token_user()
            if not user:
                self.send_json(401, {"ok": False, "success": False, "error": err or "Authentication required."})
                return
            if user.get("role") == "viewer":
                self.send_json(403, {"ok": False, "success": False, "error": "Guest accounts cannot access file downloads."})
                return

            file_list = []
            try:
                for fname in sorted(os.listdir(DOWNLOADS_DIR)):
                    fpath = os.path.join(DOWNLOADS_DIR, fname)
                    if os.path.isfile(fpath):
                        stat = os.stat(fpath)
                        file_list.append({
                            "name": fname,
                            "size": stat.st_size,
                            "modified": int(stat.st_mtime)
                        })
            except Exception as e:
                self.send_json(500, {"ok": False, "success": False, "error": str(e)})
                return
            self.send_json(200, {"ok": True, "success": True, "files": file_list})
            return

        # File download handling (Authenticated non-viewer only)
        if path.startswith("/api/download") or path.startswith("/download"):
            user, err = self.get_token_user()
            if not user:
                self.send_json(401, {"ok": False, "success": False, "error": err or "Authentication required."})
                return
            if user.get("role") == "viewer":
                self.send_json(403, {"ok": False, "success": False, "error": "Guest accounts cannot download files."})
                return

            # Check query param ?file= or URL path
            filename = ""
            if "file" in query:
                filename = query["file"][0]
            else:
                filename = path.replace("/api/download/", "").replace("/download/", "").replace("/api/download", "").replace("/download", "")
            
            filename = urllib.parse.unquote(filename).strip("/")
            if not filename:
                self.send_json(400, {"ok": False, "success": False, "error": "Missing filename."})
                return

            safe_filename = os.path.basename(filename)
            filepath = os.path.join(DOWNLOADS_DIR, safe_filename)

            if not os.path.exists(filepath) or not os.path.isfile(filepath):
                self.send_json(404, {"ok": False, "success": False, "error": "File not found."})
                return

            try:
                filesize = os.path.getsize(filepath)
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Disposition", f'attachment; filename="{safe_filename}"')
                self.send_header("Content-Length", str(filesize))
                self.send_cors_headers()
                self.end_headers()
                with open(filepath, "rb") as f:
                    shutil.copyfileobj(f, self.wfile)
            except Exception as e:
                self.send_json(500, {"ok": False, "success": False, "error": str(e)})
            return

        self.send_json(404, {"ok": False, "success": False, "error": "Endpoint not found."})

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # 1. Login endpoint (Rate Limited & Audited)
        if path in ["/api/auth/login", "/api/login"]:
            client_ip = self.get_client_ip()
            now = time.time()

            # Check rate limiting lockout
            with RATE_LIMIT_LOCK:
                recent_fails = [t for t in FAILED_LOGIN_ATTEMPTS.get(client_ip, []) if now - t < LOCKOUT_WINDOW_SECONDS]
                FAILED_LOGIN_ATTEMPTS[client_ip] = recent_fails
                if len(recent_fails) >= MAX_FAILED_LOGINS:
                    retry_wait = int(LOCKOUT_WINDOW_SECONDS - (now - recent_fails[0]))
                    self.send_json(429, {
                        "ok": False,
                        "success": False,
                        "error": f"Too many failed login attempts. Please wait {max(1, retry_wait)}s before retrying.",
                        "code": "RATE_LIMITED"
                    })
                    return

            data = self.read_json_body()
            username = data.get("username", "")
            password = data.get("password", "")
            user_agent = self.headers.get("User-Agent", "")

            ok, user_or_err = user_auth.authenticate(username, password)
            if not ok:
                with RATE_LIMIT_LOCK:
                    if client_ip not in FAILED_LOGIN_ATTEMPTS:
                        FAILED_LOGIN_ATTEMPTS[client_ip] = []
                    FAILED_LOGIN_ATTEMPTS[client_ip].append(time.time())

                user_auth.log_login_event(username, client_ip, status="FAILED", reason=str(user_or_err), user_agent=user_agent)
                self.send_json(401, {"ok": False, "success": False, "error": user_or_err})
                return

            # Clear failed login attempts on successful login
            with RATE_LIMIT_LOCK:
                FAILED_LOGIN_ATTEMPTS.pop(client_ip, None)

            token = user_auth.create_token(username)
            user_auth.log_login_event(username, client_ip, status="SUCCESS", role=user_or_err.get("role", "user"), user_agent=user_agent)
            ACTIVE_VIEWERS[username] = (time.time(), user_or_err.get("role", "user"))
            self.send_json(200, {
                "ok": True,
                "success": True,
                "token": token,
                "username": user_or_err["username"],
                "role": user_or_err["role"],
                "status": user_or_err.get("status", "active"),
                "settings": user_or_err.get("settings", {}),
                "user": user_or_err
            })
            return

        # 2. Heartbeat endpoint
        if path in ["/api/auth/heartbeat", "/api/heartbeat"]:
            user, err = self.get_token_user()
            if not user:
                self.send_json(401, {"ok": False, "success": False, "error": err, "code": "SESSION_SUPERSEDED"})
                return
            ACTIVE_VIEWERS[user["username"]] = (time.time(), user.get("role", "user"))
            self.send_json(200, {"ok": True, "success": True, "status": "active"})
            return

        # 3. Logout endpoint
        if path in ["/api/auth/logout", "/api/logout"]:
            auth_header = self.headers.get("Authorization", "")
            token = auth_header[7:].strip() if auth_header.startswith("Bearer ") else ""
            if token and "." in token:
                try:
                    payload_bytes = bytes.fromhex(token.split(".", 1)[0])
                    payload = json.loads(payload_bytes.decode("utf-8"))
                    uname = payload.get("sub", "")
                    nonce = payload.get("nonce", "")
                    if uname:
                        ACTIVE_VIEWERS.pop(uname, None)
                        user_auth.clear_active_session(uname, nonce)
                except Exception:
                    pass
            self.send_json(200, {"ok": True, "success": True, "message": "Logged out successfully."})
            return

        # 4. Password change endpoint
        if path in ["/api/auth/change-password", "/api/change-password"]:
            user, err = self.get_token_user()
            if not user:
                self.send_json(401, {"ok": False, "success": False, "error": err})
                return
            data = self.read_json_body()
            old_pw = data.get("old_password") or data.get("old_pw", "")
            new_pw = data.get("new_password") or data.get("new_pw", "")
            target_u = data.get("target_user") or data.get("target_username") or user["username"]

            if user["role"] != "admin" and target_u != user["username"]:
                self.send_json(403, {"ok": False, "success": False, "error": "Permission denied."})
                return

            if user["role"] != "admin":
                ok_auth, _ = user_auth.authenticate(user["username"], old_pw)
                if not ok_auth:
                    self.send_json(400, {"ok": False, "success": False, "error": "Incorrect current password."})
                    return

            ok_ch, msg = user_auth.change_password(user["username"], old_pw, target_u, new_pw)
            self.send_json(200 if ok_ch else 400, {
                "ok": ok_ch,
                "success": ok_ch,
                "message": msg,
                "error": msg if not ok_ch else None
            })
            return

        # 5. User Management: Add User
        if path in ["/api/auth/users/add", "/api/users/add"]:
            user, err = self.get_token_user()
            if not user:
                self.send_json(401, {"ok": False, "success": False, "error": err})
                return
            if user.get("role") != "admin":
                self.send_json(403, {"ok": False, "success": False, "error": "Admin privileges required."})
                return
            data = self.read_json_body()
            new_uname = data.get("username", "")
            new_upass = data.get("password", "")
            new_urole = data.get("role", "user")
            ok, msg = user_auth.add_user(user["role"], new_uname, new_upass, new_urole)
            self.send_json(200 if ok else 400, {
                "ok": ok,
                "success": ok,
                "message": msg,
                "error": msg if not ok else None
            })
            return

        # 6. User Management: Suspend User
        if path in ["/api/auth/users/suspend", "/api/users/suspend"]:
            user, err = self.get_token_user()
            if not user:
                self.send_json(401, {"ok": False, "success": False, "error": err})
                return
            if user.get("role") != "admin":
                self.send_json(403, {"ok": False, "success": False, "error": "Admin privileges required."})
                return
            data = self.read_json_body()
            target_u = data.get("username", "")
            ok, msg = user_auth.suspend_user(user["username"], target_u)
            ACTIVE_VIEWERS.pop(target_u, None)
            self.send_json(200 if ok else 400, {
                "ok": ok,
                "success": ok,
                "message": msg,
                "error": msg if not ok else None
            })
            return

        # 7. User Management: Unsuspend User
        if path in ["/api/auth/users/unsuspend", "/api/users/unsuspend"]:
            user, err = self.get_token_user()
            if not user:
                self.send_json(401, {"ok": False, "success": False, "error": err})
                return
            if user.get("role") != "admin":
                self.send_json(403, {"ok": False, "success": False, "error": "Admin privileges required."})
                return
            data = self.read_json_body()
            target_u = data.get("username", "")
            ok, msg = user_auth.unsuspend_user(user["username"], target_u)
            self.send_json(200 if ok else 400, {
                "ok": ok,
                "success": ok,
                "message": msg,
                "error": msg if not ok else None
            })
            return

        # 8. User Management: Kick / Terminate Session
        if path in ["/api/auth/users/kick", "/api/users/kick"]:
            user, err = self.get_token_user()
            if not user:
                self.send_json(401, {"ok": False, "success": False, "error": err})
                return
            if user.get("role") != "admin":
                self.send_json(403, {"ok": False, "success": False, "error": "Admin privileges required."})
                return
            data = self.read_json_body()
            target_u = data.get("username", "")
            ok, msg = user_auth.terminate_user_session(user["username"], target_u)
            ACTIVE_VIEWERS.pop(target_u, None)
            self.send_json(200 if ok else 400, {
                "ok": ok,
                "success": ok,
                "message": msg,
                "error": msg if not ok else None
            })
            return

        # 9. User Management: Delete User
        if path in ["/api/auth/users/delete", "/api/users/delete"]:
            user, err = self.get_token_user()
            if not user:
                self.send_json(401, {"ok": False, "success": False, "error": err})
                return
            if user.get("role") != "admin":
                self.send_json(403, {"ok": False, "success": False, "error": "Admin privileges required."})
                return
            data = self.read_json_body()
            target_u = data.get("username", "")
            ok, msg = user_auth.delete_user(user["username"], "", target_u)
            ACTIVE_VIEWERS.pop(target_u, None)
            self.send_json(200 if ok else 400, {
                "ok": ok,
                "success": ok,
                "message": msg,
                "error": msg if not ok else None
            })
            return

        # 10. Save User Settings
        if path in ["/api/save-settings", "/api/auth/save-settings"]:
            user, err = self.get_token_user()
            if not user:
                self.send_json(401, {"ok": False, "success": False, "error": err})
                return
            data = self.read_json_body()
            settings = data.get("settings", {})
            ok, msg = user_auth.update_user_settings(user["username"], settings)
            self.send_json(200 if ok else 400, {"ok": ok, "success": ok, "message": msg})
            return

        # 11. Profile Switcher (Authenticated non-viewer only)
        if path in ["/api/profile", "/api/set-profile"]:
            user, err = self.get_token_user()
            if not user:
                self.send_json(401, {"ok": False, "success": False, "error": err or "Authentication required."})
                return
            if user.get("role") == "viewer":
                self.send_json(403, {"ok": False, "success": False, "error": "Guest accounts cannot change profiles."})
                return

            data = self.read_json_body()
            prof = str(data.get("profile", "balanced")).strip().lower()
            if prof not in ["ultra_fast", "balanced", "high_quality", "low_bandwidth", "custom"]:
                self.send_json(400, {"ok": False, "success": False, "error": f"Invalid profile: {prof}"})
                return
            try:
                with open(CONFIG_FILE, "w") as f:
                    f.write(f"PROFILE={prof}\n")
            except Exception:
                pass
            self.send_json(200, {"ok": True, "success": True, "profile": prof})
            return

        # 12. Resolution Matching (Authenticated non-viewer only)
        if path in ["/api/set-resolution", "/set-resolution"]:
            user, err = self.get_token_user()
            if not user:
                self.send_json(401, {"ok": False, "success": False, "error": err or "Authentication required."})
                return
            if user.get("role") == "viewer":
                self.send_json(403, {"ok": False, "success": False, "error": "Guest accounts cannot change resolution."})
                return

            data = self.read_json_body()
            res = data.get("resolution") or data.get("mode")
            width = data.get("width")
            height = data.get("height")

            if width and height:
                try:
                    res = f"{int(width)}x{int(height)}"
                except Exception:
                    pass

            if not res or not re.match(r"^\d{3,5}x\d{3,5}$", str(res)):
                self.send_json(400, {"ok": False, "success": False, "error": "Invalid resolution format (expected e.g. 1920x1080)."})
                return

            display = os.environ.get("DISPLAY", ":0")
            env = dict(os.environ, DISPLAY=display)
            try:
                ret = subprocess.run(["xrandr", "-s", res], env=env, capture_output=True, timeout=5)
                if ret.returncode != 0:
                    # Try finding active output and adding mode
                    xrandr_out = subprocess.run(["xrandr"], env=env, capture_output=True, text=True, timeout=5).stdout
                    active_output = "Virtual1"
                    for line in xrandr_out.splitlines():
                        if " connected" in line:
                            active_output = line.split()[0]
                            break
                    subprocess.run(["xrandr", "--output", active_output, "--mode", res], env=env, timeout=5)
                self.send_json(200, {"ok": True, "success": True, "resolution": res, "applied": res})
            except Exception as e:
                self.send_json(500, {"ok": False, "success": False, "error": str(e)})
            return

        # 13. Keystroke Forwarding
        if path in ["/api/key", "/api/send-keys"]:
            user, err = self.get_token_user()
            if not user:
                self.send_json(401, {"ok": False, "success": False, "error": err or "Authentication required."})
                return
            if user.get("role") == "viewer":
                self.send_json(403, {"ok": False, "success": False, "error": "Guest accounts cannot send keystrokes."})
                return

            data = self.read_json_body()
            keys = data.get("combo") or data.get("keys", "")
            if not keys:
                self.send_json(400, {"ok": False, "success": False, "error": "Missing keys/combo parameter."})
                return

            # Locate xdotool binary (system path or standalone VNC_ROOT)
            xdotool_bin = shutil.which("xdotool")
            root_bin = os.path.join(INSTALL_DIR, "root", "usr", "bin", "xdotool")
            if not xdotool_bin and os.path.exists(root_bin):
                xdotool_bin = root_bin

            if not xdotool_bin:
                self.send_json(500, {"ok": False, "success": False, "error": "xdotool binary not found on host."})
                return

            display = os.environ.get("DISPLAY", ":0")
            env = dict(os.environ, DISPLAY=display)
            ld_path = os.path.join(INSTALL_DIR, "root", "usr", "lib", "x86_64-linux-gnu")
            if os.path.exists(ld_path):
                env["LD_LIBRARY_PATH"] = f"{ld_path}:{env.get('LD_LIBRARY_PATH', '')}"

            try:
                subprocess.run([xdotool_bin, "key", keys], env=env, timeout=5)
                self.send_json(200, {"ok": True, "success": True, "keys": keys})
            except Exception as e:
                self.send_json(500, {"ok": False, "success": False, "error": str(e)})
            return

        # 14. Power Actions
        if path in ["/api/power", "/api/auth/power"]:
            user, err = self.get_token_user()
            if not user:
                self.send_json(401, {"ok": False, "success": False, "error": err or "Authentication required."})
                return
            if user.get("role") != "admin":
                self.send_json(403, {"ok": False, "success": False, "error": "Administrative permissions required for power actions."})
                return

            data = self.read_json_body()
            action = data.get("action", "").lower()
            display = os.environ.get("DISPLAY", ":0")
            env = dict(os.environ, DISPLAY=display)

            try:
                if action == "lock":
                    subprocess.Popen(["xdg-screensaver", "lock"], env=env)
                elif action in ["switch-user", "switch_user", "switchuser"]:
                    if shutil.which("dm-tool"):
                        subprocess.Popen(["dm-tool", "switch-to-greeter"])
                    elif shutil.which("gdmflexiserver"):
                        subprocess.Popen(["gdmflexiserver"])
                    else:
                        subprocess.Popen(["loginctl", "lock-session"])
                elif action == "logout":
                    subprocess.Popen(["loginctl", "terminate-user", os.environ.get("USER", "sandeep")])
                elif action == "suspend":
                    subprocess.Popen(["systemctl", "suspend"])
                elif action == "reboot":
                    subprocess.Popen(["systemctl", "reboot"])
                elif action == "poweroff":
                    subprocess.Popen(["systemctl", "poweroff"])
                else:
                    self.send_json(400, {"ok": False, "success": False, "error": f"Unknown power action: {action}"})
                    return
                self.send_json(200, {"ok": True, "success": True, "action": action, "message": f"Action '{action}' executed."})
            except Exception as e:
                self.send_json(500, {"ok": False, "success": False, "error": str(e)})
            return

        # 15. File Uploads (Authenticated non-viewer only, chunked & bounded)
        if path in ["/api/upload", "/upload"]:
            user, err = self.get_token_user()
            if not user:
                self.send_json(401, {"ok": False, "success": False, "error": err or "Authentication required."})
                return
            if user.get("role") == "viewer":
                self.send_json(403, {"ok": False, "success": False, "error": "Guest accounts cannot upload files."})
                return

            content_len = int(self.headers.get("Content-Length", 0))
            if content_len <= 0:
                self.send_json(400, {"ok": False, "success": False, "error": "Empty upload payload."})
                return
            if content_len > MAX_UPLOAD_SIZE:
                self.send_json(413, {"ok": False, "success": False, "error": f"Payload exceeds maximum allowed size ({MAX_UPLOAD_SIZE // (1024*1024)}MB)."})
                return

            content_type = self.headers.get("Content-Type", "")
            if not content_type.startswith("multipart/form-data"):
                filename = self.headers.get("X-Filename", "uploaded_file")
                filename = os.path.basename(urllib.parse.unquote(filename))
                if not filename or filename.startswith("."):
                    filename = f"upload_{int(time.time())}"
                filepath = os.path.join(DOWNLOADS_DIR, filename)

                bytes_remaining = content_len
                chunk_size = 64 * 1024
                with open(filepath, "wb") as f:
                    while bytes_remaining > 0:
                        read_size = min(chunk_size, bytes_remaining)
                        chunk = self.rfile.read(read_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        bytes_remaining -= len(chunk)

                self.send_json(200, {"ok": True, "success": True, "filename": filename, "saved_to": filepath})
                return

            form = cgi.FieldStorage(
                fp=self.rfile,
                headers=self.headers,
                environ={
                    "REQUEST_METHOD": "POST",
                    "CONTENT_TYPE": content_type
                }
            )
            saved_files = []
            for field in form.keys():
                item = form[field]
                if item.filename:
                    fname = os.path.basename(item.filename)
                    if not fname or fname.startswith("."):
                        fname = f"upload_{int(time.time())}"
                    fpath = os.path.join(DOWNLOADS_DIR, fname)
                    with open(fpath, "wb") as f:
                        shutil.copyfileobj(item.file, f)
                    saved_files.append(fname)

            self.send_json(200, {"ok": True, "success": True, "saved_files": saved_files})
            return

        self.send_json(404, {"ok": False, "success": False, "error": "Endpoint not found."})


def run_api_server():
    server_address = ("127.0.0.1", PORT)
    httpd = HTTPServer(server_address, WebDeskAPIHandler)

    if os.path.exists(CERT_PEM):
        ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_ctx.load_cert_chain(certfile=CERT_PEM)
        httpd.socket = ssl_ctx.wrap_socket(httpd.socket, server_side=True)
    elif os.path.exists(CERT_CRT) and os.path.exists(CERT_KEY):
        ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_ctx.load_cert_chain(certfile=CERT_CRT, keyfile=CERT_KEY)
        httpd.socket = ssl_ctx.wrap_socket(httpd.socket, server_side=True)

    print(f"[WebDesk API] Listening on https://127.0.0.1:{PORT} (Loopback)...")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    user_auth.ensure_initialized()
    if "-D" in sys.argv:
        # Fork daemon process
        if os.fork() != 0:
            sys.exit(0)
        os.setsid()
        if os.fork() != 0:
            sys.exit(0)
    run_api_server()
