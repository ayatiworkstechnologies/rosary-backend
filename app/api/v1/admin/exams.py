from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.exam import Exam
from app.models.exam_schedule import ExamSchedule
from app.models.student_result import StudentResult

from app.schemas.admin_exam import (
    AdminExamCreate,
    AdminExamResponse,
    AdminExamStatusUpdate,
    AdminExamPublishResultsUpdate,
    AdminExamUpdate,
    AdminExamListResponse,
)


router = APIRouter(
    prefix="/api/v1/admin/exams",
    tags=["Admin Exams"],
)


# =========================================================
# GET ALL EXAMS
# =========================================================

@router.get(
    "",
    response_model=AdminExamListResponse,
)
def get_admin_exams(
    search: str | None = Query(
        default=None
    ),

    academic_year: str | None = Query(
        default=None
    ),

    is_active: bool | None = Query(
        default=None
    ),

    page: int = Query(
        default=1,
        ge=1,
    ),

    page_size: int = Query(
        default=20,
        ge=1,
        le=100,
    ),

    db: Session = Depends(get_db),
):
    query = db.query(Exam)

    if search:
        query = query.filter(
            Exam.name.ilike(
                f"%{search.strip()}%"
            )
        )

    if academic_year:
        query = query.filter(
            Exam.academic_year
            == academic_year.strip()
        )

    if is_active is not None:
        query = query.filter(
            Exam.is_active
            == is_active
        )

    total = query.count()

    total_pages = (
        (total + page_size - 1)
        // page_size
    )

    offset = (
        page - 1
    ) * page_size

    rows = (
        query
        .order_by(
            Exam.start_date.desc(),
            Exam.id.desc(),
        )
        .offset(offset)
        .limit(page_size)
        .all()
    )

    return {
        "data":
            rows,

        "page":
            page,

        "page_size":
            page_size,

        "total":
            total,

        "total_pages":
            total_pages,

        "has_next":
            page < total_pages,

        "has_previous":
            page > 1,
    }


# =========================================================
# GET SINGLE EXAM
# =========================================================

@router.get(
    "/{exam_id}",
    response_model=AdminExamResponse,
)
def get_admin_exam(
    exam_id: int,
    db: Session = Depends(get_db),
):
    exam = (
        db.query(Exam)
        .filter(
            Exam.id == exam_id
        )
        .first()
    )

    if not exam:
        raise HTTPException(
            status_code=
                status.HTTP_404_NOT_FOUND,
            detail="Exam not found",
        )

    return exam


# =========================================================
# CREATE EXAM
# =========================================================

@router.post(
    "",
    response_model=AdminExamResponse,
    status_code=
        status.HTTP_201_CREATED,
)
def create_admin_exam(
    payload: AdminExamCreate,
    db: Session = Depends(get_db),
):
    name = payload.name.strip()

    academic_year = (
        payload.academic_year.strip()
    )

    existing = (
        db.query(Exam)
        .filter(
            Exam.name == name,
            Exam.academic_year
            == academic_year,
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=
                status.HTTP_409_CONFLICT,
            detail=(
                "Exam already exists "
                "for this academic year"
            ),
        )

    exam = Exam(
        name=name,
        academic_year=
            academic_year,
        start_date=
            payload.start_date,
        end_date=
            payload.end_date,
        is_active=
            payload.is_active,
        results_published=False,
    )

    db.add(exam)
    db.commit()
    db.refresh(exam)

    return exam


# =========================================================
# UPDATE EXAM
# =========================================================

@router.put(
    "/{exam_id}",
    response_model=AdminExamResponse,
)
def update_admin_exam(
    exam_id: int,
    payload: AdminExamUpdate,
    db: Session = Depends(get_db),
):
    exam = (
        db.query(Exam)
        .filter(
            Exam.id == exam_id
        )
        .first()
    )

    if not exam:
        raise HTTPException(
            status_code=
                status.HTTP_404_NOT_FOUND,
            detail="Exam not found",
        )

    update_data = (
        payload.model_dump(
            exclude_unset=True
        )
    )

    if "name" in update_data:
        update_data["name"] = (
            update_data[
                "name"
            ].strip()
        )

    if (
        "academic_year"
        in update_data
    ):
        update_data[
            "academic_year"
        ] = (
            update_data[
                "academic_year"
            ].strip()
        )

    final_name = (
        update_data.get(
            "name",
            exam.name,
        )
    )

    final_year = (
        update_data.get(
            "academic_year",
            exam.academic_year,
        )
    )

    duplicate = (
        db.query(Exam)
        .filter(
            Exam.id != exam_id,
            Exam.name ==
                final_name,
            Exam.academic_year
            == final_year,
        )
        .first()
    )

    if duplicate:
        raise HTTPException(
            status_code=
                status.HTTP_409_CONFLICT,
            detail=(
                "Another exam with "
                "this name already exists "
                "for the academic year"
            ),
        )

    final_start = (
        update_data.get(
            "start_date",
            exam.start_date,
        )
    )

    final_end = (
        update_data.get(
            "end_date",
            exam.end_date,
        )
    )

    if (
        final_start
        and final_end
        and final_end <
        final_start
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                "End date cannot be "
                "before start date"
            ),
        )

    for field, value in (
        update_data.items()
    ):
        setattr(
            exam,
            field,
            value,
        )

    db.commit()
    db.refresh(exam)

    return exam


# =========================================================
# ACTIVE / INACTIVE
# =========================================================

@router.patch(
    "/{exam_id}/status",
    response_model=AdminExamResponse,
)
def update_admin_exam_status(
    exam_id: int,
    payload: AdminExamStatusUpdate,
    db: Session = Depends(get_db),
):
    exam = (
        db.query(Exam)
        .filter(
            Exam.id == exam_id
        )
        .first()
    )

    if not exam:
        raise HTTPException(
            status_code=
                status.HTTP_404_NOT_FOUND,
            detail="Exam not found",
        )

    exam.is_active = (
        payload.is_active
    )

    # Safety:
    # If exam becomes inactive,
    # automatically hide results
    # from parents.
    if not payload.is_active:
        exam.results_published = (
            False
        )

    db.commit()
    db.refresh(exam)

    return exam


# =========================================================
# PUBLISH / UNPUBLISH RESULTS
# =========================================================

@router.patch(
    "/{exam_id}/publish-results",
    response_model=AdminExamResponse,
)
def update_admin_exam_results_publish_status(
    exam_id: int,
    payload:
        AdminExamPublishResultsUpdate,
    db: Session = Depends(get_db),
):
    exam = (
        db.query(Exam)
        .filter(
            Exam.id == exam_id
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
    # PUBLISH VALIDATION
    # -----------------------------------------------------

    if payload.results_published:

        # Exam must be active
        if not exam.is_active:
            raise HTTPException(
                status_code=
                    status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Inactive exam results "
                    "cannot be published"
                ),
            )

        # At least one result must exist
        result_count = (
            db.query(
                StudentResult
            )
            .filter(
                StudentResult.exam_id
                == exam_id
            )
            .count()
        )

        if result_count == 0:
            raise HTTPException(
                status_code=
                    status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Cannot publish results "
                    "because no student "
                    "results have been "
                    "entered for this exam"
                ),
            )

    # -----------------------------------------------------
    # UPDATE PUBLISH STATUS
    # -----------------------------------------------------

    exam.results_published = (
        payload.results_published
    )

    db.commit()
    db.refresh(exam)

    return exam


# =========================================================
# DELETE EXAM
# =========================================================

@router.delete(
    "/{exam_id}",
)
def delete_admin_exam(
    exam_id: int,
    db: Session = Depends(get_db),
):
    exam = (
        db.query(Exam)
        .filter(
            Exam.id == exam_id
        )
        .first()
    )

    if not exam:
        raise HTTPException(
            status_code=
                status.HTTP_404_NOT_FOUND,
            detail="Exam not found",
        )

    schedule_count = (
        db.query(
            ExamSchedule
        )
        .filter(
            ExamSchedule.exam_id
            == exam_id
        )
        .count()
    )

    result_count = (
        db.query(
            StudentResult
        )
        .filter(
            StudentResult.exam_id
            == exam_id
        )
        .count()
    )

    if (
        schedule_count > 0
        or result_count > 0
    ):
        raise HTTPException(
            status_code=
                status.HTTP_409_CONFLICT,
            detail=(
                "Exam cannot be deleted "
                "because exam schedules "
                "or student results "
                "are linked to it. "
                "Deactivate the exam instead."
            ),
        )

    db.delete(exam)
    db.commit()

    return {
        "message":
            "Exam deleted successfully"
    }