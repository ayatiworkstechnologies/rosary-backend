from datetime import date, time

from pydantic import BaseModel


class DashboardAttendanceResponse(BaseModel):
    total_marked_days: int
    present_count: int
    absent_count: int
    attendance_percentage: float


class DashboardResultResponse(BaseModel):
    exam_id: int
    exam_name: str
    total_marks: float
    obtained_marks: float
    percentage: float
    grade: str


class DashboardUpcomingExamResponse(BaseModel):
    exam_id: int
    exam_name: str
    subject: str
    exam_date: date

    start_time: time | None = None
    end_time: time | None = None

    room: str | None = None


class DashboardCircularResponse(BaseModel):
    id: int
    title: str
    category: str
    published_date: date


class DashboardFeeResponse(BaseModel):
    total_fee: float
    total_paid: float
    total_pending: float
    overdue_amount: float


class DashboardEventResponse(BaseModel):
    id: int
    title: str
    event_type: str
    start_date: date
    location: str | None = None


class ParentDashboardResponse(BaseModel):
    parent_name: str

    student_id: int
    student_name: str

    admission_no: str

    class_id: int | None = None
    class_name: str | None = None

    academic_year: str | None = None

    attendance: DashboardAttendanceResponse

    active_homework: int
    overdue_homework: int

    latest_result: DashboardResultResponse | None = None

    upcoming_exam: DashboardUpcomingExamResponse | None = None

    fees: DashboardFeeResponse

    latest_circulars: list[
        DashboardCircularResponse
    ]

    upcoming_events: list[
        DashboardEventResponse
    ]