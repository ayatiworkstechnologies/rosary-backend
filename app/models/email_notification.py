from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from app.database import Base


class EmailNotificationBatch(Base):
    __tablename__ = "email_notification_batches"

    id = Column(Integer, primary_key=True)
    idempotency_key = Column(String(64), nullable=False, unique=True, index=True)
    request_fingerprint = Column(String(64), nullable=False)
    created_by = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    target_type = Column(String(40), nullable=False)
    category = Column(String(40), nullable=False, default="GENERAL")
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    send_in_app = Column(Boolean, nullable=False, default=True)
    send_email = Column(Boolean, nullable=False, default=False)
    status = Column(String(30), nullable=False, default="QUEUED", index=True)
    parent_recipient_count = Column(Integer, nullable=False, default=0)
    email_recipient_count = Column(Integer, nullable=False, default=0)
    missing_email_count = Column(Integer, nullable=False, default=0)
    invalid_email_count = Column(Integer, nullable=False, default=0)
    unverified_email_count = Column(Integer, nullable=False, default=0)
    opted_out_count = Column(Integer, nullable=False, default=0)
    deduplicated_email_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)


class EmailDelivery(Base):
    __tablename__ = "email_deliveries"

    id = Column(Integer, primary_key=True)
    batch_id = Column(
        Integer,
        ForeignKey("email_notification_batches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    email = Column(String(254), nullable=False)
    status = Column(String(30), nullable=False, default="QUEUED", index=True)
    attempt_count = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=3)
    next_attempt_at = Column(DateTime, nullable=True, index=True)
    last_error = Column(Text, nullable=True)
    provider_message_id = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    sent_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("batch_id", "email", name="uq_email_delivery_batch_email"),
    )
