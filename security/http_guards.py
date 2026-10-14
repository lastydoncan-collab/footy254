"""
HTTP-level protections applied to every request/response.

* ``OriginGuardMiddleware`` - CSRF defence for cookie-authenticated requests.
  ``SameSite`` cookies already block most cross-site POSTs; this adds an explicit
  check so the protection also holds for ``SameSite=None`` cross-domain
  deployments and older browsers.
* ``SecurityHeadersMiddleware`` - baseline hardening headers, a
  Content-Security-Policy for the single-page app shell, and ``no-store`` on API
  responses (they are user-specific and must never sit in a shared cache).

Both are pure ASGI middleware (no BaseHTTPMiddleware), so they add no per-request
thread hop and do not interfere with streaming or background tasks.
"""

import json
from urllib.parse import urlparse

from starlette.datastructures import Headers

from config.settings import (
    ACCESS_COOKIE_NAME,
    ALLOWED_ORIGINS,
    API_PREFIX,
    COOKIE_SECURE,
    REFRESH_COOKIE_NAME,
)

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# Server-to-server callbacks: no browser, no cookies, authenticated by a secret
# in the path instead.
EXEMPT_PREFIXES = (
    "/mpesa/callback/",
    f"{API_PREFIX}/mpesa/callback/",
    # Paystack webhook: authenticated by its HMAC signature header.
    f"{API_PREFIX}/card/webhook",
)

# Paths whose own pages (Swagger UI) need a more permissive policy than the SPA.
DOC_PREFIXES = (
    f"{API_PREFIX}/docs",
    f"{API_PREFIX}/redoc",
    f"{API_PREFIX}/openapi.json",
)


class OriginGuardMiddleware:
    def __init__(self, app, allowed_origins=None):
        self.app = app
        self.allowed = {
            origin.lower().rstrip("/")
            for origin in (ALLOWED_ORIGINS if allowed_origins is None else allowed_origins)
        }

    @staticmethod
    def _has_session_cookie(headers: Headers) -> bool:
        cookie = headers.get("cookie", "")

        return (
            f"{ACCESS_COOKIE_NAME}=" in cookie
            or f"{REFRESH_COOKIE_NAME}=" in cookie
        )

    def _origin_ok(self, headers: Headers) -> bool:
        origin = headers.get("origin")

        if not origin:
            # Non-browser clients send no Origin. Browsers always attach one to
            # cross-site unsafe requests, but Sec-Fetch-Site is the second line
            # of defence if a browser omits it.
            return headers.get("sec-fetch-site", "same-origin") in {
                "same-origin",
                "same-site",
                "none",
            }

        origin = origin.lower().rstrip("/")

        if origin in self.allowed:
            return True

        host = (headers.get("x-forwarded-host") or headers.get("host") or "").lower()

        return bool(host) and urlparse(origin).netloc == host

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in UNSAFE_METHODS:
            return await self.app(scope, receive, send)

        if scope.get("path", "").startswith(EXEMPT_PREFIXES):
            return await self.app(scope, receive, send)

        headers = Headers(scope=scope)

        # Only requests that would carry credentials can be forged.
        if self._has_session_cookie(headers) and not self._origin_ok(headers):
            body = json.dumps({"detail": "Cross-site request blocked."}).encode()

            await send(
                {
                    "type": "http.response.start",
                    "status": 403,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"content-length", str(len(body)).encode()),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body})
            return

        return await self.app(scope, receive, send)


class SecurityHeadersMiddleware:
    def __init__(self, app, csp_connect_src: str = ""):
        self.app = app

        connect = ("'self' " + csp_connect_src).strip()

        # Inline styles are required by framer-motion; scripts stay strict.
        self.csp = "; ".join(
            [
                "default-src 'self'",
                "script-src 'self'",
                "style-src 'self' 'unsafe-inline'",
                "img-src 'self' data: https:",
                "font-src 'self' data:",
                f"connect-src {connect}",
                "manifest-src 'self'",
                "worker-src 'self'",
                "object-src 'none'",
                "base-uri 'self'",
                "form-action 'self'",
                "frame-ancestors 'none'",
            ]
        ).encode()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        path = scope.get("path", "")
        is_docs = path.startswith(DOC_PREFIXES)

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                present = {name.lower() for name, _ in headers}

                def add(name: bytes, value: bytes):
                    if name not in present:
                        headers.append((name, value))
                        present.add(name)

                add(b"x-content-type-options", b"nosniff")
                add(b"referrer-policy", b"strict-origin-when-cross-origin")
                add(b"x-frame-options", b"DENY")
                add(
                    b"permissions-policy",
                    b"camera=(), microphone=(), geolocation=(), payment=()",
                )

                if COOKIE_SECURE:
                    add(
                        b"strict-transport-security",
                        b"max-age=31536000; includeSubDomains",
                    )

                content_type = dict(headers).get(b"content-type", b"")

                if not is_docs and content_type.startswith(b"text/html"):
                    add(b"content-security-policy", self.csp)

                if path.startswith(API_PREFIX + "/"):
                    add(b"cache-control", b"no-store")

                message["headers"] = headers

            await send(message)

        return await self.app(scope, receive, send_with_headers)
