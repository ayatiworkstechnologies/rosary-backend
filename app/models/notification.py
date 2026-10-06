from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
)
from sqlalchemy.sql import func

from app.database import Base


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    title = Column(
        String(200),
        nullable=False,
    )

    message = Column(
        Text,
        nullable=False,
    )

    notification_type = Column(
        String(50),
        nullable=True,
    )

    reference_id = Column(
        Integer,
        nullable=True,
    )

    link = Column(
        String(500),
        nullable=True,
    )

    is_read = Column(
        Boolean,
        nullable=False,
        default=False,
    )

    created_at = Column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )