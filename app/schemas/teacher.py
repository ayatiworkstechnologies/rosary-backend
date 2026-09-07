from pydantic import BaseModel


class TeacherClassResponse(BaseModel):
    id: int
    name: str
    section: str
    academic_year: str
    display_name: str


class TeacherStudentResponse(BaseModel):
    id: int
    admission_no: str
    roll_no: str | None = None
    full_name: str
    gender: str | None = None
    class_id: int
    class_name: str
    status: str


class TeacherStudentListResponse(BaseModel):
    class_id: int
    class_name: str
    total: int
    students: list[TeacherStudentResponse]

class TeacherClassResponse(BaseModel):
    id: int
    name: str
    section: str
    academic_year: str
    display_name: str
    subject: str | None = None