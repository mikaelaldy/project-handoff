"""Vercel serverless: simple judge authentication.

POST /api/auth  — body {"password": "..."} → returns {"token": "..."}
GET  /api/auth  — header Authorization: Bearer <token> → {"ok": true}

Token = HMAC-SHA256(timestamp, JUDGE_SECRET) valid for 24h.
No database, no user table — one shared judge password from env.
"""

import hashlib
import hmac
import json
import os
import time
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

JUDGE_PASSWORD = os.environ.get("JUDGE_PASSWORD", "")
JUDGE_SECRET = os.environ.get("JUDGE_SECRET", "handoff-judge-2026")
TOKEN_TTL = 86400  # 24 hours


def _make_token() -> str:
    ts = str(int(time.time()))
    sig = hmac.new(JUDGE_SECRET.encode(), ts.encode(), hashlib.sha256).hexdigest()
    return f"{ts}.{sig}"


def _verify_token(token: str) -> bool:
    parts = token.split(".", 1)
    if len(parts) != 2:
        return False
    ts_str, sig = parts
    try:
        ts = int(ts_str)
    except ValueError:
        return False
    if time.time() - ts > TOKEN_TTL:
        return False
    expected = hmac.new(JUDGE_SECRET.encode(), ts_str.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(sig, expected)


class handler(BaseHTTPRequestHandler):

    def _send(self, status: int, body: dict, headers: dict | None = None) -> None:
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        if headers:
            for k, v in headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw)
        except Exception:
            self._send(400, {"error": "invalid json"})
            return

        password = data.get("password", "")
        if not JUDGE_PASSWORD:
            self._send(503, {"error": "JUDGE_PASSWORD not configured"})
            return
        if not hmac.compare_digest(password, JUDGE_PASSWORD):
            self._send(401, {"error": "invalid password"})
            return

        token = _make_token()
        self._send(200, {"ok": True, "token": token})

    def do_GET(self):
        auth = self.headers.get("Authorization", "")
        token = auth.replace("Bearer ", "").strip()
        if not token or not _verify_token(token):
            self._send(401, {"ok": False, "error": "unauthorized"})
            return
        self._send(200, {"ok": True})

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def log_message(self, format, *args):
        pass
