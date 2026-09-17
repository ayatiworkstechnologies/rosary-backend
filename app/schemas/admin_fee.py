from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class AdminFeeCreate(BaseModel):
    student_id: int

    academic_year: str = Field(
        ...,
        min_length=1,
        max_length=20,
    )

    fee_title: str = Field(
        ...,
        min_length=1,
        max_length=150,
    )

    fee_type: str = Field(
        ...,
        min_length=1,
        max_length=50,
    )

    amount: Decimal = Field(
        ...,
        ge=0,
    )

    paid_amount: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
    )

    due_date: date

    paid_date: date | None = None

    receipt_no: str | None = Field(
        default=None,
        max_length=100,
    )

    payment_mode: str | None = Field(
        default=None,
        max_length=50,
    )

    remarks: str | None = None

    is_active: bool = True


class AdminFeeUpdate(BaseModel):
    student_id: int

    academic_year: str = Field(
        ...,
        min_length=1,
        max_length=20,
    )

    fee_title: str = Field(
        ...,
        min_length=1,
        max_length=150,
    )

    fee_type: str = Field(
        ...,
        min_length=1,
        max_length=50,
    )

    amount: Decimal = Field(
        ...,
        ge=0,
    )

    due_date: date

    remarks: str | None = None


class AdminFeePaymentUpdate(BaseModel):
    paid_amount: Decimal = Field(
        ...,
        ge=0,
    )

    paid_date: date | None = None

    receipt_no: str | None = Field(
        default=None,
        max_length=100,
    )

    payment_mode: str | None = Field(
        default=None,
        max_length=50,
    )

    remarks: str | None = None


class AdminFeeStatusUpdate(BaseModel):
    is_active: bool