"""Shared fixtures of the API test suite."""

from __future__ import annotations

import secrets
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app import ratelimit
from app.config import get_settings
from app.main import app


@pytest.fixture
def client() -> Iterator[TestClient]:
    """TestClient on the app; the context manager runs the app's lifespan."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def _reset_rate_limit() -> Iterator[None]:
    """Every test starts with an empty rate-limit state."""
    ratelimit.reset()
    yield
    ratelimit.reset()


@pytest.fixture
def smtp_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, str]]:
    """Set the SMTP_* variables to test values and re-read the settings.

    The password is generated per run, so no credential literal lives in the repository.
    """
    values = {
        "SMTP_HOST": "smtp.test.invalid",
        "SMTP_PORT": "2525",
        "SMTP_USERNAME": "mailer@test.invalid",
        "SMTP_PASSWORD": secrets.token_hex(12),
        "SMTP_FROM": "website@test.invalid",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    yield values
    get_settings.cache_clear()
