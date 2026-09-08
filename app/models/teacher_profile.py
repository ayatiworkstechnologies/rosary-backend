from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
)

from sqlalchemy.sql import func

from app.database import Base


class TeacherProfile(Base):
    __tablename__ = "teacher_profiles"

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
        unique=True,
        nullable=False,
        index=True,
    )

    employee_id = Column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )

    phone = Column(
        String(30),
        nullable=True,
    )

    designation = Column(
        String(100),
        nullable=True,
    )

    department = Column(
        String(100),
        nullable=True,
    )

    qualification = Column(
        String(200),
        nullable=True,
    )

    experience_years = Column(
        Integer,
        nullable=True,
    )

    joining_date = Column(
        Date,
        nullable=True,
    )

    profile_image_url = Column(
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