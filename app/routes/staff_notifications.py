from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_staff
from app.models.notification import Notification
from app.models.user import User
from app.schemas.notification import (
    NotificationListResponse,
)


router = APIRouter(
    prefix="/api/v1/staff/notifications",
    tags=["Staff Notifications"],
    dependencies=[Depends(get_current_staff)],
)


# =========================================================
# GET ALL STAFF NOTIFICATIONS
# =========================================================
#
# Staff (Teacher + Admin) equivalent of the Parent notification
# inbox. Every query is scoped to the caller's own user_id, so a
# teacher can never read another teacher's (or an admin's) rows.
# The notifications table itself is role-agnostic (user_id FK to
# users), so no schema change is required.

@router.get(
    "",
    response_model=NotificationListResponse,
)
def get_staff_notifications(
    page: int = Query(
        default=1,
        ge=1,
    ),

    page_size: int = Query(
        default=20,
        ge=1,
        le=100,
    ),

    db: Session = Depends(get_db),

    current_user: User = Depends(
        get_current_staff
    ),
):
    query = (
        db.query(Notification)
        .filter(
            Notification.user_id
            == current_user.id
        )
    )

    total = query.count()

    total_pages = (
        (total + page_size - 1)
        // page_size
    )

    offset = (
        page - 1
    ) * page_size

    notifications = (
        query
        .order_by(
            Notification.created_at.desc(),
            Notification.id.desc(),
        )
        .offset(offset)
        .limit(page_size)
        .all()
    )

    return {
        "data":
            notifications,

        "page":
            page,

        "page_size":
            page_size,

        "total":
            total,

        "total_pages":
            total_pages,

        "has_next":
            page < total_pages,

        "has_previous":
            page > 1,
    }


# =========================================================
# GET UNREAD COUNT
# =========================================================

@router.get("/unread-count")
def get_staff_unread_notification_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_staff
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
def mark_staff_notification_as_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_staff
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
