"""Small single-process guest boundary for the optional free public demo.

This does not replace proper authentication or persistent multi-user storage.
Do not enable for production financial/customer data or paid unrestricted API access.
"""
import hashlib
import hmac
import json
import os
import secrets
import threading
from collections import defaultdict
from fastapi import Request
from fastapi.responses import JSONResponse

COOKIE_NAME = "eventlens_guest"


class DemoGate:
    def __init__(self):
        self.secret = secrets.token_bytes(32)
        self.lock = threading.Lock()
        self.owner_by_research = {}
        self.research_by_guest = defaultdict(set)
        self.count_by_guest = defaultdict(lambda: {"research": 0, "ask": 0})
        self.totals = {"research": 0, "ask": 0}
        # Defaults deliberately small: server bills are the operator's risk.
        self.max_research = max(1, int(os.getenv("EVENTLENS_DEMO_MAX_RESEARCH", "12")))
        self.max_ask = max(1, int(os.getenv("EVENTLENS_DEMO_MAX_ASK", "24")))
        self.per_guest_research = 2
        self.per_guest_ask = 3

    def sign(self, token):
        mac = hmac.new(self.secret, token.encode("ascii"), hashlib.sha256).hexdigest()
        return token + "." + mac

    def identify(self, raw):
        if not raw:
            return None
        try:
            token, supplied_mac = raw.split(".", 1)
            if len(token) != 40 or not all(c in "0123456789abcdef" for c in token):
                return None
            expected = self.sign(token).split(".", 1)[1]
            return token if hmac.compare_digest(supplied_mac, expected) else None
        except (ValueError, TypeError, AttributeError):
            return None

    def register(self, guest, research_id):
        if not guest:
            raise ValueError("Public research must be bound to a guest")
        with self.lock:
            self.owner_by_research[research_id] = guest
            self.research_by_guest[guest].add(research_id)

    def owns(self, guest, research_id):
        with self.lock:
            return self.owner_by_research.get(research_id) == guest

    def owned_ids(self, guest):
        with self.lock:
            return set(self.research_by_guest.get(guest, ()))

    def count(self, guest, kind):
        with self.lock:
            total_limit = self.max_research if kind == "research" else self.max_ask
            guest_limit = self.per_guest_research if kind == "research" else self.per_guest_ask
            if self.totals[kind] >= total_limit or self.count_by_guest[guest][kind] >= guest_limit:
                return False
            self.totals[kind] += 1
            self.count_by_guest[guest][kind] += 1
            return True


def enabled():
    return os.getenv("EVENTLENS_PUBLIC_DEMO", "0") == "1"


def install(app):
    if not enabled():
        return

    gate = DemoGate()
    app.state.demo_gate = gate

    @app.middleware("http")
    async def guest_guard(request: Request, call_next):
        path = request.url.path
        raw = request.cookies.get(COOKIE_NAME)
        guest = gate.identify(raw)
        new_guest = not guest
        if new_guest:
            guest = secrets.token_hex(20)
        request.state.demo_guest = guest

        def deny(code, message):
            return JSONResponse(status_code=code, content={"detail": message},
                                headers={"Cache-Control": "no-store"})

        allowed = path == "/" or path == "/api/health" or path.startswith("/static/")
        allowed = allowed or path == "/api/research" or path.startswith("/api/research/")
        if not allowed:
            return deny(404, "公网演示仅启用独立研究入口；原生 Harness 仅在本地使用")

        if path == "/api/research":
            if request.method not in ("GET", "POST"):
                return deny(405, "方法不支持")
            if request.method == "POST" and not gate.count(guest, "research"):
                return deny(429, "公开体验研究次数已达上限；请查看已完成研究或稍后联系作者")

        if path.startswith("/api/research/"):
            tail = path[len("/api/research/"):].split("/")
            rid = tail[0]
            if not gate.owns(guest, rid):
                # 404 rather than 403 avoids confirming other visitor IDs.
                return deny(404, "该研究在当前访客会话中不存在")
            action = tail[1] if len(tail) > 1 else ""
            if action in ("source", "evidence", "refresh"):
                return deny(403, "公网演示只允许网页研究；不开放手工来源注入与无限增量检索")
            if action == "ask" and request.method == "POST":
                try:
                    payload = json.loads(await request.body())
                except (ValueError, TypeError):
                    return deny(422, "无效的 JSON")
                if not isinstance(payload, dict) or payload.get("refresh"):
                    return deny(403, "公网追问不支持额外联网刷新")
                if not gate.count(guest, "ask"):
                    return deny(429, "公开体验追问次数已达上限")
            elif action not in ("", "cancel", "judgment", "provenance", "ask"):
                return deny(404, "未知的公开操作")

        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            # Browser cross-origin form posts must not mutate guest research.
            origin = request.headers.get("origin")
            if origin:
                from urllib.parse import urlparse
                parsed = urlparse(origin)
                if parsed.netloc != request.url.netloc or parsed.scheme not in ("http", "https"):
                    return deny(403, "跨站来源不允许修改研究")
            ctype = request.headers.get("content-type", "")
            if not ctype.startswith("application/json"):
                return deny(415, "公开接口只接受 JSON 请求")

        response = await call_next(request)
        if new_guest:
            response.set_cookie(
                COOKIE_NAME, gate.sign(guest), httponly=True, samesite="lax",
                secure=request.url.scheme == "https",
                max_age=60 * 60 * 24, path="/",
            )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Frame-Options"] = "DENY"
        return response
