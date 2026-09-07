from datetime import date

from pydantic import BaseModel


class AttendanceRecordInput(BaseModel):
    student_id: int
    status: str
    remarks: str | None = None


class AttendanceSaveRequest(BaseModel):
    attendance_date: date
    records: list[AttendanceRecordInput]


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