from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_parent
from app.models.notification import Notification
from app.models.user import User
from app.schemas.notification import NotificationResponse


router = APIRouter(
    prefix="/notifications",
    tags=["Notifications"],
)


# =========================================================
# GET ALL NOTIFICATIONS
# =========================================================

@router.get(
    "",
    response_model=list[NotificationResponse],
)
def get_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_parent
    ),
):
    notifications = (
        db.query(Notification)
        .filter(
            Notification.user_id
            == current_user.id
        )
        .order_by(
            Notification.created_at.desc()
        )
        .all()
    )

    return notifications


# =========================================================
# GET UNREAD COUNT
# =========================================================

@router.get("/unread-count")
def get_unread_notification_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_parent
    ),
):
    unread_count = (
        db.query(Notification)
        .filter(
            Notification.user_id
            == current_user.id,
            Notification.is_read.is_(False),
        )
        .count()
    )

    return {
        "unread_count": unread_count
    }


# =========================================================
# MARK NOTIFICATION AS READ
# =========================================================

@router.patch("/{notification_id}/read")
def mark_notification_as_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_parent
    ),
):
    notification = (
        db.query(Notification)
        .filter(
            Notification.id == notification_id,
            Notification.user_id
            == current_user.id,
        )
        .first()
    )

    if not notification:
        raise HTTPException(
            status_code=404,
            detail="Notification not found",
        )

    notification.is_read = True

    db.commit()
    db.refresh(notification)

    return {
        "message": "Notification marked as read",
        "notification_id": notification.id,
        "is_read": notification.is_read,
    }