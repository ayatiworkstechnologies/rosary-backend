from datetime import date

from pydantic import BaseModel


class ParentAttendanceRecordResponse(BaseModel):
    attendance_date: date

    status: str

    remarks: str | None = None


class ParentAttendanceResponse(BaseModel):
    student_id: int

    student_name: str

    admission_no: str

    class_id: int | None = None

    class_name: str | None = None

    year: int

    month: int

    total_marked_days: int

    present_count: int

    absent_count: int

    attendance_percentage: float

    records: list[
        ParentAttendanceRecordResponse
    ]