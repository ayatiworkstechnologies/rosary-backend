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


def _safe(fn, db: Session, label: str):
    """Run a notification fan-out without ever failing the business action.

    Notification generation is a side effect of an admin/teacher
    workflow; an unexpected error must only be logged, never abort
    the underlying request.
    """
    try:
        fn()
    except Exception as exc:  # pragma: no cover - defensive only
        print(f"{label} notification error:", str(exc))


def notify_teachers_of_class(
    db: Session,
    class_id: int,
    title: str,
    message: str,
    notification_type: str,
    reference_id: int | None = None,
    link: str | None = None,
):
    """Create a notification for every teacher assigned to a class."""
    from app.models.teacher_class import TeacherClass
    from app.models.user import User

    def _fanout():
        teacher_ids = (
            db.query(TeacherClass.teacher_user_id)
            .join(
                User,
                User.id == TeacherClass.teacher_user_id,
            )
            .filter(
                TeacherClass.class_id == class_id,
                User.role == "TEACHER",
                User.is_active.is_(True),
            )
            .distinct()
            .all()
        )

        for (teacher_user_id,) in teacher_ids:
            create_notification(
                db=db,
                user_id=teacher_user_id,
                title=title,
                message=message,
                notification_type=notification_type,
                reference_id=reference_id,
                link=link,
            )

    _safe(_fanout, db, "Teacher class")


def notify_all_teachers(
    db: Session,
    title: str,
    message: str,
    notification_type: str,
    reference_id: int | None = None,
    link: str | None = None,
):
    """Create a notification for every active teacher."""
    from app.models.user import User

    def _fanout():
        rows = (
            db.query(User.id)
            .filter(
                User.role == "TEACHER",
                User.is_active.is_(True),
            )
            .all()
        )

        for (teacher_user_id,) in rows:
            create_notification(
                db=db,
                user_id=teacher_user_id,
                title=title,
                message=message,
                notification_type=notification_type,
                reference_id=reference_id,
                link=link,
            )

    _safe(_fanout, db, "All teachers")


def notify_all_admins(
    db: Session,
    title: str,
    message: str,
    notification_type: str,
    reference_id: int | None = None,
    link: str | None = None,
):
    """Create a notification for every active admin."""
    from app.models.user import User

    def _fanout():
        rows = (
            db.query(User.id)
            .filter(
                User.role == "ADMIN",
                User.is_active.is_(True),
            )
            .all()
        )

        for (admin_user_id,) in rows:
            create_notification(
                db=db,
                user_id=admin_user_id,
                title=title,
                message=message,
                notification_type=notification_type,
                reference_id=reference_id,
                link=link,
            )

    _safe(_fanout, db, "All admins")