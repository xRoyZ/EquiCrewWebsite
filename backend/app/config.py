"""Runtime configuration of the API, read from environment variables.

Every value has a working default or is optional, so the API boots without any SMTP
variable; the contact route then answers 503 instead of sending. No secret has a
literal value here: SMTP_PASSWORD comes from the environment only.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

DEFAULT_CORS_ORIGIN = "http://localhost:8080"


class Settings(BaseSettings):
    """API settings; each field is read from the environment variable of the same name."""

    model_config = SettingsConfigDict(case_sensitive=False, env_ignore_empty=True, extra="ignore")

    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    contact_to: str = "office@equicrew.com"
    cors_origin: str = DEFAULT_CORS_ORIGIN
    trusted_proxies: Annotated[list[str], NoDecode] = []
    rate_limit_max: int = 5
    rate_limit_window_seconds: int = 600
    max_body_bytes: int = 65536

    @field_validator("trusted_proxies", mode="before")
    @classmethod
    def _split_proxies(cls, value: object) -> object:
        """TRUSTED_PROXIES is a comma-separated list of addresses."""
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("cors_origin")
    @classmethod
    def _single_origin(cls, value: str) -> str:
        """CORS_ORIGIN is exactly one origin; a wildcard is refused."""
        origin = value.strip().rstrip("/")
        if not origin or "*" in origin or "," in origin:
            raise ValueError("CORS_ORIGIN must be one origin such as http://localhost:8080")
        return origin

    @field_validator("smtp_port", "rate_limit_max", "rate_limit_window_seconds", "max_body_bytes")
    @classmethod
    def _positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("must be a positive number")
        return value


@lru_cache
def get_settings() -> Settings:
    """Return the settings, read from the environment once and then cached."""
    return Settings()
