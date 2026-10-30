"""POST /api/contact: the website's contact form.

Validates the four fields, silently drops submissions whose hidden honeypot field is
filled and sends every other message by SMTP to CONTACT_TO. No visitor data is
logged or stored.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field, field_validator
from starlette.concurrency import run_in_threadpool

from app.config import get_settings
from app.mailer import (
    ContactMessage,
    MailDeliveryError,
    MailNotConfiguredError,
    send_contact_message,
)
from app.ratelimit import enforce_rate_limit

router = APIRouter()

MAX_NACHRICHT_CHARS = 5000
UNAVAILABLE_DETAIL = (
    "Deine Nachricht konnte gerade nicht gesendet werden. "
    "Bitte schreib uns direkt an office@equicrew.com."
)


class ContactRequest(BaseModel):
    """Body of POST /api/contact; ``website`` is the hidden honeypot field."""

    vorname: str
    nachname: str
    email: EmailStr
    nachricht: str = Field(max_length=MAX_NACHRICHT_CHARS)
    website: str = ""

    @field_validator("vorname", "nachname", "nachricht")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        """Trim the field; a field that is empty after trimming is invalid."""
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("must not be blank")
        return trimmed

    @field_validator("email", mode="before")
    @classmethod
    def _trim_email(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


@router.post("/api/contact", dependencies=[Depends(enforce_rate_limit)])
async def submit_contact(payload: ContactRequest) -> dict[str, str]:
    """Send the contact message to CONTACT_TO; answers {"status": "sent"}."""
    if payload.website.strip():
        # Honeypot filled: a bot. Answer like a success and send nothing.
        return {"status": "sent"}
    contact = ContactMessage(
        vorname=payload.vorname,
        nachname=payload.nachname,
        email=str(payload.email),
        nachricht=payload.nachricht,
    )
    try:
        await run_in_threadpool(send_contact_message, contact, get_settings())
    except (MailNotConfiguredError, MailDeliveryError):
        raise HTTPException(status_code=503, detail=UNAVAILABLE_DETAIL) from None
    return {"status": "sent"}
