from datetime import date, time

from pydantic import BaseModel


class ParentCalendarEventResponse(BaseModel):
    id: int

    title: str

    event_type: str

    description: str | None = None

    start_date: date

    end_date: date | None = None

    start_time: time | None = None

    end_time: time | None = None

    location: str | None = None

    audience: str

    class_id: int | None = None

    class_name: str | None = None


class ParentCalendarListResponse(BaseModel):
    total: int

    events: list[
        ParentCalendarEventResponse
    ]