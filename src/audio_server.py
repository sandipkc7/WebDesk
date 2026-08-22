#!/usr/bin/env python3
"""
WebDesk Audio Server (Port 6086 WSS)
Captures PulseAudio/PipeWire monitor audio and streams low-latency PCM over WebSocket.
"""

import os
import sys
import ssl
import socket
import struct
import hashlib
import base64
import threading
import subprocess
import time

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
PORT = 6086
CERT_PEM = os.path.join(INSTALL_DIR, "webdesk.pem")
CERT_CRT = os.path.join(INSTALL_DIR, "webdesk.crt")
CERT_KEY = os.path.join(INSTALL_DIR, "webdesk.key")

clients = []
clients_lock = threading.Lock()


def build_ws_frame(payload: bytes, binary: bool = True) -> bytes:
    """Encodes raw binary/text payload into a WebSocket frame."""
    b1 = 0x82 if binary else 0x81  # FIN + binary / text opcode
    length = len(payload)
    if length < 126:
        header = struct.pack("!BB", b1, length)
    elif length <= 0xFFFF:
        header = struct.pack("!BBH", b1, 126, length)
    else:
        header = struct.pack("!BBQ", b1, 127, length)
    return header + payload


def handle_client(conn, addr):
    try:
        data = conn.recv(4096).decode('utf-8', errors='ignore')
        headers = {}
        for line in data.split('\r\n')[1:]:
            if ': ' in line:
                k, v = line.split(': ', 1)
                headers[k.lower()] = v.strip()

        ws_key = headers.get('sec-websocket-key')
        if not ws_key:
            conn.close()
            return

        guid = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
        accept_raw = hashlib.sha1((ws_key + guid).encode('utf-8')).digest()
        accept_key = base64.b64encode(accept_raw).decode('utf-8')

        handshake = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept_key}\r\n\r\n"
        )
        conn.sendall(handshake.encode('utf-8'))

        with clients_lock:
            clients.append(conn)

        # Keep reading to detect disconnection
        while True:
            msg = conn.recv(1024)
            if not msg:
                break
    except Exception:
        pass
    finally:
        with clients_lock:
            if conn in clients:
                clients.remove(conn)
        try:
            conn.close()
        except Exception:
            pass


def broadcast_audio(chunk: bytes):
    frame = build_ws_frame(chunk, binary=True)
    with clients_lock:
        dead_clients = []
        for client in clients:
            try:
                client.sendall(frame)
            except Exception:
                dead_clients.append(client)
        for d in dead_clients:
            if d in clients:
                clients.remove(d)


def capture_loop():
    """Runs parec/pw-record subprocess to grab monitor audio."""
    while True:
        with clients_lock:
            has_clients = len(clients) > 0

        if not has_clients:
            time.sleep(0.5)
            continue

        cmd = ["parec", "--format=s16le", "--rate=44100", "--channels=2", "--latency=50"]
        if not shutil_which("parec"):
            cmd = ["pw-record", "--format=s16le", "--rate=44100", "--channels=2", "-"]

        proc = None
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            while True:
                with clients_lock:
                    if len(clients) == 0:
                        break
                data = proc.stdout.read(4096)
                if not data:
                    break
                broadcast_audio(data)
        except Exception:
            time.sleep(1)
        finally:
            if proc:
                try:
                    proc.kill()
                except Exception:
                    pass
            time.sleep(0.5)


def shutil_which(cmd):
    return subprocess.run(["which", cmd], capture_output=True).returncode == 0


def run_audio_server():
    t = threading.Thread(target=capture_loop, daemon=True)
    t.start()

    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(("0.0.0.0", PORT))
    server_sock.listen(10)

    if os.path.exists(CERT_PEM):
        ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_ctx.load_cert_chain(certfile=CERT_PEM)
        server_sock = ssl_ctx.wrap_socket(server_sock, server_side=True)
    elif os.path.exists(CERT_CRT) and os.path.exists(CERT_KEY):
        ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_ctx.load_cert_chain(certfile=CERT_CRT, keyfile=CERT_KEY)
        server_sock = ssl_ctx.wrap_socket(server_sock, server_side=True)

    print(f"[WebDesk Audio] Listening on wss://0.0.0.0:{PORT}...")
    while True:
        try:
            conn, addr = server_sock.accept()
            c_thread = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            c_thread.start()
        except Exception:
            break


if __name__ == "__main__":
    if "-D" in sys.argv:
        if os.fork() != 0:
            sys.exit(0)
        os.setsid()
        if os.fork() != 0:
            sys.exit(0)
    run_audio_server()
