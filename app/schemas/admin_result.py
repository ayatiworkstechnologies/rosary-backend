from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
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

    obtained_marks: float | None = Field(
        default=None,
        ge=0,
    )

    result_status: str = Field(
        default="PRESENT",
        max_length=20,
    )

    remarks: str | None = None

    @field_validator("result_status")
    @classmethod
    def validate_result_status(
        cls,
        value: str,
    ):
        status = value.strip().upper()

        allowed_statuses = {
            "PRESENT",
            "ABSENT",
        }

        if status not in allowed_statuses:
            raise ValueError(
                "Result status must be PRESENT or ABSENT"
            )

        return status

    @model_validator(mode="after")
    def validate_marks(self):
        # ---------------------------------------------
        # ABSENT
        # ---------------------------------------------
        if self.result_status == "ABSENT":
            if self.obtained_marks is not None:
                raise ValueError(
                    "Obtained marks must be null "
                    "when result status is ABSENT"
                )

            return self

        # ---------------------------------------------
        # PRESENT
        # ---------------------------------------------
        if self.obtained_marks is None:
            raise ValueError(
                "Obtained marks are required "
                "when result status is PRESENT"
            )

        if (
            self.obtained_marks
            > self.max_marks
        ):
            raise ValueError(
                "Obtained marks cannot exceed "
                "maximum marks"
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

    result_status: str | None = Field(
        default=None,
        max_length=20,
    )

    remarks: str | None = None

    @field_validator("result_status")
    @classmethod
    def validate_result_status(
        cls,
        value: str | None,
    ):
        if value is None:
            return None

        status = value.strip().upper()

        allowed_statuses = {
            "PRESENT",
            "ABSENT",
        }

        if status not in allowed_statuses:
            raise ValueError(
                "Result status must be PRESENT or ABSENT"
            )

        return status

    @model_validator(mode="after")
    def validate_update_marks(self):
        # If explicitly changing to ABSENT,
        # obtained_marks must not contain a number.
        if (
            self.result_status == "ABSENT"
            and self.obtained_marks is not None
        ):
            raise ValueError(
                "Obtained marks must be null "
                "when result status is ABSENT"
            )

        # When both marks are supplied,
        # validate the numeric range.
        if (
            self.max_marks is not None
            and self.obtained_marks is not None
            and self.obtained_marks > self.max_marks
        ):
            raise ValueError(
                "Obtained marks cannot exceed "
                "maximum marks"
            )

        return self


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

    obtained_marks: float | None = None

    result_status: str

    percentage: float

    grade: str | None = None

    remarks: str | None = None

    teacher_user_id: int | None = None

    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(
        from_attributes=True
    )