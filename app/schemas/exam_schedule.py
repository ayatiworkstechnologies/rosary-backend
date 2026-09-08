from datetime import date, time

from pydantic import BaseModel


class ExamScheduleResponse(BaseModel):
    id: int

    exam_id: int
    exam_name: str

    class_id: int
    class_name: str

    subject: str

    exam_date: date

    start_time: time
    end_time: time

    room: str | None = None
    instructions: str | None = None


class ExamScheduleListResponse(BaseModel):
    total: int

    schedules: list[
        ExamScheduleResponse
    ]