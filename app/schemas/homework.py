from datetime import date, datetime

from pydantic import BaseModel


# =========================================================
# CREATE HOMEWORK
# =========================================================

class HomeworkCreate(BaseModel):
    subject: str
    title: str

    description: str | None = None

    assigned_date: date
    due_date: date

    attachment_url: str | None = None


# =========================================================
# HOMEWORK RESPONSE
# =========================================================

class HomeworkResponse(BaseModel):
    id: int

    class_id: int
    class_name: str

    teacher_user_id: int

    subject: str
    title: str

    description: str | None = None

    assigned_date: date
    due_date: date

    attachment_url: str | None = None

    is_active: bool

    created_at: datetime | None = None


# =========================================================
# HOMEWORK LIST
# =========================================================

class HomeworkListResponse(BaseModel):
    class_id: int
    class_name: str

    total: int

    homework: list[HomeworkResponse]