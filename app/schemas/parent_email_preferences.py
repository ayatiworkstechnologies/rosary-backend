from datetime import datetime

from pydantic import BaseModel


class EmailPreferencesResponse(BaseModel):
    email: str | None
    email_verified_at: datetime | None
    email_notifications_enabled: bool
    verification_required: bool


class EmailPreferenceUpdate(BaseModel):
    email_notifications_enabled: bool


class EmailTokenRequest(BaseModel):
    token: str


class MessageResponse(BaseModel):
    message: str
