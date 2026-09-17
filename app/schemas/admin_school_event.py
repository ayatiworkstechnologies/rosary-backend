from datetime import date, time

from pydantic import BaseModel, Field


class AdminSchoolEventCreate(BaseModel):
    title: str = Field(
        ...,
        min_length=1,
        max_length=250,
    )

    event_type: str = Field(
        ...,
        min_length=1,
        max_length=50,
    )

    description: str | None = None

    start_date: date

    end_date: date | None = None

    start_time: time | None = None

    end_time: time | None = None

    location: str | None = Field(
        default=None,
        max_length=200,
    )

    audience: str = Field(
        ...,
        min_length=1,
        max_length=30,
    )

    class_id: int | None = None

    created_by: int | None = None

    is_active: bool = True


class AdminSchoolEventUpdate(BaseModel):
    title: str = Field(
        ...,
        min_length=1,
        max_length=250,
    )

    event_type: str = Field(
        ...,
        min_length=1,
        max_length=50,
    )

    description: str | None = None

    start_date: date

    end_date: date | None = None

    start_time: time | None = None

    end_time: time | None = None

    location: str | None = Field(
        default=None,
        max_length=200,
    )

    audience: str = Field(
        ...,
        min_length=1,
        max_length=30,
    )

    class_id: int | None = None


class AdminSchoolEventStatusUpdate(BaseModel):
    is_active: bool