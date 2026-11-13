"""Transactional email-outbox helpers for automatic business events.

The functions in this module only add rows to the caller's SQLAlchemy
transaction. They never commit and never contact SMTP. This keeps the business
record, in-app notifications, and email outbox consistent while the existing
worker remains responsible for delivery.
"""

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.email_notification import EmailDelivery, EmailNotificationBatch
from app.models.parent_student import ParentStudent
from app.models.student import Student
from app.models.user import User
from app.services.parent_email_service import (
    EmailRecipientPreview,
    get_email_settings,
    normalize_email,
    resolve_parent_email_recipients,
)


EVENT_FLAGS = {
    "HOMEWORK": "EMAIL_HOMEWORK_NOTIFICATIONS_ENABLED",
    "ATTENDANCE": "EMAIL_ATTENDANCE_NOTIFICATIONS_ENABLED",
    "RESULTS": "EMAIL_RESULTS_NOTIFICATIONS_ENABLED",
    "CIRCULAR": "EMAIL_CIRCULAR_NOTIFICATIONS_ENABLED",
    "EVENT": "EMAIL_EVENT_NOTIFICATIONS_ENABLED",
    "FEE_PAYMENT": "EMAIL_FEE_PAYMENT_NOTIFICATIONS_ENABLED",
}

EVENT_TEST_ALLOWLISTS = {
    "HOMEWORK": "EMAIL_HOMEWORK_TEST_RECIPIENTS",
    "ATTENDANCE": "EMAIL_ATTENDANCE_TEST_RECIPIENTS",
    "RESULTS": "EMAIL_RESULTS_TEST_RECIPIENTS",
    "CIRCULAR": "EMAIL_CIRCULAR_TEST_RECIPIENTS",
    "EVENT": "EMAIL_EVENT_TEST_RECIPIENTS",
    "FEE_PAYMENT": "EMAIL_FEE_PAYMENT_TEST_RECIPIENTS",
}

OPERATIONAL_EVENT_FLAGS = {
    category: f"EMAIL_{category}_OPERATIONAL_ENABLED" for category in EVENT_FLAGS
}


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def automatic_event_enabled(event_type: str) -> bool:
    flag = EVENT_FLAGS.get(event_type.upper())
    return bool(flag and _bool_env(flag, False))


def automatic_event_delivery_enabled(event_type: str) -> bool:
    return get_email_settings().enabled and automatic_event_enabled(event_type)


def operational_event_enabled(event_type: str) -> bool:
    """Default-deny approval for one automatic operational category."""

    normalized = event_type.strip().upper()
    flag = OPERATIONAL_EVENT_FLAGS.get(normalized)
    return bool(
        flag
        and _bool_env("EMAIL_OPERATIONAL_NOTIFICATIONS_ENABLED", False)
        and _bool_env(flag, False)
    )


def operational_notifications_enabled() -> bool:
    return _bool_env("EMAIL_OPERATIONAL_NOTIFICATIONS_ENABLED", False)


def automatic_test_mode_enabled() -> bool:
    return _bool_env("EMAIL_AUTOMATION_TEST_MODE", False)


def _test_allowlist(event_type: str) -> set[str]:
    env_name = EVENT_TEST_ALLOWLISTS.get(event_type.upper(), "")
    raw_values = os.getenv(env_name, "") if env_name else ""
    allowlist: set[str] = set()
    for value in raw_values.split(","):
        value = value.strip()
        if not value:
            continue
        try:
            allowlist.add(normalize_email(value))
        except Exception:
            # Invalid allowlist entries grant no delivery permission.
            continue
    return allowlist


def automatic_test_recipient_allowed(event_type: str, email: str) -> bool:
    """Re-check test-mode restriction at queue and worker time."""

    if not _bool_env("EMAIL_AUTOMATION_TEST_MODE", False):
        return True
    try:
        normalized = normalize_email(email)
    except Exception:
        return False
    return normalized in _test_allowlist(event_type)


def admin_test_recipient_allowed(email: str) -> bool:
    """Fail closed for manual admin email while restricted test mode is on."""

    if not _bool_env("EMAIL_AUTOMATION_TEST_MODE", False):
        return True
    try:
        normalized = normalize_email(email)
    except Exception:
        return False
    raw = os.getenv("EMAIL_ADMIN_TEST_RECIPIENTS", "")
    allowed: set[str] = set()
    for value in raw.split(","):
        try:
            if value.strip():
                allowed.add(normalize_email(value))
        except Exception:
            continue
    return normalized in allowed


def _apply_test_mode(
    preview: EmailRecipientPreview,
    event_type: str,
) -> tuple[EmailRecipientPreview, int]:
    if not _bool_env("EMAIL_AUTOMATION_TEST_MODE", False):
        return preview, 0

    # Fail closed: an enabled test mode with a blank/invalid allowlist queues
    # no delivery. The allowlist only narrows already eligible recipients; it
    # never supplies identities or bypasses verification/preferences.
    retained = [
        item
        for item in preview.recipients
        if automatic_test_recipient_allowed(event_type, item[1])
    ]
    filtered_count = len(preview.recipients) - len(retained)
    preview.recipients = retained
    return preview, filtered_count


@dataclass(frozen=True)
class AutomaticEmailQueueResult:
    enabled: bool
    batch_id: int | None = None
    queued_count: int = 0
    test_filtered_count: int = 0
    idempotent_replay: bool = False


def active_parent_ids_for_students(
    db: Session,
    student_ids: list[int],
) -> list[int]:
    """Return unique active parent accounts linked to active students."""

    if not student_ids:
        return []
    rows = (
        db.query(ParentStudent.parent_user_id)
        .join(Student, Student.id == ParentStudent.student_id)
        .join(User, User.id == ParentStudent.parent_user_id)
        .filter(
            Student.id.in_(set(student_ids)),
            Student.is_active.is_(True),
            User.role == "PARENT",
            User.is_active.is_(True),
        )
        .distinct()
        .all()
    )
    return sorted({parent_id for (parent_id,) in rows})


def active_parent_ids_for_classes(
    db: Session,
    class_ids: list[int],
) -> list[int]:
    if not class_ids:
        return []
    rows = (
        db.query(Student.id)
        .filter(
            Student.class_id.in_(set(class_ids)),
            Student.is_active.is_(True),
        )
        .all()
    )
    return active_parent_ids_for_students(db, [student_id for (student_id,) in rows])


def all_active_parent_ids(db: Session) -> list[int]:
    rows = (
        db.query(ParentStudent.parent_user_id)
        .join(Student, Student.id == ParentStudent.student_id)
        .join(User, User.id == ParentStudent.parent_user_id)
        .filter(
            Student.is_active.is_(True),
            User.role == "PARENT",
            User.is_active.is_(True),
        )
        .distinct()
        .order_by(ParentStudent.parent_user_id.asc())
        .all()
    )
    return [parent_id for (parent_id,) in rows]


def _event_key(event_type: str, reference_key: str) -> str:
    raw = f"automatic:{event_type.upper()}:{reference_key}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def queue_parent_event_email(
    db: Session,
    *,
    event_type: str,
    reference_key: str,
    parent_ids: list[int],
    created_by: int | None,
    title: str,
    message: str,
) -> AutomaticEmailQueueResult:
    """Add one idempotent parent-email batch to the current transaction."""

    normalized_event = event_type.strip().upper()
    settings = get_email_settings()
    if not automatic_event_delivery_enabled(normalized_event):
        return AutomaticEmailQueueResult(enabled=False)

    unique_parent_ids = sorted(set(parent_ids))
    recipient_policy = (
        "OPERATIONAL" if operational_event_enabled(normalized_event) else "OPTIONAL"
    )
    preview = resolve_parent_email_recipients(
        db,
        unique_parent_ids,
        policy=recipient_policy,
    )
    preview, filtered_count = _apply_test_mode(preview, normalized_event)
    retained_parent_ids = [parent_id for parent_id, _ in preview.recipients]
    if retained_parent_ids:
        preview.verified_email_recipient_count = (
            db.query(User.id)
            .filter(
                User.id.in_(retained_parent_ids),
                User.email_verified_at.isnot(None),
            )
            .count()
        )
        preview.unverified_email_recipient_count = (
            len(retained_parent_ids) - preview.verified_email_recipient_count
        )
    else:
        preview.verified_email_recipient_count = 0
        preview.unverified_email_recipient_count = 0

    idempotency_key = _event_key(normalized_event, reference_key)
    existing = (
        db.query(EmailNotificationBatch)
        .filter(EmailNotificationBatch.idempotency_key == idempotency_key)
        .first()
    )
    if existing:
        return AutomaticEmailQueueResult(
            enabled=True,
            batch_id=existing.id,
            queued_count=existing.email_recipient_count,
            test_filtered_count=filtered_count,
            idempotent_replay=True,
        )

    canonical = {
        "event_type": normalized_event,
        "recipient_policy": recipient_policy,
        "reference_key": reference_key,
        "parent_ids": unique_parent_ids,
        "recipients": [email for _, email in preview.recipients],
        "title": title.strip(),
        "message": message.strip(),
    }
    fingerprint = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    has_recipients = bool(preview.recipients)
    batch = EmailNotificationBatch(
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
        created_by=created_by,
        target_type=f"AUTOMATIC_{normalized_event}",
        category=normalized_event,
        recipient_policy=recipient_policy,
        event_reference=str(reference_key)[:255],
        title=title.strip(),
        message=message.strip(),
        send_in_app=True,
        send_email=True,
        status="QUEUED" if has_recipients else "NO_RECIPIENTS",
        parent_recipient_count=len(unique_parent_ids),
        email_recipient_count=preview.email_recipient_count,
        missing_email_count=preview.missing_email_count,
        invalid_email_count=preview.invalid_email_count,
        unverified_email_count=preview.unverified_email_count,
        opted_out_count=preview.opted_out_count,
        deduplicated_email_count=preview.deduplicated_email_count,
        suppressed_email_count=preview.suppressed_email_count,
        verified_email_recipient_count=preview.verified_email_recipient_count,
        unverified_email_recipient_count=preview.unverified_email_recipient_count,
        completed_at=None if has_recipients else now,
    )
    db.add(batch)
    db.flush()

    for parent_id, email in preview.recipients:
        db.add(
            EmailDelivery(
                batch_id=batch.id,
                parent_user_id=parent_id,
                email=email,
                status="QUEUED",
                attempt_count=0,
                max_attempts=settings.max_attempts,
                next_attempt_at=now,
            )
        )

    # Make the outbox rows visible to subsequent idempotency checks and count
    # queries in this same transaction without taking ownership of commit.
    db.flush()

    return AutomaticEmailQueueResult(
        enabled=True,
        batch_id=batch.id,
        queued_count=preview.email_recipient_count,
        test_filtered_count=filtered_count,
    )
