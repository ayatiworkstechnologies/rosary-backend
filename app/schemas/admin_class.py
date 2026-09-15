from pydantic import BaseModel, Field


class AdminClassCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    section: str = Field(..., min_length=1, max_length=20)
    academic_year: str = Field(..., min_length=1, max_length=20)
    is_active: bool = True


class AdminClassUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    section: str = Field(..., min_length=1, max_length=20)
    academic_year: str = Field(..., min_length=1, max_length=20)
    is_active: bool = True


class AdminClassStatusUpdate(BaseModel):
    is_active: bool