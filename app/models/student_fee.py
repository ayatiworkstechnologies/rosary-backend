from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)

from sqlalchemy.sql import func

from app.database import Base


class StudentFee(Base):
    __tablename__ = "student_fees"

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

    academic_year = Column(
        String(20),
        nullable=False,
        index=True,
    )

    fee_title = Column(
        String(150),
        nullable=False,
    )

    fee_type = Column(
        String(50),
        nullable=False,
        default="TUITION",
    )

    amount = Column(
        Numeric(10, 2),
        nullable=False,
    )

    paid_amount = Column(
        Numeric(10, 2),
        nullable=False,
        default=0,
    )

    due_date = Column(
        Date,
        nullable=False,
        index=True,
    )

    paid_date = Column(
        Date,
        nullable=True,
    )

    receipt_no = Column(
        String(100),
        nullable=True,
    )

    payment_mode = Column(
        String(50),
        nullable=True,
    )

    remarks = Column(
        Text,
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