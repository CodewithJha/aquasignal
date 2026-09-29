"""Request body size cap (ASGI middleware).

The app only records the photo *filename*, so there is no reason to accept
large bodies. Oversized requests get a plain 413 page; the body is never
buffered by this layer.
"""

from __future__ import annotations

import os
from html import escape

from starlette.types import ASGIApp, Message, Receive, Scope, Send

DEFAULT_MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def max_upload_bytes() -> int:
    raw = (os.environ.get("MAX_UPLOAD_BYTES") or "").strip()
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_MAX_UPLOAD_BYTES
    return value if value > 0 else DEFAULT_MAX_UPLOAD_BYTES


def _human_size(n: int) -> str:
    if n >= 1024 * 1024:
        return f"{n / (1024 * 1024):.0f} MB"
    if n >= 1024:
        return f"{n / 1024:.0f} KB"
    return f"{n} bytes"


class _BodyTooLarge(Exception):
    pass


def _page(limit: int) -> bytes:
    size = escape(_human_size(limit))
    return (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<title>Upload too large</title>"
        "<link rel=\"stylesheet\" href=\"/static/style.css\"></head><body><main>"
        "<section class=\"panel\"><h2>Upload too large</h2>"
        f"<p>Requests must be under {size}. Please choose a smaller photo "
        "(ConfirmGate only records the photo's file name) and try again.</p>"
        "<p><a href=\"/upload\">Back to the observation form</a></p>"
        "</section></main></body></html>"
    ).encode("utf-8")


class MaxBodySizeMiddleware:
    """Reject request bodies above ``MAX_UPLOAD_BYTES`` with HTTP 413."""

    def __init__(self, app: ASGIApp, max_bytes: int | None = None) -> None:
        self.app = app
        self._max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        limit = self._max_bytes or max_upload_bytes()

        declared = None
        for key, value in scope.get("headers") or ():
            if key == b"content-length":
                try:
                    declared = int(value)
                except ValueError:
                    declared = None
                break
        if declared is not None and declared > limit:
            await self._reject(send, limit)
            return

        received = 0
        exceeded = False
        started = False

        async def limited_receive() -> Message:
            nonlocal received, exceeded
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    exceeded = True
                    raise _BodyTooLarge
            return message

        # FastAPI turns body-parsing exceptions into its own 400 response, so
        # once the cap is hit the app's response is dropped and replaced.
        async def tracking_send(message: Message) -> None:
            nonlocal started
            if exceeded and not started:
                return
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracking_send)
        except _BodyTooLarge:
            pass
        if exceeded and not started:
            await self._reject(send, limit)

    @staticmethod
    async def _reject(send: Send, limit: int) -> None:
        body = _page(limit)
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"text/html; charset=utf-8"),
                    (b"content-length", str(len(body)).encode()),
                    (b"connection", b"close"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
