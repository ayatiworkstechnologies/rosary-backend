from pydantic import BaseModel, Field


class AdminParentLinkCreate(BaseModel):
    parent_user_id: int
    student_id: int
    relationship: str | None = Field(
        default=None,
        max_length=50,
    )


class AdminParentLinkUpdate(BaseModel):
    parent_user_id: int
    student_id: int
    relationship: str | None = Field(
        default=None,
        max_length=50,
    )