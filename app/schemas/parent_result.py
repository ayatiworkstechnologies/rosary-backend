from pydantic import BaseModel


class ParentResultExamResponse(BaseModel):
    id: int
    name: str
    academic_year: str


class ParentResultExamListResponse(BaseModel):
    total: int

    exams: list[
        ParentResultExamResponse
    ]


class ParentResultItemResponse(BaseModel):
    id: int

    subject: str

    max_marks: float

    obtained_marks: float

    percentage: float

    grade: str | None = None

    remarks: str | None = None


class ParentResultsResponse(BaseModel):
    student_id: int

    student_name: str

    admission_no: str

    class_id: int | None = None

    class_name: str | None = None

    exam_id: int

    exam_name: str

    academic_year: str

    total_subjects: int

    total_max_marks: float

    total_obtained_marks: float

    overall_percentage: float

    overall_grade: str

    results: list[
        ParentResultItemResponse
    ]