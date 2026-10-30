"""ASGI middleware limiting the size of a request body.

Skeleton: the body-limit ticket makes it answer 413 {"detail": str} before the body is
fully read; for now every request passes through unchanged.
"""

from __future__ import annotations

from starlette.types import ASGIApp, Receive, Scope, Send


class BodySizeLimitMiddleware:
    """Reject request bodies larger than ``max_bytes`` (pass-through for now)."""

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await self.app(scope, receive, send)
