from datetime import date

from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
)


class AttendanceRecordInput(BaseModel):
    student_id: int = Field(gt=0)
    status: str
    remarks: str | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        normalized = value.strip().upper()

        if normalized not in {"PRESENT", "ABSENT"}:
            raise ValueError(
                "Attendance status must be PRESENT or ABSENT"
            )

        return normalized


class AttendanceSaveRequest(BaseModel):
    attendance_date: date
    records: list[AttendanceRecordInput] = Field(min_length=1)

    @field_validator("attendance_date")
    @classmethod
    def validate_date(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("Future attendance dates are not allowed")

        return value

    @model_validator(mode="after")
    def validate_duplicate_students(self):
        student_ids = [record.student_id for record in self.records]

        if len(student_ids) != len(set(student_ids)):
            raise ValueError("Duplicate student IDs are not allowed")

        return self


class AttendanceStudentResponse(BaseModel):
    student_id: int
    admission_no: str
    roll_no: str | None = None
    full_name: str

    status: str | None = None
    remarks: str | None = None


class AttendanceSheetResponse(BaseModel):
    class_id: int
    class_name: str

    attendance_date: date

    total_students: int

    present_count: int
    absent_count: int
    not_marked_count: int

    students: list[AttendanceStudentResponse]


class AttendanceSaveResponse(BaseModel):
    message: str
    attendance_date: date

    total: int
    present_count: int
    absent_count: int
