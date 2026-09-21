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
from app.models.school_class import SchoolClass

from app.schemas.admin_exam_schedule import (
    AdminExamScheduleCreate,
    AdminExamScheduleResponse,
    AdminExamScheduleUpdate,
)


router = APIRouter(
    prefix="/api/v1/admin/exam-schedules",
    tags=["Admin Exam Schedules"],
)


# =========================================================
# RESPONSE BUILDER
# =========================================================

def build_schedule_response(
    schedule: ExamSchedule,
    exam: Exam,
    school_class: SchoolClass,
):
    return {
        "id": schedule.id,

        "exam_id": exam.id,
        "exam_name": exam.name,
        "academic_year": exam.academic_year,

        "class_id": school_class.id,
        "class_name": (
            f"{school_class.name} - "
            f"{school_class.section}"
        ),

        "subject": schedule.subject,

        "exam_date": schedule.exam_date,

        "start_time": schedule.start_time,
        "end_time": schedule.end_time,

        "room": schedule.room,
        "instructions": schedule.instructions,

        "created_at": schedule.created_at,
        "updated_at": schedule.updated_at,
    }


# =========================================================
# GET ALL
# =========================================================

@router.get(
    "",
    response_model=list[
        AdminExamScheduleResponse
    ],
)
def get_exam_schedules(
    exam_id: int | None = Query(
        default=None
    ),
    class_id: int | None = Query(
        default=None
    ),
    subject: str | None = Query(
        default=None
    ),
    db: Session = Depends(get_db),
):
    query = (
        db.query(
            ExamSchedule,
            Exam,
            SchoolClass,
        )
        .join(
            Exam,
            Exam.id
            == ExamSchedule.exam_id,
        )
        .join(
            SchoolClass,
            SchoolClass.id
            == ExamSchedule.class_id,
        )
    )

    if exam_id is not None:
        query = query.filter(
            ExamSchedule.exam_id
            == exam_id
        )

    if class_id is not None:
        query = query.filter(
            ExamSchedule.class_id
            == class_id
        )

    if subject:
        query = query.filter(
            ExamSchedule.subject.ilike(
                f"%{subject.strip()}%"
            )
        )

    rows = (
        query
        .order_by(
            ExamSchedule.exam_date.asc(),
            ExamSchedule.start_time.asc(),
        )
        .all()
    )

    return [
        build_schedule_response(
            schedule,
            exam,
            school_class,
        )
        for (
            schedule,
            exam,
            school_class,
        ) in rows
    ]


# =========================================================
# GET SINGLE
# =========================================================

@router.get(
    "/{schedule_id}",
    response_model=
        AdminExamScheduleResponse,
)
def get_exam_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
):
    row = (
        db.query(
            ExamSchedule,
            Exam,
            SchoolClass,
        )
        .join(
            Exam,
            Exam.id
            == ExamSchedule.exam_id,
        )
        .join(
            SchoolClass,
            SchoolClass.id
            == ExamSchedule.class_id,
        )
        .filter(
            ExamSchedule.id
            == schedule_id
        )
        .first()
    )

    if not row:
        raise HTTPException(
            status_code=
                status.HTTP_404_NOT_FOUND,
            detail=
                "Exam schedule not found",
        )

    schedule, exam, school_class = row

    return build_schedule_response(
        schedule,
        exam,
        school_class,
    )


# =========================================================
# CREATE
# =========================================================

@router.post(
    "",
    response_model=
        AdminExamScheduleResponse,
    status_code=
        status.HTTP_201_CREATED,
)
def create_exam_schedule(
    payload:
        AdminExamScheduleCreate,
    db: Session = Depends(get_db),
):
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

    school_class = (
        db.query(SchoolClass)
        .filter(
            SchoolClass.id
            == payload.class_id
        )
        .first()
    )

    if not school_class:
        raise HTTPException(
            status_code=
                status.HTTP_404_NOT_FOUND,
            detail="Class not found",
        )

    if (
        payload.end_time
        <= payload.start_time
    ):
        raise HTTPException(
            status_code=
                status.HTTP_400_BAD_REQUEST,
            detail=(
                "End time must be "
                "after start time"
            ),
        )

    subject = (
        payload.subject.strip()
    )

    duplicate = (
        db.query(ExamSchedule)
        .filter(
            ExamSchedule.exam_id
            == payload.exam_id,

            ExamSchedule.class_id
            == payload.class_id,

            ExamSchedule.subject
            == subject,

            ExamSchedule.exam_date
            == payload.exam_date,
        )
        .first()
    )

    if duplicate:
        raise HTTPException(
            status_code=
                status.HTTP_409_CONFLICT,
            detail=(
                "An exam schedule already "
                "exists for this exam, "
                "class, subject and date"
            ),
        )

    schedule = ExamSchedule(
        exam_id=payload.exam_id,
        class_id=payload.class_id,
        subject=subject,
        exam_date=payload.exam_date,
        start_time=payload.start_time,
        end_time=payload.end_time,
        room=(
            payload.room.strip()
            if payload.room
            else None
        ),
        instructions=(
            payload.instructions.strip()
            if payload.instructions
            else None
        ),
    )

    db.add(schedule)
    db.commit()
    db.refresh(schedule)

    return build_schedule_response(
        schedule,
        exam,
        school_class,
    )


# =========================================================
# UPDATE
# =========================================================

@router.put(
    "/{schedule_id}",
    response_model=
        AdminExamScheduleResponse,
)
def update_exam_schedule(
    schedule_id: int,
    payload:
        AdminExamScheduleUpdate,
    db: Session = Depends(get_db),
):
    schedule = (
        db.query(ExamSchedule)
        .filter(
            ExamSchedule.id
            == schedule_id
        )
        .first()
    )

    if not schedule:
        raise HTTPException(
            status_code=
                status.HTTP_404_NOT_FOUND,
            detail=
                "Exam schedule not found",
        )

    final_exam_id = (
        payload.exam_id
        if payload.exam_id
        is not None
        else schedule.exam_id
    )

    final_class_id = (
        payload.class_id
        if payload.class_id
        is not None
        else schedule.class_id
    )

    final_subject = (
        payload.subject.strip()
        if payload.subject
        is not None
        else schedule.subject
    )

    final_exam_date = (
        payload.exam_date
        if payload.exam_date
        is not None
        else schedule.exam_date
    )

    final_start_time = (
        payload.start_time
        if payload.start_time
        is not None
        else schedule.start_time
    )

    final_end_time = (
        payload.end_time
        if payload.end_time
        is not None
        else schedule.end_time
    )

    if (
        final_end_time
        <= final_start_time
    ):
        raise HTTPException(
            status_code=
                status.HTTP_400_BAD_REQUEST,
            detail=(
                "End time must be "
                "after start time"
            ),
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

    school_class = (
        db.query(SchoolClass)
        .filter(
            SchoolClass.id
            == final_class_id
        )
        .first()
    )

    if not school_class:
        raise HTTPException(
            status_code=
                status.HTTP_404_NOT_FOUND,
            detail="Class not found",
        )

    duplicate = (
        db.query(ExamSchedule)
        .filter(
            ExamSchedule.id
            != schedule_id,

            ExamSchedule.exam_id
            == final_exam_id,

            ExamSchedule.class_id
            == final_class_id,

            ExamSchedule.subject
            == final_subject,

            ExamSchedule.exam_date
            == final_exam_date,
        )
        .first()
    )

    if duplicate:
        raise HTTPException(
            status_code=
                status.HTTP_409_CONFLICT,
            detail=(
                "Another exam schedule "
                "already exists for this "
                "exam, class, subject "
                "and date"
            ),
        )

    schedule.exam_id = (
        final_exam_id
    )

    schedule.class_id = (
        final_class_id
    )

    schedule.subject = (
        final_subject
    )

    schedule.exam_date = (
        final_exam_date
    )

    schedule.start_time = (
        final_start_time
    )

    schedule.end_time = (
        final_end_time
    )

    if (
        "room"
        in payload.model_fields_set
    ):
        schedule.room = (
            payload.room.strip()
            if payload.room
            else None
        )

    if (
        "instructions"
        in payload.model_fields_set
    ):
        schedule.instructions = (
            payload.instructions.strip()
            if payload.instructions
            else None
        )

    db.commit()
    db.refresh(schedule)

    return build_schedule_response(
        schedule,
        exam,
        school_class,
    )


# =========================================================
# DELETE
# =========================================================

@router.delete(
    "/{schedule_id}",
)
def delete_exam_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
):
    schedule = (
        db.query(ExamSchedule)
        .filter(
            ExamSchedule.id
            == schedule_id
        )
        .first()
    )

    if not schedule:
        raise HTTPException(
            status_code=
                status.HTTP_404_NOT_FOUND,
            detail=
                "Exam schedule not found",
        )

    db.delete(schedule)
    db.commit()

    return {
        "message":
            "Exam schedule deleted successfully"
    }