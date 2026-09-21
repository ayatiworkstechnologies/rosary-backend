from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class AdminDownloadCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    category: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    audience: str = Field(..., min_length=1, max_length=30)
    class_id: int | None = None
    published_date: date
    is_active: bool = True


class AdminDownloadUpdate(BaseModel):
    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )

    category: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    description: str | None = None

    audience: str | None = Field(
        default=None,
        min_length=1,
        max_length=30,
    )

    class_id: int | None = None
    published_date: date | None = None
    is_active: bool | None = None


class AdminDownloadStatusUpdate(BaseModel):
    is_active: bool


class AdminDownloadResponse(BaseModel):
    id: int
    title: str
    category: str
    description: str | None = None
    audience: str
    class_id: int | None = None

    file_name: str
    file_url: str

    published_date: date
    is_active: bool

    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)