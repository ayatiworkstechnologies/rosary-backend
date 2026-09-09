from datetime import date, time

from pydantic import BaseModel


class ParentExamOptionResponse(BaseModel):
    id: int
    name: str
    academic_year: str


class ParentExamScheduleItemResponse(BaseModel):
    id: int

    exam_id: int
    exam_name: str

    subject: str

    exam_date: date

    start_time: time
    end_time: time

    room: str | None = None

    instructions: str | None = None


class ParentExamScheduleResponse(BaseModel):
    student_id: int

    student_name: str

    admission_no: str

    class_id: int

    class_name: str

    total: int

    exams: list[
        ParentExamOptionResponse
    ]

    schedules: list[
        ParentExamScheduleItemResponse
    ]