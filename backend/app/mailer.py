"""SMTP delivery of contact-form messages.

Headers are set only through ``EmailMessage``'s header API (never by string
concatenation), and CR/LF is removed from the visitor's name before it reaches the
subject, so a crafted name cannot add a header or a recipient (AC-16).

Nothing here logs or raises visitor data, the SMTP password or an SMTP exception's
text: a failure is logged as a fixed event text and surfaces as ``MailDeliveryError``
without a message (AC-20, AC-30).
"""

from __future__ import annotations

import logging
import re
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from email.policy import default as default_policy

from app.config import Settings

logger = logging.getLogger("equicrew.api.mailer")

SMTP_TIMEOUT_SECONDS = 15
SMTPS_PORT = 465
SUBMISSION_PORT = 587
SUBJECT_PREFIX = "Neue Nachricht über equicrew.com von"

# CR and LF plus every other character a mail header or a mail client could treat
# as a line break.
_LINE_BREAKS = re.compile(r"[\r\n\v\f\x85\u2028\u2029]")


class MailNotConfiguredError(Exception):
    """SMTP_HOST or SMTP_FROM is missing, so no message can be sent."""


class MailDeliveryError(Exception):
    """Building or sending the message failed; carries no details on purpose."""


@dataclass(frozen=True)
class ContactMessage:
    """The visitor's message, already validated."""

    vorname: str
    nachname: str
    email: str
    nachricht: str


def strip_line_breaks(value: str) -> str:
    """Replace every line break in ``value`` with a space and collapse whitespace."""
    return " ".join(_LINE_BREAKS.sub(" ", value).split())


def is_configured(settings: Settings) -> bool:
    """True when the settings name an SMTP host and a sender address."""
    return bool(settings.smtp_host) and bool(settings.smtp_from)


def build_message(contact: ContactMessage, settings: Settings) -> EmailMessage:
    """Build the e-mail to CONTACT_TO with the visitor's address as Reply-To."""
    name = strip_line_breaks(f"{contact.vorname} {contact.nachname}")
    message = EmailMessage(policy=default_policy)
    message["To"] = settings.contact_to
    message["From"] = settings.smtp_from or ""
    message["Reply-To"] = contact.email
    message["Subject"] = f"{SUBJECT_PREFIX} {name}"
    message.set_content(
        "Neue Nachricht über das Kontaktformular auf equicrew.com\n\n"
        f"Name: {name}\n"
        f"E-Mail: {contact.email}\n\n"
        "Nachricht:\n"
        f"{contact.nachricht}\n"
    )
    return message


def _deliver(message: EmailMessage, settings: Settings) -> None:
    """Open the SMTP connection, secure it, log in if configured and send once."""
    host = settings.smtp_host or ""
    port = settings.smtp_port
    tls_context = ssl.create_default_context()
    if port == SMTPS_PORT:
        connection: smtplib.SMTP = smtplib.SMTP_SSL(
            host, port, timeout=SMTP_TIMEOUT_SECONDS, context=tls_context
        )
    else:
        connection = smtplib.SMTP(host, port, timeout=SMTP_TIMEOUT_SECONDS)
    with connection as smtp:
        if port != SMTPS_PORT:
            smtp.ehlo()
            # STARTTLS is mandatory on the submission port; on any other port (a local
            # test mail server, for instance) it is used whenever the server offers it.
            if port == SUBMISSION_PORT or smtp.has_extn("starttls"):
                smtp.starttls(context=tls_context)
                smtp.ehlo()
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password or "")
        smtp.send_message(
            message,
            from_addr=settings.smtp_from,
            to_addrs=[settings.contact_to],
        )


def send_contact_message(contact: ContactMessage, settings: Settings) -> None:
    """Send the contact message exactly once to ``settings.contact_to``.

    Raises ``MailNotConfiguredError`` when SMTP is not configured and
    ``MailDeliveryError`` when building or sending the message fails.
    """
    if not is_configured(settings):
        logger.warning("contact mail not sent: SMTP is not configured")
        raise MailNotConfiguredError
    try:
        message = build_message(contact, settings)
        _deliver(message, settings)
    except (smtplib.SMTPException, OSError, ValueError):
        # Fixed text only: the exception can carry server replies or credentials.
        logger.warning("contact mail delivery failed")
        raise MailDeliveryError from None
