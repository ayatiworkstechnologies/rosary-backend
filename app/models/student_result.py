from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)

from sqlalchemy.sql import func

from app.database import Base


class StudentResult(Base):
    __tablename__ = "student_results"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    student_id = Column(
        Integer,
        ForeignKey(
            "students.id",
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

    exam_id = Column(
        Integer,
        ForeignKey(
            "exams.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    teacher_user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    subject = Column(
        String(100),
        nullable=False,
    )

    max_marks = Column(
        Numeric(6, 2),
        nullable=False,
    )

    obtained_marks = Column(
        Numeric(6, 2),
        nullable=False,
    )

    grade = Column(
        String(10),
        nullable=True,
    )

    remarks = Column(
        Text,
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
            "student_id",
            "exam_id",
            "subject",
            name="uq_student_exam_subject",
        ),
    )