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

from app.models.student_fee import StudentFee

from app.schemas.parent_fee import (
    ParentFeeResponse,
)
from app.models.download_form import DownloadForm
from app.schemas.parent_download import (
    ParentDownloadFormListResponse,
)
from app.models.parent_profile import ParentProfile
from app.schemas.parent_profile import (
    ParentProfileResponse,
)
from app.schemas.parent_dashboard import (
    ParentDashboardResponse,
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

# =========================================================
# GET CHILD FEE INFORMATION
# =========================================================

@router.get(
    "/children/{student_id}/fees",
    response_model=ParentFeeResponse,
)
def get_child_fees(
    student_id: int,
    academic_year: str | None = None,
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
    # STUDENT
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
    # CLASS
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
    # ACADEMIC YEAR
    # -----------------------------------------------------

    selected_academic_year = (
        academic_year
        or (
            school_class.academic_year
            if school_class
            else "2026-2027"
        )
    )

    # -----------------------------------------------------
    # FEE QUERY
    # -----------------------------------------------------

    fee_rows = (
        db.query(StudentFee)
        .filter(
            StudentFee.student_id
            == student_id,

            StudentFee.academic_year
            == selected_academic_year,

            StudentFee.is_active.is_(True),
        )
        .order_by(
            StudentFee.due_date.asc(),
            StudentFee.id.asc(),
        )
        .all()
    )

    today = date.today()

    total_fee = 0.0
    total_paid = 0.0
    total_pending = 0.0
    overdue_amount = 0.0

    fee_items = []

    # -----------------------------------------------------
    # CALCULATE
    # -----------------------------------------------------

    for fee in fee_rows:

        amount = float(
            fee.amount or 0
        )

        paid_amount = float(
            fee.paid_amount or 0
        )

        pending_amount = max(
            amount - paid_amount,
            0,
        )

        if paid_amount >= amount:
            fee_status = "PAID"

        elif paid_amount > 0:
            if fee.due_date < today:
                fee_status = "OVERDUE"
            else:
                fee_status = "PARTIAL"

        elif fee.due_date < today:
            fee_status = "OVERDUE"

        else:
            fee_status = "PENDING"

        total_fee += amount
        total_paid += paid_amount
        total_pending += pending_amount

        if (
            fee_status == "OVERDUE"
            and pending_amount > 0
        ):
            overdue_amount += (
                pending_amount
            )

        fee_items.append(
            {
                "id":
                    fee.id,

                "fee_title":
                    fee.fee_title,

                "fee_type":
                    fee.fee_type,

                "amount":
                    amount,

                "paid_amount":
                    paid_amount,

                "pending_amount":
                    pending_amount,

                "due_date":
                    fee.due_date,

                "paid_date":
                    fee.paid_date,

                "receipt_no":
                    fee.receipt_no,

                "payment_mode":
                    fee.payment_mode,

                "remarks":
                    fee.remarks,

                "status":
                    fee_status,
            }
        )

    return {
        "student_id":
            student.id,

        "student_name":
            student.full_name,

        "admission_no":
            student.admission_no,

        "class_name":
            class_name,

        "academic_year":
            selected_academic_year,

        "total_fee":
            round(
                total_fee,
                2
            ),

        "total_paid":
            round(
                total_paid,
                2
            ),

        "total_pending":
            round(
                total_pending,
                2
            ),

        "overdue_amount":
            round(
                overdue_amount,
                2
            ),

        "total_items":
            len(fee_items),

        "fees":
            fee_items,
    }

# =========================================================
# GET PARENT DOWNLOAD FORMS
# =========================================================

@router.get(
    "/download-forms",
    response_model=ParentDownloadFormListResponse,
)
def get_parent_download_forms(
    student_id: int | None = None,
    category: str | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
    current_parent: User = Depends(
        get_current_parent
    ),
):
    # -----------------------------------------------------
    # LINKED CHILDREN
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
    # AUDIENCE RULES
    # -----------------------------------------------------

    audience_conditions = [
        DownloadForm.audience
        == "ALL",

        DownloadForm.audience
        == "PARENT",
    ]

    if selected_class_ids:
        audience_conditions.append(
            (
                DownloadForm.audience
                == "CLASS"
            )
            &
            (
                DownloadForm.class_id.in_(
                    selected_class_ids
                )
            )
        )

    # -----------------------------------------------------
    # QUERY
    # -----------------------------------------------------

    query = (
        db.query(DownloadForm)
        .filter(
            DownloadForm.is_active.is_(True),

            or_(
                *audience_conditions
            ),
        )
    )

    # -----------------------------------------------------
    # CATEGORY
    # -----------------------------------------------------

    if category:

        clean_category = (
            category
            .strip()
            .upper()
        )

        if clean_category:
            query = query.filter(
                DownloadForm.category
                == clean_category
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
                    DownloadForm.title.ilike(
                        value
                    ),

                    DownloadForm.description.ilike(
                        value
                    ),

                    DownloadForm.category.ilike(
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
            DownloadForm.published_date.desc(),
            DownloadForm.id.desc(),
        )
        .all()
    )

    forms = []

    for item in rows:

        class_name = None

        if item.class_id:

            school_class = (
                db.query(SchoolClass)
                .filter(
                    SchoolClass.id
                    == item.class_id
                )
                .first()
            )

            if school_class:
                class_name = (
                    f"{school_class.name} - "
                    f"{school_class.section}"
                )

        forms.append(
            {
                "id":
                    item.id,

                "title":
                    item.title,

                "category":
                    item.category,

                "description":
                    item.description,

                "audience":
                    item.audience,

                "class_id":
                    item.class_id,

                "class_name":
                    class_name,

                "file_name":
                    item.file_name,

                "file_url":
                    item.file_url,

                "published_date":
                    item.published_date,
            }
        )

    return {
        "total":
            len(forms),

        "forms":
            forms,
    }

# =========================================================
# GET PARENT PROFILE
# =========================================================

@router.get(
    "/profile",
    response_model=ParentProfileResponse,
)
def get_parent_profile(
    db: Session = Depends(get_db),
    current_parent: User = Depends(
        get_current_parent
    ),
):
    # -----------------------------------------------------
    # EXTENDED PROFILE
    # -----------------------------------------------------

    profile = (
        db.query(ParentProfile)
        .filter(
            ParentProfile.user_id
            == current_parent.id
        )
        .first()
    )

    # -----------------------------------------------------
    # LINKED CHILDREN
    # -----------------------------------------------------

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
                "student_id":
                    student.id,

                "admission_no":
                    student.admission_no,

                "full_name":
                    student.full_name,

                "class_name":
                    class_name,

                "academic_year":
                    academic_year,

                "relationship":
                    parent_student.relationship,
            }
        )

    # -----------------------------------------------------
    # RESPONSE
    # -----------------------------------------------------

    return {
        "user_id":
            current_parent.id,

        "name":
            current_parent.name,

        "username":
            current_parent.username,

        "email":
            current_parent.email,

        "role":
            current_parent.role,

        "is_active":
            current_parent.is_active,

        "phone":
            profile.phone
            if profile
            else None,

        "alternate_phone":
            profile.alternate_phone
            if profile
            else None,

        "occupation":
            profile.occupation
            if profile
            else None,

        "address":
            profile.address
            if profile
            else None,

        "city":
            profile.city
            if profile
            else None,

        "state":
            profile.state
            if profile
            else None,

        "pincode":
            profile.pincode
            if profile
            else None,

        "profile_image_url":
            profile.profile_image_url
            if profile
            else None,

        "children":
            children,
    }

# =========================================================
# GET PARENT DASHBOARD
# =========================================================

@router.get(
    "/dashboard",
    response_model=ParentDashboardResponse,
)
def get_parent_dashboard(
    student_id: int,
    db: Session = Depends(get_db),
    current_parent: User = Depends(
        get_current_parent
    ),
):
    today = date.today()

    # =====================================================
    # SECURITY + CHILD
    # =====================================================

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
            status_code=
                status.HTTP_404_NOT_FOUND,

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


    # =====================================================
    # ATTENDANCE - CURRENT MONTH
    # =====================================================

    month_start = date(
        today.year,
        today.month,
        1,
    )


    attendance_rows = (
        db.query(Attendance)
        .filter(
            Attendance.student_id
            == student.id,

            Attendance.attendance_date
            >= month_start,

            Attendance.attendance_date
            <= today,
        )
        .all()
    )


    present_count = sum(
        1
        for item in attendance_rows
        if item.status == "PRESENT"
    )


    absent_count = sum(
        1
        for item in attendance_rows
        if item.status == "ABSENT"
    )


    total_marked_days = (
        present_count
        + absent_count
    )


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


    # =====================================================
    # HOMEWORK
    # =====================================================

    active_homework = 0
    overdue_homework = 0


    if student.class_id:

        active_homework = (
            db.query(Homework)
            .filter(
                Homework.class_id
                == student.class_id,

                Homework.is_active.is_(
                    True
                ),

                Homework.assigned_date
                <= today,

                Homework.due_date
                >= today,
            )
            .count()
        )


        overdue_homework = (
            db.query(Homework)
            .filter(
                Homework.class_id
                == student.class_id,

                Homework.is_active.is_(
                    True
                ),

                Homework.due_date
                < today,
            )
            .count()
        )


    # =====================================================
    # LATEST RESULT
    # =====================================================

    latest_result = None


    latest_exam = (
        db.query(Exam)
        .join(
            StudentResult,
            StudentResult.exam_id
            == Exam.id,
        )
        .filter(
            StudentResult.student_id
            == student.id,

            Exam.is_active.is_(True),
        )
        .order_by(
            Exam.start_date.desc(),
            Exam.id.desc(),
        )
        .first()
    )


    if latest_exam:

        result_rows = (
            db.query(StudentResult)
            .filter(
                StudentResult.student_id
                == student.id,

                StudentResult.exam_id
                == latest_exam.id,
            )
            .all()
        )


        total_marks = 0.0
        obtained_marks = 0.0


        for result in result_rows:

            total_marks += float(
                result.max_marks or 0
            )

            obtained_marks += float(
                result.obtained_marks or 0
            )


        result_percentage = 0.0


        if total_marks > 0:

            result_percentage = round(
                (
                    obtained_marks
                    / total_marks
                )
                * 100,
                2,
            )


        latest_result = {
            "exam_id":
                latest_exam.id,

            "exam_name":
                latest_exam.name,

            "total_marks":
                round(
                    total_marks,
                    2
                ),

            "obtained_marks":
                round(
                    obtained_marks,
                    2
                ),

            "percentage":
                result_percentage,

            "grade":
                calculate_result_grade(
                    result_percentage
                ),
        }


    # =====================================================
    # UPCOMING EXAM
    # =====================================================

    upcoming_exam = None


    if student.class_id:

        exam_schedule_row = (
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

                ExamSchedule.exam_date
                >= today,

                Exam.is_active.is_(True),
            )
            .order_by(
                ExamSchedule.exam_date.asc(),
                ExamSchedule.start_time.asc(),
            )
            .first()
        )


        if exam_schedule_row:

            (
                schedule,
                exam,
            ) = exam_schedule_row


            upcoming_exam = {
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
            }


    # =====================================================
    # FEE SUMMARY
    # =====================================================

    total_fee = 0.0
    total_paid = 0.0
    total_pending = 0.0
    overdue_amount = 0.0


    fee_query = (
        db.query(StudentFee)
        .filter(
            StudentFee.student_id
            == student.id,

            StudentFee.is_active.is_(
                True
            ),
        )
    )


    if academic_year:

        fee_query = (
            fee_query.filter(
                StudentFee.academic_year
                == academic_year
            )
        )


    fee_rows = fee_query.all()


    for fee in fee_rows:

        amount = float(
            fee.amount or 0
        )

        paid = float(
            fee.paid_amount or 0
        )

        pending = max(
            amount - paid,
            0,
        )


        total_fee += amount

        total_paid += paid

        total_pending += pending


        if (
            fee.due_date < today
            and pending > 0
        ):

            overdue_amount += (
                pending
            )


    fee_summary = {
        "total_fee":
            round(
                total_fee,
                2
            ),

        "total_paid":
            round(
                total_paid,
                2
            ),

        "total_pending":
            round(
                total_pending,
                2
            ),

        "overdue_amount":
            round(
                overdue_amount,
                2
            ),
    }


    # =====================================================
    # CIRCULARS
    # =====================================================

    circular_conditions = [
        Circular.audience
        == "ALL",

        Circular.audience
        == "PARENT",
    ]


    if student.class_id:

        circular_conditions.append(
            (
                Circular.audience
                == "CLASS"
            )
            &
            (
                Circular.class_id
                == student.class_id
            )
        )


    circular_rows = (
        db.query(Circular)
        .filter(
            Circular.is_active.is_(True),

            or_(
                *circular_conditions
            ),
        )
        .order_by(
            Circular.published_date.desc(),
            Circular.id.desc(),
        )
        .limit(3)
        .all()
    )


    latest_circulars = [
        {
            "id":
                circular.id,

            "title":
                circular.title,

            "category":
                circular.category,

            "published_date":
                circular.published_date,
        }
        for circular in circular_rows
    ]


    # =====================================================
    # UPCOMING SCHOOL EVENTS
    # =====================================================

    event_conditions = [
        SchoolEvent.audience
        == "ALL",

        SchoolEvent.audience
        == "PARENT",
    ]


    if student.class_id:

        event_conditions.append(
            (
                SchoolEvent.audience
                == "CLASS"
            )
            &
            (
                SchoolEvent.class_id
                == student.class_id
            )
        )


    event_rows = (
        db.query(SchoolEvent)
        .filter(
            SchoolEvent.is_active.is_(True),

            SchoolEvent.start_date
            >= today,

            or_(
                *event_conditions
            ),
        )
        .order_by(
            SchoolEvent.start_date.asc(),
            SchoolEvent.start_time.asc(),
        )
        .limit(3)
        .all()
    )


    upcoming_events = [
        {
            "id":
                event.id,

            "title":
                event.title,

            "event_type":
                event.event_type,

            "start_date":
                event.start_date,

            "location":
                event.location,
        }
        for event in event_rows
    ]


    # =====================================================
    # FINAL RESPONSE
    # =====================================================

    return {
        "parent_name":
            current_parent.name,

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

        "academic_year":
            academic_year,

        "attendance": {
            "total_marked_days":
                total_marked_days,

            "present_count":
                present_count,

            "absent_count":
                absent_count,

            "attendance_percentage":
                attendance_percentage,
        },

        "active_homework":
            active_homework,

        "overdue_homework":
            overdue_homework,

        "latest_result":
            latest_result,

        "upcoming_exam":
            upcoming_exam,

        "fees":
            fee_summary,

        "latest_circulars":
            latest_circulars,

        "upcoming_events":
            upcoming_events,
    }