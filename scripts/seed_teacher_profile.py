from datetime import date

from app.database import (
    Base,
    SessionLocal,
    engine,
)

import app.models

from app.models.user import User
from app.models.teacher_profile import (
    TeacherProfile,
)


Base.metadata.create_all(
    bind=engine
)


db = SessionLocal()


try:

    # =====================================================
    # FIND TEACHER USER
    # =====================================================

    teacher = (
        db.query(User)
        .filter(
            User.username
            == "TEACHER001"
        )
        .first()
    )


    if not teacher:
        raise Exception(
            "TEACHER001 not found. "
            "Run seed_users first."
        )


    # =====================================================
    # CHECK PROFILE
    # =====================================================

    existing = (
        db.query(TeacherProfile)
        .filter(
            TeacherProfile.user_id
            == teacher.id
        )
        .first()
    )


    if existing:

        print(
            "Teacher profile already exists."
        )

    else:

        profile = TeacherProfile(
            user_id=
                teacher.id,

            employee_id=
                "ROS-T-001",

            phone=
                "9876543210",

            designation=
                "Mathematics Teacher",

            department=
                "Mathematics",

            qualification=
                "M.Sc Mathematics, B.Ed",

            experience_years=
                6,

            joining_date=
                date(
                    2021,
                    6,
                    1
                ),

            profile_image_url=
                None,
        )


        db.add(
            profile
        )


        db.commit()


        print(
            "Teacher profile created successfully."
        )


except Exception as error:

    db.rollback()

    print(
        "Teacher profile seed failed:"
    )

    print(error)

    raise


finally:

    db.close()