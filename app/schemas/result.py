from pydantic import BaseModel


# =========================================================
# EXAM
# =========================================================

class ExamResponse(BaseModel):
    id: int
    name: str
    academic_year: str


# =========================================================
# RESULT INPUT
# =========================================================

class StudentResultInput(BaseModel):
    student_id: int

    max_marks: float
    obtained_marks: float

    remarks: str | None = None


class ResultSaveRequest(BaseModel):
    exam_id: int
    subject: str

    results: list[StudentResultInput]


# =========================================================
# STUDENT RESULT RESPONSE
# =========================================================

class StudentResultResponse(BaseModel):
    student_id: int

    admission_no: str
    roll_no: str | None = None
    full_name: str

    max_marks: float | None = None
    obtained_marks: float | None = None

    grade: str | None = None
    remarks: str | None = None


class ResultSheetResponse(BaseModel):
    class_id: int
    class_name: str

    exam_id: int
    exam_name: str

    subject: str

    total_students: int

    students: list[StudentResultResponse]


class ResultSaveResponse(BaseModel):
    message: str
    total: int