# =========================================================
# SQLALCHEMY MODELS REGISTRY
# =========================================================
#
# Import every SQLAlchemy model here.
#
# Why?
# ----
# SQLAlchemy needs all models loaded into Base.metadata
# before it can correctly resolve:
#
# ForeignKey("users.id")
# ForeignKey("school_classes.id")
# ForeignKey("exams.id")
# etc.
#
# Then, in seed files or startup code, you can simply use:
#
# import app.models
#
# instead of manually importing every model one by one.
# =========================================================

from app.database import (
    Base,
    SessionLocal,
    engine,
)

import app.models


Base.metadata.create_all(
    bind=engine
)
from app.models.user import User

from app.models.school_class import SchoolClass

from app.models.student import Student

from app.models.teacher_class import TeacherClass

from app.models.attendance import Attendance

from app.models.homework import Homework

from app.models.exam import Exam

from app.models.student_result import StudentResult

from app.models.exam_schedule import ExamSchedule

from app.models.circular import Circular

from app.models.school_event import SchoolEvent

from app.models.teacher_profile import TeacherProfile

from app.models.parent_student import ParentStudent
from app.models.student_fee import StudentFee
from app.models.download_form import DownloadForm
from app.models.parent_profile import ParentProfile
# =========================================================
# OPTIONAL EXPORT LIST
# =========================================================

__all__ = [
    "User",
    "SchoolClass",
    "Student",
    "TeacherClass",
    "Attendance",
    "Homework",
    "Exam",
    "StudentResult",
    "ExamSchedule",
    "Circular",
    "SchoolEvent",
    "TeacherProfile",
    "ParentStudent",
    "StudentFee",
    "DownloadForm", 
    "ParentProfile",
]