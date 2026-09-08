from datetime import date

from pydantic import BaseModel


class TeacherAssignedClassResponse(BaseModel):
    class_id: int

    class_name: str

    subject: str | None = None

    academic_year: str


class TeacherProfileResponse(BaseModel):
    user_id: int

    name: str
    username: str

    email: str | None = None

    role: str

    is_active: bool

    employee_id: str | None = None

    phone: str | None = None

    designation: str | None = None

    department: str | None = None

    qualification: str | None = None

    experience_years: int | None = None

    joining_date: date | None = None

    profile_image_url: str | None = None

    assigned_classes: list[
        TeacherAssignedClassResponse
    ]