from sqlalchemy.orm import Session

from app.models.notification import Notification


def create_notification(
    db: Session,
    user_id: int,
    title: str,
    message: str,
    notification_type: str | None = None,
    reference_id: int | None = None,
    link: str | None = None,
):
    notification = Notification(
        user_id=user_id,
        title=title,
        message=message,
        notification_type=notification_type,
        reference_id=reference_id,
        link=link,
        is_read=False,
    )

    db.add(notification)

    return notification