from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Time,
    UniqueConstraint,
)

from sqlalchemy.sql import func

from app.database import Base


class ExamSchedule(Base):
    __tablename__ = "exam_schedules"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    exam_id = Column(
        Integer,
        ForeignKey(
            "exams.id",
            ondelete="CASCADE",
        ),
        nullable=False,
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

    subject = Column(
        String(100),
        nullable=False,
    )

    exam_date = Column(
        Date,
        nullable=False,
        index=True,
    )

    start_time = Column(
        Time,
        nullable=False,
    )

    end_time = Column(
        Time,
        nullable=False,
    )

    room = Column(
        String(100),
        nullable=True,
    )

    instructions = Column(
        String(500),
        nullable=True,
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

    __table_args__ = (
        UniqueConstraint(
            "exam_id",
            "class_id",
            "subject",
            "exam_date",
            name="uq_exam_class_subject_date",
        ),
    )