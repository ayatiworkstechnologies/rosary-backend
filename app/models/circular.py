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


class Circular(Base):
    __tablename__ = "circulars"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    title = Column(
        String(250),
        nullable=False,
    )

    category = Column(
        String(100),
        nullable=False,
        default="General",
    )

    description = Column(
        Text,
        nullable=True,
    )

    published_date = Column(
        Date,
        nullable=False,
        index=True,
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

    # Used only when audience = CLASS
    class_id = Column(
        Integer,
        ForeignKey(
            "school_classes.id",
            ondelete="CASCADE",
        ),
        nullable=True,
        index=True,
    )

    attachment_url = Column(
        String(500),
        nullable=True,
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