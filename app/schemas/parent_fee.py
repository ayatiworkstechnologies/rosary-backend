from datetime import date

from pydantic import BaseModel


class ParentFeeItemResponse(BaseModel):
    id: int

    fee_title: str

    fee_type: str

    amount: float

    paid_amount: float

    pending_amount: float

    due_date: date

    paid_date: date | None = None

    receipt_no: str | None = None

    payment_mode: str | None = None

    remarks: str | None = None

    status: str


class ParentFeeResponse(BaseModel):
    student_id: int

    student_name: str

    admission_no: str

    class_name: str | None = None

    academic_year: str

    total_fee: float

    total_paid: float

    total_pending: float

    overdue_amount: float

    total_items: int

    fees: list[
        ParentFeeItemResponse
    ]