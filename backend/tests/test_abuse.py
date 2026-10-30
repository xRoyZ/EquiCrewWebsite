"""Abuse protection of the API: per-IP rate limit and request body size limit.

Only the status codes these two modules produce (429, 413) are asserted; what the
contact route itself answers belongs to the contact ticket's tests.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from starlette.types import Message, Receive, Scope, Send

from app import ratelimit
from app.body_limit import BodySizeLimitMiddleware
from app.config import get_settings

CONTACT = "/api/contact"
PAYLOAD = {
    "vorname": "Erika",
    "nachname": "Muster",
    "email": "erika@example.org",
    "nachricht": "Hallo",
    "website": "",
}


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> FakeClock:
    fake = FakeClock()
    monkeypatch.setattr(ratelimit, "_clock", fake)
    return fake


@pytest.fixture
def trusted_testclient(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Configure the TestClient's connecting address as a trusted proxy."""
    monkeypatch.setenv("TRUSTED_PROXIES", "testclient")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def no_trusted_proxy(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.delenv("TRUSTED_PROXIES", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _post(client: TestClient, xff: str | None = None) -> int:
    headers = {"X-Forwarded-For": xff} if xff is not None else {}
    return client.post(CONTACT, json=PAYLOAD, headers=headers).status_code


def test_sixth_request_from_one_client_is_429(client: TestClient, clock: FakeClock) -> None:
    for _ in range(5):
        assert _post(client) != 429
    response = client.post(CONTACT, json=PAYLOAD)
    assert response.status_code == 429
    body = response.json()
    assert set(body) == {"detail"}
    assert isinstance(body["detail"], str) and body["detail"]
    assert int(response.headers["Retry-After"]) > 0


def test_changing_forwarded_for_does_not_avoid_429_without_trusted_proxy(
    client: TestClient, clock: FakeClock, no_trusted_proxy: None
) -> None:
    for i in range(5):
        assert _post(client, f"203.0.113.{i}") != 429
    assert _post(client, "198.51.100.77") == 429
    assert _post(client, "198.51.100.78") == 429


def test_forwarded_for_counts_separately_behind_trusted_proxy(
    client: TestClient, clock: FakeClock, trusted_testclient: None
) -> None:
    for _ in range(5):
        assert _post(client, "203.0.113.1") != 429
    assert _post(client, "203.0.113.1") == 429
    assert _post(client, "203.0.113.2") != 429
    # A spoofed left-most entry does not help: the address the proxy appended counts.
    assert _post(client, "198.51.100.9, 203.0.113.1") == 429


def test_entries_vanish_after_the_window(client: TestClient, clock: FakeClock) -> None:
    window = get_settings().rate_limit_window_seconds
    for _ in range(5):
        assert _post(client) != 429
    assert _post(client) == 429
    assert ratelimit.tracked_count() == 1

    clock.now += window + 1
    assert ratelimit.tracked_count() == 0
    assert _post(client) != 429


def test_window_slides(client: TestClient, clock: FakeClock) -> None:
    window = get_settings().rate_limit_window_seconds
    assert _post(client) != 429
    clock.now += window / 2
    for _ in range(4):
        assert _post(client) != 429
    assert _post(client) == 429
    # The first request leaves the window; exactly one slot frees up.
    clock.now += window / 2 + 1
    assert _post(client) != 429
    assert _post(client) == 429


def test_reset_clears_state(client: TestClient, clock: FakeClock) -> None:
    for _ in range(6):
        _post(client)
    ratelimit.reset()
    assert ratelimit.tracked_count() == 0
    assert _post(client) != 429


def test_oversized_body_is_413(client: TestClient) -> None:
    big = {**PAYLOAD, "nachricht": "x" * (100 * 1024)}
    response = client.post(CONTACT, json=big)
    assert response.status_code == 413
    body = response.json()
    assert set(body) == {"detail"}
    assert isinstance(body["detail"], str) and body["detail"]
    # Refused before the route ran, so the request did not count for the rate limit.
    assert ratelimit.tracked_count() == 0


def test_oversized_chunked_body_is_413(client: TestClient) -> None:
    def chunks() -> Iterator[bytes]:
        for _ in range(20):
            yield b"x" * 8192

    response = client.post(CONTACT, content=chunks(), headers={"Content-Type": "application/json"})
    assert response.status_code == 413
    assert set(response.json()) == {"detail"}


def _run_asgi(
    middleware: BodySizeLimitMiddleware, headers: list[tuple[bytes, bytes]], parts: list[bytes]
) -> tuple[list[Message], int]:
    sent: list[Message] = []
    queue = [
        {"type": "http.request", "body": p, "more_body": i < len(parts) - 1}
        for i, p in enumerate(parts)
    ]
    delivered = 0

    async def receive() -> Message:
        nonlocal delivered
        delivered += 1
        return queue.pop(0)

    async def send(message: Message) -> None:
        sent.append(message)

    scope: Scope = {"type": "http", "method": "POST", "path": "/", "headers": headers}
    asyncio.run(middleware(scope, receive, send))
    return sent, delivered


async def _echo_app(scope: Scope, receive: Receive, send: Send) -> None:
    body = b""
    more = True
    while more:
        message = await receive()
        body += message.get("body", b"")
        more = message.get("more_body", False)
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": body})


def test_declared_length_rejected_without_reading_body() -> None:
    mw = BodySizeLimitMiddleware(_echo_app, max_bytes=10)
    sent, delivered = _run_asgi(mw, [(b"content-length", b"11")], [b"x" * 11])
    assert sent[0]["status"] == 413
    assert delivered == 0


def test_streamed_body_aborts_as_soon_as_limit_passed() -> None:
    mw = BodySizeLimitMiddleware(_echo_app, max_bytes=10)
    sent, delivered = _run_asgi(mw, [], [b"x" * 6, b"x" * 6, b"x" * 6, b"x" * 6])
    assert sent[0]["status"] == 413
    assert delivered == 2


def test_body_within_limit_passes() -> None:
    mw = BodySizeLimitMiddleware(_echo_app, max_bytes=10)
    sent, _ = _run_asgi(mw, [], [b"x" * 5, b"x" * 5])
    assert sent[0]["status"] == 200
    assert sent[1]["body"] == b"x" * 10
