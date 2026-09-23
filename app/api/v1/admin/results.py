from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db

from app.models.exam import Exam
from app.models.school_class import SchoolClass
from app.models.student import Student
from app.models.student_result import StudentResult

from app.schemas.admin_result import (
    AdminResultCreate,
    AdminResultResponse,
    AdminResultUpdate,
)
from app.dependencies import get_current_admin

router = APIRouter(
    prefix="/api/v1/admin/results",
    tags=["Admin Results"],
    dependencies=[
        Depends(get_current_admin)
    ],
)


# =========================================================
# GRADE CALCULATION
# Same grading logic as Teacher Results
# =========================================================

def calculate_grade(
    obtained_marks: float,
    max_marks: float,
):
    if max_marks <= 0:
        return None

    percentage = (
        obtained_marks
        / max_marks
    ) * 100

    if percentage >= 90:
        return "A+"

    if percentage >= 80:
        return "A"

    if percentage >= 70:
        return "B+"

    if percentage >= 60:
        return "B"

    if percentage >= 50:
        return "C"

    if percentage >= 40:
        return "D"

    return "F"


# =========================================================
# BUILD RESPONSE
# =========================================================

def build_result_response(
    result: StudentResult,
    student: Student,
    school_class: SchoolClass,
    exam: Exam,
):
    max_marks = float(
        result.max_marks
    )

    obtained_marks = float(
        result.obtained_marks
    )

    percentage = 0.0

    if max_marks > 0:
        percentage = round(
            (
                obtained_marks
                / max_marks
            )
            * 100,
            2,
        )

    return {
        "id":
            result.id,

        "student_id":
            student.id,

        "admission_no":
            student.admission_no,

        "roll_no":
            student.roll_no,

        "student_name":
            student.full_name,

        "class_id":
            school_class.id,

        "class_name":
            (
                f"{school_class.name} - "
                f"{school_class.section}"
            ),

        "exam_id":
            exam.id,

        "exam_name":
            exam.name,

        "academic_year":
            exam.academic_year,

        "subject":
            result.subject,

        "max_marks":
            max_marks,

        "obtained_marks":
            obtained_marks,

        "percentage":
            percentage,

        "grade":
            result.grade,

        "remarks":
            result.remarks,

        "teacher_user_id":
            result.teacher_user_id,

        "created_at":
            result.created_at,

        "updated_at":
            result.updated_at,
    }


# =========================================================
# GET ALL RESULTS
# =========================================================

@router.get(
    "",
    response_model=list[
        AdminResultResponse
    ],
)
def get_admin_results(
    search: str | None = Query(
        default=None
    ),
    class_id: int | None = Query(
        default=None
    ),
    exam_id: int | None = Query(
        default=None
    ),
    subject: str | None = Query(
        default=None
    ),
    db: Session = Depends(get_db),
):
    query = (
        db.query(
            StudentResult,
            Student,
            SchoolClass,
            Exam,
        )
        .join(
            Student,
            Student.id
            == StudentResult.student_id,
        )
        .join(
            SchoolClass,
            SchoolClass.id
            == StudentResult.class_id,
        )
        .join(
            Exam,
            Exam.id
            == StudentResult.exam_id,
        )
    )

    # -----------------------------------------------------
    # SEARCH
    # -----------------------------------------------------

    if search:
        search_value = (
            f"%{search.strip()}%"
        )

        query = query.filter(
            or_(
                Student.full_name.ilike(
                    search_value
                ),
                Student.admission_no.ilike(
                    search_value
                ),
                Student.roll_no.ilike(
                    search_value
                ),
                StudentResult.subject.ilike(
                    search_value
                ),
            )
        )

    # -----------------------------------------------------
    # CLASS FILTER
    # -----------------------------------------------------

    if class_id is not None:
        query = query.filter(
            StudentResult.class_id
            == class_id
        )

    # -----------------------------------------------------
    # EXAM FILTER
    # -----------------------------------------------------

    if exam_id is not None:
        query = query.filter(
            StudentResult.exam_id
            == exam_id
        )

    # -----------------------------------------------------
    # SUBJECT FILTER
    # -----------------------------------------------------

    if subject:
        query = query.filter(
            StudentResult.subject
            == subject.strip()
        )

    rows = (
        query
        .order_by(
            Exam.id.desc(),
            SchoolClass.id.asc(),
            Student.roll_no.asc(),
            Student.id.asc(),
        )
        .all()
    )

    return [
        build_result_response(
            result=result,
            student=student,
            school_class=school_class,
            exam=exam,
        )
        for (
            result,
            student,
            school_class,
            exam,
        ) in rows
    ]


# =========================================================
# GET SINGLE RESULT
# =========================================================

@router.get(
    "/{result_id}",
    response_model=AdminResultResponse,
)
def get_admin_result(
    result_id: int,
    db: Session = Depends(get_db),
):
    row = (
        db.query(
            StudentResult,
            Student,
            SchoolClass,
            Exam,
        )
        .join(
            Student,
            Student.id
            == StudentResult.student_id,
        )
        .join(
            SchoolClass,
            SchoolClass.id
            == StudentResult.class_id,
        )
        .join(
            Exam,
            Exam.id
            == StudentResult.exam_id,
        )
        .filter(
            StudentResult.id
            == result_id
        )
        .first()
    )

    if not row:
        raise HTTPException(
            status_code=
                status.HTTP_404_NOT_FOUND,
            detail="Result not found",
        )

    (
        result,
        student,
        school_class,
        exam,
    ) = row

    return build_result_response(
        result=result,
        student=student,
        school_class=school_class,
        exam=exam,
    )


# =========================================================
# CREATE RESULT
# =========================================================

@router.post(
    "",
    response_model=AdminResultResponse,
    status_code=
        status.HTTP_201_CREATED,
)
def create_admin_result(
    payload: AdminResultCreate,
    db: Session = Depends(get_db),
):
    # -----------------------------------------------------
    # STUDENT
    # -----------------------------------------------------

    student = (
        db.query(Student)
        .filter(
            Student.id
            == payload.student_id
        )
        .first()
    )

    if not student:
        raise HTTPException(
            status_code=
                status.HTTP_404_NOT_FOUND,
            detail="Student not found",
        )

    if student.class_id is None:
        raise HTTPException(
            status_code=
                status.HTTP_400_BAD_REQUEST,
            detail=(
                "Student is not assigned "
                "to a class"
            ),
        )

    # -----------------------------------------------------
    # CLASS
    # -----------------------------------------------------

    school_class = (
        db.query(SchoolClass)
        .filter(
            SchoolClass.id
            == student.class_id
        )
        .first()
    )

    if not school_class:
        raise HTTPException(
            status_code=
                status.HTTP_404_NOT_FOUND,
            detail="Student class not found",
        )

    # -----------------------------------------------------
    # EXAM
    # -----------------------------------------------------

    exam = (
        db.query(Exam)
        .filter(
            Exam.id
            == payload.exam_id
        )
        .first()
    )

    if not exam:
        raise HTTPException(
            status_code=
                status.HTTP_404_NOT_FOUND,
            detail="Exam not found",
        )

    # -----------------------------------------------------
    # VALIDATE MARKS
    # -----------------------------------------------------

    if payload.max_marks <= 0:
        raise HTTPException(
            status_code=
                status.HTTP_400_BAD_REQUEST,
            detail=(
                "Maximum marks must "
                "be greater than zero"
            ),
        )

    if payload.obtained_marks < 0:
        raise HTTPException(
            status_code=
                status.HTTP_400_BAD_REQUEST,
            detail=(
                "Obtained marks cannot "
                "be negative"
            ),
        )

    if (
        payload.obtained_marks
        > payload.max_marks
    ):
        raise HTTPException(
            status_code=
                status.HTTP_400_BAD_REQUEST,
            detail=(
                "Obtained marks cannot "
                "exceed maximum marks"
            ),
        )

    subject = (
        payload.subject.strip()
    )

    # -----------------------------------------------------
    # DUPLICATE CHECK
    # -----------------------------------------------------

    existing = (
        db.query(StudentResult)
        .filter(
            StudentResult.student_id
            == student.id,

            StudentResult.exam_id
            == exam.id,

            StudentResult.subject
            == subject,
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=
                status.HTTP_409_CONFLICT,
            detail=(
                "Result already exists "
                "for this student, exam "
                "and subject"
            ),
        )

    # -----------------------------------------------------
    # CALCULATE GRADE
    # -----------------------------------------------------

    grade = calculate_grade(
        payload.obtained_marks,
        payload.max_marks,
    )

    # -----------------------------------------------------
    # CREATE
    # -----------------------------------------------------

    result = StudentResult(
        student_id=
            student.id,

        class_id=
            school_class.id,

        exam_id=
            exam.id,

        # Admin-created result
        # has no teacher owner.
        teacher_user_id=None,

        subject=
            subject,

        max_marks=
            payload.max_marks,

        obtained_marks=
            payload.obtained_marks,

        grade=
            grade,

        remarks=
            payload.remarks,
    )

    db.add(result)
    db.commit()
    db.refresh(result)

    return build_result_response(
        result=result,
        student=student,
        school_class=school_class,
        exam=exam,
    )


# =========================================================
# UPDATE RESULT
# =========================================================

@router.put(
    "/{result_id}",
    response_model=AdminResultResponse,
)
def update_admin_result(
    result_id: int,
    payload: AdminResultUpdate,
    db: Session = Depends(get_db),
):
    result = (
        db.query(StudentResult)
        .filter(
            StudentResult.id
            == result_id
        )
        .first()
    )

    if not result:
        raise HTTPException(
            status_code=
                status.HTTP_404_NOT_FOUND,
            detail="Result not found",
        )

    # -----------------------------------------------------
    # FINAL STUDENT
    # -----------------------------------------------------

    final_student_id = (
        payload.student_id
        if payload.student_id
        is not None
        else result.student_id
    )

    student = (
        db.query(Student)
        .filter(
            Student.id
            == final_student_id
        )
        .first()
    )

    if not student:
        raise HTTPException(
            status_code=
                status.HTTP_404_NOT_FOUND,
            detail="Student not found",
        )

    if student.class_id is None:
        raise HTTPException(
            status_code=
                status.HTTP_400_BAD_REQUEST,
            detail=(
                "Student is not assigned "
                "to a class"
            ),
        )

    school_class = (
        db.query(SchoolClass)
        .filter(
            SchoolClass.id
            == student.class_id
        )
        .first()
    )

    if not school_class:
        raise HTTPException(
            status_code=
                status.HTTP_404_NOT_FOUND,
            detail="Student class not found",
        )

    # -----------------------------------------------------
    # FINAL EXAM
    # -----------------------------------------------------

    final_exam_id = (
        payload.exam_id
        if payload.exam_id
        is not None
        else result.exam_id
    )

    exam = (
        db.query(Exam)
        .filter(
            Exam.id
            == final_exam_id
        )
        .first()
    )

    if not exam:
        raise HTTPException(
            status_code=
                status.HTTP_404_NOT_FOUND,
            detail="Exam not found",
        )

    # -----------------------------------------------------
    # FINAL VALUES
    # -----------------------------------------------------

    final_subject = (
        payload.subject.strip()
        if payload.subject
        is not None
        else result.subject
    )

    final_max_marks = (
        payload.max_marks
        if payload.max_marks
        is not None
        else float(
            result.max_marks
        )
    )

    final_obtained_marks = (
        payload.obtained_marks
        if payload.obtained_marks
        is not None
        else float(
            result.obtained_marks
        )
    )

    # -----------------------------------------------------
    # VALIDATE MARKS
    # -----------------------------------------------------

    if final_max_marks <= 0:
        raise HTTPException(
            status_code=
                status.HTTP_400_BAD_REQUEST,
            detail=(
                "Maximum marks must "
                "be greater than zero"
            ),
        )

    if final_obtained_marks < 0:
        raise HTTPException(
            status_code=
                status.HTTP_400_BAD_REQUEST,
            detail=(
                "Obtained marks cannot "
                "be negative"
            ),
        )

    if (
        final_obtained_marks
        > final_max_marks
    ):
        raise HTTPException(
            status_code=
                status.HTTP_400_BAD_REQUEST,
            detail=(
                "Obtained marks cannot "
                "exceed maximum marks"
            ),
        )

    # -----------------------------------------------------
    # DUPLICATE CHECK
    # -----------------------------------------------------

    duplicate = (
        db.query(StudentResult)
        .filter(
            StudentResult.id
            != result_id,

            StudentResult.student_id
            == student.id,

            StudentResult.exam_id
            == exam.id,

            StudentResult.subject
            == final_subject,
        )
        .first()
    )

    if duplicate:
        raise HTTPException(
            status_code=
                status.HTTP_409_CONFLICT,
            detail=(
                "Another result already "
                "exists for this student, "
                "exam and subject"
            ),
        )

    # -----------------------------------------------------
    # CALCULATE GRADE
    # -----------------------------------------------------

    grade = calculate_grade(
        final_obtained_marks,
        final_max_marks,
    )

    # -----------------------------------------------------
    # UPDATE
    # -----------------------------------------------------

    result.student_id = (
        student.id
    )

    result.class_id = (
        school_class.id
    )

    result.exam_id = (
        exam.id
    )

    result.subject = (
        final_subject
    )

    result.max_marks = (
        final_max_marks
    )

    result.obtained_marks = (
        final_obtained_marks
    )

    result.grade = grade

    if (
        "remarks"
        in payload.model_fields_set
    ):
        result.remarks = (
            payload.remarks
        )

    # Important:
    # Existing teacher_user_id
    # is preserved.

    db.commit()
    db.refresh(result)

    return build_result_response(
        result=result,
        student=student,
        school_class=school_class,
        exam=exam,
    )


# =========================================================
# DELETE RESULT
# =========================================================

@router.delete(
    "/{result_id}",
)
def delete_admin_result(
    result_id: int,
    db: Session = Depends(get_db),
):
    result = (
        db.query(StudentResult)
        .filter(
            StudentResult.id
            == result_id
        )
        .first()
    )

    if not result:
        raise HTTPException(
            status_code=
                status.HTTP_404_NOT_FOUND,
            detail="Result not found",
        )

    db.delete(result)
    db.commit()

    return {
        "message":
            "Result deleted successfully"
    }