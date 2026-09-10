from app.database import (
    Base,
    SessionLocal,
    engine,
)

import app.models

from app.models.user import User
from app.models.student import Student
from app.models.parent_student import (
    ParentStudent,
)


# =========================================================
# CREATE TABLES
# =========================================================

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


    print(
        f"Parent found: {parent.name}"
    )


    # =====================================================
    # CHILDREN TO LINK
    # =====================================================

    children_to_link = [
        {
            "admission_no":
                "ROS001",

            "relationship":
                "Father",
        },

        {
            "admission_no":
                "ROS002",

            "relationship":
                "Father",
        },
    ]


    # =====================================================
    # LOOP CHILDREN
    # =====================================================

    for child_data in children_to_link:

        admission_no = (
            child_data[
                "admission_no"
            ]
        )

        relationship = (
            child_data[
                "relationship"
            ]
        )


        # -------------------------------------------------
        # FIND STUDENT
        # -------------------------------------------------

        student = (
            db.query(Student)
            .filter(
                Student.admission_no
                == admission_no
            )
            .first()
        )


        if not student:

            print(
                f"Student not found: "
                f"{admission_no}"
            )

            continue


        # -------------------------------------------------
        # CHECK EXISTING RELATION
        # -------------------------------------------------

        existing = (
            db.query(
                ParentStudent
            )
            .filter(
                ParentStudent.parent_user_id
                == parent.id,

                ParentStudent.student_id
                == student.id,
            )
            .first()
        )


        if existing:

            # Optional:
            # keep relationship updated

            existing.relationship = (
                relationship
            )


            print(
                f"Already linked: "
                f"{parent.username} "
                f"→ {student.full_name}"
            )

            continue


        # -------------------------------------------------
        # CREATE RELATION
        # -------------------------------------------------

        relation = ParentStudent(
            parent_user_id=
                parent.id,

            student_id=
                student.id,

            relationship=
                relationship,
        )


        db.add(
            relation
        )


        print(
            f"Linked: "
            f"{parent.username} "
            f"→ {student.full_name}"
        )


    # =====================================================
    # SAVE ALL
    # =====================================================

    db.commit()


    print(
        "\nParent children seed completed."
    )


    # =====================================================
    # SHOW CURRENT CHILDREN
    # =====================================================

    relations = (
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
            == parent.id
        )
        .all()
    )


    print(
        "\nChildren linked to PARENT001:"
    )


    for (
        relation,
        student,
    ) in relations:

        print(
            f"- {student.full_name} "
            f"({student.admission_no}) "
            f"- {relation.relationship}"
        )


except Exception as error:

    db.rollback()


    print(
        "\nParent children seed failed:"
    )

    print(
        error
    )


    raise


finally:

    db.close()