
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_admin

from app.models.user import User
from app.models.student import Student
from app.models.parent_student import ParentStudent
from app.models.school_class import SchoolClass
from app.models.notification import Notification

from app.schemas.admin_notification import (
    AdminNotificationPreviewRequest,
    AdminNotificationPreviewResponse,
    AdminNotificationSendRequest,
    AdminNotificationSendResponse,
)


router = APIRouter(
    prefix="/api/v1/admin/notifications",
    tags=["Admin Notifications"],
    dependencies=[Depends(get_current_admin)],
)


# =========================================================
# RESOLVE NOTIFICATION RECIPIENTS
# =========================================================

def resolve_parent_ids(
    db: Session,
    target_type: str,
    class_ids: list[int],
    parent_user_id: int | None,
) -> list[int]:

    # ALL ACTIVE PARENTS
    if target_type == "ALL_PARENTS":
        rows = (
            db.query(User.id)
            .filter(
                User.role == "PARENT",
                User.is_active.is_(True),
            )
            .all()
        )

        return sorted({row[0] for row in rows})

    # SELECTED CLASSES
    if target_type == "CLASSES":

        selected_ids = set(class_ids)

        valid_class_ids = {
            row[0]
            for row in (
                db.query(SchoolClass.id)
                .filter(
                    SchoolClass.id.in_(selected_ids),
                    SchoolClass.is_active.is_(True),
                )
                .all()
            )
        }

        if valid_class_ids != selected_ids:
            raise HTTPException(
                status_code=400,
                detail="One or more selected classes are invalid or inactive",
            )

        rows = (
            db.query(ParentStudent.parent_user_id)
            .join(
                Student,
                ParentStudent.student_id == Student.id,
            )
            .join(
                User,
                ParentStudent.parent_user_id == User.id,
            )
            .filter(
                Student.class_id.in_(valid_class_ids),
                Student.is_active.is_(True),
                User.role == "PARENT",
                User.is_active.is_(True),
            )
            .distinct()
            .all()
        )

        return sorted({row[0] for row in rows})

    # INDIVIDUAL PARENT
    if target_type == "INDIVIDUAL_PARENT":

        parent = (
            db.query(User)
            .filter(
                User.id == parent_user_id,
                User.role == "PARENT",
                User.is_active.is_(True),
            )
            .first()
        )

        if not parent:
            raise HTTPException(
                status_code=404,
                detail="Active parent account not found",
            )

        return [parent.id]

    raise HTTPException(
        status_code=400,
        detail="Invalid notification target",
    )


# =========================================================
# PREVIEW RECIPIENT COUNT
# =========================================================

@router.post(
    "/preview",
    response_model=AdminNotificationPreviewResponse,
)
def preview_notification(
    payload: AdminNotificationPreviewRequest,
    db: Session = Depends(get_db),
):
    parent_ids = resolve_parent_ids(
        db=db,
        target_type=payload.target_type,
        class_ids=payload.class_ids,
        parent_user_id=payload.parent_user_id,
    )

    return {
        "target_type": payload.target_type,
        "recipient_count": len(parent_ids),
    }


# =========================================================
# SEND NOTIFICATIONS
# =========================================================

@router.post(
    "/send",
    response_model=AdminNotificationSendResponse,
)
def send_notification(
    payload: AdminNotificationSendRequest,
    db: Session = Depends(get_db),
):
    parent_ids = resolve_parent_ids(
        db=db,
        target_type=payload.target_type,
        class_ids=payload.class_ids,
        parent_user_id=payload.parent_user_id,
    )

    if not parent_ids:
        raise HTTPException(
            status_code=400,
            detail="No eligible parents found",
        )

    try:
        for parent_id in parent_ids:
            notification = Notification(
                user_id=parent_id,
                title=payload.title.strip(),
                message=payload.message.strip(),
                notification_type="ADMIN_ANNOUNCEMENT",
                is_read=False,
            )

            db.add(notification)

        db.commit()

    except Exception:
        db.rollback()
        raise

    return {
        "message": "Notifications sent successfully",
        "recipient_count": len(parent_ids),
        "notifications_created": len(parent_ids),
    }
