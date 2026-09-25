from datetime import date

from pydantic import BaseModel, Field


class AdminStudentCreate(BaseModel):
    admission_no: str = Field(
        ...,
        min_length=1,
        max_length=50,
    )

    roll_no: str | None = Field(
        default=None,
        max_length=20,
    )

    full_name: str = Field(
        ...,
        min_length=1,
        max_length=150,
    )

    date_of_birth: date | None = None

    gender: str | None = Field(
        default=None,
        max_length=20,
    )

    class_id: int | None = None

    is_active: bool = True


class AdminStudentUpdate(BaseModel):
    admission_no: str = Field(
        ...,
        min_length=1,
        max_length=50,
    )

    roll_no: str | None = Field(
        default=None,
        max_length=20,
    )

    full_name: str = Field(
        ...,
        min_length=1,
        max_length=150,
    )

    date_of_birth: date | None = None

    gender: str | None = Field(
        default=None,
        max_length=20,
    )

    class_id: int | None = None

    is_active: bool = True


class AdminStudentStatusUpdate(BaseModel):
    is_active: bool