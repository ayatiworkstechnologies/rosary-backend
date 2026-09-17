from datetime import date

from pydantic import BaseModel, Field


class AdminCircularCreate(BaseModel):
    title: str = Field(
        ...,
        min_length=1,
        max_length=255,
    )

    category: str = Field(
        ...,
        min_length=1,
        max_length=100,
    )

    description: str = Field(
        ...,
        min_length=1,
    )

    published_date: date

    audience: str = Field(
        ...,
        min_length=1,
        max_length=30,
    )

    class_id: int | None = None

    attachment_url: str | None = Field(
        default=None,
        max_length=500,
    )

    created_by: int | None = None

    is_active: bool = True


class AdminCircularUpdate(BaseModel):
    title: str = Field(
        ...,
        min_length=1,
        max_length=255,
    )

    category: str = Field(
        ...,
        min_length=1,
        max_length=100,
    )

    description: str = Field(
        ...,
        min_length=1,
    )

    published_date: date

    audience: str = Field(
        ...,
        min_length=1,
        max_length=30,
    )

    class_id: int | None = None

    attachment_url: str | None = Field(
        default=None,
        max_length=500,
    )


class AdminCircularStatusUpdate(BaseModel):
    is_active: bool