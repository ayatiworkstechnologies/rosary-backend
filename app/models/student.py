from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Integer,
    String,
)

from app.database import Base


class Student(Base):
    __tablename__ = "students"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    admission_no = Column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )

    roll_no = Column(
        String(20),
        nullable=True,
    )

    full_name = Column(
        String(150),
        nullable=False,
    )

    gender = Column(
        String(20),
        nullable=True,
    )

    class_id = Column(
        Integer,
        ForeignKey(
            "school_classes.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
    )