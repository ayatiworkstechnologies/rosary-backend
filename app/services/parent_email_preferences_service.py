import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import jwt
from jwt.exceptions import InvalidTokenError
from sqlalchemy.orm import Session

from app.models.email_verification import EmailVerificationToken
from app.models.user import User
from app.services.parent_email_service import (
    MockEmailTransport,
    SMTPEmailTransport,
    get_email_settings,
    normalize_email,
)


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _positive_int_env(name: str, default: int, minimum: int = 1) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def verification_email_enabled() -> bool:
    """A narrow gate independent from automatic/bulk notification delivery."""

    return _bool_env("EMAIL_VERIFICATION_ENABLED", False)


def verification_rate_limit() -> tuple[int, int, int]:
    return (
        _positive_int_env("EMAIL_VERIFICATION_MAX_REQUESTS", 3),
        _positive_int_env("EMAIL_VERIFICATION_WINDOW_SECONDS", 3600, 60),
        _positive_int_env("EMAIL_VERIFICATION_COOLDOWN_SECONDS", 60),
    )


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verification_expiry_hours() -> int:
    try:
        return max(1, int(os.getenv("EMAIL_VERIFICATION_EXPIRE_HOURS", "24")))
    except ValueError:
        return 24


def create_verification_token(db: Session, user: User) -> str:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    raw_token = secrets.token_urlsafe(32)
    email = normalize_email(user.email)

    # Only the newest token is valid. Keeping used rows provides a small audit
    # trail while invalidating every outstanding unused token for the account.
    db.query(EmailVerificationToken).filter(
        EmailVerificationToken.user_id == user.id,
        EmailVerificationToken.used_at.is_(None),
    ).update({"used_at": now}, synchronize_session=False)
    db.add(
        EmailVerificationToken(
            user_id=user.id,
            token_hash=token_digest(raw_token),
            email=email,
            expires_at=now + timedelta(hours=verification_expiry_hours()),
        )
    )
    db.commit()
    return raw_token


def send_verification_email(recipient: str, raw_token: str, transport=None) -> str:
    settings = get_email_settings()
    if not verification_email_enabled() or not settings.provider_ready:
        raise RuntimeError("Email provider is unavailable")
    if transport is None:
        transport = (
            MockEmailTransport()
            if settings.transport == "mock"
            else SMTPEmailTransport(settings)
        )
    verification_url = (
        f"{settings.portal_url}/verify-email?token={quote(raw_token, safe='')}"
    )
    return transport.send(
        recipient,
        "Verify your Rosary School email",
        "Verify your email address to receive parent notifications.\n\n"
        f"This link expires in {verification_expiry_hours()} hours:\n"
        f"{verification_url}\n\n"
        "If you did not request this, you can ignore this email.",
        category="EMAIL_VERIFICATION",
    )


def create_unsubscribe_token(user: User) -> str:
    secret_key = os.getenv("SECRET_KEY")
    if not secret_key:
        raise RuntimeError("SECRET_KEY is not configured")
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "email": normalize_email(user.email),
        "purpose": "parent-email-unsubscribe",
        "iat": now,
        # Long-lived enough for older notification emails, while an email
        # change immediately invalidates it during endpoint validation.
        "exp": now + timedelta(days=365),
    }
    return jwt.encode(
        payload,
        secret_key,
        algorithm=os.getenv("ALGORITHM", "HS256"),
    )


def decode_unsubscribe_token(token: str) -> tuple[int, str]:
    secret_key = os.getenv("SECRET_KEY")
    if not secret_key:
        raise InvalidTokenError("SECRET_KEY is not configured")
    payload = jwt.decode(
        token,
        secret_key,
        algorithms=[os.getenv("ALGORITHM", "HS256")],
    )
    if payload.get("purpose") != "parent-email-unsubscribe":
        raise InvalidTokenError("Invalid token purpose")
    try:
        user_id = int(payload["sub"])
        email = str(payload["email"])
    except (KeyError, TypeError, ValueError) as exc:
        raise InvalidTokenError("Invalid token payload") from exc
    return user_id, email


def unsubscribe_urls(user: User) -> tuple[str, str]:
    token = create_unsubscribe_token(user)
    api_url = os.getenv("PUBLIC_API_URL", "http://localhost:8000").rstrip("/")
    portal_url = get_email_settings().portal_url
    one_click_url = (
        f"{api_url}/api/v1/parent/email-preferences/unsubscribe"
        f"?token={quote(token, safe='')}"
    )
    browser_url = f"{portal_url}/unsubscribe?token={quote(token, safe='')}"
    return one_click_url, browser_url
