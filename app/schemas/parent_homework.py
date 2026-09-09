from datetime import date

from pydantic import BaseModel


class ParentHomeworkItemResponse(BaseModel):
    id: int

    class_id: int
    class_name: str

    teacher_user_id: int
    teacher_name: str | None = None

    subject: str
    title: str

    description: str | None = None

    assigned_date: date
    due_date: date

    attachment_url: str | None = None

    status: str


class ParentHomeworkListResponse(BaseModel):
    student_id: int
    student_name: str

    admission_no: str

    class_id: int
    class_name: str

    total: int

    homework: list[
        ParentHomeworkItemResponse
    ]