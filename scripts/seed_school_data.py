from app.database import (
    Base,
    SessionLocal,
    engine,
)

from app.models.user import User
from app.models.school_class import SchoolClass
from app.models.student import Student
from app.models.teacher_class import TeacherClass


Base.metadata.create_all(
    bind=engine
)


db = SessionLocal()


try:
    # =====================================================
    # GET TEACHER
    # =====================================================

    teacher = (
        db.query(User)
        .filter(
            User.username == "TEACHER001"
        )
        .first()
    )

    if not teacher:
        raise Exception(
            "TEACHER001 not found. "
            "Run your user seed first."
        )

    # =====================================================
    # CREATE CLASS VIII - A
    # =====================================================

    school_class = (
        db.query(SchoolClass)
        .filter(
            SchoolClass.name == "VIII",
            SchoolClass.section == "A",
            SchoolClass.academic_year
            == "2026-2027",
        )
        .first()
    )

    if not school_class:
        school_class = SchoolClass(
            name="VIII",
            section="A",
            academic_year="2026-2027",
            is_active=True,
        )

        db.add(school_class)
        db.flush()

        print(
            "Created class: VIII - A"
        )

    # =====================================================
    # ASSIGN TEACHER
    # =====================================================

    teacher_assignment = (
        db.query(TeacherClass)
        .filter(
            TeacherClass.teacher_user_id
            == teacher.id,
            TeacherClass.class_id
            == school_class.id,
        )
        .first()
    )

    if not teacher_assignment:
        teacher_assignment = TeacherClass(
            teacher_user_id=teacher.id,
            class_id=school_class.id,
            subject="Mathematics",
        )

        db.add(teacher_assignment)

        print(
            "Assigned TEACHER001 "
            "to VIII - A"
        )

    # =====================================================
    # STUDENTS
    # =====================================================

    students = [
        {
            "admission_no": "ROS001",
            "roll_no": "01",
            "full_name": "Ashvik R",
            "gender": "Male",
        },
        {
            "admission_no": "ROS002",
            "roll_no": "02",
            "full_name": "Aaradhya S",
            "gender": "Female",
        },
        {
            "admission_no": "ROS003",
            "roll_no": "03",
            "full_name": "Aditya Kumar",
            "gender": "Male",
        },
        {
            "admission_no": "ROS004",
            "roll_no": "04",
            "full_name": "Harini K",
            "gender": "Female",
        },
        {
            "admission_no": "ROS005",
            "roll_no": "05",
            "full_name": "Joshua M",
            "gender": "Male",
        },
    ]

    for item in students:
        existing_student = (
            db.query(Student)
            .filter(
                Student.admission_no
                == item["admission_no"]
            )
            .first()
        )

        if existing_student:
            print(
                "Already exists:",
                item["admission_no"],
            )
            continue

        student = Student(
            admission_no=
                item["admission_no"],
            roll_no=item["roll_no"],
            full_name=item["full_name"],
            gender=item["gender"],
            class_id=school_class.id,
            is_active=True,
        )

        db.add(student)

        print(
            "Created student:",
            item["full_name"],
        )

    db.commit()

    print(
        "\nSchool seed completed."
    )

finally:
    db.close()