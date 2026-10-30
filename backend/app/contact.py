"""POST /api/contact: the website's contact form.

Skeleton: the route is declared with its final path, body and rate-limit dependency;
the contact ticket fills the body (validation, honeypot, SMTP delivery). Until then it
answers 501 explicitly.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.ratelimit import enforce_rate_limit

router = APIRouter()


class ContactRequest(BaseModel):
    """Body of POST /api/contact; ``website`` is the hidden honeypot field."""

    vorname: str
    nachname: str
    email: str
    nachricht: str
    website: str = ""


@router.post("/api/contact", dependencies=[Depends(enforce_rate_limit)])
async def submit_contact(payload: ContactRequest) -> dict[str, str]:
    """Send the contact message to CONTACT_TO; answers {"status": "sent"}."""
    raise HTTPException(status_code=501, detail="The contact ticket implements sending.")
