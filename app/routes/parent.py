from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)

from sqlalchemy.orm import Session

from app.database import get_db

from app.dependencies import (
    get_current_parent,
)

from app.models.user import User
from app.models.student import Student
from app.models.school_class import SchoolClass
from app.models.parent_student import ParentStudent

from calendar import monthrange
from datetime import date
from sqlalchemy import or_

from app.models.attendance import Attendance

from app.schemas.parent_attendance import (
    ParentAttendanceResponse,
)

from app.schemas.parent import (
    ParentChildResponse,
    ParentChildrenListResponse,
)
from app.models.homework import Homework
from app.schemas.parent_homework import (
    ParentHomeworkListResponse,
)
from app.models.exam import Exam
from app.models.student_result import StudentResult

from app.schemas.parent_result import (
    ParentResultExamListResponse,
    ParentResultsResponse,
)
from app.models.exam import Exam
from app.models.exam_schedule import ExamSchedule
from app.schemas.parent_exam_schedule import (
    ParentExamScheduleResponse,
)
from app.models.circular import Circular
from app.schemas.parent_circular import (
    ParentCircularListResponse,
)
from app.models.school_event import SchoolEvent
from app.schemas.parent_calendar import (
    ParentCalendarListResponse,
)

router = APIRouter(
    prefix="/api/v1/parent",
    tags=["Parent"],
)


# =========================================================
# RESULT GRADE HELPER
# =========================================================

def calculate_result_grade(
    percentage: float,
):
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
# GET CHILD RESULT EXAMS
# =========================================================

@router.get(
    "/children/{student_id}/result-exams",
    response_model=ParentResultExamListResponse,
)
def get_child_result_exams(
    student_id: int,
    db: Session = Depends(get_db),
    current_parent: User = Depends(
        get_current_parent
    ),
):
    # -----------------------------------------------------
    # SECURITY CHECK
    # -----------------------------------------------------

    relation = (
        db.query(ParentStudent)
        .filter(
            ParentStudent.parent_user_id
            == current_parent.id,

            ParentStudent.student_id
            == student_id,
        )
        .first()
    )

    if not relation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Child not found",
        )

    # -----------------------------------------------------
    # GET CHILD
    # -----------------------------------------------------

    student = (
        db.query(Student)
        .filter(
            Student.id == student_id,
            Student.is_active.is_(True),
        )
        .first()
    )

    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Child not found",
        )

    # -----------------------------------------------------
    # GET EXAMS WHICH HAVE RESULTS
    # -----------------------------------------------------

    rows = (
        db.query(Exam)
        .join(
            StudentResult,
            StudentResult.exam_id
            == Exam.id,
        )
        .filter(
            StudentResult.student_id
            == student_id,

            Exam.is_active.is_(True),
        )
        .distinct()
        .order_by(
            Exam.start_date.desc(),
            Exam.id.desc(),
        )
        .all()
    )

    exams = [
        {
            "id":
                exam.id,

            "name":
                exam.name,

            "academic_year":
                exam.academic_year,
        }
        for exam in rows
    ]

    return {
        "total":
            len(exams),

        "exams":
            exams,
    }

    # =========================================================
# GET CHILD ACADEMIC RESULTS
# =========================================================

@router.get(
    "/children/{student_id}/results",
    response_model=ParentResultsResponse,
)
def get_child_results(
    student_id: int,
    exam_id: int,
    db: Session = Depends(get_db),
    current_parent: User = Depends(
        get_current_parent
    ),
):
    # -----------------------------------------------------
    # SECURITY:
    # Parent must own/link to this student
    # -----------------------------------------------------

    relation = (
        db.query(ParentStudent)
        .filter(
            ParentStudent.parent_user_id
            == current_parent.id,

            ParentStudent.student_id
            == student_id,
        )
        .first()
    )

    if not relation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Child not found",
        )

    # -----------------------------------------------------
    # GET STUDENT
    # -----------------------------------------------------

    student = (
        db.query(Student)
        .filter(
            Student.id == student_id,
            Student.is_active.is_(True),
        )
        .first()
    )

    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Child not found",
        )

    # -----------------------------------------------------
    # GET CLASS
    # -----------------------------------------------------

    school_class = None
    class_name = None

    if student.class_id:

        school_class = (
            db.query(SchoolClass)
            .filter(
                SchoolClass.id
                == student.class_id
            )
            .first()
        )

        if school_class:
            class_name = (
                f"{school_class.name} - "
                f"{school_class.section}"
            )

    # -----------------------------------------------------
    # GET EXAM
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

    # -----------------------------------------------------
    # GET RESULTS
    # -----------------------------------------------------

    rows = (
        db.query(StudentResult)
        .filter(
            StudentResult.student_id
            == student_id,

            StudentResult.exam_id
            == exam_id,
        )
        .order_by(
            StudentResult.subject.asc()
        )
        .all()
    )

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Results not available for this exam",
        )

    # -----------------------------------------------------
    # BUILD SUBJECT RESULTS
    # -----------------------------------------------------

    result_items = []

    total_max_marks = 0.0
    total_obtained_marks = 0.0

    for result in rows:

        max_marks = float(
            result.max_marks or 0
        )

        obtained_marks = float(
            result.obtained_marks or 0
        )

        subject_percentage = 0.0

        if max_marks > 0:
            subject_percentage = round(
                (
                    obtained_marks
                    / max_marks
                )
                * 100,
                2,
            )

        total_max_marks += (
            max_marks
        )

        total_obtained_marks += (
            obtained_marks
        )

        result_items.append(
            {
                "id":
                    result.id,

                "subject":
                    result.subject,

                "max_marks":
                    max_marks,

                "obtained_marks":
                    obtained_marks,

                "percentage":
                    subject_percentage,

                "grade":
                    result.grade,

                "remarks":
                    result.remarks,
            }
        )

    # -----------------------------------------------------
    # OVERALL PERCENTAGE
    # -----------------------------------------------------

    overall_percentage = 0.0

    if total_max_marks > 0:

        overall_percentage = round(
            (
                total_obtained_marks
                / total_max_marks
            )
            * 100,
            2,
        )

    overall_grade = (
        calculate_result_grade(
            overall_percentage
        )
    )

    # -----------------------------------------------------
    # RESPONSE
    # -----------------------------------------------------

    return {
        "student_id":
            student.id,

        "student_name":
            student.full_name,

        "admission_no":
            student.admission_no,

        "class_id":
            student.class_id,

        "class_name":
            class_name,

        "exam_id":
            exam.id,

        "exam_name":
            exam.name,

        "academic_year":
            exam.academic_year,

        "total_subjects":
            len(result_items),

        "total_max_marks":
            round(
                total_max_marks,
                2
            ),

        "total_obtained_marks":
            round(
                total_obtained_marks,
                2
            ),

        "overall_percentage":
            overall_percentage,

        "overall_grade":
            overall_grade,

        "results":
            result_items,
    }

# =========================================================
# GET MY CHILDREN
# =========================================================

@router.get(
    "/children",
    response_model=ParentChildrenListResponse,
)
def get_my_children(
    db: Session = Depends(get_db),
    current_parent: User = Depends(
        get_current_parent
    ),
):
    rows = (
        db.query(
            ParentStudent,
            Student,
            SchoolClass,
        )
        .join(
            Student,
            Student.id
            == ParentStudent.student_id,
        )
        .outerjoin(
            SchoolClass,
            SchoolClass.id
            == Student.class_id,
        )
        .filter(
            ParentStudent.parent_user_id
            == current_parent.id,

            Student.is_active.is_(True),
        )
        .order_by(
            Student.full_name.asc()
        )
        .all()
    )

    children = []

    for (
        parent_student,
        student,
        school_class,
    ) in rows:

        class_name = None
        academic_year = None

        if school_class:
            class_name = (
                f"{school_class.name} - "
                f"{school_class.section}"
            )

            academic_year = (
                school_class.academic_year
            )

        children.append(
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

                "academic_year":
                    academic_year,

                "relationship":
                    parent_student.relationship,

                "status":
                    (
                        "Active"
                        if student.is_active
                        else "Inactive"
                    ),
            }
        )

    return {
        "total":
            len(children),

        "children":
            children,
    }


# =========================================================
# GET ONE CHILD
# =========================================================

@router.get(
    "/children/{student_id}",
    response_model=ParentChildResponse,
)
def get_my_child(
    student_id: int,
    db: Session = Depends(get_db),
    current_parent: User = Depends(
        get_current_parent
    ),
):
    row = (
        db.query(
            ParentStudent,
            Student,
            SchoolClass,
        )
        .join(
            Student,
            Student.id
            == ParentStudent.student_id,
        )
        .outerjoin(
            SchoolClass,
            SchoolClass.id
            == Student.class_id,
        )
        .filter(
            ParentStudent.parent_user_id
            == current_parent.id,

            ParentStudent.student_id
            == student_id,

            Student.is_active.is_(True),
        )
        .first()
    )

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Child not found",
        )

    (
        parent_student,
        student,
        school_class,
    ) = row

    class_name = None
    academic_year = None

    if school_class:
        class_name = (
            f"{school_class.name} - "
            f"{school_class.section}"
        )

        academic_year = (
            school_class.academic_year
        )

    return {
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

        "academic_year":
            academic_year,

        "relationship":
            parent_student.relationship,

        "status":
            (
                "Active"
                if student.is_active
                else "Inactive"
            ),
    }

# =========================================================
# GET CHILD MONTHLY ATTENDANCE
# =========================================================

@router.get(
    "/children/{student_id}/attendance",
    response_model=ParentAttendanceResponse,
)
def get_child_attendance(
    student_id: int,
    year: int,
    month: int,
    db: Session = Depends(get_db),
    current_parent: User = Depends(
        get_current_parent
    ),
):
    # -----------------------------------------------------
    # Validate month
    # -----------------------------------------------------

    if month < 1 or month > 12:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Month must be between 1 and 12",
        )

    if year < 2000 or year > 2100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid year",
        )

    # -----------------------------------------------------
    # IMPORTANT SECURITY CHECK
    #
    # Parent can only access students linked through:
    # parent_students
    # -----------------------------------------------------

    relation = (
        db.query(ParentStudent)
        .filter(
            ParentStudent.parent_user_id
            == current_parent.id,

            ParentStudent.student_id
            == student_id,
        )
        .first()
    )

    if not relation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Child not found",
        )

    # -----------------------------------------------------
    # Get student
    # -----------------------------------------------------

    student = (
        db.query(Student)
        .filter(
            Student.id == student_id,
            Student.is_active.is_(True),
        )
        .first()
    )

    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Child not found",
        )

    # -----------------------------------------------------
    # Get class
    # -----------------------------------------------------

    school_class = None

    if student.class_id:
        school_class = (
            db.query(SchoolClass)
            .filter(
                SchoolClass.id
                == student.class_id
            )
            .first()
        )

    class_name = None

    if school_class:
        class_name = (
            f"{school_class.name} - "
            f"{school_class.section}"
        )

    # -----------------------------------------------------
    # Calculate month date range
    # -----------------------------------------------------

    last_day = monthrange(
        year,
        month,
    )[1]

    start_date = date(
        year,
        month,
        1,
    )

    end_date = date(
        year,
        month,
        last_day,
    )

    # -----------------------------------------------------
    # Attendance records
    # -----------------------------------------------------

    records = (
        db.query(Attendance)
        .filter(
            Attendance.student_id
            == student_id,

            Attendance.attendance_date
            >= start_date,

            Attendance.attendance_date
            <= end_date,
        )
        .order_by(
            Attendance.attendance_date.asc()
        )
        .all()
    )

    # -----------------------------------------------------
    # Counts
    # -----------------------------------------------------

    present_count = sum(
        1
        for item in records
        if item.status == "PRESENT"
    )

    absent_count = sum(
        1
        for item in records
        if item.status == "ABSENT"
    )

    total_marked_days = (
        present_count +
        absent_count
    )

    # -----------------------------------------------------
    # Percentage
    # -----------------------------------------------------

    attendance_percentage = 0.0

    if total_marked_days > 0:
        attendance_percentage = round(
            (
                present_count
                / total_marked_days
            )
            * 100,
            2,
        )

    # -----------------------------------------------------
    # Response
    # -----------------------------------------------------

    return {
        "student_id":
            student.id,

        "student_name":
            student.full_name,

        "admission_no":
            student.admission_no,

        "class_id":
            student.class_id,

        "class_name":
            class_name,

        "year":
            year,

        "month":
            month,

        "total_marked_days":
            total_marked_days,

        "present_count":
            present_count,

        "absent_count":
            absent_count,

        "attendance_percentage":
            attendance_percentage,

        "records": [
            {
                "attendance_date":
                    item.attendance_date,

                "status":
                    item.status,

                "remarks":
                    item.remarks,
            }
            for item in records
        ],
    }

# =========================================================
# GET CHILD HOMEWORK
# =========================================================

@router.get(
    "/children/{student_id}/homework",
    response_model=ParentHomeworkListResponse,
)
def get_child_homework(
    student_id: int,
    search: str | None = None,
    db: Session = Depends(get_db),
    current_parent: User = Depends(
        get_current_parent
    ),
):
    # -----------------------------------------------------
    # SECURITY:
    # Parent can only access their linked child
    # -----------------------------------------------------

    relation = (
        db.query(ParentStudent)
        .filter(
            ParentStudent.parent_user_id
            == current_parent.id,

            ParentStudent.student_id
            == student_id,
        )
        .first()
    )

    if not relation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Child not found",
        )

    # -----------------------------------------------------
    # Get student
    # -----------------------------------------------------

    student = (
        db.query(Student)
        .filter(
            Student.id == student_id,
            Student.is_active.is_(True),
        )
        .first()
    )

    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Child not found",
        )

    # -----------------------------------------------------
    # Student must have class
    # -----------------------------------------------------

    if not student.class_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student is not assigned to a class",
        )

    # -----------------------------------------------------
    # Get class
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
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student class not found",
        )

    class_name = (
        f"{school_class.name} - "
        f"{school_class.section}"
    )

    # -----------------------------------------------------
    # Homework query
    # -----------------------------------------------------

    query = (
        db.query(
            Homework,
            User,
        )
        .outerjoin(
            User,
            User.id
            == Homework.teacher_user_id,
        )
        .filter(
            Homework.class_id
            == student.class_id,

            Homework.is_active.is_(True),
        )
    )

    # -----------------------------------------------------
    # Optional search
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

                Homework.subject.ilike(
                    search_value
                ),

                Homework.description.ilike(
                    search_value
                ),
            )
        )

    # -----------------------------------------------------
    # Order newest first
    # -----------------------------------------------------

    rows = (
        query
        .order_by(
            Homework.assigned_date.desc(),
            Homework.id.desc(),
        )
        .all()
    )

    # -----------------------------------------------------
    # Build response
    # -----------------------------------------------------

    today = date.today()

    homework_list = []

    for homework, teacher in rows:

        if homework.assigned_date > today:
            homework_status = "UPCOMING"

        elif homework.due_date < today:
            homework_status = "OVERDUE"

        else:
            homework_status = "ACTIVE"

        homework_list.append(
            {
                "id":
                    homework.id,

                "class_id":
                    homework.class_id,

                "class_name":
                    class_name,

                "teacher_user_id":
                    homework.teacher_user_id,

                "teacher_name":
                    (
                        teacher.name
                        if teacher
                        else None
                    ),

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

                "status":
                    homework_status,
            }
        )

    return {
        "student_id":
            student.id,

        "student_name":
            student.full_name,

        "admission_no":
            student.admission_no,

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
# GET CHILD EXAM SCHEDULE
# =========================================================

@router.get(
    "/children/{student_id}/exam-schedule",
    response_model=ParentExamScheduleResponse,
)
def get_child_exam_schedule(
    student_id: int,
    exam_id: int | None = None,
    db: Session = Depends(get_db),
    current_parent: User = Depends(
        get_current_parent
    ),
):
    # -----------------------------------------------------
    # SECURITY CHECK
    # Parent can only access their own linked child
    # -----------------------------------------------------

    relation = (
        db.query(ParentStudent)
        .filter(
            ParentStudent.parent_user_id
            == current_parent.id,

            ParentStudent.student_id
            == student_id,
        )
        .first()
    )

    if not relation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Child not found",
        )

    # -----------------------------------------------------
    # GET STUDENT
    # -----------------------------------------------------

    student = (
        db.query(Student)
        .filter(
            Student.id
            == student_id,

            Student.is_active.is_(True),
        )
        .first()
    )

    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Child not found",
        )

    # -----------------------------------------------------
    # STUDENT MUST HAVE CLASS
    # -----------------------------------------------------

    if not student.class_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student is not assigned to a class",
        )

    # -----------------------------------------------------
    # GET CLASS
    # -----------------------------------------------------

    school_class = (
        db.query(SchoolClass)
        .filter(
            SchoolClass.id
            == student.class_id,

            SchoolClass.is_active.is_(True),
        )
        .first()
    )

    if not school_class:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student class not found",
        )

    class_name = (
        f"{school_class.name} - "
        f"{school_class.section}"
    )

    # -----------------------------------------------------
    # GET AVAILABLE EXAMS FOR THIS CLASS
    # -----------------------------------------------------

    available_exams = (
        db.query(Exam)
        .join(
            ExamSchedule,
            ExamSchedule.exam_id
            == Exam.id,
        )
        .filter(
            ExamSchedule.class_id
            == student.class_id,

            Exam.is_active.is_(True),
        )
        .distinct()
        .order_by(
            Exam.start_date.asc(),
            Exam.id.asc(),
        )
        .all()
    )

    exam_options = [
        {
            "id":
                exam.id,

            "name":
                exam.name,

            "academic_year":
                exam.academic_year,
        }
        for exam in available_exams
    ]

    # -----------------------------------------------------
    # EXAM SCHEDULE QUERY
    # -----------------------------------------------------

    query = (
        db.query(
            ExamSchedule,
            Exam,
        )
        .join(
            Exam,
            Exam.id
            == ExamSchedule.exam_id,
        )
        .filter(
            ExamSchedule.class_id
            == student.class_id,

            Exam.is_active.is_(True),
        )
    )

    # -----------------------------------------------------
    # OPTIONAL EXAM FILTER
    # -----------------------------------------------------

    if exam_id is not None:

        valid_exam = any(
            exam.id == exam_id
            for exam in available_exams
        )

        if not valid_exam:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Exam schedule not found",
            )

        query = query.filter(
            ExamSchedule.exam_id
            == exam_id
        )

    # -----------------------------------------------------
    # ORDER
    # -----------------------------------------------------

    rows = (
        query
        .order_by(
            ExamSchedule.exam_date.asc(),
            ExamSchedule.start_time.asc(),
        )
        .all()
    )

    # -----------------------------------------------------
    # RESPONSE
    # -----------------------------------------------------

    schedules = []

    for (
        schedule,
        exam,
    ) in rows:

        schedules.append(
            {
                "id":
                    schedule.id,

                "exam_id":
                    exam.id,

                "exam_name":
                    exam.name,

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
        "student_id":
            student.id,

        "student_name":
            student.full_name,

        "admission_no":
            student.admission_no,

        "class_id":
            school_class.id,

        "class_name":
            class_name,

        "total":
            len(schedules),

        "exams":
            exam_options,

        "schedules":
            schedules,
    }

# =========================================================
# GET PARENT CIRCULARS
# =========================================================

@router.get(
    "/circulars",
    response_model=ParentCircularListResponse,
)
def get_parent_circulars(
    student_id: int | None = None,
    category: str | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
    current_parent: User = Depends(
        get_current_parent
    ),
):
    # -----------------------------------------------------
    # GET PARENT'S LINKED CHILDREN
    # -----------------------------------------------------

    linked_rows = (
        db.query(
            ParentStudent,
            Student,
        )
        .join(
            Student,
            Student.id
            == ParentStudent.student_id,
        )
        .filter(
            ParentStudent.parent_user_id
            == current_parent.id,

            Student.is_active.is_(True),
        )
        .all()
    )

    # -----------------------------------------------------
    # BUILD LINKED STUDENT IDS
    # -----------------------------------------------------

    linked_student_ids = [
        student.id
        for parent_student, student
        in linked_rows
    ]

    # -----------------------------------------------------
    # BUILD LINKED CLASS IDS
    # -----------------------------------------------------

    linked_class_ids = list(
        {
            student.class_id
            for parent_student, student
            in linked_rows
            if student.class_id is not None
        }
    )

    # -----------------------------------------------------
    # OPTIONAL CHILD FILTER
    # -----------------------------------------------------

    selected_class_ids = (
        linked_class_ids
    )

    if student_id is not None:

        # Security:
        # Parent can only filter using their own child.
        if student_id not in linked_student_ids:

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Child not found",
            )

        selected_student = next(
            (
                student
                for parent_student, student
                in linked_rows
                if student.id
                == student_id
            ),
            None,
        )

        selected_class_ids = []

        if (
            selected_student
            and
            selected_student.class_id
            is not None
        ):
            selected_class_ids = [
                selected_student.class_id
            ]

    # -----------------------------------------------------
    # BASE AUDIENCE RULES
    # -----------------------------------------------------

    audience_conditions = [
        Circular.audience == "ALL",
        Circular.audience == "PARENT",
    ]

    # -----------------------------------------------------
    # CLASS CIRCULARS
    # -----------------------------------------------------

    if selected_class_ids:

        audience_conditions.append(
            (
                Circular.audience
                == "CLASS"
            )
            &
            (
                Circular.class_id.in_(
                    selected_class_ids
                )
            )
        )

    # -----------------------------------------------------
    # BASE QUERY
    # -----------------------------------------------------

    query = (
        db.query(Circular)
        .filter(
            Circular.is_active.is_(True),

            or_(
                *audience_conditions
            ),
        )
    )

    # -----------------------------------------------------
    # CATEGORY FILTER
    # -----------------------------------------------------

    if category:

        clean_category = (
            category
            .strip()
        )

        if clean_category:

            query = query.filter(
                Circular.category
                == clean_category
            )

    # -----------------------------------------------------
    # SEARCH
    # -----------------------------------------------------

    if search:

        clean_search = (
            search
            .strip()
        )

        if clean_search:

            search_value = (
                f"%{clean_search}%"
            )

            query = query.filter(
                or_(
                    Circular.title.ilike(
                        search_value
                    ),

                    Circular.category.ilike(
                        search_value
                    ),

                    Circular.description.ilike(
                        search_value
                    ),
                )
            )

    # -----------------------------------------------------
    # ORDER
    # -----------------------------------------------------

    rows = (
        query
        .order_by(
            Circular.published_date.desc(),
            Circular.id.desc(),
        )
        .all()
    )

    # -----------------------------------------------------
    # BUILD RESPONSE
    # -----------------------------------------------------

    circulars = []

    for circular in rows:

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
# GET PARENT SCHOOL CALENDAR
# =========================================================

@router.get(
    "/calendar",
    response_model=ParentCalendarListResponse,
)
def get_parent_calendar(
    student_id: int | None = None,
    event_type: str | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
    current_parent: User = Depends(
        get_current_parent
    ),
):
    # -----------------------------------------------------
    # GET LINKED CHILDREN
    # -----------------------------------------------------

    linked_rows = (
        db.query(
            ParentStudent,
            Student,
        )
        .join(
            Student,
            Student.id
            == ParentStudent.student_id,
        )
        .filter(
            ParentStudent.parent_user_id
            == current_parent.id,

            Student.is_active.is_(True),
        )
        .all()
    )


    linked_student_ids = [
        student.id
        for _, student
        in linked_rows
    ]


    linked_class_ids = list(
        {
            student.class_id
            for _, student
            in linked_rows
            if student.class_id is not None
        }
    )


    # -----------------------------------------------------
    # OPTIONAL CHILD FILTER
    # -----------------------------------------------------

    selected_class_ids = (
        linked_class_ids
    )


    if student_id is not None:

        if student_id not in linked_student_ids:

            raise HTTPException(
                status_code=
                    status.HTTP_404_NOT_FOUND,

                detail=
                    "Child not found",
            )


        selected_student = next(
            (
                student
                for _, student
                in linked_rows
                if student.id
                == student_id
            ),
            None,
        )


        selected_class_ids = []


        if (
            selected_student
            and
            selected_student.class_id
            is not None
        ):
            selected_class_ids = [
                selected_student.class_id
            ]


    # -----------------------------------------------------
    # AUDIENCE CONDITIONS
    # -----------------------------------------------------

    audience_conditions = [
        SchoolEvent.audience == "ALL",
        SchoolEvent.audience == "PARENT",
    ]


    if selected_class_ids:

        audience_conditions.append(
            (
                SchoolEvent.audience
                == "CLASS"
            )
            &
            (
                SchoolEvent.class_id.in_(
                    selected_class_ids
                )
            )
        )


    # -----------------------------------------------------
    # BASE QUERY
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
    # EVENT TYPE FILTER
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
    # SEARCH
    # -----------------------------------------------------

    if search:

        clean_search = (
            search.strip()
        )


        if clean_search:

            value = (
                f"%{clean_search}%"
            )


            query = query.filter(
                or_(
                    SchoolEvent.title.ilike(
                        value
                    ),

                    SchoolEvent.description.ilike(
                        value
                    ),

                    SchoolEvent.location.ilike(
                        value
                    ),
                )
            )


    # -----------------------------------------------------
    # ORDER
    # -----------------------------------------------------

    rows = (
        query
        .order_by(
            SchoolEvent.start_date.asc(),
            SchoolEvent.start_time.asc(),
            SchoolEvent.id.asc(),
        )
        .all()
    )


    # -----------------------------------------------------
    # RESPONSE
    # -----------------------------------------------------

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