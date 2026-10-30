"""Per-IP rate limit of POST /api/contact (kept in memory only).

A sliding window per client address: at most ``settings.rate_limit_max`` requests
within ``settings.rate_limit_window_seconds``; the next one is answered with 429.

Privacy (AC-30): addresses live only in this module's dictionary, are never logged or
written anywhere, and every call purges timestamps older than the window together with
addresses that have none left, so no address outlives its window.
"""

from __future__ import annotations

import ipaddress
import math
import threading
import time
from collections import deque

from fastapi import HTTPException, Request

from app.config import Settings, get_settings

RATE_LIMIT_DETAIL = "Zu viele Anfragen. Bitte versuchen Sie es später erneut."

# Monotonic clock, a module attribute so tests can move time forward.
_clock = time.monotonic

_lock = threading.Lock()
_hits: dict[str, deque[float]] = {}


def _purge(now: float, window: float) -> None:
    """Drop expired timestamps and every address without a timestamp left."""
    cutoff = now - window
    for ip in list(_hits):
        stamps = _hits[ip]
        while stamps and stamps[0] <= cutoff:
            stamps.popleft()
        if not stamps:
            del _hits[ip]


def _is_trusted(address: str, trusted: list[str]) -> bool:
    """True when ``address`` equals a configured proxy or lies in a configured network."""
    if address in trusted:
        return True
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    for entry in trusted:
        try:
            if ip in ipaddress.ip_network(entry, strict=False):
                return True
        except ValueError:
            continue
    return False


def client_ip(request: Request, settings: Settings) -> str:
    """Return the address the rate limit is keyed by.

    The connecting address is used, unless it is a configured trusted proxy: then the
    X-Forwarded-For chain is walked from the right and the first address that is not a
    trusted proxy is the client. Unparseable entries fall back to the connecting address.
    """
    peer = request.client.host if request.client is not None else "unknown"
    trusted = settings.trusted_proxies
    if not trusted or not _is_trusted(peer, trusted):
        return peer
    header = request.headers.get("x-forwarded-for", "")
    chain = [part.strip() for part in header.split(",") if part.strip()]
    if not chain:
        return peer
    candidate = chain[0]
    for entry in reversed(chain):
        if not _is_trusted(entry, trusted):
            candidate = entry
            break
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return peer


async def enforce_rate_limit(request: Request) -> None:
    """Raise HTTPException(429) once a client exceeded the limit within the window."""
    settings = get_settings()
    window = float(settings.rate_limit_window_seconds)
    ip = client_ip(request, settings)
    with _lock:
        now = _clock()
        _purge(now, window)
        stamps = _hits.get(ip)
        if stamps is not None and len(stamps) >= settings.rate_limit_max:
            retry_after = max(1, math.ceil(stamps[0] + window - now))
            raise HTTPException(
                status_code=429,
                detail=RATE_LIMIT_DETAIL,
                headers={"Retry-After": str(retry_after)},
            )
        _hits.setdefault(ip, deque()).append(now)


def tracked_count() -> int:
    """Number of addresses currently held in memory (after purging expired ones)."""
    settings = get_settings()
    with _lock:
        _purge(_clock(), float(settings.rate_limit_window_seconds))
        return len(_hits)


def reset() -> None:
    """Clear all in-memory rate-limit state."""
    with _lock:
        _hits.clear()
