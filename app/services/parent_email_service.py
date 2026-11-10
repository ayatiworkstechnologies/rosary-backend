import html
import logging
import os
import smtplib
import ssl
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.email_notification import EmailDelivery, EmailNotificationBatch
from app.models.user import User


logger = logging.getLogger(__name__)


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int, minimum: int = 0) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except ValueError:
        return default


@dataclass(frozen=True)
class EmailSettings:
    enabled: bool
    transport: str
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    smtp_from_email: str
    smtp_from_name: str
    smtp_use_tls: bool
    smtp_use_ssl: bool
    smtp_message_id_domain: str
    batch_size: int
    rate_limit_per_second: int
    max_attempts: int
    retry_base_seconds: int
    poll_seconds: int
    processing_timeout_seconds: int
    fee_reminders_enabled: bool
    portal_url: str

    @property
    def provider_ready(self) -> bool:
        if self.transport == "mock":
            return True
        if self.transport == "smtp":
            return bool(
                self.smtp_host
                and self.smtp_port
                and self.smtp_from_email
                and self.smtp_username
                and self.smtp_password
            )
        return False


def get_email_settings() -> EmailSettings:
    return EmailSettings(
        enabled=_bool_env("EMAIL_NOTIFICATIONS_ENABLED", False),
        transport=os.getenv("EMAIL_TRANSPORT", "smtp").strip().lower(),
        smtp_host=os.getenv("SMTP_HOST", "").strip(),
        smtp_port=_int_env("SMTP_PORT", 587, 1),
        smtp_username=os.getenv("SMTP_USERNAME", "").strip(),
        smtp_password=os.getenv("SMTP_PASSWORD", ""),
        smtp_from_email=os.getenv("SMTP_FROM_EMAIL", "").strip(),
        smtp_from_name=os.getenv("SMTP_FROM_NAME", "Rosary School").strip(),
        smtp_use_tls=_bool_env("SMTP_USE_TLS", True),
        smtp_use_ssl=_bool_env("SMTP_USE_SSL", False),
        batch_size=_int_env("EMAIL_BATCH_SIZE", 50, 1),
        rate_limit_per_second=_int_env("EMAIL_RATE_LIMIT_PER_SECOND", 5, 0),
        max_attempts=_int_env("EMAIL_MAX_ATTEMPTS", 3, 1),
        retry_base_seconds=_int_env("EMAIL_RETRY_BASE_SECONDS", 60, 1),
        poll_seconds=_int_env("EMAIL_WORKER_POLL_SECONDS", 10, 1),
        processing_timeout_seconds=_int_env(
            "EMAIL_PROCESSING_TIMEOUT_SECONDS", 900, 60
        ),
        fee_reminders_enabled=_bool_env("EMAIL_FEE_REMINDERS_ENABLED", False),
        smtp_message_id_domain=os.getenv(
            "SMTP_MESSAGE_ID_DOMAIN",
            os.getenv("SMTP_FROM_EMAIL", "localhost").split("@")[-1]
            if "@" in os.getenv("SMTP_FROM_EMAIL", "")
            else "localhost",
        ),
        portal_url=os.getenv(
            "SCHOOL_PORTAL_URL", "https://rosary-frontend.vercel.app"
        ).rstrip("/"),
    )


@dataclass
class EmailRecipientPreview:
    parent_ids: list[int]
    recipients: list[tuple[int, str]] = field(default_factory=list)
    missing_email_count: int = 0
    invalid_email_count: int = 0
    unverified_email_count: int = 0
    opted_out_count: int = 0
    deduplicated_email_count: int = 0

    @property
    def email_recipient_count(self) -> int:
        return len(self.recipients)


def normalize_email(value: str) -> str:
    result = validate_email(value.strip(), check_deliverability=False)
    return result.normalized.lower()


def resolve_parent_email_recipients(
    db: Session,
    parent_ids: list[int],
) -> EmailRecipientPreview:
    preview = EmailRecipientPreview(parent_ids=parent_ids)
    if not parent_ids:
        return preview

    users = (
        db.query(User)
        .filter(
            User.id.in_(parent_ids),
            User.role == "PARENT",
            User.is_active.is_(True),
        )
        .order_by(User.id.asc())
        .all()
    )

    seen: set[str] = set()
    for user in users:
        if not user.email or not user.email.strip():
            preview.missing_email_count += 1
            continue

        try:
            normalized = normalize_email(user.email)
        except EmailNotValidError:
            preview.invalid_email_count += 1
            continue

        if user.email_verified_at is None:
            preview.unverified_email_count += 1
            continue

        if not user.email_notifications_enabled:
            preview.opted_out_count += 1
            continue

        if normalized in seen:
            preview.deduplicated_email_count += 1
            continue

        seen.add(normalized)
        preview.recipients.append((user.id, normalized))

    return preview


def render_parent_email_html(
    title: str,
    message: str,
    portal_url: str,
    unsubscribe_url: str | None = None,
) -> str:
    safe_title = html.escape(title)
    safe_message = "<br>".join(html.escape(message).splitlines())
    safe_portal_url = html.escape(portal_url, quote=True)
    unsubscribe_html = ""
    if unsubscribe_url:
        safe_unsubscribe_url = html.escape(unsubscribe_url, quote=True)
        unsubscribe_html = (
            f'<br><a href="{safe_unsubscribe_url}" '
            'style="color:#475569">Unsubscribe from email notifications</a>'
        )
    return f"""<!doctype html>
<html lang="en">
  <body style="margin:0;background:#f3f7fe;font-family:Arial,sans-serif;color:#10233f">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="padding:24px 12px">
      <tr><td align="center">
        <table role="presentation" width="600" cellspacing="0" cellpadding="0" style="max-width:600px;background:#fff;border:1px solid #cfe0f5;border-radius:16px;overflow:hidden">
          <tr><td style="background:#0b3a67;padding:22px 28px;color:#fff">
            <div style="font-size:22px;font-weight:700">Rosary School</div>
            <div style="font-size:12px;opacity:.85;margin-top:4px">Parent notification</div>
          </td></tr>
          <tr><td style="padding:30px 28px">
            <h1 style="font-size:22px;margin:0 0 18px">{safe_title}</h1>
            <div style="font-size:15px;line-height:1.65">{safe_message}</div>
            <p style="margin:26px 0 0">
              <a href="{safe_portal_url}/login" style="display:inline-block;background:#2563eb;color:#fff;text-decoration:none;padding:12px 18px;border-radius:10px;font-weight:700">Open Parent Portal</a>
            </p>
          </td></tr>
          <tr><td style="padding:16px 28px;background:#f8fafc;color:#64748b;font-size:12px">
            This message was sent by Rosary School. Please do not reply with sensitive student information.
            {unsubscribe_html}
          </td></tr>
        </table>
      </td></tr>
    </table>
  </body>
</html>"""


class SMTPEmailTransport:
    def __init__(self, settings: EmailSettings):
        self.settings = settings

    def send(
        self,
        recipient: str,
        title: str,
        message: str,
        unsubscribe_url: str | None = None,
        unsubscribe_page_url: str | None = None,
    ) -> str:
        email = EmailMessage()
        email["Subject"] = title
        email["From"] = (
            f"{self.settings.smtp_from_name} <{self.settings.smtp_from_email}>"
        )
        email["To"] = recipient
        message_id_domain = (
            self.settings.smtp_message_id_domain or "localhost"
        )
        email["Message-ID"] = f"<{uuid.uuid4()}@{message_id_domain}>"
        if unsubscribe_url:
            email["List-Unsubscribe"] = f"<{unsubscribe_url}>"
            email["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
        email.set_content(message)
        email.add_alternative(
            render_parent_email_html(
                title,
                message,
                self.settings.portal_url,
                unsubscribe_page_url or unsubscribe_url,
            ),
            subtype="html",
        )

        if self.settings.smtp_use_ssl:
            client = smtplib.SMTP_SSL(
                self.settings.smtp_host,
                self.settings.smtp_port,
                timeout=30,
                context=ssl.create_default_context(),
            )
        else:
            client = smtplib.SMTP(
                self.settings.smtp_host,
                self.settings.smtp_port,
                timeout=30,
            )

        with client:
            if self.settings.smtp_use_tls and not self.settings.smtp_use_ssl:
                client.starttls(context=ssl.create_default_context())
            if self.settings.smtp_username:
                client.login(
                    self.settings.smtp_username,
                    self.settings.smtp_password,
                )
            client.send_message(email)

        return email["Message-ID"]


class MockEmailTransport:
    def __init__(self, fail_recipients: set[str] | None = None):
        self.fail_recipients = fail_recipients or set()
        self.sent: list[str] = []

    def send(
        self,
        recipient: str,
        title: str,
        message: str,
        unsubscribe_url: str | None = None,
        unsubscribe_page_url: str | None = None,
    ) -> str:
        if recipient in self.fail_recipients:
            raise RuntimeError("mock provider rejection")
        self.sent.append(recipient)
        return f"mock-{uuid.uuid4()}"


def _safe_provider_error(exc: Exception, settings: EmailSettings) -> str:
    message = " ".join(str(exc).split())[:500] or exc.__class__.__name__
    for secret in (settings.smtp_password, settings.smtp_username):
        if secret:
            message = message.replace(secret, "[redacted]")
    return message


def mask_email(value: str) -> str:
    local, _, domain = value.partition("@")
    if not domain:
        return "invalid"
    visible = local[:1]
    return f"{visible}{'*' * max(3, len(local) - 1)}@{domain}"


def _refresh_batch_status(db: Session, batch_id: int, now: datetime) -> None:
    # Persist the delivery's latest state before aggregating it. This matters
    # for SQLite row-only queries and is also explicit/cheap on MySQL.
    db.flush()
    batch = db.query(EmailNotificationBatch).filter_by(id=batch_id).first()
    if not batch:
        return
    deliveries = db.query(EmailDelivery.status).filter_by(batch_id=batch_id).all()
    statuses = [row[0] for row in deliveries]
    if not statuses:
        batch.status = "COMPLETED" if batch.send_in_app else "NO_RECIPIENTS"
        batch.completed_at = now
    elif all(status == "SENT" for status in statuses):
        batch.status = "COMPLETED"
        batch.completed_at = now
    elif all(status in {"SENT", "FAILED"} for status in statuses):
        batch.status = "COMPLETED_WITH_FAILURES"
        batch.completed_at = now
    elif any(status == "PROCESSING" for status in statuses):
        batch.status = "PROCESSING"
    else:
        batch.status = "QUEUED"


def process_email_queue(
    db: Session,
    transport=None,
    *,
    now: datetime | None = None,
    limit: int | None = None,
) -> dict:
    settings = get_email_settings()
    if not settings.enabled or not settings.provider_ready:
        return {"processed": 0, "sent": 0, "failed": 0, "retried": 0}

    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    stale_before = now - timedelta(seconds=settings.processing_timeout_seconds)
    stale = (
        db.query(EmailDelivery)
        .filter(
            EmailDelivery.status == "PROCESSING",
            EmailDelivery.updated_at < stale_before,
        )
        .all()
    )
    for delivery in stale:
        delivery.status = "RETRY"
        delivery.next_attempt_at = now
    if stale:
        db.commit()

    effective_limit = limit or settings.batch_size
    # Claim a batch inside one transaction. MySQL 8 uses SKIP LOCKED so
    # multiple supervised workers cannot select and send the same delivery.
    # SQLite does not support SKIP LOCKED; use a plain lock there since the
    # test/E2E environment is single-process.
    use_skip_locked = db.bind.dialect.name != "sqlite"
    deliveries = (
        db.query(EmailDelivery)
        .filter(
            EmailDelivery.status.in_(["QUEUED", "RETRY"]),
            or_(
                EmailDelivery.next_attempt_at.is_(None),
                EmailDelivery.next_attempt_at <= now,
            ),
        )
        .order_by(EmailDelivery.id.asc())
        .with_for_update(skip_locked=use_skip_locked)
        .limit(effective_limit)
        .all()
    )
    if not deliveries:
        return {"processed": 0, "sent": 0, "failed": 0, "retried": 0}

    claimed_ids = []
    for delivery in deliveries:
        delivery.status = "PROCESSING"
        delivery.attempt_count += 1
        claimed_ids.append(delivery.id)
    db.commit()

    if transport is None:
        transport = (
            MockEmailTransport()
            if settings.transport == "mock"
            else SMTPEmailTransport(settings)
        )

    result = {"processed": 0, "sent": 0, "failed": 0, "retried": 0}
    delay = (
        1 / settings.rate_limit_per_second
        if settings.rate_limit_per_second > 0
        else 0
    )

    for delivery_id in claimed_ids:
        delivery = db.get(EmailDelivery, delivery_id)
        if delivery is None or delivery.status != "PROCESSING":
            continue

        batch = (
            db.query(EmailNotificationBatch)
            .filter(EmailNotificationBatch.id == delivery.batch_id)
            .first()
        )
        try:
            parent = db.get(User, delivery.parent_user_id)
            delivery_unsubscribe_url = None
            if parent and parent.email:
                from app.services.parent_email_preferences_service import (
                    unsubscribe_urls,
                )

                (
                    delivery_unsubscribe_url,
                    delivery_unsubscribe_page_url,
                ) = unsubscribe_urls(parent)
            else:
                delivery_unsubscribe_page_url = None
            provider_id = transport.send(
                delivery.email,
                batch.title,
                batch.message,
                unsubscribe_url=delivery_unsubscribe_url,
                unsubscribe_page_url=delivery_unsubscribe_page_url,
            )
            delivery.status = "SENT"
            delivery.provider_message_id = provider_id
            delivery.last_error = None
            delivery.sent_at = now
            result["sent"] += 1
        except Exception as exc:  # provider failures are persisted, not raised
            delivery.last_error = _safe_provider_error(exc, settings)
            if delivery.attempt_count >= delivery.max_attempts:
                delivery.status = "FAILED"
                delivery.next_attempt_at = None
                result["failed"] += 1
            else:
                delivery.status = "RETRY"
                backoff = settings.retry_base_seconds * (
                    2 ** (delivery.attempt_count - 1)
                )
                delivery.next_attempt_at = now + timedelta(seconds=backoff)
                result["retried"] += 1
            logger.warning(
                "Parent email delivery failed delivery_id=%s attempt=%s error=%s",
                delivery.id,
                delivery.attempt_count,
                delivery.last_error,
            )

        result["processed"] += 1
        _refresh_batch_status(db, delivery.batch_id, now)
        db.commit()
        if delay:
            time.sleep(delay)

    return result
