from pydantic import BaseModel


class ParentProfileChildResponse(BaseModel):
    student_id: int

    admission_no: str

    full_name: str

    class_name: str | None = None

    academic_year: str | None = None

    relationship: str | None = None


class ParentProfileResponse(BaseModel):
    user_id: int

    name: str

    username: str

    email: str | None = None

    role: str

    is_active: bool

    phone: str | None = None

    alternate_phone: str | None = None

    occupation: str | None = None

    address: str | None = None

    city: str | None = None

    state: str | None = None

    pincode: str | None = None

    profile_image_url: str | None = None

    children: list[
        ParentProfileChildResponse
    ]