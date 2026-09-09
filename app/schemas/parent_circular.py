from datetime import date

from pydantic import BaseModel


class ParentCircularResponse(BaseModel):
    id: int

    title: str

    category: str

    description: str | None = None

    published_date: date

    audience: str

    class_id: int | None = None

    class_name: str | None = None

    attachment_url: str | None = None


class ParentCircularListResponse(BaseModel):
    total: int

    circulars: list[
        ParentCircularResponse
    ]