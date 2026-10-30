"""Tests of the API skeleton: health, route table, CORS and the error shape."""

from __future__ import annotations

import logging
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app

FOREIGN_ORIGIN = "https://foreign.example"


def test_health_answers_ok(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_answers_without_smtp_configuration(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    for key in ("SMTP_HOST", "SMTP_PORT", "SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_FROM"):
        monkeypatch.delenv(key, raising=False)
    get_settings.cache_clear()
    try:
        response = client.get("/api/health")
    finally:
        get_settings.cache_clear()
    assert response.status_code == 200


def test_contact_route_is_registered_as_post() -> None:
    paths = app.openapi()["paths"]
    assert "/api/contact" in paths
    assert set(paths["/api/contact"]) == {"post"}
    assert "/api/contact/" not in paths


def test_allowed_origin_gets_cors_header(client: TestClient) -> None:
    origin = get_settings().cors_origin
    response = client.get("/api/health", headers={"Origin": origin})
    assert response.headers.get("access-control-allow-origin") == origin
    assert "access-control-allow-credentials" not in response.headers


def test_allowed_origin_preflight_for_contact(client: TestClient) -> None:
    origin = get_settings().cors_origin
    response = client.options(
        "/api/contact",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin
    assert "access-control-allow-credentials" not in response.headers


def test_foreign_origin_gets_no_cors_header(client: TestClient) -> None:
    response = client.get("/api/health", headers={"Origin": FOREIGN_ORIGIN})
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
    assert "access-control-allow-credentials" not in response.headers


def test_foreign_origin_preflight_is_refused(client: TestClient) -> None:
    response = client.options(
        "/api/contact",
        headers={"Origin": FOREIGN_ORIGIN, "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in response.headers
    assert "access-control-allow-credentials" not in response.headers


def test_unknown_route_error_body_is_detail_string(client: TestClient) -> None:
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    body = response.json()
    assert set(body) == {"detail"}
    assert isinstance(body["detail"], str)


def test_wildcard_cors_origin_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGIN", "*")
    with pytest.raises(ValueError):
        Settings()


def test_trusted_proxies_are_comma_separated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRUSTED_PROXIES", "10.0.0.1, 10.0.0.2")
    assert Settings().trusted_proxies == ["10.0.0.1", "10.0.0.2"]
    monkeypatch.setenv("TRUSTED_PROXIES", "")
    assert Settings().trusted_proxies == []


def test_settings_defaults_boot_without_smtp(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("SMTP_HOST", "SMTP_PORT", "SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_FROM"):
        monkeypatch.delenv(key, raising=False)
    settings = Settings()
    assert settings.smtp_host is None
    assert settings.smtp_password is None
    assert settings.smtp_port == 587
    assert settings.contact_to


def test_smtp_env_fixture_is_read(smtp_env: dict[str, str]) -> None:
    settings = get_settings()
    assert settings.smtp_host == smtp_env["SMTP_HOST"]
    assert settings.smtp_port == int(smtp_env["SMTP_PORT"])
    assert settings.smtp_password == smtp_env["SMTP_PASSWORD"]


@pytest.fixture
def failing_route() -> Iterator[str]:
    """Temporarily add a route that raises, and remove it again afterwards."""
    path = "/api/test-failing-route"

    async def fail() -> None:
        raise RuntimeError("secret-text")

    app.add_api_route(path, fail, methods=["GET"])
    yield path
    app.router.routes[:] = [r for r in app.router.routes if getattr(r, "path", None) != path]


def test_unhandled_error_is_generic_and_keeps_cors(client: TestClient, failing_route: str) -> None:
    origin = get_settings().cors_origin
    response = client.get(failing_route, headers={"Origin": origin})
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error."}
    assert "secret-text" not in response.text
    assert response.headers.get("access-control-allow-origin") == origin


def test_unhandled_error_log_has_no_exception_text(
    client: TestClient, failing_route: str, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG):
        client.get(failing_route)
    assert "RuntimeError" in caplog.text
    assert "secret-text" not in caplog.text
