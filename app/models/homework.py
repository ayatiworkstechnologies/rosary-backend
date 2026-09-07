from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)

from sqlalchemy.sql import func

from app.database import Base


class Homework(Base):
    __tablename__ = "homework"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    class_id = Column(
        Integer,
        ForeignKey(
            "school_classes.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    teacher_user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    subject = Column(
        String(100),
        nullable=False,
    )

    title = Column(
        String(200),
        nullable=False,
    )

    description = Column(
        Text,
        nullable=True,
    )

    assigned_date = Column(
        Date,
        nullable=False,
    )

    due_date = Column(
        Date,
        nullable=False,
    )

    attachment_url = Column(
        String(500),
        nullable=True,
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
    )

    created_at = Column(
        DateTime,
        server_default=func.now(),
    )

    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )