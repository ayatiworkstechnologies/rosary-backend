from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
)

from sqlalchemy.sql import func

from app.database import Base


class SchoolEvent(Base):
    __tablename__ = "school_events"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    title = Column(
        String(250),
        nullable=False,
    )

    # EVENT
    # HOLIDAY
    # MEETING
    # ACADEMIC
    # EXAM
    event_type = Column(
        String(50),
        nullable=False,
        default="EVENT",
        index=True,
    )

    description = Column(
        Text,
        nullable=True,
    )

    start_date = Column(
        Date,
        nullable=False,
        index=True,
    )

    end_date = Column(
        Date,
        nullable=True,
    )

    start_time = Column(
        Time,
        nullable=True,
    )

    end_time = Column(
        Time,
        nullable=True,
    )

    location = Column(
        String(200),
        nullable=True,
    )

    # ALL
    # TEACHER
    # PARENT
    # CLASS
    audience = Column(
        String(30),
        nullable=False,
        default="ALL",
        index=True,
    )

    class_id = Column(
        Integer,
        ForeignKey(
            "school_classes.id",
            ondelete="CASCADE",
        ),
        nullable=True,
        index=True,
    )

    created_by = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
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