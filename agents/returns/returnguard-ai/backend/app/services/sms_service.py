"""SMS provider abstraction.

- MockProvider: local development and automated tests only. Captures messages
  in an internal store so pytest fixtures can assert delivery. It is never
  exposed through any HTTP route; OTP values must not leak via a public API.
- TwilioProvider: real HTTP delivery using the Twilio REST API. Requires
  TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / TWILIO_FROM_NUMBER.

Production refuses to start when SMS_PROVIDER=mock (enforced in app lifespan),
and real-provider failures raise instead of silently falling back to mock.
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

import httpx

from app.core.config import settings

logger = logging.getLogger("returnsguard.sms")


class SMSProviderError(Exception):
    """Raised when a real provider fails to deliver a message."""


class SMSProvider(Protocol):
    name: str

    def send(self, to_phone: str, body: str) -> None: ...

    def health(self) -> dict: ...


def _now() -> datetime:
    return datetime.now(timezone.utc)


def mask_phone(phone: str) -> str:
    """+15551234567 -> +1******4567 (last 4 visible)."""
    digits = phone.strip()
    if len(digits) <= 4:
        return "****"
    keep = digits[-4:]
    prefix = "+" if digits.startswith("+") else ""
    return f"{prefix}{'*' * (len(digits) - 4)}{keep}"


@dataclass
class CapturedMessage:
    to_phone: str
    body: str
    sent_at: datetime = field(default_factory=_now)


class MockSMSProvider:
    """In-memory message capture for development and tests.

    The captured store is intentionally process-local and only reachable from
    server-side Python (tests / dev tooling), never from an HTTP endpoint.
    """

    name = "mock"

    def __init__(self) -> None:
        self._messages: list[CapturedMessage] = []
        self._lock = threading.Lock()

    def send(self, to_phone: str, body: str) -> None:
        with self._lock:
            self._messages.append(CapturedMessage(to_phone=to_phone, body=body))
        # Log only masked destination and length — never message contents,
        # because the body contains an OTP.
        logger.info("mock SMS queued to=%s chars=%d", mask_phone(to_phone), len(body))
        # Optional local-dev outbox mirror (settings.mock_sms_outbox) so a
        # developer can read codes during manual UI testing. The mock provider
        # cannot exist in production (startup refuses it), so this file sink
        # has no production surface, and no HTTP endpoint exposes it.
        outbox = settings.mock_sms_outbox.strip()
        if outbox:
            try:
                from pathlib import Path

                p = Path(outbox)
                p.parent.mkdir(parents=True, exist_ok=True)
                with p.open("a", encoding="utf-8") as fh:
                    fh.write(f"{to_phone}\t{_now().isoformat()}\t{body}\n")
            except OSError:  # pragma: no cover - dev convenience only
                logger.warning("could not write mock SMS outbox file")

    def health(self) -> dict:
        with self._lock:
            count = len(self._messages)
        return {"provider": self.name, "captured_messages": count, "mode": "local-capture"}

    # --- test fixture access (server-side only) ---------------------------
    def messages_for(self, phone: str) -> list[CapturedMessage]:
        with self._lock:
            return [m for m in self._messages if m.to_phone == phone]

    def last_for(self, phone: str) -> CapturedMessage | None:
        msgs = self.messages_for(phone)
        return msgs[-1] if msgs else None

    def clear(self) -> None:
        with self._lock:
            self._messages.clear()


class TwilioProvider:
    """Real SMS delivery through Twilio's REST API."""

    name = "twilio"

    def __init__(self, account_sid: str, auth_token: str, from_number: str) -> None:
        if not (account_sid and auth_token and from_number):
            raise ValueError("Twilio provider requires TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN and TWILIO_FROM_NUMBER")
        self._account_sid = account_sid
        self._auth_token = auth_token
        self._from = from_number

    def send(self, to_phone: str, body: str) -> None:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{self._account_sid}/Messages.json"
        try:
            response = httpx.post(
                url,
                data={"To": to_phone, "From": self._from, "Body": body},
                auth=(self._account_sid, self._auth_token),
                timeout=15.0,
            )
        except httpx.HTTPError as exc:
            logger.error("Twilio request failed to=%s error=%s", mask_phone(to_phone), type(exc).__name__)
            raise SMSProviderError("SMS provider request failed") from exc
        if response.status_code >= 400:
            logger.error("Twilio rejected message to=%s status=%d", mask_phone(to_phone), response.status_code)
            raise SMSProviderError(f"SMS provider returned status {response.status_code}")
        logger.info("Twilio message queued to=%s", mask_phone(to_phone))

    def health(self) -> dict:
        return {"provider": self.name, "mode": "live"}


_provider: SMSProvider | None = None
_provider_lock = threading.Lock()


def get_sms_provider() -> SMSProvider:
    global _provider
    if _provider is not None:
        return _provider
    with _provider_lock:
        if _provider is None:
            if settings.sms_provider == "mock":
                _provider = MockSMSProvider()
            else:
                _provider = TwilioProvider(
                    settings.twilio_account_sid,
                    settings.twilio_auth_token,
                    settings.twilio_from_number,
                )
    return _provider


def reset_sms_provider() -> None:
    """Test helper to rebuild the provider after settings changes."""
    global _provider
    with _provider_lock:
        _provider = None
