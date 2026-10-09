"""Password hashing and token utilities.

Password hashing uses PBKDF2-HMAC-SHA256 from the Python standard library
(600,000 iterations per OWASP 2023 guidance) so the project has no native
hashing dependency that can break on any platform.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from app.core.config import settings

PBKDF2_ITERATIONS = 600_000


# --------------------------------------------------------------------------
# Password hashing
# --------------------------------------------------------------------------
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt_b64, digest_b64 = stored.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
        return hmac.compare_digest(candidate, expected)
    except (ValueError, TypeError):
        return False


# --------------------------------------------------------------------------
# Secret token helpers (QR tokens, OTP codes)
# --------------------------------------------------------------------------
def generate_high_entropy_token(nbytes: int = 32) -> str:
    """URL-safe cryptographically secure token."""
    return secrets.token_urlsafe(nbytes)


def hash_token(token: str) -> str:
    """One-way hash for storing opaque tokens (QR secrets) at rest."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_otp_code(digits: int = 6) -> str:
    """Cryptographically secure numeric OTP (no leading-zero bias)."""
    return f"{secrets.randbelow(10 ** digits):0{digits}d}"


def hash_otp(code: str) -> str:
    """Keyed hash of an OTP; the raw code is never persisted."""
    key = settings.secret_key.encode("utf-8")
    return hmac.new(key, code.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_otp_hash(code: str, digest: str) -> bool:
    return hmac.compare_digest(hash_otp(code), digest)


# --------------------------------------------------------------------------
# JWT helpers (purpose-scoped)
# --------------------------------------------------------------------------
def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(user_id: str, role: str) -> str:
    now = _utcnow()
    payload = {
        "sub": user_id,
        "role": role,
        "purpose": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
        "jti": secrets.token_hex(8),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def create_scan_token(return_id: str, agent_id: str, qr_auth_id: str) -> str:
    """Short-lived token proving a successful QR scan; carries the binding to
    one specific return + agent + QR authorization so the raw QR secret is not
    needed again."""
    now = _utcnow()
    payload = {
        "sub": agent_id,
        "rid": return_id,
        "qid": qr_auth_id,
        "purpose": "scan",
        "iat": now,
        "exp": now + timedelta(minutes=15),
        "jti": secrets.token_hex(8),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def create_inspection_token(return_id: str, agent_id: str, otp_challenge_id: str) -> str:
    """Issued only after successful OTP verification; authorizes image upload
    and inspection reads for that return."""
    now = _utcnow()
    payload = {
        "sub": agent_id,
        "rid": return_id,
        "cid": otp_challenge_id,
        "purpose": "inspection",
        "iat": now,
        "exp": now + timedelta(minutes=settings.inspection_token_expire_minutes),
        "jti": secrets.token_hex(8),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_token(token: str, expected_purpose: str) -> dict[str, Any]:
    """Decode and validate a JWT, ensuring it was issued for the expected purpose.

    Raises jwt.PyJWTError on any failure; callers translate to HTTP errors.
    """
    payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    if payload.get("purpose") != expected_purpose:
        raise jwt.InvalidTokenError("wrong token purpose")
    return payload
