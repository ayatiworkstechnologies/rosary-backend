from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class NotificationResponse(BaseModel):
    id: int
    user_id: int
    title: str
    message: str
    notification_type: Optional[str] = None
    reference_id: Optional[int] = None
    link: Optional[str] = None
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True

class NotificationListResponse(BaseModel):
    data: list[NotificationResponse]

    page: int
    page_size: int
    total: int
    total_pages: int
    has_next: bool
    has_previous: bool
    