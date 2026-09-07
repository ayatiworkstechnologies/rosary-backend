from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)

from app.database import Base


class TeacherClass(Base):
    __tablename__ = "teacher_classes"

    id = Column(
        Integer,
        primary_key=True,
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
        nullable=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "teacher_user_id",
            "class_id",
            name="uq_teacher_class",
        ),
    )