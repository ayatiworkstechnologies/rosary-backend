import logging
import os
import smtplib
import ssl
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Literal

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.email_notification import (
    EmailDelivery,
    EmailNotificationBatch,
    EmailSuppression,
)
from app.models.user import User
from app.services.email_templates import (
    render_notification_email_html,
    render_notification_email_text,
)


logger = logging.getLogger(__name__)

RecipientPolicy = Literal["OPTIONAL", "OPERATIONAL"]
GENERIC_OPERATIONAL_SUBJECT = "New School Update \u2014 Rosary School"
GENERIC_OPERATIONAL_MESSAGE = (
    "Dear Parent,\n\n"
    "A new school update is available in the Rosary School Parent Portal.\n\n"
    "Please sign in to view the details securely.\n\n"
    "Rosary School Administration"
)


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
    suppressed_email_count: int = 0
    verified_email_recipient_count: int = 0
    unverified_email_recipient_count: int = 0
    test_filtered_count: int = 0

    @property
    def email_recipient_count(self) -> int:
        return len(self.recipients)


def normalize_email(value: str) -> str:
    result = validate_email(value.strip(), check_deliverability=False)
    return result.normalized.lower()


def resolve_parent_email_recipients(
    db: Session,
    parent_ids: list[int],
    *,
    policy: RecipientPolicy = "OPTIONAL",
) -> EmailRecipientPreview:
    if policy not in {"OPTIONAL", "OPERATIONAL"}:
        raise ValueError("Unsupported email recipient policy")
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

        suppressed = (
            db.query(EmailSuppression.id)
            .filter(
                EmailSuppression.email == normalized,
                EmailSuppression.is_active.is_(True),
            )
            .first()
        )
        if suppressed:
            preview.suppressed_email_count += 1
            continue

        is_verified = user.email_verified_at is not None
        if policy == "OPTIONAL" and not is_verified:
            preview.unverified_email_count += 1
            continue

        if policy == "OPTIONAL" and not user.email_notifications_enabled:
            preview.opted_out_count += 1
            continue

        if normalized in seen:
            preview.deduplicated_email_count += 1
            continue

        seen.add(normalized)
        preview.recipients.append((user.id, normalized))
        if is_verified:
            preview.verified_email_recipient_count += 1
        else:
            preview.unverified_email_recipient_count += 1

    return preview


def suppress_email_address(
    db: Session,
    email: str,
    *,
    reason: str,
    source: str,
    created_by: int | None = None,
) -> EmailSuppression:
    """Create or reactivate a normalized suppression without committing."""

    normalized = normalize_email(email)
    suppression = db.query(EmailSuppression).filter_by(email=normalized).first()
    if suppression is None:
        suppression = EmailSuppression(
            email=normalized,
            reason=reason[:100],
            source=source[:40],
            created_by=created_by,
            is_active=True,
        )
        db.add(suppression)
    else:
        suppression.reason = reason[:100]
        suppression.source = source[:40]
        suppression.is_active = True
        if created_by is not None:
            suppression.created_by = created_by
    db.flush()
    return suppression


def build_parent_email_readiness_report(db: Session) -> dict[str, int]:
    """Aggregate recipient data quality without returning personal data."""

    from app.models.parent_student import ParentStudent
    from app.models.student import Student

    active_parent_ids = {
        row[0]
        for row in db.query(User.id)
        .filter(User.role == "PARENT", User.is_active.is_(True))
        .all()
    }
    linked_active_parent_ids = {
        row[0]
        for row in db.query(ParentStudent.parent_user_id)
        .join(Student, Student.id == ParentStudent.student_id)
        .join(User, User.id == ParentStudent.parent_user_id)
        .filter(
            Student.is_active.is_(True),
            User.role == "PARENT",
            User.is_active.is_(True),
        )
        .distinct()
        .all()
    }
    inactive_linked_parents = (
        db.query(ParentStudent.parent_user_id)
        .join(User, User.id == ParentStudent.parent_user_id)
        .filter(User.role == "PARENT", User.is_active.is_(False))
        .distinct()
        .count()
    )
    active_students_without_parent = (
        db.query(Student.id)
        .outerjoin(ParentStudent, ParentStudent.student_id == Student.id)
        .filter(
            Student.is_active.is_(True),
            ParentStudent.student_id.is_(None),
        )
        .count()
    )
    inactive_students = db.query(Student.id).filter(Student.is_active.is_(False)).count()
    active_student_links = (
        db.query(ParentStudent.parent_user_id, ParentStudent.student_id)
        .join(Student, Student.id == ParentStudent.student_id)
        .join(User, User.id == ParentStudent.parent_user_id)
        .filter(
            Student.is_active.is_(True),
            User.role == "PARENT",
            User.is_active.is_(True),
        )
    )
    active_students_with_multiple_parents = (
        active_student_links.with_entities(ParentStudent.student_id)
        .group_by(ParentStudent.student_id)
        .having(func.count(func.distinct(ParentStudent.parent_user_id)) > 1)
        .count()
    )
    parents_with_multiple_active_students = (
        active_student_links.with_entities(ParentStudent.parent_user_id)
        .group_by(ParentStudent.parent_user_id)
        .having(func.count(func.distinct(ParentStudent.student_id)) > 1)
        .count()
    )
    parent_ids = sorted(linked_active_parent_ids)
    optional = resolve_parent_email_recipients(db, parent_ids, policy="OPTIONAL")
    operational = resolve_parent_email_recipients(
        db, parent_ids, policy="OPERATIONAL"
    )
    return {
        "active_parent_accounts": len(active_parent_ids),
        "active_linked_parent_accounts": len(linked_active_parent_ids),
        "active_unlinked_parent_accounts": len(
            active_parent_ids - linked_active_parent_ids
        ),
        "inactive_linked_parent_accounts": inactive_linked_parents,
        "active_students_without_parent": active_students_without_parent,
        "inactive_students": inactive_students,
        "active_students_with_multiple_parents": (
            active_students_with_multiple_parents
        ),
        "parents_with_multiple_active_students": (
            parents_with_multiple_active_students
        ),
        "optional_eligible_addresses": optional.email_recipient_count,
        "operational_address_ready": operational.email_recipient_count,
        "operational_unverified_addresses": (
            operational.unverified_email_recipient_count
        ),
        "missing_email_addresses": operational.missing_email_count,
        "invalid_email_addresses": operational.invalid_email_count,
        "suppressed_addresses": operational.suppressed_email_count,
        "duplicate_normalized_addresses": (
            operational.deduplicated_email_count
        ),
        "optional_unverified_addresses": optional.unverified_email_count,
        "optional_opted_out_addresses": optional.opted_out_count,
    }


def render_parent_email_html(
    title: str,
    message: str,
    portal_url: str,
    unsubscribe_url: str | None = None,
) -> str:
    return render_notification_email_html(
        "GENERAL", title, message, portal_url, unsubscribe_url
    )


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
        category: str = "GENERAL",
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
        email.set_content(
            render_notification_email_text(
                category, title, message, self.settings.portal_url
            )
        )
        email.add_alternative(
            render_notification_email_html(
                category,
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
        self.messages: list[dict[str, str | None]] = []

    def send(
        self,
        recipient: str,
        title: str,
        message: str,
        unsubscribe_url: str | None = None,
        unsubscribe_page_url: str | None = None,
        category: str = "GENERAL",
    ) -> str:
        if recipient in self.fail_recipients:
            raise RuntimeError("mock provider rejection")
        self.sent.append(recipient)
        self.messages.append(
            {
                "recipient": recipient,
                "title": title,
                "message": message,
                "category": category,
                "unsubscribe_url": unsubscribe_url,
            }
        )
        return f"mock-{uuid.uuid4()}"


def _safe_provider_error(
    exc: Exception,
    settings: EmailSettings,
    *sensitive_values: str,
) -> str:
    message = " ".join(str(exc).split())[:500] or exc.__class__.__name__
    for secret in (
        settings.smtp_password,
        settings.smtp_username,
        *sensitive_values,
    ):
        if secret:
            message = message.replace(secret, "[redacted]")
    return message


def _is_permanent_delivery_error(exc: Exception) -> bool:
    """Return true only for SMTP failures that cannot succeed on retry."""

    if isinstance(
        exc,
        (
            smtplib.SMTPAuthenticationError,
            smtplib.SMTPRecipientsRefused,
            smtplib.SMTPSenderRefused,
            smtplib.SMTPNotSupportedError,
        ),
    ):
        return True
    if isinstance(exc, smtplib.SMTPResponseException):
        return 500 <= int(exc.smtp_code) <= 599
    return False


def _delivery_recipient_is_eligible(
    db: Session,
    delivery: EmailDelivery,
    batch: EmailNotificationBatch,
) -> tuple[bool, User | None]:
    """Re-check policy, suppression and account ownership before delivery."""

    parent = db.get(User, delivery.parent_user_id)
    if (
        parent is None
        or parent.role != "PARENT"
        or not parent.is_active
        or not parent.email
    ):
        return False, parent
    try:
        if normalize_email(parent.email) != delivery.email:
            return False, parent
    except EmailNotValidError:
        return False, parent

    if (
        db.query(EmailSuppression.id)
        .filter(
            EmailSuppression.email == delivery.email,
            EmailSuppression.is_active.is_(True),
        )
        .first()
    ):
        return False, parent

    from app.services.automatic_email_service import (
        admin_test_recipient_allowed,
        automatic_event_delivery_enabled,
        automatic_test_recipient_allowed,
        operational_event_enabled,
    )

    is_automatic = batch.target_type == f"AUTOMATIC_{batch.category}"
    if batch.target_type.startswith("AUTOMATIC_") and not is_automatic:
        return False, parent
    if is_automatic and not (
        automatic_event_delivery_enabled(batch.category)
        and automatic_test_recipient_allowed(batch.category, delivery.email)
    ):
        return False, parent
    if not is_automatic and not admin_test_recipient_allowed(delivery.email):
        return False, parent

    if batch.recipient_policy == "OPTIONAL":
        return bool(
            parent.email_verified_at is not None
            and parent.email_notifications_enabled
        ), parent

    if batch.recipient_policy != "OPERATIONAL":
        return False, parent

    # Operational delivery is limited to automatic, explicitly approved
    # categories. Approval is re-evaluated on every attempt.
    return operational_event_enabled(batch.category), parent


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
        if delivery.attempt_count >= delivery.max_attempts:
            delivery.status = "FAILED"
            delivery.next_attempt_at = None
            delivery.last_error = "Worker interrupted after maximum attempts"
        else:
            delivery.status = "RETRY"
            delivery.next_attempt_at = now
            delivery.last_error = "Recovered after interrupted worker attempt"
        _refresh_batch_status(db, delivery.batch_id, now)
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
            if batch is None:
                raise RuntimeError("Email batch no longer exists")
            eligible, parent = _delivery_recipient_is_eligible(db, delivery, batch)
            if not eligible:
                delivery.status = "FAILED"
                delivery.next_attempt_at = None
                delivery.last_error = "Recipient is no longer eligible for delivery"
                result["failed"] += 1
                result["processed"] += 1
                _refresh_batch_status(db, delivery.batch_id, now)
                db.commit()
                continue

            delivery_unsubscribe_url = None
            delivery_unsubscribe_page_url = None
            if parent and batch.recipient_policy == "OPTIONAL":
                from app.services.parent_email_preferences_service import (
                    unsubscribe_urls,
                )

                (
                    delivery_unsubscribe_url,
                    delivery_unsubscribe_page_url,
                ) = unsubscribe_urls(parent)
            title = batch.title
            message = batch.message
            if (
                batch.recipient_policy == "OPERATIONAL"
                and parent
                and parent.email_verified_at is None
            ):
                title = GENERIC_OPERATIONAL_SUBJECT
                message = GENERIC_OPERATIONAL_MESSAGE
            provider_id = transport.send(
                delivery.email,
                title,
                message,
                unsubscribe_url=delivery_unsubscribe_url,
                unsubscribe_page_url=delivery_unsubscribe_page_url,
                category=batch.category,
            )
            delivery.status = "SENT"
            delivery.provider_message_id = provider_id
            delivery.last_error = None
            delivery.sent_at = now
            result["sent"] += 1
        except Exception as exc:  # provider failures are persisted, not raised
            delivery.last_error = _safe_provider_error(
                exc,
                settings,
                delivery.email,
            )
            if (
                _is_permanent_delivery_error(exc)
                or delivery.attempt_count >= delivery.max_attempts
            ):
                delivery.status = "FAILED"
                delivery.next_attempt_at = None
                result["failed"] += 1
                if isinstance(exc, smtplib.SMTPRecipientsRefused):
                    suppress_email_address(
                        db,
                        delivery.email,
                        reason="Permanent recipient rejection",
                        source="SMTP_RECIPIENT_REFUSED",
                    )
            else:
                delivery.status = "RETRY"
                backoff = settings.retry_base_seconds * (
                    2 ** (delivery.attempt_count - 1)
                )
                delivery.next_attempt_at = now + timedelta(seconds=backoff)
                result["retried"] += 1
            logger.warning(
                "email_delivery_failed %s",
                {"delivery_id": delivery.id, "attempt": delivery.attempt_count,
                 "status": delivery.status, "error": delivery.last_error},
            )

        result["processed"] += 1
        _refresh_batch_status(db, delivery.batch_id, now)
        db.commit()
        if delay:
            time.sleep(delay)

    return result
