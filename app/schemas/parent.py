from pydantic import BaseModel


class ParentChildResponse(BaseModel):
    id: int

    admission_no: str

    roll_no: str | None = None

    full_name: str

    gender: str | None = None

    class_id: int | None = None

    class_name: str | None = None

    academic_year: str | None = None

    relationship: str | None = None

    status: str


class ParentChildrenListResponse(BaseModel):
    total: int

    children: list[
        ParentChildResponse
    ]