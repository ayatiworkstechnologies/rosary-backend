from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from sqlalchemy.sql import func

from app.database import Base


class Attendance(Base):
    __tablename__ = "attendance"

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

    attendance_date = Column(
        Date,
        nullable=False,
        index=True,
    )

    status = Column(
        String(20),
        nullable=False,
    )

    remarks = Column(
        Text,
        nullable=True,
    )

    marked_by = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
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
            "attendance_date",
            name="uq_student_attendance_date",
        ),
    )