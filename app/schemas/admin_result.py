from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


# =========================================================
# CREATE RESULT
# =========================================================

class AdminResultCreate(BaseModel):
    student_id: int
    exam_id: int

    subject: str = Field(
        ...,
        min_length=1,
        max_length=100,
    )

    max_marks: float = Field(
        ...,
        gt=0,
    )

    obtained_marks: float = Field(
        ...,
        ge=0,
    )

    remarks: str | None = None

    @model_validator(mode="after")
    def validate_marks(self):
        if (
            self.obtained_marks
            > self.max_marks
        ):
            raise ValueError(
                "Obtained marks cannot exceed maximum marks"
            )

        return self


# =========================================================
# UPDATE RESULT
# =========================================================

class AdminResultUpdate(BaseModel):
    student_id: int | None = None
    exam_id: int | None = None

    subject: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    max_marks: float | None = Field(
        default=None,
        gt=0,
    )

    obtained_marks: float | None = Field(
        default=None,
        ge=0,
    )

    remarks: str | None = None


# =========================================================
# RESPONSE
# =========================================================

class AdminResultResponse(BaseModel):
    id: int

    student_id: int
    admission_no: str
    roll_no: str | None = None
    student_name: str

    class_id: int
    class_name: str

    exam_id: int
    exam_name: str
    academic_year: str

    subject: str

    max_marks: float
    obtained_marks: float

    percentage: float
    grade: str | None = None

    remarks: str | None = None

    teacher_user_id: int | None = None

    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(
        from_attributes=True
    )