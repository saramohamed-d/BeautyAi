"""
How a message actually leaves the platform (Sprint 15; docs/notifications.md).

One interface, three implementations:

- **demo** — writes the message to the log and returns a fake id. The
  default for local development and tests: no account, no cost, and the
  whole scheduling path still runs.
- **smtp** — real email over SMTP, so email works with any mailbox
  provider rather than tying the platform to one vendor's API.
- **twilio** — SMS and WhatsApp through Twilio's Messages API (WhatsApp
  numbers are prefixed `whatsapp:`), the common route in Egypt.

Design decisions:

- **A provider never decides *whether* to send.** It is handed a rendered
  message and either delivers it or raises `NotificationError`; the
  service layer owns preferences, scheduling and retries.
- **Failures are ordinary.** A wrong number or a full mailbox must not
  take a request down, so everything is wrapped and reported as a
  failure on the notification row.
- Staging and production refuse to start on the demo provider (config),
  the same rule as the AI and payment providers.
"""

import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from functools import lru_cache
from typing import Protocol

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.enums import NotificationChannel

logger = get_logger(__name__)


class NotificationError(Exception):
    """The message could not be delivered. Carries what to show an admin."""


@dataclass(frozen=True)
class SendResult:
    """Which provider delivered it, and its id there."""

    provider: str
    message_id: str


@dataclass(frozen=True)
class Message:
    channel: NotificationChannel
    # Email address or phone number in international format.
    recipient: str
    subject: str | None
    body: str


class Notifier(Protocol):
    name: str

    def supports(self, channel: NotificationChannel) -> bool: ...

    async def send(self, message: Message) -> SendResult:
        """Delivers the message, or raises NotificationError."""


class DemoNotifier:
    """Local development and tests: nothing leaves the machine."""

    name = "demo"

    def supports(self, channel: NotificationChannel) -> bool:
        return True

    async def send(self, message: Message) -> SendResult:
        logger.info(
            "notification.demo_send",
            channel=message.channel.value,
            recipient=message.recipient,
            subject=message.subject,
            body=message.body[:200],
        )
        return SendResult(self.name, f"demo-{abs(hash((message.recipient, message.body))) % 10**12}")


class SmtpNotifier:
    """Email over SMTP. Any mailbox provider works; no vendor lock-in."""

    name = "smtp"

    def supports(self, channel: NotificationChannel) -> bool:
        return channel == NotificationChannel.EMAIL

    async def send(self, message: Message) -> SendResult:
        settings = get_settings()
        if message.channel != NotificationChannel.EMAIL:
            raise NotificationError(f"SMTP can't send {message.channel.value}")

        mail = EmailMessage()
        mail["From"] = settings.smtp_from
        mail["To"] = message.recipient
        mail["Subject"] = message.subject or ""
        mail.set_content(message.body)

        try:
            # Blocking, but a send takes milliseconds and the sender runs
            # outside the request path (app/notifications/cli.py).
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
                if settings.smtp_use_tls:
                    server.starttls()
                if settings.smtp_username:
                    server.login(settings.smtp_username, settings.smtp_password or "")
                server.send_message(mail)
        except (smtplib.SMTPException, OSError) as exc:
            raise NotificationError(f"SMTP error: {type(exc).__name__}") from exc
        return SendResult(self.name, mail["Message-ID"] or "sent")


class TwilioNotifier:
    """
    SMS and WhatsApp through Twilio's Messages API.

    `POST /2010-04-01/Accounts/{sid}/Messages.json`, form-encoded, with
    HTTP basic auth (account SID + auth token). WhatsApp uses the same
    endpoint with both numbers prefixed `whatsapp:`.
    """

    name = "twilio"
    BASE_URL = "https://api.twilio.com"

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.settings = get_settings()
        self._transport = transport  # tests inject a mock transport

    def supports(self, channel: NotificationChannel) -> bool:
        if channel == NotificationChannel.SMS:
            return bool(self.settings.twilio_sms_from)
        if channel == NotificationChannel.WHATSAPP:
            return bool(self.settings.twilio_whatsapp_from)
        return False

    def _numbers(self, message: Message) -> tuple[str, str]:
        if message.channel == NotificationChannel.WHATSAPP:
            return f"whatsapp:{self.settings.twilio_whatsapp_from}", f"whatsapp:{message.recipient}"
        return self.settings.twilio_sms_from or "", message.recipient

    async def send(self, message: Message) -> SendResult:
        if not self.supports(message.channel):
            raise NotificationError(f"Twilio isn't configured for {message.channel.value}")
        sender, recipient = self._numbers(message)
        # SMS has no subject; the subject line only matters for email.
        body = message.body

        try:
            async with httpx.AsyncClient(
                base_url=self.BASE_URL,
                timeout=20,
                transport=self._transport,
                auth=(self.settings.twilio_account_sid or "", self.settings.twilio_auth_token or ""),
            ) as client:
                response = await client.post(
                    f"/2010-04-01/Accounts/{self.settings.twilio_account_sid}/Messages.json",
                    data={"From": sender, "To": recipient, "Body": body},
                )
        except httpx.HTTPError as exc:
            raise NotificationError(f"Twilio unreachable: {type(exc).__name__}") from exc
        if response.status_code >= 400:
            logger.warning("twilio.rejected", status=response.status_code, body=response.text[:300])
            raise NotificationError(f"Twilio rejected the message ({response.status_code})")
        return SendResult(self.name, str(response.json().get("sid", "")))


class CompositeNotifier:
    """
    Routes each channel to the provider that handles it: email by SMTP,
    SMS and WhatsApp by Twilio. Anything unconfigured is a failure with a
    clear reason rather than a silent drop.
    """

    name = "composite"

    def __init__(self, notifiers: list[Notifier]) -> None:
        self._notifiers = notifiers

    def supports(self, channel: NotificationChannel) -> bool:
        return any(notifier.supports(channel) for notifier in self._notifiers)

    def _for(self, channel: NotificationChannel) -> Notifier:
        for notifier in self._notifiers:
            if notifier.supports(channel):
                return notifier
        raise NotificationError(f"No provider configured for {channel.value}")

    async def send(self, message: Message) -> SendResult:
        return await self._for(message.channel).send(message)


@lru_cache
def get_notifier() -> Notifier:
    """FastAPI dependency and CLI entry point. Tests may override it."""
    if get_settings().notification_provider == "demo":
        return DemoNotifier()
    return CompositeNotifier([SmtpNotifier(), TwilioNotifier()])
