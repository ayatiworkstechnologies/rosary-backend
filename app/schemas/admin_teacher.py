from datetime import date

from pydantic import BaseModel, Field


class AdminTeacherCreate(BaseModel):
    name: str = Field(
        ...,
        min_length=1,
        max_length=150,
    )

    username: str = Field(
        ...,
        min_length=1,
        max_length=100,
    )

    email: str | None = Field(
        default=None,
        max_length=150,
    )

    password: str = Field(
        ...,
        min_length=6,
        max_length=100,
    )

    employee_id: str = Field(
        ...,
        min_length=1,
        max_length=50,
    )

    date_of_birth: date | None = None

    gender: str | None = Field(
        default=None,
        max_length=20,
    )

    phone: str | None = Field(
        default=None,
        max_length=30,
    )

    designation: str | None = Field(
        default=None,
        max_length=100,
    )

    department: str | None = Field(
        default=None,
        max_length=100,
    )

    qualification: str | None = Field(
        default=None,
        max_length=200,
    )

    specialization: str | None = Field(
        default=None,
        max_length=150,
    )

    experience_years: int | None = None

    joining_date: date | None = None

    profile_image_url: str | None = Field(
        default=None,
        max_length=500,
    )

    is_active: bool = True


class AdminTeacherUpdate(BaseModel):
    name: str = Field(
        ...,
        min_length=1,
        max_length=150,
    )

    username: str = Field(
        ...,
        min_length=1,
        max_length=100,
    )

    email: str | None = Field(
        default=None,
        max_length=150,
    )

    employee_id: str = Field(
        ...,
        min_length=1,
        max_length=50,
    )

    date_of_birth: date | None = None

    gender: str | None = Field(
        default=None,
        max_length=20,
    )

    phone: str | None = Field(
        default=None,
        max_length=30,
    )

    designation: str | None = Field(
        default=None,
        max_length=100,
    )

    department: str | None = Field(
        default=None,
        max_length=100,
    )

    qualification: str | None = Field(
        default=None,
        max_length=200,
    )

    specialization: str | None = Field(
        default=None,
        max_length=150,
    )

    experience_years: int | None = None

    joining_date: date | None = None

    profile_image_url: str | None = Field(
        default=None,
        max_length=500,
    )


class AdminTeacherStatusUpdate(BaseModel):
    is_active: bool


class AdminTeacherPasswordUpdate(BaseModel):
    password: str = Field(
        ...,
        min_length=6,
        max_length=100,
    )


class AdminTeacherClassCreate(BaseModel):
    class_id: int

    subject: str | None = Field(
        default=None,
        max_length=100,
    )

    is_class_teacher: bool = False


class AdminTeacherClassUpdate(BaseModel):
    subject: str | None = Field(
        default=None,
        max_length=100,
    )

    is_class_teacher: bool = False