from datetime import date, datetime, time

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


# =========================================================
# CREATE
# =========================================================

class AdminExamScheduleCreate(BaseModel):
    exam_id: int
    class_id: int

    subject: str = Field(
        ...,
        min_length=1,
        max_length=100,
    )

    exam_date: date

    start_time: time
    end_time: time

    room: str | None = Field(
        default=None,
        max_length=100,
    )

    instructions: str | None = Field(
        default=None,
        max_length=500,
    )

    @model_validator(mode="after")
    def validate_times(self):
        if self.end_time <= self.start_time:
            raise ValueError(
                "End time must be after start time"
            )

        return self


# =========================================================
# UPDATE
# =========================================================

class AdminExamScheduleUpdate(BaseModel):
    exam_id: int | None = None
    class_id: int | None = None

    subject: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    exam_date: date | None = None

    start_time: time | None = None
    end_time: time | None = None

    room: str | None = Field(
        default=None,
        max_length=100,
    )

    instructions: str | None = Field(
        default=None,
        max_length=500,
    )


# =========================================================
# RESPONSE
# =========================================================

class AdminExamScheduleResponse(BaseModel):
    id: int

    exam_id: int
    exam_name: str
    academic_year: str

    class_id: int
    class_name: str

    subject: str

    exam_date: date

    start_time: time
    end_time: time

    room: str | None = None
    instructions: str | None = None

    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(
        from_attributes=True
    )