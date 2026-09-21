from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AdminExamCreate(BaseModel):
    name: str = Field(
        ...,
        min_length=1,
        max_length=150,
    )

    academic_year: str = Field(
        default="2026-2027",
        min_length=1,
        max_length=20,
    )

    start_date: date | None = None
    end_date: date | None = None

    is_active: bool = True

    @model_validator(mode="after")
    def validate_dates(self):
        if (
            self.start_date
            and self.end_date
            and self.end_date < self.start_date
        ):
            raise ValueError(
                "End date cannot be before start date"
            )

        return self


class AdminExamUpdate(BaseModel):
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=150,
    )

    academic_year: str | None = Field(
        default=None,
        min_length=1,
        max_length=20,
    )

    start_date: date | None = None
    end_date: date | None = None

    is_active: bool | None = None

    @model_validator(mode="after")
    def validate_dates(self):
        if (
            self.start_date
            and self.end_date
            and self.end_date < self.start_date
        ):
            raise ValueError(
                "End date cannot be before start date"
            )

        return self


class AdminExamStatusUpdate(BaseModel):
    is_active: bool


class AdminExamResponse(BaseModel):
    id: int

    name: str
    academic_year: str

    start_date: date | None = None
    end_date: date | None = None

    is_active: bool

    created_at: datetime | None = None

    model_config = ConfigDict(
        from_attributes=True
    )