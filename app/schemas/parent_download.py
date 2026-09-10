from datetime import date

from pydantic import BaseModel


class ParentDownloadFormResponse(BaseModel):
    id: int

    title: str

    category: str

    description: str | None = None

    audience: str

    class_id: int | None = None

    class_name: str | None = None

    file_name: str

    file_url: str

    published_date: date


class ParentDownloadFormListResponse(BaseModel):
    total: int

    forms: list[
        ParentDownloadFormResponse
    ]