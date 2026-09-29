"""First-party ``cg_observer`` cookie → request.state.observer_ref.

The cookie carries a random 128-bit token (HttpOnly, SameSite=Lax, Secure on
https). Only the derived observer_ref reaches handlers; the token is never
logged or rendered. Secure follows the request scheme uvicorn reports; behind a
TLS-terminating proxy that needs ``--proxy-headers`` plus a trusted
``--forwarded-allow-ips`` (the Dockerfile sets both).
"""

from __future__ import annotations

from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from starlette.datastructures import MutableHeaders
from http.cookies import SimpleCookie

from app.domain.observer import (
    OBSERVER_COOKIE,
    is_observer_token,
    new_observer_token,
    observer_ref_for_token,
)

OBSERVER_COOKIE_MAX_AGE = 365 * 24 * 3600


def _set_cookie_header(token: str, *, secure: bool) -> str:
    cookie: SimpleCookie = SimpleCookie()
    cookie[OBSERVER_COOKIE] = token
    morsel = cookie[OBSERVER_COOKIE]
    morsel["path"] = "/"
    morsel["max-age"] = str(OBSERVER_COOKIE_MAX_AGE)
    morsel["httponly"] = True
    morsel["samesite"] = "Lax"
    if secure:
        morsel["secure"] = True
    return morsel.OutputString()


class ObserverCookieMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request = Request(scope)
        token = request.cookies.get(OBSERVER_COOKIE)
        fresh = not is_observer_token(token)
        if fresh:
            token = new_observer_token()
        scope.setdefault("state", {})["observer_ref"] = observer_ref_for_token(token)
        secure = request.url.scheme == "https"

        async def send_with_cookie(message: Message) -> None:
            if fresh and message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.append("set-cookie", _set_cookie_header(token, secure=secure))
            await send(message)

        await self.app(scope, receive, send_with_cookie)


def current_observer_ref(request: Request) -> str | None:
    return getattr(request.state, "observer_ref", None)
