from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy import or_
from app.models.circular import Circular
from app.schemas.circular import (
    CircularListResponse,
)

from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_teacher

from app.models.user import User
from app.models.school_class import SchoolClass
from app.models.student import Student
from app.models.teacher_class import TeacherClass

from app.schemas.teacher import (
    TeacherClassResponse,
    TeacherStudentListResponse,
)
from datetime import date
from app.models.attendance import Attendance

from app.schemas.attendance import (
    AttendanceSaveRequest,
    AttendanceSaveResponse,
    AttendanceSheetResponse,
)

from app.models.homework import Homework

from app.schemas.homework import (
    HomeworkCreate,
    HomeworkListResponse,
    HomeworkResponse,
)

from app.models.exam import Exam
from app.models.student_result import StudentResult

from app.schemas.result import (
    ExamResponse,
    ResultSaveRequest,
    ResultSaveResponse,
    ResultSheetResponse,
)

from app.models.exam_schedule import ExamSchedule
from app.schemas.exam_schedule import (
    ExamScheduleListResponse,
)
from app.models.school_event import SchoolEvent
from app.schemas.school_event import (
    SchoolEventListResponse,
)
from app.models.teacher_profile import (
    TeacherProfile,
)
from app.schemas.teacher_profile import (
    TeacherProfileResponse,
)


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
    # Verify teacher assignment
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
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not assigned to this class",
        )

    # -----------------------------------------------------
    # Class
    # -----------------------------------------------------

    school_class = (
        db.query(SchoolClass)
        .filter(
            SchoolClass.id == class_id,
            SchoolClass.is_active.is_(True),
        )
        .first()
    )

    if not school_class:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Class not found",
        )

    # -----------------------------------------------------
    # Exam
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
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam not found",
        )

    clean_subject = subject.strip()

    if not clean_subject:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Subject is required",
        )

    # -----------------------------------------------------
    # Students
    # -----------------------------------------------------

    students = (
        db.query(Student)
        .filter(
            Student.class_id == class_id,
            Student.is_active.is_(True),
        )
        .order_by(Student.roll_no)
        .all()
    )

    # -----------------------------------------------------
    # Existing results
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
                    float(result.max_marks)
                    if result
                    else None,

                "obtained_marks":
                    float(
                        result.obtained_marks
                    )
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
    # Teacher assignment
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
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not assigned to this class",
        )

    # -----------------------------------------------------
    # Exam
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
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam not found",
        )

    subject = payload.subject.strip()

    if not subject:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Subject is required",
        )

    # -----------------------------------------------------
    # Valid class students
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
    # Save / update each result
    # -----------------------------------------------------

    for item in payload.results:
        if (
            item.student_id
            not in valid_student_ids
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Student "
                    f"{item.student_id} "
                    "does not belong to this class"
                ),
            )

        if item.max_marks <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Maximum marks must "
                    "be greater than zero"
                ),
            )

        if item.obtained_marks < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Obtained marks cannot "
                    "be negative"
                ),
            )

        if (
            item.obtained_marks
            > item.max_marks
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Obtained marks cannot "
                    "exceed maximum marks"
                ),
            )

        grade = calculate_grade(
            item.obtained_marks,
            item.max_marks,
        )

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
                item.obtained_marks
            )

            existing.grade = (
                grade
            )

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
                    item.obtained_marks,

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
    response_model=ExamScheduleListResponse,
)
def get_teacher_exam_schedule(
    class_id: int | None = None,
    exam_id: int | None = None,
    db: Session = Depends(get_db),
    current_teacher: User = Depends(
        get_current_teacher
    ),
):
    # -----------------------------------------------------
    # Teacher assigned classes
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # If specific class requested, verify teacher access
    # -----------------------------------------------------

    if (
        class_id is not None
        and class_id
        not in assigned_class_ids
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "You are not assigned "
                "to this class"
            ),
        )

    # -----------------------------------------------------
    # Query schedule
    # -----------------------------------------------------

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
            SchoolClass.is_active.is_(True),
        )
    )

    # -----------------------------------------------------
    # Class filter
    # -----------------------------------------------------

    if class_id is not None:
        query = query.filter(
            ExamSchedule.class_id
            == class_id
        )

    # -----------------------------------------------------
    # Exam filter
    # -----------------------------------------------------

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

@router.get(
    "/classes",
    response_model=list[TeacherClassResponse],
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
            SchoolClass.is_active.is_(True),
        )
        .order_by(
            SchoolClass.name,
            SchoolClass.section,
        )
        .all()
    )

    return [
        {
            "id": school_class.id,

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
        for school_class, subject in rows
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
    db: Session = Depends(get_db),
    current_teacher: User = Depends(
        get_current_teacher
    ),
):
    # -----------------------------------------------------
    # Get teacher assigned classes
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # Base query
    # -----------------------------------------------------

    query = (
        db.query(Circular)
        .filter(
            Circular.is_active.is_(True)
        )
    )

    # -----------------------------------------------------
    # Audience filter
    # -----------------------------------------------------

    audience_conditions = [
        Circular.audience == "ALL",
        Circular.audience == "TEACHER",
    ]

    if assigned_class_ids:
        audience_conditions.append(
            (
                Circular.audience == "CLASS"
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

    # -----------------------------------------------------
    # Category filter
    # -----------------------------------------------------

    if category:
        clean_category = (
            category.strip()
        )

        if clean_category:
            query = query.filter(
                Circular.category
                == clean_category
            )

    # -----------------------------------------------------
    # Search filter
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # Execute
    # -----------------------------------------------------

    circular_rows = (
        query
        .order_by(
            Circular.published_date.desc(),
            Circular.id.desc(),
        )
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
            len(circulars),

        "circulars":
            circulars,
    }

# =========================================================
# GET TEACHER SCHOOL CALENDAR
# =========================================================

@router.get(
    "/calendar",
    response_model=SchoolEventListResponse,
)
def get_teacher_calendar(
    event_type: str | None = None,
    db: Session = Depends(get_db),
    current_teacher: User = Depends(
        get_current_teacher
    ),
):
    # -----------------------------------------------------
    # Teacher assigned classes
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # Audience permissions
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # Base query
    # -----------------------------------------------------

    query = (
        db.query(SchoolEvent)
        .filter(
            SchoolEvent.is_active.is_(True),
            or_(
                *audience_conditions
            ),
        )
    )

    # -----------------------------------------------------
    # Event type filter
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # Order
    # -----------------------------------------------------

    rows = (
        query
        .order_by(
            SchoolEvent.start_date.asc(),
            SchoolEvent.start_time.asc(),
        )
        .all()
    )

    events = []

    # -----------------------------------------------------
    # Build response
    # -----------------------------------------------------

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
    db: Session = Depends(get_db),
    current_teacher: User = Depends(
        get_current_teacher
    ),
):
    # -----------------------------------------------------
    # Verify teacher belongs to class
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
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not assigned to this class",
        )

    # -----------------------------------------------------
    # Get class
    # -----------------------------------------------------

    school_class = (
        db.query(SchoolClass)
        .filter(
            SchoolClass.id == class_id,
            SchoolClass.is_active.is_(True),
        )
        .first()
    )

    if not school_class:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Class not found",
        )

    # -----------------------------------------------------
    # Homework
    # -----------------------------------------------------

    rows = (
        db.query(Homework)
        .filter(
            Homework.class_id == class_id,
            Homework.is_active.is_(True),
        )
        .order_by(
            Homework.created_at.desc()
        )
        .all()
    )

    class_name = (
        f"{school_class.name} - "
        f"{school_class.section}"
    )

    homework_list = []

    for item in rows:
        homework_list.append(
            {
                "id": item.id,

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
            len(homework_list),

        "homework":
            homework_list,
    }

# =========================================================
# CREATE HOMEWORK
# =========================================================

@router.post(
    "/classes/{class_id}/homework",
    response_model=HomeworkResponse,
    status_code=status.HTTP_201_CREATED,
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
    # Verify teacher assignment
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
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not assigned to this class",
        )

    # -----------------------------------------------------
    # Get class
    # -----------------------------------------------------

    school_class = (
        db.query(SchoolClass)
        .filter(
            SchoolClass.id == class_id,
            SchoolClass.is_active.is_(True),
        )
        .first()
    )

    if not school_class:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Class not found",
        )

    # -----------------------------------------------------
    # Validate dates
    # -----------------------------------------------------

    if payload.due_date < payload.assigned_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Due date cannot be before "
                "assigned date"
            ),
        )

    # -----------------------------------------------------
    # Validate required strings
    # -----------------------------------------------------

    subject = payload.subject.strip()
    title = payload.title.strip()

    if not subject:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Subject is required",
        )

    if not title:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Homework title is required",
        )

    # -----------------------------------------------------
    # Create
    # -----------------------------------------------------

    homework = Homework(
        class_id=class_id,

        teacher_user_id=
            current_teacher.id,

        subject=subject,

        title=title,

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
    response_model=AttendanceSheetResponse,
)
def get_class_attendance(
    class_id: int,
    attendance_date: date,
    db: Session = Depends(get_db),
    current_teacher: User = Depends(
        get_current_teacher
    ),
):
    # -----------------------------------------------------
    # Check teacher class assignment
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
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not assigned to this class",
        )

    # -----------------------------------------------------
    # Find class
    # -----------------------------------------------------

    school_class = (
        db.query(SchoolClass)
        .filter(
            SchoolClass.id == class_id,
            SchoolClass.is_active.is_(True),
        )
        .first()
    )

    if not school_class:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Class not found",
        )

    # -----------------------------------------------------
    # Students
    # -----------------------------------------------------

    students = (
        db.query(Student)
        .filter(
            Student.class_id == class_id,
            Student.is_active.is_(True),
        )
        .order_by(Student.roll_no)
        .all()
    )

    # -----------------------------------------------------
    # Existing attendance
    # -----------------------------------------------------

    attendance_rows = (
        db.query(Attendance)
        .filter(
            Attendance.class_id == class_id,
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
        attendance = attendance_map.get(
            student.id
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
                "student_id": student.id,
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
        "class_id": school_class.id,

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
# GET TEACHER CLASSES
# =========================================================

@router.get(
    "/classes",
    response_model=list[TeacherClassResponse],
)
def get_teacher_classes(
    db: Session = Depends(get_db),
    current_teacher: User = Depends(
        get_current_teacher
    ),
):
    rows = (
        db.query(
            SchoolClass
        )
        .join(
            TeacherClass,
            TeacherClass.class_id
            == SchoolClass.id,
        )
        .filter(
            TeacherClass.teacher_user_id
            == current_teacher.id,
            SchoolClass.is_active.is_(True),
        )
        .order_by(
            SchoolClass.name,
            SchoolClass.section,
        )
        .all()
    )

    return [
        {
            "id": school_class.id,
            "name": school_class.name,
            "section": school_class.section,
            "academic_year":
                school_class.academic_year,
            "display_name":
                f"{school_class.name} - "
                f"{school_class.section}",
        }
        for school_class in rows
    ]


# =========================================================
# SAVE ATTENDANCE
# =========================================================

@router.post(
    "/classes/{class_id}/attendance",
    response_model=AttendanceSaveResponse,
)
def save_class_attendance(
    class_id: int,
    payload: AttendanceSaveRequest,
    db: Session = Depends(get_db),
    current_teacher: User = Depends(
        get_current_teacher
    ),
):
    # -----------------------------------------------------
    # Check teacher assignment
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
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not assigned to this class",
        )

    # -----------------------------------------------------
    # Get students belonging to class
    # -----------------------------------------------------

    class_students = (
        db.query(Student)
        .filter(
            Student.class_id == class_id,
            Student.is_active.is_(True),
        )
        .all()
    )

    valid_student_ids = {
        student.id
        for student in class_students
    }

    present_count = 0
    absent_count = 0

    # -----------------------------------------------------
    # Save / Update attendance
    # -----------------------------------------------------

    for record in payload.records:

        if record.student_id not in valid_student_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Student {record.student_id} "
                    "does not belong to this class"
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
                status_code=status.HTTP_400_BAD_REQUEST,
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
            existing.class_id = class_id

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

        if attendance_status == "PRESENT":
            present_count += 1

        if attendance_status == "ABSENT":
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
    response_model=TeacherStudentListResponse,
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
    # -----------------------------------------------------
    # Verify teacher owns / is assigned to this class
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
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "You are not assigned to this class"
            ),
        )

    # -----------------------------------------------------
    # Find class
    # -----------------------------------------------------

    school_class = (
        db.query(SchoolClass)
        .filter(
            SchoolClass.id == class_id,
            SchoolClass.is_active.is_(True),
        )
        .first()
    )

    if not school_class:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Class not found",
        )

    # -----------------------------------------------------
    # Student query
    # -----------------------------------------------------

    query = (
        db.query(Student)
        .filter(
            Student.class_id == class_id,
            Student.is_active.is_(True),
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
        .order_by(Student.roll_no)
        .all()
    )

    class_name = (
        f"{school_class.name} - "
        f"{school_class.section}"
    )

    return {
        "class_id": school_class.id,
        "class_name": class_name,
        "total": len(students),
        "students": [
            {
                "id": student.id,
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
    response_model=TeacherProfileResponse,
)
def get_teacher_profile(
    db: Session = Depends(get_db),
    current_teacher: User = Depends(
        get_current_teacher
    ),
):
    # -----------------------------------------------------
    # Teacher extended profile
    # -----------------------------------------------------

    profile = (
        db.query(TeacherProfile)
        .filter(
            TeacherProfile.user_id
            == current_teacher.id
        )
        .first()
    )

    # -----------------------------------------------------
    # Assigned classes
    # -----------------------------------------------------

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

            SchoolClass.is_active.is_(True),
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

    # -----------------------------------------------------
    # Response
    # -----------------------------------------------------

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