from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class DownloadFormBase(BaseModel):
    title: str
    category: str
    description: str | None = None
    audience: str
    class_id: int | None = None
    published_date: date
    is_active: bool = True


class DownloadFormCreate(DownloadFormBase):
    pass


class DownloadFormUpdate(BaseModel):
    title: str | None = None
    category: str | None = None
    description: str | None = None
    audience: str | None = None
    class_id: int | None = None
    published_date: date | None = None
    is_active: bool | None = None


class DownloadFormStatusUpdate(BaseModel):
    is_active: bool


class DownloadFormResponse(DownloadFormBase):
    id: int
    file_name: str
    file_url: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)