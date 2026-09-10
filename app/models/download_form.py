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


class DownloadForm(Base):
    __tablename__ = "download_forms"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    title = Column(
        String(200),
        nullable=False,
    )

    category = Column(
        String(100),
        nullable=False,
        default="GENERAL",
        index=True,
    )

    description = Column(
        Text,
        nullable=True,
    )

    # ALL / PARENT / CLASS
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

    file_name = Column(
        String(255),
        nullable=False,
    )

    file_url = Column(
        String(500),
        nullable=False,
    )

    published_date = Column(
        Date,
        nullable=False,
        index=True,
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