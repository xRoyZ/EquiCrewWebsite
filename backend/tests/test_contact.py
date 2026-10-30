"""Tests of POST /api/contact: validation, honeypot and SMTP delivery (SMTP mocked)."""

from __future__ import annotations

import logging
import smtplib
from collections.abc import Iterator
from email.message import EmailMessage
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings

VALID = {
    "vorname": "Anna",
    "nachname": "Muster",
    "email": "anna@example.org",
    "nachricht": "Hallo EquiCrew,\nich interessiere mich für den EquiCube.",
}
SMTP_VARS = ("SMTP_HOST", "SMTP_PORT", "SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_FROM")


@pytest.fixture
def smtp_mock() -> Iterator[MagicMock]:
    """Replace smtplib.SMTP; the yielded mock is the connection the code talks to."""
    with patch("app.mailer.smtplib.SMTP") as smtp_class:
        connection = MagicMock()
        connection.__enter__.return_value = connection
        connection.__exit__.return_value = False
        smtp_class.return_value = connection
        connection.smtp_class = smtp_class
        yield connection


def _sent_message(connection: MagicMock) -> tuple[EmailMessage, dict[str, object]]:
    assert connection.send_message.call_count == 1
    call = connection.send_message.call_args
    return call.args[0], call.kwargs


def test_valid_submission_sends_exactly_one_mail(
    client: TestClient, smtp_env: dict[str, str], smtp_mock: MagicMock
) -> None:
    response = client.post("/api/contact", json=VALID)

    assert response.status_code == 200
    assert response.json() == {"status": "sent"}
    message, kwargs = _sent_message(smtp_mock)
    assert kwargs["to_addrs"] == ["office@equicrew.com"]
    assert message["To"] == "office@equicrew.com"
    assert message["From"] == smtp_env["SMTP_FROM"]
    assert message["Reply-To"] == VALID["email"]
    assert message["Subject"] == "Neue Nachricht über equicrew.com von Anna Muster"
    body = message.get_content()
    assert "Anna Muster" in body
    assert VALID["email"] in body
    assert VALID["nachricht"] in body
    smtp_mock.smtp_class.assert_called_once()
    assert smtp_mock.smtp_class.call_args.args[:2] == ("smtp.test.invalid", 2525)
    smtp_mock.login.assert_called_once_with(smtp_env["SMTP_USERNAME"], smtp_env["SMTP_PASSWORD"])


def test_contact_to_is_configurable(
    client: TestClient,
    smtp_env: dict[str, str],
    smtp_mock: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CONTACT_TO", "team@test.invalid")
    get_settings.cache_clear()

    assert client.post("/api/contact", json=VALID).status_code == 200
    message, kwargs = _sent_message(smtp_mock)
    assert kwargs["to_addrs"] == ["team@test.invalid"]
    assert message["To"] == "team@test.invalid"


def test_submission_port_requires_starttls(
    client: TestClient,
    smtp_env: dict[str, str],
    smtp_mock: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SMTP_PORT", "587")
    get_settings.cache_clear()
    smtp_mock.has_extn.return_value = False

    assert client.post("/api/contact", json=VALID).status_code == 200
    smtp_mock.starttls.assert_called_once()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("vorname", ""),
        ("vorname", "   "),
        ("nachname", ""),
        ("nachname", " \t "),
        ("email", ""),
        ("email", "keine-adresse"),
        ("email", "anna@"),
        ("nachricht", ""),
        ("nachricht", "\n  \n"),
    ],
)
def test_invalid_field_answers_422(
    client: TestClient, smtp_env: dict[str, str], smtp_mock: MagicMock, field: str, value: str
) -> None:
    response = client.post("/api/contact", json={**VALID, field: value})

    assert response.status_code == 422
    body = response.json()
    assert set(body) == {"detail"}
    assert isinstance(body["detail"], str)
    smtp_mock.send_message.assert_not_called()


@pytest.mark.parametrize("field", ["vorname", "nachname", "email", "nachricht"])
def test_missing_field_answers_422(
    client: TestClient, smtp_env: dict[str, str], smtp_mock: MagicMock, field: str
) -> None:
    payload = {key: value for key, value in VALID.items() if key != field}

    response = client.post("/api/contact", json=payload)

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)
    smtp_mock.send_message.assert_not_called()


def test_nachricht_over_5000_chars_answers_422(
    client: TestClient, smtp_env: dict[str, str], smtp_mock: MagicMock
) -> None:
    response = client.post("/api/contact", json={**VALID, "nachricht": "a" * 5001})

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)
    smtp_mock.send_message.assert_not_called()


def test_nachricht_of_exactly_5000_chars_is_sent(
    client: TestClient, smtp_env: dict[str, str], smtp_mock: MagicMock
) -> None:
    response = client.post("/api/contact", json={**VALID, "nachricht": "a" * 5000})

    assert response.status_code == 200
    smtp_mock.send_message.assert_called_once()


def test_filled_honeypot_answers_200_and_sends_nothing(
    client: TestClient, smtp_env: dict[str, str], smtp_mock: MagicMock
) -> None:
    response = client.post("/api/contact", json={**VALID, "website": "https://spam.example"})

    assert response.status_code == 200
    assert response.json() == {"status": "sent"}
    smtp_mock.smtp_class.assert_not_called()
    smtp_mock.send_message.assert_not_called()


def test_missing_smtp_configuration_answers_503(
    client: TestClient, smtp_mock: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    for key in SMTP_VARS:
        monkeypatch.delenv(key, raising=False)
    get_settings.cache_clear()
    try:
        response = client.post("/api/contact", json=VALID)
    finally:
        get_settings.cache_clear()

    assert response.status_code == 503
    body = response.json()
    assert set(body) == {"detail"}
    assert "office@equicrew.com" in body["detail"]
    smtp_mock.smtp_class.assert_not_called()


@pytest.mark.parametrize("missing", ["SMTP_HOST", "SMTP_FROM"])
def test_partial_smtp_configuration_answers_503(
    client: TestClient,
    smtp_env: dict[str, str],
    smtp_mock: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    missing: str,
) -> None:
    monkeypatch.delenv(missing)
    get_settings.cache_clear()

    response = client.post("/api/contact", json=VALID)

    assert response.status_code == 503
    smtp_mock.send_message.assert_not_called()


@pytest.mark.parametrize(
    "failure",
    [
        "login",
        "send_message",
    ],
)
def test_smtp_error_answers_generic_503(
    client: TestClient,
    smtp_env: dict[str, str],
    smtp_mock: MagicMock,
    caplog: pytest.LogCaptureFixture,
    failure: str,
) -> None:
    password = smtp_env["SMTP_PASSWORD"]
    secret_text = f"535 authentication failed for {password} at smtp.test.invalid"
    getattr(smtp_mock, failure).side_effect = smtplib.SMTPException(secret_text)

    with caplog.at_level(logging.DEBUG):
        response = client.post("/api/contact", json=VALID)

    assert response.status_code == 503
    body = response.json()
    assert set(body) == {"detail"}
    for leaked in (password, secret_text, "535", "smtp.test.invalid", VALID["email"], "Anna"):
        assert leaked not in response.text
        assert leaked not in caplog.text


def test_connection_error_answers_503(
    client: TestClient, smtp_env: dict[str, str], smtp_mock: MagicMock
) -> None:
    smtp_mock.smtp_class.side_effect = ConnectionRefusedError("connection refused")

    response = client.post("/api/contact", json=VALID)

    assert response.status_code == 503
    assert "refused" not in response.text


def test_header_injection_in_name_adds_no_header_or_recipient(
    client: TestClient, smtp_env: dict[str, str], smtp_mock: MagicMock
) -> None:
    payload = {**VALID, "vorname": "Anna\r\nBcc: x@y", "nachname": "Muster\nCc: z@y"}

    response = client.post("/api/contact", json=payload)

    assert response.status_code == 200
    message, kwargs = _sent_message(smtp_mock)
    assert message["Bcc"] is None
    assert message["Cc"] is None
    expected_headers = {
        "To",
        "From",
        "Reply-To",
        "Subject",
        "Content-Type",
        "Content-Transfer-Encoding",
        "MIME-Version",
    }
    assert sorted(message.keys()) == sorted(expected_headers)
    assert kwargs["to_addrs"] == ["office@equicrew.com"]
    subject = message["Subject"]
    assert "\r" not in subject and "\n" not in subject
    serialized = message.as_string()
    assert "\nBcc:" not in serialized
    assert "\nCc:" not in serialized
