from datetime import date

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_teacher

from app.models.attendance import Attendance
from app.models.circular import Circular
from app.models.exam import Exam
from app.models.exam_schedule import ExamSchedule
from app.models.homework import Homework
from app.models.parent_student import ParentStudent
from app.models.school_class import SchoolClass
from app.models.school_event import SchoolEvent
from app.models.student import Student
from app.models.student_result import StudentResult
from app.models.teacher_class import TeacherClass
from app.models.teacher_profile import TeacherProfile
from app.models.user import User

from app.schemas.attendance import (
    AttendanceSaveRequest,
    AttendanceSaveResponse,
    AttendanceSheetResponse,
)
from app.schemas.circular import CircularListResponse
from app.schemas.exam_schedule import ExamScheduleListResponse
from app.schemas.homework import (
    HomeworkCreate,
    HomeworkListResponse,
    HomeworkResponse,
)
from app.schemas.result import (
    ExamResponse,
    ResultSaveRequest,
    ResultSaveResponse,
    ResultSheetResponse,
)
from app.schemas.school_event import SchoolEventListResponse
from app.schemas.teacher import (
    TeacherClassResponse,
    TeacherStudentListResponse,
)
from app.schemas.teacher_profile import TeacherProfileResponse
from app.schemas.teacher_exam_schedule import (
    TeacherExamScheduleCreate,
    TeacherExamScheduleUpdate,
)

from app.services.notification_service import create_notification

router = APIRouter(
    prefix="/api/v1/teacher",
    tags=["Teacher"],
)


# =========================================================
# GET EXAMS
# =========================================================

@router.get(
    "/exams",
    response_model=list[ExamResponse],
)
def get_teacher_exams(
    db: Session = Depends(get_db),
    current_teacher: User = Depends(
        get_current_teacher
    ),
):
    exams = (
        db.query(Exam)
        .filter(
            Exam.is_active.is_(True)
        )
        .order_by(
            Exam.start_date.desc()
        )
        .all()
    )

    return [
        {
            "id": exam.id,
            "name": exam.name,
            "academic_year":
                exam.academic_year,
        }
        for exam in exams
    ]


# =========================================================
# GET CLASS RESULTS
# =========================================================

@router.get(
    "/classes/{class_id}/results",
    response_model=ResultSheetResponse,
)
def get_class_results(
    class_id: int,
    exam_id: int,
    subject: str,
    db: Session = Depends(get_db),
    current_teacher: User = Depends(
        get_current_teacher
    ),
):
    # -----------------------------------------------------
    # VERIFY TEACHER CLASS ASSIGNMENT
    # -----------------------------------------------------

    teacher_assignments = (
        db.query(TeacherClass)
        .filter(
            TeacherClass.teacher_user_id
            == current_teacher.id,
            TeacherClass.class_id
            == class_id,
        )
        .all()
    )

    if not teacher_assignments:
        raise HTTPException(
            status_code=
                status.HTTP_403_FORBIDDEN,
            detail=(
                "You are not assigned "
                "to this class"
            ),
        )

    # -----------------------------------------------------
    # VERIFY CLASS
    # -----------------------------------------------------

    school_class = (
        db.query(SchoolClass)
        .filter(
            SchoolClass.id == class_id,
            SchoolClass.is_active.is_(
                True
            ),
        )
        .first()
    )

    if not school_class:
        raise HTTPException(
            status_code=
                status.HTTP_404_NOT_FOUND,
            detail="Class not found",
        )

    # -----------------------------------------------------
    # VERIFY EXAM
    # -----------------------------------------------------

    exam = (
        db.query(Exam)
        .filter(
            Exam.id == exam_id,
            Exam.is_active.is_(True),
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
    # VERIFY SUBJECT
    # -----------------------------------------------------

    clean_subject = (
        subject.strip()
    )

    if not clean_subject:
        raise HTTPException(
            status_code=
                status.HTTP_400_BAD_REQUEST,
            detail="Subject is required",
        )

    assigned_subjects = [
        assignment.subject.strip()
        for assignment in teacher_assignments
        if assignment.subject and assignment.subject.strip()
    ]

    if not assigned_subjects:
        raise HTTPException(
            status_code=
                status.HTTP_403_FORBIDDEN,
            detail=(
                "No subject is assigned "
                "to you for this class"
            ),
        )

    assigned_subject = next(
        (
            value
            for value in assigned_subjects
            if value.casefold() == clean_subject.casefold()
        ),
        None,
    )

    if assigned_subject is None:
        raise HTTPException(
            status_code=
                status.HTTP_403_FORBIDDEN,
            detail=(
                "You are not assigned to "
                "this subject for this class"
            ),
        )

    # Always use DB assignment value.
    clean_subject = assigned_subject

    # -----------------------------------------------------
    # STUDENTS
    # -----------------------------------------------------

    students = (
        db.query(Student)
        .filter(
            Student.class_id == class_id,
            Student.is_active.is_(True),
        )
        .order_by(
            Student.roll_no
        )
        .all()
    )

    # -----------------------------------------------------
    # EXISTING RESULTS
    # -----------------------------------------------------

    existing_results = (
        db.query(StudentResult)
        .filter(
            StudentResult.class_id
            == class_id,
            StudentResult.exam_id
            == exam_id,
            StudentResult.subject
            == clean_subject,
        )
        .all()
    )

    result_map = {
        result.student_id: result
        for result in existing_results
    }

    student_results = []

    for student in students:
        result = result_map.get(
            student.id
        )

        student_results.append(
            {
                "student_id":
                    student.id,

                "admission_no":
                    student.admission_no,

                "roll_no":
                    student.roll_no,

                "full_name":
                    student.full_name,

                "max_marks":
                    float(
                        result.max_marks
                    )
                    if result
                    else None,

                "obtained_marks":
                    float(
                        result.obtained_marks
                    )
                    if (
                        result
                        and
                        result.obtained_marks
                        is not None
                    )
                    else None,

                "result_status":
                    result.result_status
                    if result
                    else None,

                "grade":
                    result.grade
                    if result
                    else None,

                "remarks":
                    result.remarks
                    if result
                    else None,
            }
        )

    return {
        "class_id":
            school_class.id,

        "class_name":
            f"{school_class.name} - "
            f"{school_class.section}",

        "exam_id":
            exam.id,

        "exam_name":
            exam.name,

        "subject":
            clean_subject,

        "total_students":
            len(student_results),

        "students":
            student_results,
    }


# =========================================================
# SAVE CLASS RESULTS
# =========================================================

@router.post(
    "/classes/{class_id}/results",
    response_model=ResultSaveResponse,
)
def save_class_results(
    class_id: int,
    payload: ResultSaveRequest,
    db: Session = Depends(get_db),
    current_teacher: User = Depends(
        get_current_teacher
    ),
):
    # -----------------------------------------------------
    # VERIFY TEACHER ASSIGNMENT
    # -----------------------------------------------------

    teacher_assignments = (
        db.query(TeacherClass)
        .filter(
            TeacherClass.teacher_user_id
            == current_teacher.id,
            TeacherClass.class_id
            == class_id,
        )
        .all()
    )

    if not teacher_assignments:
        raise HTTPException(
            status_code=
                status.HTTP_403_FORBIDDEN,
            detail=(
                "You are not assigned "
                "to this class"
            ),
        )

    # -----------------------------------------------------
    # VERIFY EXAM
    # -----------------------------------------------------

    exam = (
        db.query(Exam)
        .filter(
            Exam.id == payload.exam_id,
            Exam.is_active.is_(True),
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
    # BLOCK EDITING AFTER RESULTS ARE PUBLISHED
    # -----------------------------------------------------

    if exam.results_published:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Results for this examination are already published. "
                "Ask the administrator to unpublish the results before editing."
            ),
        )
    # -----------------------------------------------------
    # VERIFY SUBJECT
    # -----------------------------------------------------

    subject = (
        payload.subject.strip()
    )

    if not subject:
        raise HTTPException(
            status_code=
                status.HTTP_400_BAD_REQUEST,
            detail="Subject is required",
        )

    assigned_subjects = [
        assignment.subject.strip()
        for assignment in teacher_assignments
        if assignment.subject and assignment.subject.strip()
    ]

    if not assigned_subjects:
        raise HTTPException(
            status_code=
                status.HTTP_403_FORBIDDEN,
            detail=(
                "No subject is assigned "
                "to you for this class"
            ),
        )

    assigned_subject = next(
        (
            value
            for value in assigned_subjects
            if value.casefold() == subject.casefold()
        ),
        None,
    )

    if assigned_subject is None:
        raise HTTPException(
            status_code=
                status.HTTP_403_FORBIDDEN,
            detail=(
                "You are not assigned to "
                "this subject for this class"
            ),
        )

    subject = assigned_subject

    # -----------------------------------------------------
    # VALID CLASS STUDENTS
    # -----------------------------------------------------

    students = (
        db.query(Student)
        .filter(
            Student.class_id == class_id,
            Student.is_active.is_(True),
        )
        .all()
    )

    valid_student_ids = {
        student.id
        for student in students
    }

    # -----------------------------------------------------
    # SAVE RESULTS
    # -----------------------------------------------------

    for item in payload.results:

        if (
            item.student_id
            not in valid_student_ids
        ):
            raise HTTPException(
                status_code=
                    status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Student "
                    f"{item.student_id} "
                    "does not belong to "
                    "this class"
                ),
            )

        if item.max_marks <= 0:
            raise HTTPException(
                status_code=
                    status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Maximum marks must "
                    "be greater than zero"
                ),
            )

        result_status = (
            item.result_status
            or "PRESENT"
        ).strip().upper()

        # ---------------------------------------------
        # ABSENT
        # ---------------------------------------------

        if result_status == "ABSENT":
            obtained_marks = None
            grade = None

        # ---------------------------------------------
        # PRESENT
        # ---------------------------------------------

        else:
            if (
                item.obtained_marks
                is None
            ):
                raise HTTPException(
                    status_code=
                        status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "Obtained marks are "
                        "required when result "
                        "status is PRESENT"
                    ),
                )

            obtained_marks = (
                item.obtained_marks
            )

            if obtained_marks < 0:
                raise HTTPException(
                    status_code=
                        status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "Obtained marks cannot "
                        "be negative"
                    ),
                )

            if (
                obtained_marks
                > item.max_marks
            ):
                raise HTTPException(
                    status_code=
                        status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "Obtained marks cannot "
                        "exceed maximum marks"
                    ),
                )

            grade = calculate_grade(
                obtained_marks,
                item.max_marks,
            )

        # ---------------------------------------------
        # EXISTING RESULT
        # ---------------------------------------------

        existing = (
            db.query(StudentResult)
            .filter(
                StudentResult.student_id
                == item.student_id,

                StudentResult.exam_id
                == payload.exam_id,

                StudentResult.subject
                == subject,
            )
            .first()
        )

        if existing:
            existing.class_id = (
                class_id
            )

            existing.teacher_user_id = (
                current_teacher.id
            )

            existing.max_marks = (
                item.max_marks
            )

            existing.obtained_marks = (
                obtained_marks
            )

            existing.result_status = (
                result_status
            )

            existing.grade = grade

            existing.remarks = (
                item.remarks
            )

        else:
            result = StudentResult(
                student_id=
                    item.student_id,

                class_id=
                    class_id,

                exam_id=
                    payload.exam_id,

                teacher_user_id=
                    current_teacher.id,

                subject=
                    subject,

                max_marks=
                    item.max_marks,

                obtained_marks=
                    obtained_marks,

                result_status=
                    result_status,

                grade=
                    grade,

                remarks=
                    item.remarks,
            )

            db.add(result)

    db.commit()

    return {
        "message":
            "Results saved successfully",

        "total":
            len(payload.results),
    }


# =========================================================
# GET TEACHER EXAM SCHEDULE
# =========================================================

@router.get(
    "/exam-schedule",
    response_model=
        ExamScheduleListResponse,
)
def get_teacher_exam_schedule(
    class_id: int | None = None,
    exam_id: int | None = None,
    db: Session = Depends(get_db),
    current_teacher: User = Depends(
        get_current_teacher
    ),
):
    teacher_assignments = (
        db.query(TeacherClass)
        .filter(
            TeacherClass.teacher_user_id
            == current_teacher.id
        )
        .all()
    )

    assigned_class_ids = [
        item.class_id
        for item in teacher_assignments
    ]

    if not assigned_class_ids:
        return {
            "total": 0,
            "schedules": [],
        }

    if (
        class_id is not None
        and
        class_id
        not in assigned_class_ids
    ):
        raise HTTPException(
            status_code=
                status.HTTP_403_FORBIDDEN,
            detail=(
                "You are not assigned "
                "to this class"
            ),
        )

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
        .filter(
            ExamSchedule.class_id.in_(
                assigned_class_ids
            ),
            Exam.is_active.is_(True),
            SchoolClass.is_active.is_(
                True
            ),
        )
    )

    if class_id is not None:
        query = query.filter(
            ExamSchedule.class_id
            == class_id
        )

    if exam_id is not None:
        query = query.filter(
            ExamSchedule.exam_id
            == exam_id
        )

    rows = (
        query
        .order_by(
            ExamSchedule.exam_date.asc(),
            ExamSchedule.start_time.asc(),
        )
        .all()
    )

    schedules = []

    for (
        schedule,
        exam,
        school_class,
    ) in rows:

        schedules.append(
            {
                "id":
                    schedule.id,

                "exam_id":
                    exam.id,

                "exam_name":
                    exam.name,

                "class_id":
                    school_class.id,

                "class_name":
                    f"{school_class.name} - "
                    f"{school_class.section}",

                "subject":
                    schedule.subject,

                "exam_date":
                    schedule.exam_date,

                "start_time":
                    schedule.start_time,

                "end_time":
                    schedule.end_time,

                "room":
                    schedule.room,

                "instructions":
                    schedule.instructions,
            }
        )

    return {
        "total":
            len(schedules),

        "schedules":
            schedules,
    }


# =========================================================
# GRADE CALCULATION
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
# GET TEACHER CLASSES
# =========================================================

@router.get(
    "/classes",
    response_model=
        list[TeacherClassResponse],
)
def get_teacher_classes(
    db: Session = Depends(get_db),
    current_teacher: User = Depends(
        get_current_teacher
    ),
):
    rows = (
        db.query(
            SchoolClass,
            TeacherClass.subject,
        )
        .join(
            TeacherClass,
            TeacherClass.class_id
            == SchoolClass.id,
        )
        .filter(
            TeacherClass.teacher_user_id
            == current_teacher.id,

            SchoolClass.is_active.is_(
                True
            ),
        )
        .order_by(
            SchoolClass.name,
            SchoolClass.section,
        )
        .all()
    )

    return [
        {
            "id":
                school_class.id,

            "name":
                school_class.name,

            "section":
                school_class.section,

            "academic_year":
                school_class.academic_year,

            "display_name":
                f"{school_class.name} - "
                f"{school_class.section}",

            "subject":
                subject,
        }
        for school_class, subject
        in rows
    ]


# =========================================================
# GET TEACHER CIRCULARS
# =========================================================

@router.get(
    "/circulars",
    response_model=CircularListResponse,
)
def get_teacher_circulars(
    category: str | None = None,
    search: str | None = None,

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

    current_teacher: User = Depends(
        get_current_teacher
    ),
):
    assignments = (
        db.query(TeacherClass)
        .filter(
            TeacherClass.teacher_user_id
            == current_teacher.id
        )
        .all()
    )

    assigned_class_ids = [
        item.class_id
        for item in assignments
    ]

    query = (
        db.query(Circular)
        .filter(
            Circular.is_active.is_(True)
        )
    )

    audience_conditions = [
        Circular.audience == "ALL",
        Circular.audience == "TEACHER",
    ]

    if assigned_class_ids:
        audience_conditions.append(
            (
                Circular.audience
                == "CLASS"
            )
            &
            (
                Circular.class_id.in_(
                    assigned_class_ids
                )
            )
        )

    query = query.filter(
        or_(
            *audience_conditions
        )
    )

    if category:
        clean_category = (
            category.strip()
        )

        if clean_category:
            query = query.filter(
                Circular.category
                == clean_category
            )

    if search:
        search_value = (
            f"%{search.strip()}%"
        )

        query = query.filter(
            or_(
                Circular.title.ilike(
                    search_value
                ),

                Circular.description.ilike(
                    search_value
                ),

                Circular.category.ilike(
                    search_value
                ),
            )
        )

    total = query.count()

    total_pages = (
        (total + page_size - 1)
        // page_size
    )

    offset = (
        page - 1
    ) * page_size

    circular_rows = (
        query
        .order_by(
            Circular.published_date.desc(),
            Circular.id.desc(),
        )
        .offset(offset)
        .limit(page_size)
        .all()
    )

    circulars = []

    for circular in circular_rows:
        class_name = None

        if circular.class_id:
            school_class = (
                db.query(SchoolClass)
                .filter(
                    SchoolClass.id
                    == circular.class_id
                )
                .first()
            )

            if school_class:
                class_name = (
                    f"{school_class.name} - "
                    f"{school_class.section}"
                )

        circulars.append(
            {
                "id":
                    circular.id,

                "title":
                    circular.title,

                "category":
                    circular.category,

                "description":
                    circular.description,

                "published_date":
                    circular.published_date,

                "audience":
                    circular.audience,

                "class_id":
                    circular.class_id,

                "class_name":
                    class_name,

                "attachment_url":
                    circular.attachment_url,
            }
        )

    return {
        "total":
            total,

        "page":
            page,

        "page_size":
            page_size,

        "total_pages":
            total_pages,

        "has_next":
            page < total_pages,

        "has_previous":
            page > 1,

        "circulars":
            circulars,
    }


# =========================================================
# GET TEACHER SCHOOL CALENDAR
# =========================================================

@router.get(
    "/calendar",
    response_model=
        SchoolEventListResponse,
)
def get_teacher_calendar(
    event_type: str | None = None,
    db: Session = Depends(get_db),
    current_teacher: User = Depends(
        get_current_teacher
    ),
):
    assignments = (
        db.query(TeacherClass)
        .filter(
            TeacherClass.teacher_user_id
            == current_teacher.id
        )
        .all()
    )

    assigned_class_ids = [
        item.class_id
        for item in assignments
    ]

    audience_conditions = [
        SchoolEvent.audience == "ALL",
        SchoolEvent.audience == "TEACHER",
    ]

    if assigned_class_ids:
        audience_conditions.append(
            (
                SchoolEvent.audience
                == "CLASS"
            )
            &
            (
                SchoolEvent.class_id.in_(
                    assigned_class_ids
                )
            )
        )

    query = (
        db.query(SchoolEvent)
        .filter(
            SchoolEvent.is_active.is_(
                True
            ),
            or_(
                *audience_conditions
            ),
        )
    )

    if event_type:
        clean_type = (
            event_type
            .strip()
            .upper()
        )

        if clean_type:
            query = query.filter(
                SchoolEvent.event_type
                == clean_type
            )

    rows = (
        query
        .order_by(
            SchoolEvent.start_date.asc(),
            SchoolEvent.start_time.asc(),
        )
        .all()
    )

    events = []

    for event in rows:
        class_name = None

        if event.class_id:
            school_class = (
                db.query(SchoolClass)
                .filter(
                    SchoolClass.id
                    == event.class_id
                )
                .first()
            )

            if school_class:
                class_name = (
                    f"{school_class.name} - "
                    f"{school_class.section}"
                )

        events.append(
            {
                "id":
                    event.id,

                "title":
                    event.title,

                "event_type":
                    event.event_type,

                "description":
                    event.description,

                "start_date":
                    event.start_date,

                "end_date":
                    event.end_date,

                "start_time":
                    event.start_time,

                "end_time":
                    event.end_time,

                "location":
                    event.location,

                "audience":
                    event.audience,

                "class_id":
                    event.class_id,

                "class_name":
                    class_name,
            }
        )

    return {
        "total":
            len(events),

        "events":
            events,
    }


# =========================================================
# GET CLASS HOMEWORK
# =========================================================

@router.get(
    "/classes/{class_id}/homework",
    response_model=HomeworkListResponse,
)
def get_class_homework(
    class_id: int,

    search: str | None = Query(
        default=None
    ),

    from_date: date | None = Query(
        default=None
    ),

    to_date: date | None = Query(
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

    current_teacher: User = Depends(
        get_current_teacher
    ),
):
    # -----------------------------------------------------
    # VERIFY TEACHER CLASS ASSIGNMENT
    # -----------------------------------------------------

    teacher_class = (
        db.query(TeacherClass)
        .filter(
            TeacherClass.teacher_user_id
            == current_teacher.id,

            TeacherClass.class_id
            == class_id,
        )
        .first()
    )

    if not teacher_class:
        raise HTTPException(
            status_code=
                status.HTTP_403_FORBIDDEN,
            detail=(
                "You are not assigned "
                "to this class"
            ),
        )

    # -----------------------------------------------------
    # VERIFY CLASS
    # -----------------------------------------------------

    school_class = (
        db.query(SchoolClass)
        .filter(
            SchoolClass.id == class_id,
            SchoolClass.is_active.is_(
                True
            ),
        )
        .first()
    )

    if not school_class:
        raise HTTPException(
            status_code=
                status.HTTP_404_NOT_FOUND,
            detail="Class not found",
        )

    # -----------------------------------------------------
    # ASSIGNED SUBJECT
    # -----------------------------------------------------

    assigned_subject = (
        teacher_class.subject or ""
    ).strip()

    if not assigned_subject:
        raise HTTPException(
            status_code=
                status.HTTP_403_FORBIDDEN,
            detail=(
                "No subject is assigned "
                "to you for this class"
            ),
        )

    # -----------------------------------------------------
    # BASE QUERY
    # -----------------------------------------------------

    query = (
        db.query(Homework)
        .filter(
            Homework.class_id
            == class_id,

            Homework.subject
            == assigned_subject,

            Homework.is_active.is_(
                True
            ),
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
                Homework.title.ilike(
                    search_value
                ),
                Homework.description.ilike(
                    search_value
                ),
            )
        )

    # -----------------------------------------------------
    # DATE FILTERS
    # -----------------------------------------------------

    if from_date is not None:
        query = query.filter(
            Homework.assigned_date
            >= from_date
        )

    if to_date is not None:
        query = query.filter(
            Homework.assigned_date
            <= to_date
        )

    # -----------------------------------------------------
    # TOTAL
    # -----------------------------------------------------

    total = query.count()

    # -----------------------------------------------------
    # PAGINATION
    # -----------------------------------------------------

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
            Homework.created_at.desc(),
            Homework.id.desc(),
        )
        .offset(offset)
        .limit(page_size)
        .all()
    )

    # -----------------------------------------------------
    # RESPONSE
    # -----------------------------------------------------

    class_name = (
        f"{school_class.name} - "
        f"{school_class.section}"
    )

    homework_list = []

    for item in rows:
        homework_list.append(
            {
                "id":
                    item.id,

                "class_id":
                    item.class_id,

                "class_name":
                    class_name,

                "teacher_user_id":
                    item.teacher_user_id,

                "subject":
                    item.subject,

                "title":
                    item.title,

                "description":
                    item.description,

                "assigned_date":
                    item.assigned_date,

                "due_date":
                    item.due_date,

                "attachment_url":
                    item.attachment_url,

                "is_active":
                    item.is_active,

                "created_at":
                    item.created_at,
            }
        )

    return {
        "class_id":
            school_class.id,

        "class_name":
            class_name,

        "total":
            total,

        "page":
            page,

        "page_size":
            page_size,

        "total_pages":
            total_pages,

        "has_next":
            page < total_pages,

        "has_previous":
            page > 1,

        "homework":
            homework_list,
    }

# =========================================================
# CREATE HOMEWORK
# =========================================================

@router.post(
    "/classes/{class_id}/homework",
    response_model=HomeworkResponse,
    status_code=
        status.HTTP_201_CREATED,
)
def create_homework(
    class_id: int,
    payload: HomeworkCreate,
    db: Session = Depends(get_db),
    current_teacher: User = Depends(
        get_current_teacher
    ),
):
    # -----------------------------------------------------
    # VERIFY TEACHER ASSIGNMENT
    # -----------------------------------------------------

    teacher_class = (
        db.query(TeacherClass)
        .filter(
            TeacherClass.teacher_user_id
            == current_teacher.id,

            TeacherClass.class_id
            == class_id,
        )
        .first()
    )

    if not teacher_class:
        raise HTTPException(
            status_code=
                status.HTTP_403_FORBIDDEN,
            detail=(
                "You are not assigned "
                "to this class"
            ),
        )

    # -----------------------------------------------------
    # VERIFY CLASS
    # -----------------------------------------------------

    school_class = (
        db.query(SchoolClass)
        .filter(
            SchoolClass.id == class_id,
            SchoolClass.is_active.is_(
                True
            ),
        )
        .first()
    )

    if not school_class:
        raise HTTPException(
            status_code=
                status.HTTP_404_NOT_FOUND,
            detail="Class not found",
        )

    # -----------------------------------------------------
    # VALIDATE DATES
    # -----------------------------------------------------

    if (
        payload.due_date
        < payload.assigned_date
    ):
        raise HTTPException(
            status_code=
                status.HTTP_400_BAD_REQUEST,
            detail=(
                "Due date cannot be before "
                "assigned date"
            ),
        )

    # -----------------------------------------------------
    # ASSIGNED SUBJECT
    # -----------------------------------------------------

    assigned_subject = (
        teacher_class.subject or ""
    ).strip()

    if not assigned_subject:
        raise HTTPException(
            status_code=
                status.HTTP_403_FORBIDDEN,
            detail=(
                "No subject is assigned "
                "to you for this class"
            ),
        )

    # IMPORTANT:
    # Never trust subject coming from frontend.
    # Use teacher's DB assignment only.
    subject = assigned_subject

    # -----------------------------------------------------
    # VALIDATE TITLE
    # -----------------------------------------------------

    title = (
        payload.title.strip()
    )

    if not title:
        raise HTTPException(
            status_code=
                status.HTTP_400_BAD_REQUEST,
            detail=(
                "Homework title is required"
            ),
        )

    # -----------------------------------------------------
    # CREATE HOMEWORK
    # -----------------------------------------------------

    homework = Homework(
        class_id=
            class_id,

        teacher_user_id=
            current_teacher.id,

        subject=
            subject,

        title=
            title,

        description=(
            payload.description.strip()
            if payload.description
            else None
        ),

        assigned_date=
            payload.assigned_date,

        due_date=
            payload.due_date,

        attachment_url=(
            payload.attachment_url.strip()
            if payload.attachment_url
            else None
        ),

        is_active=True,
    )

    db.add(homework)

    # Generate homework ID before notification
    db.flush()

    # -----------------------------------------------------
    # FIND PARENTS FOR THIS CLASS
    # -----------------------------------------------------

    parent_user_ids = (
        db.query(
            ParentStudent.parent_user_id
        )
        .join(
            Student,
            Student.id
            == ParentStudent.student_id,
        )
        .filter(
            Student.class_id
            == class_id,

            Student.is_active.is_(
                True
            ),
        )
        .distinct()
        .all()
    )

    # -----------------------------------------------------
    # CREATE PARENT NOTIFICATIONS
    # -----------------------------------------------------

    for (
        parent_user_id,
    ) in parent_user_ids:

        create_notification(
            db=db,

            user_id=
                parent_user_id,

            title=
                "New Homework",

            message=(
                f"{homework.subject} "
                "homework has been added "
                f"for {school_class.name}-"
                f"{school_class.section}."
            ),

            notification_type=
                "HOMEWORK",

            reference_id=
                homework.id,

            link=
                "/parent/homework",
        )

    # Save homework + notifications together.
    db.commit()

    db.refresh(homework)

    class_name = (
        f"{school_class.name} - "
        f"{school_class.section}"
    )

    return {
        "id":
            homework.id,

        "class_id":
            homework.class_id,

        "class_name":
            class_name,

        "teacher_user_id":
            homework.teacher_user_id,

        "subject":
            homework.subject,

        "title":
            homework.title,

        "description":
            homework.description,

        "assigned_date":
            homework.assigned_date,

        "due_date":
            homework.due_date,

        "attachment_url":
            homework.attachment_url,

        "is_active":
            homework.is_active,

        "created_at":
            homework.created_at,
    }


# =========================================================
# GET ATTENDANCE SHEET
# =========================================================

@router.get(
    "/classes/{class_id}/attendance",
    response_model=
        AttendanceSheetResponse,
)
def get_class_attendance(
    class_id: int,
    attendance_date: date,
    db: Session = Depends(get_db),
    current_teacher: User = Depends(
        get_current_teacher
    ),
):
    teacher_class = (
        db.query(TeacherClass)
        .filter(
            TeacherClass.teacher_user_id
            == current_teacher.id,

            TeacherClass.class_id
            == class_id,
        )
        .first()
    )

    if not teacher_class:
        raise HTTPException(
            status_code=
                status.HTTP_403_FORBIDDEN,
            detail=(
                "You are not assigned "
                "to this class"
            ),
        )

    school_class = (
        db.query(SchoolClass)
        .filter(
            SchoolClass.id == class_id,
            SchoolClass.is_active.is_(
                True
            ),
        )
        .first()
    )

    if not school_class:
        raise HTTPException(
            status_code=
                status.HTTP_404_NOT_FOUND,
            detail="Class not found",
        )

    students = (
        db.query(Student)
        .filter(
            Student.class_id
            == class_id,

            Student.is_active.is_(
                True
            ),
        )
        .order_by(
            Student.roll_no
        )
        .all()
    )

    attendance_rows = (
        db.query(Attendance)
        .filter(
            Attendance.class_id
            == class_id,

            Attendance.attendance_date
            == attendance_date,
        )
        .all()
    )

    attendance_map = {
        row.student_id: row
        for row in attendance_rows
    }

    present_count = 0
    absent_count = 0
    not_marked_count = 0

    student_list = []

    for student in students:
        attendance = (
            attendance_map.get(
                student.id
            )
        )

        student_status = (
            attendance.status
            if attendance
            else None
        )

        if student_status == "PRESENT":
            present_count += 1

        elif student_status == "ABSENT":
            absent_count += 1

        else:
            not_marked_count += 1

        student_list.append(
            {
                "student_id":
                    student.id,

                "admission_no":
                    student.admission_no,

                "roll_no":
                    student.roll_no,

                "full_name":
                    student.full_name,

                "status":
                    student_status,

                "remarks":
                    (
                        attendance.remarks
                        if attendance
                        else None
                    ),
            }
        )

    return {
        "class_id":
            school_class.id,

        "class_name":
            f"{school_class.name} - "
            f"{school_class.section}",

        "attendance_date":
            attendance_date,

        "total_students":
            len(students),

        "present_count":
            present_count,

        "absent_count":
            absent_count,

        "not_marked_count":
            not_marked_count,

        "students":
            student_list,
    }


# =========================================================
# SAVE ATTENDANCE
# =========================================================

@router.post(
    "/classes/{class_id}/attendance",
    response_model=
        AttendanceSaveResponse,
)
def save_class_attendance(
    class_id: int,
    payload: AttendanceSaveRequest,
    db: Session = Depends(get_db),
    current_teacher: User = Depends(
        get_current_teacher
    ),
):
    teacher_class = (
        db.query(TeacherClass)
        .filter(
            TeacherClass.teacher_user_id
            == current_teacher.id,

            TeacherClass.class_id
            == class_id,
        )
        .first()
    )

    if not teacher_class:
        raise HTTPException(
            status_code=
                status.HTTP_403_FORBIDDEN,
            detail=(
                "You are not assigned "
                "to this class"
            ),
        )

    class_students = (
        db.query(Student)
        .filter(
            Student.class_id
            == class_id,

            Student.is_active.is_(
                True
            ),
        )
        .all()
    )

    valid_student_ids = {
        student.id
        for student in class_students
    }

    present_count = 0
    absent_count = 0

    for record in payload.records:

        if (
            record.student_id
            not in valid_student_ids
        ):
            raise HTTPException(
                status_code=
                    status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Student "
                    f"{record.student_id} "
                    "does not belong "
                    "to this class"
                ),
            )

        attendance_status = (
            record.status
            .strip()
            .upper()
        )

        if attendance_status not in {
            "PRESENT",
            "ABSENT",
        }:
            raise HTTPException(
                status_code=
                    status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Attendance status must be "
                    "PRESENT or ABSENT"
                ),
            )

        existing = (
            db.query(Attendance)
            .filter(
                Attendance.student_id
                == record.student_id,

                Attendance.attendance_date
                == payload.attendance_date,
            )
            .first()
        )

        if existing:
            existing.class_id = (
                class_id
            )

            existing.status = (
                attendance_status
            )

            existing.remarks = (
                record.remarks
            )

            existing.marked_by = (
                current_teacher.id
            )

        else:
            attendance = Attendance(
                student_id=
                    record.student_id,

                class_id=
                    class_id,

                attendance_date=
                    payload.attendance_date,

                status=
                    attendance_status,

                remarks=
                    record.remarks,

                marked_by=
                    current_teacher.id,
            )

            db.add(attendance)

        if (
            attendance_status
            == "PRESENT"
        ):
            present_count += 1

        if (
            attendance_status
            == "ABSENT"
        ):
            absent_count += 1

    db.commit()

    return {
        "message":
            "Attendance saved successfully",

        "attendance_date":
            payload.attendance_date,

        "total":
            len(payload.records),

        "present_count":
            present_count,

        "absent_count":
            absent_count,
    }


# =========================================================
# GET STUDENTS FOR TEACHER CLASS
# =========================================================

@router.get(
    "/classes/{class_id}/students",
    response_model=
        TeacherStudentListResponse,
)
def get_class_students(
    class_id: int,
    search: str | None = Query(
        default=None
    ),
    db: Session = Depends(get_db),
    current_teacher: User = Depends(
        get_current_teacher
    ),
):
    teacher_class = (
        db.query(TeacherClass)
        .filter(
            TeacherClass.teacher_user_id
            == current_teacher.id,

            TeacherClass.class_id
            == class_id,
        )
        .first()
    )

    if not teacher_class:
        raise HTTPException(
            status_code=
                status.HTTP_403_FORBIDDEN,
            detail=(
                "You are not assigned "
                "to this class"
            ),
        )

    school_class = (
        db.query(SchoolClass)
        .filter(
            SchoolClass.id == class_id,
            SchoolClass.is_active.is_(
                True
            ),
        )
        .first()
    )

    if not school_class:
        raise HTTPException(
            status_code=
                status.HTTP_404_NOT_FOUND,
            detail="Class not found",
        )

    query = (
        db.query(Student)
        .filter(
            Student.class_id
            == class_id,

            Student.is_active.is_(
                True
            ),
        )
    )

    if search:
        search_value = (
            f"%{search.strip()}%"
        )

        query = query.filter(
            (
                Student.full_name.ilike(
                    search_value
                )
            )
            |
            (
                Student.admission_no.ilike(
                    search_value
                )
            )
            |
            (
                Student.roll_no.ilike(
                    search_value
                )
            )
        )

    students = (
        query
        .order_by(
            Student.roll_no
        )
        .all()
    )

    class_name = (
        f"{school_class.name} - "
        f"{school_class.section}"
    )

    return {
        "class_id":
            school_class.id,

        "class_name":
            class_name,

        "total":
            len(students),

        "students": [
            {
                "id":
                    student.id,

                "admission_no":
                    student.admission_no,

                "roll_no":
                    student.roll_no,

                "full_name":
                    student.full_name,

                "gender":
                    student.gender,

                "class_id":
                    student.class_id,

                "class_name":
                    class_name,

                "status":
                    (
                        "Active"
                        if student.is_active
                        else "Inactive"
                    ),
            }
            for student in students
        ],
    }


# =========================================================
# GET TEACHER PROFILE
# =========================================================

@router.get(
    "/profile",
    response_model=
        TeacherProfileResponse,
)
def get_teacher_profile(
    db: Session = Depends(get_db),
    current_teacher: User = Depends(
        get_current_teacher
    ),
):
    profile = (
        db.query(TeacherProfile)
        .filter(
            TeacherProfile.user_id
            == current_teacher.id
        )
        .first()
    )

    assignments = (
        db.query(
            TeacherClass,
            SchoolClass,
        )
        .join(
            SchoolClass,
            SchoolClass.id
            == TeacherClass.class_id,
        )
        .filter(
            TeacherClass.teacher_user_id
            == current_teacher.id,

            SchoolClass.is_active.is_(
                True
            ),
        )
        .order_by(
            SchoolClass.name,
            SchoolClass.section,
        )
        .all()
    )

    assigned_classes = []

    for (
        assignment,
        school_class,
    ) in assignments:

        assigned_classes.append(
            {
                "class_id":
                    school_class.id,

                "class_name":
                    f"{school_class.name} - "
                    f"{school_class.section}",

                "subject":
                    assignment.subject,

                "academic_year":
                    school_class.academic_year,
            }
        )

    return {
        "user_id":
            current_teacher.id,

        "name":
            current_teacher.name,

        "username":
            current_teacher.username,

        "email":
            current_teacher.email,

        "role":
            current_teacher.role,

        "is_active":
            current_teacher.is_active,

        "employee_id":
            (
                profile.employee_id
                if profile
                else None
            ),

        "phone":
            (
                profile.phone
                if profile
                else None
            ),

        "designation":
            (
                profile.designation
                if profile
                else None
            ),

        "department":
            (
                profile.department
                if profile
                else None
            ),

        "qualification":
            (
                profile.qualification
                if profile
                else None
            ),

        "experience_years":
            (
                profile.experience_years
                if profile
                else None
            ),

        "joining_date":
            (
                profile.joining_date
                if profile
                else None
            ),

        "profile_image_url":
            (
                profile.profile_image_url
                if profile
                else None
            ),

        "assigned_classes":
            assigned_classes,
    }


# =========================================================
# CREATE TEACHER EXAM SCHEDULE
# =========================================================

@router.post(
    "/exam-schedule",
    status_code=status.HTTP_201_CREATED,
)
def create_teacher_exam_schedule(
    payload: TeacherExamScheduleCreate,
    db: Session = Depends(get_db),
    current_teacher: User = Depends(
        get_current_teacher
    ),
):
    class_id = payload.class_id
    exam_id = payload.exam_id
    subject = payload.subject
    exam_date = payload.exam_date
    start_time = payload.start_time
    end_time = payload.end_time
    room = payload.room
    instructions = payload.instructions


    # -----------------------------------------------------
    # VERIFY TEACHER CLASS + SUBJECT ASSIGNMENT
    # -----------------------------------------------------

    teacher_assignment = (
        db.query(TeacherClass)
        .filter(
            TeacherClass.teacher_user_id
            == current_teacher.id,

            TeacherClass.class_id
            == class_id,
        )
        .all()
    )

    if not teacher_assignment:
        raise HTTPException(
            status_code=
                status.HTTP_403_FORBIDDEN,
            detail=(
                "You are not assigned "
                "to this class"
            ),
        )


    assigned_subjects = {
        (
            item.subject
            or ""
        ).strip().lower()
        for item in teacher_assignment
        if item.subject
    }

    if (
        subject.lower()
        not in assigned_subjects
    ):
        raise HTTPException(
            status_code=
                status.HTTP_403_FORBIDDEN,
            detail=(
                "You are not assigned "
                "to this subject"
            ),
        )


    # -----------------------------------------------------
    # VERIFY CLASS
    # -----------------------------------------------------

    school_class = (
        db.query(SchoolClass)
        .filter(
            SchoolClass.id
            == class_id,

            SchoolClass.is_active.is_(
                True
            ),
        )
        .first()
    )

    if not school_class:
        raise HTTPException(
            status_code=
                status.HTTP_404_NOT_FOUND,
            detail="Class not found",
        )


    # -----------------------------------------------------
    # VERIFY EXAM
    # -----------------------------------------------------

    exam = (
        db.query(Exam)
        .filter(
            Exam.id
            == exam_id,

            Exam.is_active.is_(
                True
            ),
        )
        .first()
    )

    if not exam:
        raise HTTPException(
            status_code=
                status.HTTP_404_NOT_FOUND,
            detail="Exam not found",
        )

    if exam.start_date and exam_date < exam.start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Exam date cannot be before the examination start date",
        )

    if exam.end_date and exam_date > exam.end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Exam date cannot be after the examination end date",
        )


    # -----------------------------------------------------
    # CHECK DUPLICATE
    # -----------------------------------------------------

    duplicate = (
        db.query(ExamSchedule)
        .filter(
            ExamSchedule.class_id
            == class_id,

            ExamSchedule.exam_id
            == exam_id,

            ExamSchedule.subject
            == subject,
        )
        .first()
    )

    if duplicate:
        raise HTTPException(
            status_code=
                status.HTTP_409_CONFLICT,
            detail=(
                "Schedule already exists "
                "for this class, exam "
                "and subject"
            ),
        )


    # -----------------------------------------------------
    # CREATE
    # -----------------------------------------------------

    schedule = ExamSchedule(
        class_id=class_id,
        exam_id=exam_id,
        subject=subject,
        exam_date=exam_date,
        start_time=start_time,
        end_time=end_time,
        room=room or None,
        instructions=
            instructions or None,
    )

    db.add(schedule)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Schedule already exists for this class, exam, subject, and date"
            ),
        ) from error
    db.refresh(schedule)

    return {
        "id": schedule.id,

        "class_id":
            schedule.class_id,

        "exam_id":
            schedule.exam_id,

        "subject":
            schedule.subject,

        "exam_date":
            str(
                schedule.exam_date
            ),

        "start_time":
            str(
                schedule.start_time
            ),

        "end_time":
            str(
                schedule.end_time
            ),

        "room":
            schedule.room,

        "instructions":
            schedule.instructions,

        "message":
            "Exam schedule created successfully",
    }


# =========================================================
# UPDATE TEACHER EXAM SCHEDULE
# =========================================================

@router.put(
    "/exam-schedule/{schedule_id}",
)
def update_teacher_exam_schedule(
    schedule_id: int,
    payload: TeacherExamScheduleUpdate,
    db: Session = Depends(get_db),
    current_teacher: User = Depends(
        get_current_teacher
    ),
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
            detail=(
                "Exam schedule not found"
            ),
        )


    # -----------------------------------------------------
    # VERIFY TEACHER OWNS CLASS + SUBJECT
    # -----------------------------------------------------

    assignment = (
        db.query(TeacherClass)
        .filter(
            TeacherClass.teacher_user_id
            == current_teacher.id,

            TeacherClass.class_id
            == schedule.class_id,
        )
        .all()
    )

    if not assignment:
        raise HTTPException(
            status_code=
                status.HTTP_403_FORBIDDEN,
            detail=(
                "You cannot edit "
                "this schedule"
            ),
        )


    assigned_subjects = {
        (
            item.subject
            or ""
        ).strip().lower()
        for item in assignment
        if item.subject
    }

    if (
        (
            schedule.subject
            or ""
        ).strip().lower()
        not in assigned_subjects
    ):
        raise HTTPException(
            status_code=
                status.HTTP_403_FORBIDDEN,
            detail=(
                "You cannot edit "
                "another teacher's subject"
            ),
        )


    # -----------------------------------------------------
    # UPDATE ALLOWED VALUES
    # -----------------------------------------------------

    updates = payload.model_dump(
        exclude_unset=True
    )

    proposed_start = updates.get(
        "start_time",
        schedule.start_time,
    )
    proposed_end = updates.get(
        "end_time",
        schedule.end_time,
    )

    if proposed_end <= proposed_start:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="End time must be after start time",
        )

    if "exam_date" in updates:
        exam = (
            db.query(Exam)
            .filter(Exam.id == schedule.exam_id)
            .first()
        )
        proposed_date = updates["exam_date"]

        if exam and exam.start_date and proposed_date < exam.start_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Exam date cannot be before the examination start date"
                ),
            )

        if exam and exam.end_date and proposed_date > exam.end_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Exam date cannot be after the examination end date"
                ),
            )

    for field, value in updates.items():
        setattr(schedule, field, value)

    db.commit()
    db.refresh(schedule)

    return {
        "id": schedule.id,

        "class_id":
            schedule.class_id,

        "exam_id":
            schedule.exam_id,

        "subject":
            schedule.subject,

        "exam_date":
            str(
                schedule.exam_date
            ),

        "start_time":
            str(
                schedule.start_time
            ),

        "end_time":
            str(
                schedule.end_time
            ),

        "room":
            schedule.room,

        "instructions":
            schedule.instructions,

        "message":
            "Exam schedule updated successfully",
    }


# =========================================================
# DELETE TEACHER EXAM SCHEDULE
# =========================================================

@router.delete(
    "/exam-schedule/{schedule_id}",
)
def delete_teacher_exam_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_teacher: User = Depends(
        get_current_teacher
    ),
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
            detail=(
                "Exam schedule not found"
            ),
        )


    assignment = (
        db.query(TeacherClass)
        .filter(
            TeacherClass.teacher_user_id
            == current_teacher.id,

            TeacherClass.class_id
            == schedule.class_id,
        )
        .all()
    )

    if not assignment:
        raise HTTPException(
            status_code=
                status.HTTP_403_FORBIDDEN,
            detail=(
                "You cannot delete "
                "this schedule"
            ),
        )


    assigned_subjects = {
        (
            item.subject
            or ""
        ).strip().lower()
        for item in assignment
        if item.subject
    }

    if (
        (
            schedule.subject
            or ""
        ).strip().lower()
        not in assigned_subjects
    ):
        raise HTTPException(
            status_code=
                status.HTTP_403_FORBIDDEN,
            detail=(
                "You cannot delete "
                "another teacher's subject"
            ),
        )


    db.delete(schedule)
    db.commit()

    return {
        "message":
            "Exam schedule deleted successfully"
    }
