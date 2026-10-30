"""ASGI middleware limiting the size of a request body.

A request announcing a Content-Length above ``max_bytes`` is answered with 413 before a
single body byte is read. A body without Content-Length (chunked transfer) is counted
while the application receives it; as soon as the count passes the limit, reading stops
and the client gets 413 instead of whatever the application would have answered.
"""

from __future__ import annotations

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

BODY_TOO_LARGE_DETAIL = "Die Anfrage ist zu groß."
BAD_LENGTH_DETAIL = "Ungültige Content-Length."


class _BodyTooLargeError(Exception):
    """Raised from the wrapped ``receive`` once the streamed body passed the limit."""


class BodySizeLimitMiddleware:
    """Reject request bodies larger than ``max_bytes`` with 413 {"detail": str}."""

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        declared = _content_length(scope)
        if declared == -1:
            await JSONResponse({"detail": BAD_LENGTH_DETAIL}, status_code=400)(scope, receive, send)
            return
        if declared is not None and declared > self.max_bytes:
            await _too_large(scope, receive, send)
            return

        received = 0
        exceeded = False
        response_started = False

        async def limited_receive() -> Message:
            nonlocal received, exceeded
            if exceeded:
                raise _BodyTooLargeError
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    exceeded = True
                    raise _BodyTooLargeError
            return message

        async def guarded_send(message: Message) -> None:
            nonlocal response_started
            # Once the limit was passed, the application's own answer (often a 400
            # about an unreadable body) is withheld and replaced by the 413 below.
            if exceeded and not response_started:
                return
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, guarded_send)
        except Exception:
            if not exceeded or response_started:
                raise
        if exceeded and not response_started:
            await _too_large(scope, receive, send)


def _content_length(scope: Scope) -> int | None:
    """The declared Content-Length; None when absent, -1 when malformed."""
    for name, value in scope.get("headers", []):
        if name.lower() == b"content-length":
            try:
                length = int(value)
            except ValueError:
                return -1
            return length if length >= 0 else -1
    return None


async def _too_large(scope: Scope, receive: Receive, send: Send) -> None:
    response = JSONResponse({"detail": BODY_TOO_LARGE_DETAIL}, status_code=413)
    response.headers["Connection"] = "close"
    await response(scope, receive, send)
