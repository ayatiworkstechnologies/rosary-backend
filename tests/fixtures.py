"""Synthetic test fixtures for the Rosary backend test suite.

Every record created here is fully synthetic (TEST_* / TESTADM* identifiers).
Nothing in this module reads from or writes to production data.
"""
import os
from datetime import date, time as _time, timedelta

import tests._env  # noqa: F401  (isolate DB before importing any app modules)

from app.core.security import hash_password
from app.database import Base, engine, SessionLocal

TEACHER_PW = "Teach@Test1!"
PARENT_PW = "Par@Test1!"
ADMIN_PW = "Admin@Test1!"
OTHER_PW = "Other@Test1!"

# Id map cached after the first seed in this process.
_ids = None


def _create_schema():
    """Create all tables on the configured (test) database."""
    import app.models  # noqa: F401  (registers all models)

    Base.metadata.create_all(bind=engine)


def seed(db):
    """Insert the synthetic dataset and return an id map."""
    from app.models.user import User
    from app.models.teacher_profile import TeacherProfile
    from app.models.parent_profile import ParentProfile
    from app.models.school_class import SchoolClass
    from app.models.student import Student
    from app.models.parent_student import ParentStudent
    from app.models.teacher_class import TeacherClass
    from app.models.exam import Exam
    from app.models.exam_schedule import ExamSchedule
    from app.models.student_fee import StudentFee
    from app.models.circular import Circular
    from app.models.school_event import SchoolEvent

    def user(name, username, role, pw):
        u = User(name=name, username=username, email=f"{username.lower()}@test.local",
                 password_hash=hash_password(pw), role=role, is_active=True)
        db.add(u)
        db.flush()
        return u

    admin = user("Test Admin", "ADM_TEST", "ADMIN", ADMIN_PW)
    teacher = user("Test Teacher", "TEACH_TEST", "TEACHER", TEACHER_PW)
    other_teacher = user("Other Teacher", "TEACH_OTHER", "TEACHER", OTHER_PW)
    parent = user("Test Parent", "PAR_TEST", "PARENT", PARENT_PW)
    other_parent = user("Other Parent", "PAR_OTHER", "PARENT", OTHER_PW)

    db.add_all([
        TeacherProfile(user_id=teacher.id, employee_id="TESTEMP1",
                       designation="Teacher", phone="9999000001"),
        TeacherProfile(user_id=other_teacher.id, employee_id="TESTEMP2",
                       designation="Teacher", phone="9999000002"),
        ParentProfile(user_id=parent.id, phone="9999000003"),
        ParentProfile(user_id=other_parent.id, phone="9999000004"),
    ])
    db.flush()

    class_a = SchoolClass(name="TEST", section="A", academic_year="2026-2027", is_active=True)
    class_b = SchoolClass(name="TEST", section="B", academic_year="2026-2027", is_active=True)
    db.add_all([class_a, class_b])
    db.flush()

    db.add_all([
        TeacherClass(teacher_user_id=teacher.id, class_id=class_a.id,
                     subject="Mathematics", is_class_teacher=True),
        TeacherClass(teacher_user_id=other_teacher.id, class_id=class_b.id,
                     subject="Science", is_class_teacher=False),
    ])

    s1 = Student(admission_no="TESTADM1", roll_no="1", full_name="Test Student One",
                 class_id=class_a.id, gender="M", is_active=True)
    s2 = Student(admission_no="TESTADM2", roll_no="2", full_name="Test Student Two",
                 class_id=class_a.id, gender="F", is_active=True)
    s3 = Student(admission_no="TESTADM3", roll_no="1", full_name="Test Student Three",
                 class_id=class_b.id, gender="F", is_active=True)
    db.add_all([s1, s2, s3])
    db.flush()

    db.add_all([
        ParentStudent(parent_user_id=parent.id, student_id=s1.id, relationship="Father"),
        ParentStudent(parent_user_id=parent.id, student_id=s2.id, relationship="Father"),
        ParentStudent(parent_user_id=other_parent.id, student_id=s3.id, relationship="Mother"),
    ])

    today = date.today()
    # The exam window must cover dates the E2E/UI tests can schedule;
    # a fixed past-dated window would expire as calendar days pass.
    exam = Exam(name="TESTEXAM", academic_year="2026-2027",
                start_date=today - timedelta(days=7),
                end_date=today + timedelta(days=30),
                is_active=True, results_published=False)
    exam2 = Exam(name="TESTEXAM2", academic_year="2026-2027",
                 start_date=today - timedelta(days=7),
                 end_date=today + timedelta(days=30),
                 is_active=True, results_published=False)
    db.add_all([exam, exam2])
    db.flush()

    db.add_all([
        StudentFee(student_id=s1.id, academic_year="2026-2027",
                   fee_title="Term 1", fee_type="TUITION",
                   amount=1000, paid_amount=1000, due_date=today - timedelta(days=30),
                   paid_date=today - timedelta(days=20), receipt_no="RCP-TEST-1"),
        StudentFee(student_id=s1.id, academic_year="2026-2027",
                   fee_title="Term 2", fee_type="TUITION",
                   amount=500, paid_amount=0, due_date=today + timedelta(days=30)),
    ])

    db.add(Circular(title="Test Circular", category="General",
                    description="Synthetic circular", audience="ALL",
                    published_date=today, is_active=True))
    db.add(SchoolEvent(title="Test Event", event_type="EVENT",
                       description="Synthetic event", audience="ALL",
                       start_date=today, end_date=today, is_active=True))

    db.commit()

    return {
        "admin": admin.id, "teacher": teacher.id, "other_teacher": other_teacher.id,
        "parent": parent.id, "other_parent": other_parent.id,
        "class_a": class_a.id, "class_b": class_b.id,
        "s1": s1.id, "s2": s2.id, "s3": s3.id, "exam": exam.id,
        "exam2": exam2.id,
    }


def init_test_db():
    """Create schema + synthetic seed data. Returns the id map.

    Safe to call from multiple suites in one process: the in-memory
    database is shared, so seeding happens exactly once and every
    suite reuses the same synthetic ids.
    """
    global _ids
    if _ids is not None:
        return _ids

    _create_schema()
    db = SessionLocal()
    try:
        _ids = seed(db)
    finally:
        db.close()
    return _ids
