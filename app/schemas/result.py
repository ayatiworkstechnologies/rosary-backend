from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
)


# =========================================================
# EXAM
# =========================================================

class ExamResponse(BaseModel):
    id: int
    name: str
    academic_year: str


# =========================================================
# RESULT INPUT
# =========================================================

class StudentResultInput(BaseModel):
    student_id: int

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

        # -------------------------------------------------
        # ABSENT
        # -------------------------------------------------

        if self.result_status == "ABSENT":

            if self.obtained_marks is not None:
                raise ValueError(
                    "Obtained marks must be null "
                    "when result status is ABSENT"
                )

            return self

        # -------------------------------------------------
        # PRESENT
        # -------------------------------------------------

        if self.obtained_marks is None:
            raise ValueError(
                "Obtained marks are required "
                "when result status is PRESENT"
            )

        if self.obtained_marks > self.max_marks:
            raise ValueError(
                "Obtained marks cannot exceed "
                "maximum marks"
            )

        return self


class ResultSaveRequest(BaseModel):
    exam_id: int

    subject: str = Field(
        ...,
        min_length=1,
        max_length=100,
    )

    results: list[
        StudentResultInput
    ]


# =========================================================
# STUDENT RESULT RESPONSE
# =========================================================

class StudentResultResponse(BaseModel):
    student_id: int

    admission_no: str
    roll_no: str | None = None
    full_name: str

    max_marks: float | None = None

    obtained_marks: float | None = None

    result_status: str | None = None

    grade: str | None = None

    remarks: str | None = None


class ResultSheetResponse(BaseModel):
    class_id: int
    class_name: str

    exam_id: int
    exam_name: str

    subject: str

    total_students: int

    students: list[
        StudentResultResponse
    ]


class ResultSaveResponse(BaseModel):
    message: str
    total: int