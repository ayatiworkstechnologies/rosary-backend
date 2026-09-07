from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
)

from app.database import Base


class SchoolClass(Base):
    __tablename__ = "school_classes"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    name = Column(
        String(50),
        nullable=False,
    )

    section = Column(
        String(20),
        nullable=False,
    )

    academic_year = Column(
        String(20),
        nullable=False,
        default="2026-2027",
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
    )