from datetime import datetime, timedelta, timezone

from email_validator import EmailNotValidError
from fastapi import APIRouter, Depends, HTTPException, Query, status
from jwt.exceptions import InvalidTokenError
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_parent
from app.models.email_verification import EmailVerificationToken
from app.models.user import User
from app.schemas.parent_email_preferences import (
    EmailPreferencesResponse,
    EmailPreferenceUpdate,
    EmailTokenRequest,
    MessageResponse,
)
from app.services.parent_email_preferences_service import (
    create_verification_token,
    decode_unsubscribe_token,
    send_verification_email,
    token_digest,
    verification_email_enabled,
    verification_rate_limit,
)
from app.services.parent_email_service import normalize_email


router = APIRouter(
    prefix="/api/v1/parent/email-preferences",
    tags=["Parent Email Preferences"],
)


def _response(user: User) -> EmailPreferencesResponse:
    return EmailPreferencesResponse(
        email=user.email,
        email_verified_at=user.email_verified_at,
        email_notifications_enabled=user.email_notifications_enabled,
        verification_required=bool(user.email and not user.email_verified_at),
    )


@router.get("", response_model=EmailPreferencesResponse)
def get_email_preferences(
    current_user: User = Depends(get_current_parent),
):
    return _response(current_user)


@router.patch("", response_model=EmailPreferencesResponse)
def update_email_preferences(
    payload: EmailPreferenceUpdate,
    current_user: User = Depends(get_current_parent),
    db: Session = Depends(get_db),
):
    if payload.email_notifications_enabled:
        if not current_user.email:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Add an email address before enabling notifications",
            )
        if current_user.email_verified_at is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Verify your email address before enabling notifications",
            )

    current_user.email_notifications_enabled = payload.email_notifications_enabled
    db.commit()
    db.refresh(current_user)
    return _response(current_user)


@router.post("/verification/request", response_model=MessageResponse)
def request_email_verification(
    current_user: User = Depends(get_current_parent),
    db: Session = Depends(get_db),
):
    if not current_user.email:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Add an email address before requesting verification",
        )
    try:
        recipient = normalize_email(current_user.email)
    except EmailNotValidError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A valid email address is required",
        ) from exc

    if current_user.email_verified_at is not None:
        return MessageResponse(message="Email address is already verified")

    if not verification_email_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email verification is temporarily unavailable",
        )

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    max_requests, window_seconds, cooldown_seconds = verification_rate_limit()
    window_start = now - timedelta(seconds=window_seconds)
    recent_query = db.query(EmailVerificationToken).filter(
        EmailVerificationToken.user_id == current_user.id,
        EmailVerificationToken.created_at >= window_start,
    )
    latest_created_at = recent_query.with_entities(
        func.max(EmailVerificationToken.created_at)
    ).scalar()
    if latest_created_at is not None:
        retry_after = cooldown_seconds - int((now - latest_created_at).total_seconds())
        if retry_after > 0:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Please wait before requesting another verification email",
                headers={"Retry-After": str(retry_after)},
            )
    if recent_query.count() >= max_requests:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Verification email request limit reached. Please try again later",
            headers={"Retry-After": str(window_seconds)},
        )

    raw_token = create_verification_token(db, current_user)
    try:
        send_verification_email(recipient, raw_token)
    except Exception as exc:
        # Do not leave a usable token behind when its email was not sent.
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        db.query(EmailVerificationToken).filter(
            EmailVerificationToken.token_hash == token_digest(raw_token),
            EmailVerificationToken.used_at.is_(None),
        ).update({"used_at": now}, synchronize_session=False)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Verification email could not be sent",
        ) from exc

    return MessageResponse(message="Verification email sent")


@router.post("/verification/confirm", response_model=EmailPreferencesResponse)
def confirm_email_verification(
    payload: EmailTokenRequest,
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    token = (
        db.query(EmailVerificationToken)
        .filter(
            EmailVerificationToken.token_hash == token_digest(payload.token),
            EmailVerificationToken.used_at.is_(None),
            EmailVerificationToken.expires_at >= now,
        )
        .with_for_update()
        .first()
    )
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification token is invalid or expired",
        )

    user = db.get(User, token.user_id)
    try:
        current_email = normalize_email(user.email) if user and user.email else None
    except EmailNotValidError:
        current_email = None
    if user is None or user.role.upper() != "PARENT" or current_email != token.email:
        token.used_at = now
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification token is invalid or expired",
        )

    token.used_at = now
    user.email_verified_at = now
    db.commit()
    db.refresh(user)
    return _response(user)


@router.post("/unsubscribe", response_model=MessageResponse)
def unsubscribe_parent_email(
    token: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
):
    try:
        user_id, token_email = decode_unsubscribe_token(token)
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsubscribe token is invalid or expired",
        ) from exc

    user = db.get(User, user_id)
    try:
        current_email = normalize_email(user.email) if user and user.email else None
    except EmailNotValidError:
        current_email = None
    if user is None or user.role.upper() != "PARENT" or current_email != token_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsubscribe token is invalid or expired",
        )

    # Idempotent by design: mail clients may retry one-click unsubscribe.
    user.email_notifications_enabled = False
    db.commit()
    return MessageResponse(message="Email notifications have been disabled")
