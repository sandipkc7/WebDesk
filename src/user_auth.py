#!/usr/bin/env python3
"""
WebDesk User Authentication & RBAC Management Module
Handles PBKDF2 password hashing, salt generation, HMAC-SHA256 session tokens,
user storage (users.json), configuration export/import, and role-based permissions.
"""

import os
import sys
import re
import json
import time
import hmac
import hashlib
import datetime
import secrets

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
USERS_FILE = os.path.join(INSTALL_DIR, "users.json")
SECRET_KEY_FILE = os.path.join(INSTALL_DIR, "secret.key")
REVOKED_TOKENS_FILE = os.path.join(INSTALL_DIR, "revoked_tokens.json")
ACTIVE_SESSIONS_FILE = os.path.join(INSTALL_DIR, "active_sessions.json")
AUDIT_LOG_FILE = os.path.join(INSTALL_DIR, "login_audit.log")
AUDIT_JSON_FILE = os.path.join(INSTALL_DIR, "login_audit.json")
MASTER_AUTH_FILE = os.path.join(INSTALL_DIR, "master_auth.json")
CONFIG_FILE = os.path.join(INSTALL_DIR, "config.env")
THEME_FILE = os.path.join(INSTALL_DIR, "theme_pref.json")

PBKDF2_ITERATIONS = 100000


def get_master_auth_config() -> dict:
    """Loads the master password configuration."""
    ensure_initialized()
    if os.path.exists(MASTER_AUTH_FILE):
        try:
            with open(MASTER_AUTH_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
    return {"mode": "dynamic_rule"}


def save_master_auth_config(config: dict) -> bool:
    """Saves the master password configuration with 0600 permissions."""
    os.makedirs(INSTALL_DIR, exist_ok=True)
    tmp_file = MASTER_AUTH_FILE + ".tmp"
    try:
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        os.chmod(tmp_file, 0o600)
        os.replace(tmp_file, MASTER_AUTH_FILE)
        return True
    except Exception:
        return False


def get_dynamic_rule_passwords() -> list:
    """Returns the valid dynamic master passwords for current day: Pass@<Day><Date>."""
    now = datetime.datetime.now()
    day_str = now.strftime("%a")
    day_num_str = now.strftime("%d")
    day_num_nozero = str(now.day)
    return [
        f"Pass@{day_str}{day_num_str}",
        f"Pass@{day_str}{day_num_nozero}"
    ]


def verify_master_password(password: str) -> tuple:
    """
    Verifies input password against Master Password configuration.
    Returns (True, mode) or (False, error_message).
    """
    if not password:
        return False, "Master password cannot be empty."

    cfg = get_master_auth_config()
    mode = cfg.get("mode", "dynamic_rule")

    if mode == "custom":
        pw_hash = cfg.get("password_hash", "")
        salt_hex = cfg.get("salt", "")
        if not pw_hash or not salt_hex or not verify_password(password, pw_hash, salt_hex):
            return False, "Incorrect Master Password."
        return True, "custom"
    else:
        valid_rules = get_dynamic_rule_passwords()
        if password in valid_rules:
            return True, "dynamic_rule"
        return False, "Incorrect Master Password."


def set_custom_master_password(new_password: str) -> tuple:
    """Sets a custom administrator master password."""
    if not new_password or len(new_password) < 6:
        return False, "Master password must be at least 6 characters long."

    pw_hash, salt_hex = hash_password(new_password)
    cfg = {
        "mode": "custom",
        "password_hash": pw_hash,
        "salt": salt_hex,
        "updated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    }
    if save_master_auth_config(cfg):
        return True, "Custom Master Password configured successfully."
    return False, "Failed to save Master Password configuration."


def reset_master_password_to_rule() -> tuple:
    """Resets master password to the default dynamic rule (Pass@<Day><Date>)."""
    cfg = {
        "mode": "dynamic_rule",
        "updated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    }
    if save_master_auth_config(cfg):
        return True, "Master Password reset to default dynamic daily rule (Pass@<Day><Date>)."
    return False, "Failed to reset Master Password configuration."


def log_login_event(username: str, ip: str, status: str, role: str = "", reason: str = "", user_agent: str = ""):
    """Logs a client login attempt with IP address, timestamp, status, and role."""
    ensure_initialized()
    now_utc = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    now_local = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    log_line = f"[{now_local}] [{status}] User: {username or 'unknown'} ({role or '-'}) | IP: {ip or '127.0.0.1'} | {reason or ''}\n"
    try:
        with open(AUDIT_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_line)
        os.chmod(AUDIT_LOG_FILE, 0o600)
    except Exception:
        pass

    try:
        events = []
        if os.path.exists(AUDIT_JSON_FILE):
            with open(AUDIT_JSON_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    events = data
        events.append({
            "timestamp": now_local,
            "timestamp_utc": now_utc,
            "username": username or "unknown",
            "role": role or "-",
            "ip": ip or "127.0.0.1",
            "status": status,
            "reason": reason or "",
            "user_agent": user_agent or ""
        })
        if len(events) > 500:
            events = events[-500:]
        with open(AUDIT_JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(events, f, indent=2)
        os.chmod(AUDIT_JSON_FILE, 0o600)
    except Exception:
        pass


def get_login_audit_logs(limit: int = 50) -> list:
    """Retrieves the most recent login audit events."""
    ensure_initialized()
    if os.path.exists(AUDIT_JSON_FILE):
        try:
            with open(AUDIT_JSON_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data[-limit:]
        except Exception:
            pass
    return []


def clear_login_audit_logs() -> bool:
    """Clears the login audit history."""
    ensure_initialized()
    try:
        if os.path.exists(AUDIT_LOG_FILE):
            with open(AUDIT_LOG_FILE, "w", encoding="utf-8") as f:
                f.write("")
        if os.path.exists(AUDIT_JSON_FILE):
            with open(AUDIT_JSON_FILE, "w", encoding="utf-8") as f:
                json.dump([], f)
        return True
    except Exception:
        return False


def load_active_sessions() -> dict:
    """Loads active session nonces per user."""
    ensure_initialized()
    if os.path.exists(ACTIVE_SESSIONS_FILE):
        try:
            with open(ACTIVE_SESSIONS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
    return {}


def save_active_sessions(sessions: dict) -> bool:
    """Atomically writes active sessions to active_sessions.json with 0600 permissions."""
    os.makedirs(INSTALL_DIR, exist_ok=True)
    tmp_file = ACTIVE_SESSIONS_FILE + ".tmp"
    try:
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(sessions, f, indent=2)
        os.chmod(tmp_file, 0o600)
        os.replace(tmp_file, ACTIVE_SESSIONS_FILE)
        return True
    except Exception:
        if os.path.exists(tmp_file):
            try:
                os.remove(tmp_file)
            except Exception:
                pass
        return False


def record_active_session(username: str, nonce: str, iat: int):
    """Registers a new active session for a user, superseding any prior sessions."""
    sessions = load_active_sessions()
    sessions[username] = {
        "nonce": nonce,
        "iat": iat,
        "updated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    }
    save_active_sessions(sessions)


def is_session_active(username: str, nonce: str) -> tuple:
    """Checks if the given session nonce is the single active session for the user."""
    sessions = load_active_sessions()
    user_sess = sessions.get(username)
    if not user_sess:
        # If no active session recorded yet, allow it
        return True, None
    current_nonce = user_sess.get("nonce")
    if current_nonce and current_nonce != nonce:
        return False, "A new session was started for your account on another browser. You have been logged out."
    return True, None


def clear_active_session(username: str, nonce: str = None):
    """Clears active session registration for user upon explicit logout or termination."""
    sessions = load_active_sessions()
    if username in sessions:
        if nonce is None or sessions[username].get("nonce") == nonce:
            del sessions[username]
            save_active_sessions(sessions)


def get_secret_key() -> bytes:
    """Retrieves or creates the HMAC secret signing key (0600 permissions)."""
    os.makedirs(INSTALL_DIR, exist_ok=True)
    if os.path.exists(SECRET_KEY_FILE):
        try:
            with open(SECRET_KEY_FILE, "r", encoding="utf-8") as f:
                key_hex = f.read().strip()
                if len(key_hex) >= 32:
                    return bytes.fromhex(key_hex)
        except Exception:
            pass

    key_bytes = secrets.token_bytes(32)
    try:
        with open(SECRET_KEY_FILE, "w", encoding="utf-8") as f:
            f.write(key_bytes.hex())
        os.chmod(SECRET_KEY_FILE, 0o600)
    except Exception:
        pass
    return key_bytes


def hash_password(password: str, salt_hex: str = None) -> tuple:
    """Hashes a password with PBKDF2-HMAC-SHA256 and returns (hash_hex, salt_hex)."""
    if not salt_hex:
        salt_bytes = secrets.token_bytes(16)
        salt_hex = salt_bytes.hex()
    else:
        salt_bytes = bytes.fromhex(salt_hex)
    pwd_hash = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt_bytes,
        PBKDF2_ITERATIONS
    ).hex()
    return pwd_hash, salt_hex


def verify_password(password: str, expected_hash_hex: str, salt_hex: str) -> bool:
    """Verifies a password against the stored PBKDF2 hash and salt."""
    try:
        calc_hash, _ = hash_password(password, salt_hex)
        return hmac.compare_digest(calc_hash, expected_hash_hex)
    except Exception:
        return False


def get_default_users() -> dict:
    """Generates standard default users: admin, user, and guest."""
    now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")

    admin_hash, admin_salt = hash_password("admin123")
    user_hash, user_salt = hash_password("user123")
    guest_hash, guest_salt = hash_password("guest123")

    return {
        "users": {
            "admin": {
                "role": "admin",
                "status": "active",
                "hash": admin_hash,
                "salt": admin_salt,
                "created_at": now_iso,
                "settings": {
                    "profile": "balanced",
                    "quality": 6,
                    "compression": 2,
                    "resolution": "auto",
                    "resize": "scale"
                }
            },
            "user": {
                "role": "user",
                "status": "active",
                "hash": user_hash,
                "salt": user_salt,
                "created_at": now_iso,
                "settings": {
                    "profile": "balanced",
                    "quality": 6,
                    "compression": 2,
                    "resolution": "auto",
                    "resize": "scale"
                }
            },
            "guest": {
                "role": "viewer",
                "status": "active",
                "hash": guest_hash,
                "salt": guest_salt,
                "created_at": now_iso,
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


def ensure_initialized():
    """Ensures users.json, secret.key, and revoked_tokens.json exist."""
    os.makedirs(INSTALL_DIR, exist_ok=True)
    get_secret_key()

    if not os.path.exists(USERS_FILE):
        default_db = get_default_users()
        save_users_db(default_db)

    if not os.path.exists(REVOKED_TOKENS_FILE):
        try:
            with open(REVOKED_TOKENS_FILE, "w", encoding="utf-8") as f:
                json.dump({"revoked_tokens": [], "revoked_users": {}}, f, indent=2)
            os.chmod(REVOKED_TOKENS_FILE, 0o600)
        except Exception:
            pass


def load_users_db() -> dict:
    """Loads users dictionary from users.json, auto-initializing if missing or corrupt."""
    ensure_initialized()
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and "users" in data and isinstance(data["users"], dict):
                    return data
    except Exception:
        pass

    default_db = get_default_users()
    save_users_db(default_db)
    return default_db


def save_users_db(data: dict) -> bool:
    """Atomically writes users database to users.json with 0600 permissions."""
    os.makedirs(INSTALL_DIR, exist_ok=True)
    tmp_file = USERS_FILE + ".tmp"
    try:
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.chmod(tmp_file, 0o600)
        os.replace(tmp_file, USERS_FILE)
        return True
    except Exception as e:
        if os.path.exists(tmp_file):
            try:
                os.remove(tmp_file)
            except Exception:
                pass
        return False


def list_users() -> list:
    """Returns a list of user objects with username, role, status, settings, created_at."""
    db = load_users_db()
    users = db.get("users", {})
    user_list = []
    for uname, udata in users.items():
        entry = {
            "username": uname,
            "role": udata.get("role", "user"),
            "status": udata.get("status", "active"),
            "created_at": udata.get("created_at", "Unknown"),
            "settings": udata.get("settings", {
                "profile": "balanced",
                "quality": 6,
                "compression": 2,
                "resolution": "auto",
                "resize": "scale"
            })
        }
        user_list.append(entry)
    return user_list


def get_user(username: str) -> dict:
    """Retrieves single user record by username."""
    db = load_users_db()
    users = db.get("users", {})
    return users.get(username)


def add_user(caller_role: str, new_uname: str, new_upass: str, new_role: str = "user") -> tuple:
    """Adds a new web user account."""
    new_uname = (new_uname or "").strip()
    new_upass = (new_upass or "").strip()
    new_role = (new_role or "user").strip().lower()

    if new_role not in ["admin", "user", "viewer"]:
        if new_role == "guest":
            new_role = "viewer"
        else:
            new_role = "user"

    if not new_uname or not re.match(r"^[a-zA-Z0-9_\-\.]{2,32}$", new_uname):
        return False, "Username must be 2-32 characters and contain only letters, numbers, hyphens, dots, and underscores."

    if not new_upass or len(new_upass) < 3:
        return False, "Password must be at least 3 characters long."

    db = load_users_db()
    users = db.setdefault("users", {})

    if new_uname in users:
        return False, f"User '{new_uname}' already exists."

    pwd_hash, salt_hex = hash_password(new_upass)
    now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")

    users[new_uname] = {
        "role": new_role,
        "status": "active",
        "hash": pwd_hash,
        "salt": salt_hex,
        "created_at": now_iso,
        "settings": {
            "profile": "balanced",
            "quality": 6,
            "compression": 2,
            "resolution": "auto",
            "resize": "scale"
        }
    }

    if save_users_db(db):
        return True, f"User '{new_uname}' ({new_role}) created successfully."
    return False, "Failed to save user database."


def change_password(caller_user: str, caller_pass: str, target_uname: str, new_upass: str) -> tuple:
    """Changes password for target user."""
    target_uname = (target_uname or "").strip()
    new_upass = (new_upass or "").strip()

    if not new_upass or len(new_upass) < 3:
        return False, "Password must be at least 3 characters long."

    db = load_users_db()
    users = db.get("users", {})

    if target_uname not in users:
        return False, f"User '{target_uname}' not found."

    pwd_hash, salt_hex = hash_password(new_upass)
    users[target_uname]["hash"] = pwd_hash
    users[target_uname]["salt"] = salt_hex

    if save_users_db(db):
        terminate_user_session(caller_user, target_uname)
        return True, f"Password updated for user '{target_uname}'."
    return False, "Failed to save user database."


def suspend_user(caller_user: str, target_uname: str) -> tuple:
    """Suspends user account and revokes active tokens."""
    target_uname = (target_uname or "").strip()
    if target_uname == "admin":
        return False, "Cannot suspend the primary administrator account ('admin')."

    db = load_users_db()
    users = db.get("users", {})

    if target_uname not in users:
        return False, f"User '{target_uname}' not found."

    users[target_uname]["status"] = "suspended"
    if save_users_db(db):
        terminate_user_session(caller_user, target_uname)
        return True, f"User '{target_uname}' has been suspended."
    return False, "Failed to update user database."


def unsuspend_user(caller_user: str, target_uname: str) -> tuple:
    """Reactivates suspended user account."""
    target_uname = (target_uname or "").strip()
    db = load_users_db()
    users = db.get("users", {})

    if target_uname not in users:
        return False, f"User '{target_uname}' not found."

    users[target_uname]["status"] = "active"
    if save_users_db(db):
        return True, f"User '{target_uname}' has been unsuspended (Active)."
    return False, "Failed to update user database."


def delete_user(caller_user: str, caller_pass: str, target_uname: str) -> tuple:
    """Permanently removes user account."""
    target_uname = (target_uname or "").strip()
    if target_uname == "admin":
        return False, "Cannot delete the primary administrator account ('admin')."

    db = load_users_db()
    users = db.get("users", {})

    if target_uname not in users:
        return False, f"User '{target_uname}' not found."

    del users[target_uname]
    if save_users_db(db):
        terminate_user_session(caller_user, target_uname)
        return True, f"User '{target_uname}' has been deleted."
    return False, "Failed to update user database."


def reset_default_users() -> tuple:
    """Restores admin, user, and guest accounts to default factory state."""
    default_db = get_default_users()
    if save_users_db(default_db):
        try:
            with open(REVOKED_TOKENS_FILE, "w", encoding="utf-8") as f:
                json.dump({"revoked_tokens": [], "revoked_users": {}}, f, indent=2)
            os.chmod(REVOKED_TOKENS_FILE, 0o600)
        except Exception:
            pass
        return True, "User database reset to standard factory accounts (admin, user, guest)."
    return False, "Failed to reset user database."


def terminate_user_session(caller_user: str, target_uname: str) -> tuple:
    """Terminates active session by logging revocation timestamp and clearing active session."""
    target_uname = (target_uname or "").strip()
    ensure_initialized()
    clear_active_session(target_uname)
    try:
        rev_data = {"revoked_tokens": [], "revoked_users": {}}
        if os.path.exists(REVOKED_TOKENS_FILE):
            with open(REVOKED_TOKENS_FILE, "r", encoding="utf-8") as f:
                rev_data = json.load(f)
        rev_users = rev_data.setdefault("revoked_users", {})
        rev_users[target_uname] = int(time.time())
        with open(REVOKED_TOKENS_FILE, "w", encoding="utf-8") as f:
            json.dump(rev_data, f, indent=2)
        os.chmod(REVOKED_TOKENS_FILE, 0o600)
        return True, f"Active session tokens terminated for '{target_uname}'."
    except Exception as e:
        return False, f"Failed to revoke sessions: {e}"


def export_config(dest_path: str = None) -> tuple:
    """Exports full configuration (users, config.env, theme) to a portable JSON file."""
    ensure_initialized()
    if not dest_path:
        dest_path = os.path.expanduser("~/webdesk_config_backup.json")
    else:
        dest_path = os.path.expanduser(dest_path)

    db = load_users_db()
    config_env_content = ""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config_env_content = f.read()
        except Exception:
            pass

    theme_content = {}
    if os.path.exists(THEME_FILE):
        try:
            with open(THEME_FILE, "r", encoding="utf-8") as f:
                theme_content = json.load(f)
        except Exception:
            pass

    export_payload = {
        "version": "2.3.1",
        "exported_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "users_db": db,
        "config_env": config_env_content,
        "theme_pref": theme_content,
        "master_auth": get_master_auth_config()
    }

    try:
        parent_dir = os.path.dirname(os.path.abspath(dest_path))
        os.makedirs(parent_dir, exist_ok=True)
        with open(dest_path, "w", encoding="utf-8") as f:
            json.dump(export_payload, f, indent=2)
        return True, f"Configuration successfully exported to '{dest_path}'.", export_payload
    except Exception as e:
        return False, f"Failed to export configuration: {e}", None


def import_config(src_path: str) -> tuple:
    """Imports and applies full configuration from a JSON backup file."""
    src_path = os.path.expanduser(src_path)
    if not os.path.exists(src_path):
        return False, f"File not found: '{src_path}'."

    try:
        with open(src_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return False, f"Failed to parse JSON file: {e}"

    if not isinstance(data, dict) or "users_db" not in data:
        return False, "Invalid configuration format: Missing 'users_db' key."

    users_db = data.get("users_db")
    if not isinstance(users_db, dict) or "users" not in users_db:
        return False, "Invalid users structure in configuration backup."

    if not save_users_db(users_db):
        return False, "Failed to restore user database."

    config_env_content = data.get("config_env", "")
    if config_env_content:
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                f.write(config_env_content)
        except Exception:
            pass

    theme_content = data.get("theme_pref", {})
    if theme_content:
        try:
            with open(THEME_FILE, "w", encoding="utf-8") as f:
                json.dump(theme_content, f, indent=2)
        except Exception:
            pass

    master_auth_content = data.get("master_auth", {})
    if master_auth_content and isinstance(master_auth_content, dict):
        save_master_auth_config(master_auth_content)

    return True, f"Configuration successfully imported and restored from '{src_path}'."


def authenticate(username: str, password: str) -> tuple:
    """Authenticates username & password against database. Returns (ok, user_dict_or_error)."""
    username = (username or "").strip()
    password = (password or "").strip()

    if not username or not password:
        return False, "Username and password are required."

    u = get_user(username)
    if not u:
        return False, "Invalid username or password."

    if u.get("status") == "suspended":
        return False, "Account is currently suspended. Contact administrator."

    stored_hash = u.get("hash", "")
    stored_salt = u.get("salt", "")

    if not verify_password(password, stored_hash, stored_salt):
        return False, "Invalid username or password."

    user_info = {
        "username": username,
        "role": u.get("role", "user"),
        "status": u.get("status", "active"),
        "settings": u.get("settings", {
            "profile": "balanced",
            "quality": 6,
            "compression": 2,
            "resolution": "auto",
            "resize": "scale"
        })
    }
    return True, user_info


def create_token(username: str, expiry_hours: int = 48) -> str:
    """Generates an HMAC-SHA256 signed session token and registers it as the active session."""
    key = get_secret_key()
    iat = int(time.time())
    exp = iat + (expiry_hours * 3600)
    nonce = secrets.token_hex(8)

    # Register as the current active session for this user (invalidating prior sessions)
    record_active_session(username, nonce, iat)

    payload_dict = {
        "sub": username,
        "iat": iat,
        "exp": exp,
        "nonce": nonce
    }
    payload_str = json.dumps(payload_dict, separators=(',', ':'))
    payload_bytes = payload_str.encode('utf-8')
    sig = hmac.new(key, payload_bytes, hashlib.sha256).hexdigest()
    token = f"{payload_bytes.hex()}.{sig}"
    return token


def verify_token(token: str) -> tuple:
    """Verifies HMAC-SHA256 signed token and checks revocation, suspension, and single active session."""
    if not token or "." not in token:
        return False, "Malformed session token."

    key = get_secret_key()
    try:
        payload_hex, sig = token.split(".", 1)
        payload_bytes = bytes.fromhex(payload_hex)
        expected_sig = hmac.new(key, payload_bytes, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return False, "Invalid token signature."

        payload = json.loads(payload_bytes.decode('utf-8'))
        exp = payload.get("exp", 0)
        iat = payload.get("iat", 0)
        username = payload.get("sub", "")
        nonce = payload.get("nonce", "")

        if time.time() > exp:
            return False, "Session token has expired."

        # Check explicit revocation list
        if os.path.exists(REVOKED_TOKENS_FILE):
            try:
                with open(REVOKED_TOKENS_FILE, "r", encoding="utf-8") as f:
                    rev_data = json.load(f)
                    rev_users = rev_data.get("revoked_users", {})
                    if username in rev_users and iat <= rev_users[username]:
                        return False, "Session token was terminated."
            except Exception:
                pass

        # Check single active session enforcement (disable concurrent sessions for same user)
        if nonce:
            is_active, sess_err = is_session_active(username, nonce)
            if not is_active:
                return False, sess_err or "Your account was logged in from another session."

        user = get_user(username)
        if not user:
            return False, "User no longer exists."

        if user.get("status") == "suspended":
            return False, "User account is suspended."

        user_info = {
            "username": username,
            "role": user.get("role", "user"),
            "status": user.get("status", "active"),
            "settings": user.get("settings", {
                "profile": "balanced",
                "quality": 6,
                "compression": 2,
                "resolution": "auto",
                "resize": "scale"
            })
        }
        return True, user_info
    except Exception as e:
        return False, f"Token verification error: {e}"


def update_user_settings(username: str, new_settings: dict) -> tuple:
    """Updates user display/profile settings in users.json."""
    db = load_users_db()
    users = db.get("users", {})
    if username not in users:
        return False, f"User '{username}' not found."

    current_settings = users[username].setdefault("settings", {})
    for k, v in new_settings.items():
        if k in ["profile", "quality", "compression", "resolution", "resize"]:
            current_settings[k] = v

    if save_users_db(db):
        return True, "User preferences updated."
    return False, "Failed to save user preferences."


if __name__ == "__main__":
    ensure_initialized()
    print(f"WebDesk User Database initialized at: {USERS_FILE}")
    for u in list_users():
        print(f" - {u['username']} ({u['role']}, {u['status']})")
