from app.database import (
    Base,
    SessionLocal,
    engine,
)

import app.models

from app.models.user import User
from app.models.student import Student
from app.models.parent_student import ParentStudent


Base.metadata.create_all(
    bind=engine
)


db = SessionLocal()


try:

    # =====================================================
    # FIND PARENT
    # =====================================================

    parent = (
        db.query(User)
        .filter(
            User.username
            == "PARENT001"
        )
        .first()
    )

    if not parent:
        raise Exception(
            "PARENT001 not found. "
            "Run seed_users first."
        )


    # =====================================================
    # FIND CHILD
    # =====================================================

    student = (
        db.query(Student)
        .filter(
            Student.admission_no
            == "ROS001"
        )
        .first()
    )

    if not student:
        raise Exception(
            "ROS001 student not found. "
            "Run seed_school_data first."
        )


    # =====================================================
    # CHECK EXISTING LINK
    # =====================================================

    existing = (
        db.query(ParentStudent)
        .filter(
            ParentStudent.parent_user_id
            == parent.id,

            ParentStudent.student_id
            == student.id,
        )
        .first()
    )


    if existing:

        print(
            "Parent-child relationship already exists."
        )

    else:

        relation = ParentStudent(
            parent_user_id=
                parent.id,

            student_id=
                student.id,

            relationship=
                "Father",
        )

        db.add(
            relation
        )

        db.commit()

        print(
            "Linked PARENT001 -> ROS001"
        )


    print(
        "\nParent children seed completed."
    )


except Exception as error:

    db.rollback()

    print(
        "\nParent children seed failed:"
    )

    print(error)

    raise


finally:

    db.close()