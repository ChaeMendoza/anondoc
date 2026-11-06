"""
HTTP hardening: request-size cap, per-IP rate limiting and security headers.
"""
import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from anondoc.config import AppConfig

# Multipart framing overhead allowed on top of the file limit.
BODY_OVERHEAD_BYTES = 1024 * 1024

SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
        "connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
}


class BodySizeLimitMiddleware:
    """Rejects oversized bodies by Content-Length and by actual streamed bytes."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        limit = AppConfig.MAX_FILE_SIZE_BYTES + BODY_OVERHEAD_BYTES
        declared = dict(scope["headers"]).get(b"content-length")
        too_large = JSONResponse(
            {"detail": "La solicitud excede el tamaño máximo permitido.", "code": "request_too_large"}, status_code=413
        )
        if declared is not None:
            try:
                if int(declared) > limit:
                    return await too_large(scope, receive, send)
            except ValueError:
                return await JSONResponse({"detail": "Solicitud inválida.", "code": "bad_request"}, status_code=400)(scope, receive, send)

        received = 0
        started = False

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise _BodyTooLarge()
            return message

        async def tracking_send(message: Message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracking_send)
        except _BodyTooLarge:
            if not started:
                await too_large(scope, receive, send)


class _BodyTooLarge(Exception):
    pass


class RateLimiter:
    """In-memory sliding window per client key."""

    def __init__(self):
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int, window: int) -> bool:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > window:
                hits.popleft()
            if len(hits) >= limit:
                return False
            hits.append(now)
            if len(self._hits) > 10_000:
                for k in [k for k, v in self._hits.items() if not v or now - v[-1] > window]:
                    del self._hits[k]
            return True


limiter = RateLimiter()


def client_key(request) -> str:
    return request.client.host if request.client else "unknown"


async def security_middleware(request, call_next):
    key = client_key(request)
    path = request.url.path
    if path.startswith("/api/"):
        if not limiter.allow(f"all:{key}", AppConfig.RATE_LIMIT_REQUESTS, AppConfig.RATE_LIMIT_WINDOW_SECONDS):
            return _limited()
        if request.method == "POST" and path == "/api/v1/documents":
            if not limiter.allow(f"upload:{key}", AppConfig.UPLOAD_RATE_LIMIT, AppConfig.RATE_LIMIT_WINDOW_SECONDS):
                return _limited()

    response = await call_next(request)
    for name, value in SECURITY_HEADERS.items():
        response.headers.setdefault(name, value)
    if path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


def _limited():
    response = JSONResponse(
        {"detail": "Demasiadas solicitudes. Intente más tarde.", "code": "rate_limited"}, status_code=429,
        headers={"Retry-After": str(AppConfig.RATE_LIMIT_WINDOW_SECONDS)},
    )
    for name, value in SECURITY_HEADERS.items():
        response.headers.setdefault(name, value)
    return response
