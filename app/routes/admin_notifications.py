import hashlib
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_admin
from app.models.email_notification import (
    EmailDelivery,
    EmailNotificationBatch,
    EmailSuppression,
)
from app.models.notification import Notification
from app.models.parent_student import ParentStudent
from app.models.school_class import SchoolClass
from app.models.student import Student
from app.models.user import User
from app.schemas.admin_notification import (
    AdminNotificationPreviewRequest,
    AdminNotificationPreviewResponse,
    AdminNotificationSendRequest,
    AdminNotificationSendResponse,
    EmailSuppressionRemoveRequest,
    EmailSuppressionRequest,
)
from app.services.parent_email_service import (
    _safe_provider_error,
    build_parent_email_readiness_report,
    get_email_settings,
    mask_email,
    normalize_email,
    resolve_parent_email_recipients,
    suppress_email_address,
)
from app.services.automatic_email_service import (
    EVENT_FLAGS,
    OPERATIONAL_EVENT_FLAGS,
    automatic_event_enabled,
    automatic_test_mode_enabled,
    admin_test_recipient_allowed,
    operational_event_enabled,
    operational_notifications_enabled,
)
from app.services.email_worker_health import read_worker_heartbeat
from app.services.parent_email_preferences_service import verification_email_enabled


router = APIRouter(
    prefix="/api/v1/admin/notifications",
    tags=["Admin Notifications"],
    dependencies=[Depends(get_current_admin)],
)


def resolve_parent_ids(
    db: Session,
    target_type: str,
    class_ids: list[int],
    student_ids: list[int],
    parent_user_id: int | None,
) -> list[int]:
    base = (
        db.query(ParentStudent.parent_user_id)
        .join(Student, ParentStudent.student_id == Student.id)
        .join(User, ParentStudent.parent_user_id == User.id)
        .filter(
            Student.is_active.is_(True),
            User.role == "PARENT",
            User.is_active.is_(True),
        )
    )

    if target_type == "ALL_PARENTS":
        return sorted({row[0] for row in base.distinct().all()})

    if target_type == "CLASSES":
        selected_ids = set(class_ids)
        valid_class_ids = {
            row[0]
            for row in db.query(SchoolClass.id)
            .filter(
                SchoolClass.id.in_(selected_ids),
                SchoolClass.is_active.is_(True),
            )
            .all()
        }
        if valid_class_ids != selected_ids:
            raise HTTPException(
                status_code=400,
                detail="One or more selected classes are invalid or inactive",
            )
        rows = base.filter(Student.class_id.in_(valid_class_ids)).distinct().all()
        return sorted({row[0] for row in rows})

    if target_type == "STUDENTS":
        selected_ids = set(student_ids)
        valid_student_ids = {
            row[0]
            for row in db.query(Student.id)
            .filter(
                Student.id.in_(selected_ids),
                Student.is_active.is_(True),
            )
            .all()
        }
        if valid_student_ids != selected_ids:
            raise HTTPException(
                status_code=400,
                detail="One or more selected students are invalid or inactive",
            )
        rows = base.filter(Student.id.in_(valid_student_ids)).distinct().all()
        return sorted({row[0] for row in rows})

    if target_type == "INDIVIDUAL_PARENT":
        row = base.filter(User.id == parent_user_id).first()
        if not row:
            raise HTTPException(
                status_code=404,
                detail="Active linked parent account not found",
            )
        return [row[0]]

    raise HTTPException(status_code=400, detail="Invalid notification target")


def _resolve(payload, db: Session):
    parent_ids = resolve_parent_ids(
        db=db,
        target_type=payload.target_type,
        class_ids=payload.class_ids,
        student_ids=payload.student_ids,
        parent_user_id=payload.parent_user_id,
    )
    preview = resolve_parent_email_recipients(db, parent_ids)
    retained = [
        item for item in preview.recipients if admin_test_recipient_allowed(item[1])
    ]
    preview.test_filtered_count = len(preview.recipients) - len(retained)
    preview.recipients = retained
    preview.verified_email_recipient_count = len(retained)
    return parent_ids, preview


def _preview_response(payload, email_preview, operational_preview) -> dict:
    settings = get_email_settings()
    excluded_email_recipient_count = (
        email_preview.missing_email_count
        + email_preview.invalid_email_count
        + email_preview.unverified_email_count
        + email_preview.opted_out_count
        + email_preview.deduplicated_email_count
        + email_preview.suppressed_email_count
        + email_preview.test_filtered_count
    )
    return {
        "target_type": payload.target_type,
        "recipient_count": len(email_preview.parent_ids),
        "email_recipient_count": email_preview.email_recipient_count,
        "excluded_email_recipient_count": excluded_email_recipient_count,
        "missing_email_count": email_preview.missing_email_count,
        "invalid_email_count": email_preview.invalid_email_count,
        "unverified_email_count": email_preview.unverified_email_count,
        "opted_out_count": email_preview.opted_out_count,
        "deduplicated_email_count": email_preview.deduplicated_email_count,
        "suppressed_email_count": email_preview.suppressed_email_count,
        "verified_email_recipient_count": (
            email_preview.verified_email_recipient_count
        ),
        "operational_email_recipient_count": (
            operational_preview.email_recipient_count
        ),
        "operational_unverified_email_count": (
            operational_preview.unverified_email_recipient_count
        ),
        "test_filtered_count": email_preview.test_filtered_count,
        "email_sending_enabled": settings.enabled,
        "provider_ready": settings.provider_ready,
        "fee_reminders_enabled": settings.fee_reminders_enabled,
    }


@router.get("/email-status")
def get_email_status():
    settings = get_email_settings()
    test_mode_enabled = automatic_test_mode_enabled()
    if not settings.enabled:
        delivery_mode = "disabled"
        delivery_status_message = (
            "Optional parent email delivery is disabled by backend configuration. "
            "In-app notifications remain available."
        )
    elif not settings.provider_ready:
        delivery_mode = "misconfigured"
        delivery_status_message = (
            "Optional parent email delivery is enabled, but the configured "
            "provider is not ready. Email selection is unavailable."
        )
    elif test_mode_enabled:
        delivery_mode = "test"
        delivery_status_message = (
            "Restricted test mode is active. Optional email is available only "
            "to approved test recipients; an empty allowlist sends to nobody."
        )
    else:
        delivery_mode = "available"
        delivery_status_message = (
            "Optional parent email delivery is available for verified, opted-in "
            "recipients."
        )
    return {
        "enabled": settings.enabled,
        "delivery_mode": delivery_mode,
        "delivery_status_message": delivery_status_message,
        "verification_enabled": verification_email_enabled(),
        "provider_ready": settings.provider_ready,
        "transport": settings.transport,
        "fee_reminders_enabled": settings.fee_reminders_enabled,
        "batch_size": settings.batch_size,
        "rate_limit_per_second": settings.rate_limit_per_second,
        "max_attempts": settings.max_attempts,
        "operational_master_enabled": operational_notifications_enabled(),
        "test_mode_enabled": test_mode_enabled,
        "automatic_categories": {
            category: {
                "automatic_enabled": automatic_event_enabled(category),
                "operational_enabled": operational_event_enabled(category),
                "automatic_flag": EVENT_FLAGS[category],
                "operational_flag": OPERATIONAL_EVENT_FLAGS[category],
            }
            for category in EVENT_FLAGS
        },
    }


@router.get("/recipient-readiness")
def get_recipient_readiness(db: Session = Depends(get_db)):
    """Return aggregate readiness counts only; never expose address lists."""

    return build_parent_email_readiness_report(db)


@router.post("/email-suppressions")
def create_email_suppression(
    payload: EmailSuppressionRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    suppression = suppress_email_address(
        db,
        str(payload.email),
        reason=payload.reason,
        source="ADMIN",
        created_by=current_admin.id,
    )
    db.commit()
    return {
        "status": "suppressed",
        "email": mask_email(suppression.email),
        "reason": suppression.reason,
    }


@router.post("/email-suppressions/remove")
def remove_email_suppression(
    payload: EmailSuppressionRemoveRequest,
    db: Session = Depends(get_db),
):
    normalized = normalize_email(str(payload.email))
    suppression = db.query(EmailSuppression).filter_by(email=normalized).first()
    if suppression is None or not suppression.is_active:
        raise HTTPException(status_code=404, detail="Active suppression not found")
    suppression.is_active = False
    db.commit()
    return {"status": "removed", "email": mask_email(normalized)}


@router.get("/email-health")
def get_email_health():
    """Verify SMTP connectivity without sending a message.

    Attempts to open an SMTP connection (with STARTTLS when configured)
    and authenticate if credentials are present. Returns quickly on failure
    so the endpoint is safe to poll.
    """
    import smtplib
    import ssl

    settings = get_email_settings()

    if not settings.enabled and not verification_email_enabled():
        return {
            "status": "disabled",
            "detail": "Automatic and verification email delivery are disabled",
        }

    if settings.transport == "mock":
        return {
            "status": "ok",
            "transport": "mock",
            "detail": "Mock transport — no network connectivity checked",
        }

    if not settings.provider_ready:
        return {
            "status": "misconfigured",
            "detail": "SMTP configuration is incomplete (host, port, from, username, or password missing)",
        }

    try:
        if settings.smtp_use_ssl:
            client = smtplib.SMTP_SSL(
                settings.smtp_host,
                settings.smtp_port,
                timeout=10,
                context=ssl.create_default_context(),
            )
        else:
            client = smtplib.SMTP(
                settings.smtp_host,
                settings.smtp_port,
                timeout=10,
            )

        with client:
            if settings.smtp_use_tls and not settings.smtp_use_ssl:
                client.starttls(context=ssl.create_default_context())
            if settings.smtp_username:
                client.login(settings.smtp_username, settings.smtp_password)

        return {
            "status": "ok",
            "transport": "smtp",
            "host": settings.smtp_host,
            "port": settings.smtp_port,
            "detail": "SMTP connection and authentication successful",
        }
    except Exception as exc:  # connectivity/auth failures are reported, not raised
        message = _safe_provider_error(exc, settings)
        return {
            "status": "error",
            "transport": "smtp",
            "host": settings.smtp_host,
            "port": settings.smtp_port,
            "detail": message,
        }


@router.post("/preview", response_model=AdminNotificationPreviewResponse)
def preview_notification(
    payload: AdminNotificationPreviewRequest,
    db: Session = Depends(get_db),
):
    parent_ids, email_preview = _resolve(payload, db)
    operational_preview = resolve_parent_email_recipients(
        db, parent_ids, policy="OPERATIONAL"
    )
    retained_operational = [
        item
        for item in operational_preview.recipients
        if admin_test_recipient_allowed(item[1])
    ]
    operational_preview.recipients = retained_operational
    retained_ids = {parent_id for parent_id, _ in retained_operational}
    operational_preview.verified_email_recipient_count = (
        db.query(User.id)
        .filter(User.id.in_(retained_ids), User.email_verified_at.isnot(None))
        .count()
        if retained_ids
        else 0
    )
    operational_preview.unverified_email_recipient_count = (
        len(retained_ids) - operational_preview.verified_email_recipient_count
    )
    return _preview_response(payload, email_preview, operational_preview)


def _batch_response(
    batch: EmailNotificationBatch,
    *,
    idempotent_replay: bool = False,
) -> dict:
    return {
        "message": (
            "Notification request already accepted"
            if idempotent_replay
            else "Notification request accepted"
        ),
        "recipient_count": batch.parent_recipient_count,
        "notifications_created": (
            batch.parent_recipient_count if batch.send_in_app else 0
        ),
        "batch_id": batch.id,
        "email_queued": batch.email_recipient_count if batch.send_email else 0,
        "status": batch.status,
        "idempotent_replay": idempotent_replay,
    }


def _request_fingerprint(payload: AdminNotificationSendRequest) -> str:
    canonical = {
        "target_type": payload.target_type,
        "class_ids": sorted(payload.class_ids),
        "student_ids": sorted(payload.student_ids),
        "parent_user_id": payload.parent_user_id,
        "category": payload.category,
        "send_in_app": payload.send_in_app,
        "send_email": payload.send_email,
        "title": payload.title.strip(),
        "message": payload.message.strip(),
    }
    return hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


@router.post("/send", response_model=AdminNotificationSendResponse)
def send_notification(
    payload: AdminNotificationSendRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    settings = get_email_settings()
    if payload.category == "FEE_REMINDER" and not settings.fee_reminders_enabled:
        raise HTTPException(status_code=403, detail="Fee reminder emails are disabled")

    if payload.send_email:
        if not settings.enabled:
            raise HTTPException(
                status_code=503,
                detail="Parent email delivery is not enabled",
            )
        if not settings.provider_ready:
            raise HTTPException(
                status_code=503,
                detail="Email provider configuration is incomplete",
            )

    idempotency_key = payload.idempotency_key or str(uuid.uuid4())
    request_fingerprint = _request_fingerprint(payload)
    existing = (
        db.query(EmailNotificationBatch)
        .filter(EmailNotificationBatch.idempotency_key == idempotency_key)
        .first()
    )
    if existing:
        if existing.request_fingerprint != request_fingerprint:
            raise HTTPException(
                status_code=409,
                detail="Idempotency key was already used for a different request",
            )
        return _batch_response(existing, idempotent_replay=True)

    parent_ids, email_preview = _resolve(payload, db)
    if not parent_ids:
        raise HTTPException(status_code=400, detail="No eligible linked parents found")

    if payload.send_email:
        if payload.confirmed_email_recipient_count != email_preview.email_recipient_count:
            raise HTTPException(
                status_code=409,
                detail="Eligible email recipient count changed. Preview and confirm again.",
            )
        if not email_preview.recipients:
            raise HTTPException(
                status_code=400,
                detail="No verified parent email recipients are eligible",
            )

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    batch = EmailNotificationBatch(
        idempotency_key=idempotency_key,
        request_fingerprint=request_fingerprint,
        created_by=current_admin.id,
        target_type=payload.target_type,
        category=payload.category,
        recipient_policy="OPTIONAL",
        title=payload.title.strip(),
        message=payload.message.strip(),
        send_in_app=payload.send_in_app,
        send_email=payload.send_email,
        status="QUEUED" if payload.send_email else "COMPLETED",
        parent_recipient_count=len(parent_ids),
        email_recipient_count=email_preview.email_recipient_count,
        missing_email_count=email_preview.missing_email_count,
        invalid_email_count=email_preview.invalid_email_count,
        unverified_email_count=email_preview.unverified_email_count,
        opted_out_count=email_preview.opted_out_count,
        deduplicated_email_count=email_preview.deduplicated_email_count,
        suppressed_email_count=email_preview.suppressed_email_count,
        verified_email_recipient_count=(
            email_preview.verified_email_recipient_count
        ),
        unverified_email_recipient_count=0,
        completed_at=None if payload.send_email else now,
    )
    db.add(batch)
    db.flush()

    if payload.send_in_app:
        for parent_id in parent_ids:
            db.add(
                Notification(
                    user_id=parent_id,
                    title=payload.title.strip(),
                    message=payload.message.strip(),
                    notification_type=(
                        "FEE_REMINDER"
                        if payload.category == "FEE_REMINDER"
                        else "ADMIN_ANNOUNCEMENT"
                    ),
                    is_read=False,
                )
            )

    if payload.send_email:
        for parent_id, email in email_preview.recipients:
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

    try:
        db.commit()
        db.refresh(batch)
    except Exception:
        db.rollback()
        replay = (
            db.query(EmailNotificationBatch)
            .filter(EmailNotificationBatch.idempotency_key == idempotency_key)
            .first()
        )
        if replay:
            if replay.request_fingerprint != request_fingerprint:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Idempotency key was already used for a different "
                        "request"
                    ),
                )
            return _batch_response(replay, idempotent_replay=True)
        raise

    return _batch_response(batch)


@router.get("/email-metrics")
def get_email_metrics(db: Session = Depends(get_db)):
    """Return aggregate outbox health without exposing recipient details."""

    delivery_counts = {
        status: count
        for status, count in db.query(
            EmailDelivery.status,
            func.count(EmailDelivery.id),
        )
        .group_by(EmailDelivery.status)
        .all()
    }
    batch_counts = {
        status: count
        for status, count in db.query(
            EmailNotificationBatch.status,
            func.count(EmailNotificationBatch.id),
        )
        .group_by(EmailNotificationBatch.status)
        .all()
    }
    notifications_created = db.query(
        func.coalesce(
            func.sum(
                case(
                    (
                        EmailNotificationBatch.send_in_app.is_(True),
                        EmailNotificationBatch.parent_recipient_count,
                    ),
                    else_=0,
                )
            ),
            0,
        )
    ).scalar()
    retry_count = db.query(
        func.coalesce(
            func.sum(
                case(
                    (
                        EmailDelivery.attempt_count > 1,
                        EmailDelivery.attempt_count - 1,
                    ),
                    else_=0,
                )
            ),
            0,
        )
    ).scalar()
    last_worker_activity = (
        db.query(func.max(EmailDelivery.updated_at))
        .filter(EmailDelivery.attempt_count > 0)
        .scalar()
    )
    heartbeat = read_worker_heartbeat()
    if heartbeat and heartbeat.get("timestamp"):
        last_worker_activity = heartbeat["timestamp"]
    recent_failures = (
        db.query(EmailDelivery)
        .filter(EmailDelivery.status == "FAILED")
        .order_by(EmailDelivery.updated_at.desc(), EmailDelivery.id.desc())
        .limit(20)
        .all()
    )

    return {
        "total_batches": db.query(EmailNotificationBatch).count(),
        "total_notifications_created": int(notifications_created or 0),
        # Kept for clients that used the original name; this is total created.
        "total_emails_queued": db.query(EmailDelivery).count(),
        "total_emails_created": db.query(EmailDelivery).count(),
        "total_queued": int(delivery_counts.get("QUEUED", 0)),
        "currently_processing": int(delivery_counts.get("PROCESSING", 0)),
        "total_retried": int(retry_count or 0),
        "total_sent": int(delivery_counts.get("SENT", 0)),
        "total_failed": int(delivery_counts.get("FAILED", 0)),
        "delivery_counts": {
            status: int(delivery_counts.get(status, 0))
            for status in ("QUEUED", "PROCESSING", "RETRY", "SENT", "FAILED")
        },
        "retry_count": int(retry_count or 0),
        "last_worker_activity": last_worker_activity,
        "worker_heartbeat": heartbeat,
        "batch_counts": batch_counts,
        "recent_failures": [
            {
                "delivery_id": delivery.id,
                "batch_id": delivery.batch_id,
                "email": mask_email(delivery.email),
                "attempt_count": delivery.attempt_count,
                "reason": delivery.last_error,
                "updated_at": delivery.updated_at,
            }
            for delivery in recent_failures
        ],
    }


@router.get("/email-batches")
def list_email_batches(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(EmailNotificationBatch)
    total = query.count()
    batches = (
        query.order_by(EmailNotificationBatch.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    data = []
    for batch in batches:
        counts = {
            status: db.query(EmailDelivery)
            .filter(
                EmailDelivery.batch_id == batch.id,
                EmailDelivery.status == status,
            )
            .count()
            for status in ("QUEUED", "RETRY", "PROCESSING", "SENT", "FAILED")
        }
        data.append(
            {
                "id": batch.id,
                "title": batch.title,
                "category": batch.category,
                "recipient_policy": batch.recipient_policy,
                "event_reference": batch.event_reference,
                "target_type": batch.target_type,
                "status": batch.status,
                "send_in_app": batch.send_in_app,
                "send_email": batch.send_email,
                "parent_recipient_count": batch.parent_recipient_count,
                "email_recipient_count": batch.email_recipient_count,
                "verified_email_recipient_count": (
                    batch.verified_email_recipient_count
                ),
                "unverified_email_recipient_count": (
                    batch.unverified_email_recipient_count
                ),
                "suppressed_email_count": batch.suppressed_email_count,
                "delivery_counts": counts,
                "created_at": batch.created_at,
                "completed_at": batch.completed_at,
            }
        )
    return {"data": data, "page": page, "page_size": page_size, "total": total}


@router.get("/email-batches/{batch_id}")
def get_email_batch(batch_id: int, db: Session = Depends(get_db)):
    batch = (
        db.query(EmailNotificationBatch)
        .filter(EmailNotificationBatch.id == batch_id)
        .first()
    )
    if not batch:
        raise HTTPException(status_code=404, detail="Email batch not found")
    deliveries = (
        db.query(EmailDelivery)
        .filter(EmailDelivery.batch_id == batch_id)
        .order_by(EmailDelivery.id.asc())
        .all()
    )
    return {
        "id": batch.id,
        "title": batch.title,
        "category": batch.category,
        "recipient_policy": batch.recipient_policy,
        "event_reference": batch.event_reference,
        "status": batch.status,
        "counts": {
            "parents": batch.parent_recipient_count,
            "email_recipients": batch.email_recipient_count,
            "missing_email": batch.missing_email_count,
            "invalid_email": batch.invalid_email_count,
            "unverified_email": batch.unverified_email_count,
            "opted_out": batch.opted_out_count,
            "deduplicated_email": batch.deduplicated_email_count,
            "suppressed_email": batch.suppressed_email_count,
            "verified_recipients": batch.verified_email_recipient_count,
            "unverified_recipients": batch.unverified_email_recipient_count,
        },
        "deliveries": [
            {
                "id": delivery.id,
                "parent_user_id": delivery.parent_user_id,
                "email": mask_email(delivery.email),
                "status": delivery.status,
                "attempt_count": delivery.attempt_count,
                "last_error": delivery.last_error,
                "sent_at": delivery.sent_at,
            }
            for delivery in deliveries
        ],
    }
