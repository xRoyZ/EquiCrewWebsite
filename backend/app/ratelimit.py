"""Per-IP rate limit of POST /api/contact (kept in memory only).

Skeleton: the rate-limit ticket fills these functions; the signatures are fixed.
"""

from __future__ import annotations

from fastapi import Request

from app.config import Settings


async def enforce_rate_limit(request: Request) -> None:
    """Raise HTTPException(429) once a client exceeded the limit. Does nothing yet."""
    return None


def client_ip(request: Request, settings: Settings) -> str:
    """Return the address of the connecting client."""
    if request.client is None:
        return "unknown"
    return request.client.host


def reset() -> None:
    """Clear all in-memory rate-limit state. Nothing is kept yet."""
    return None
