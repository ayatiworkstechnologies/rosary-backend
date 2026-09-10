from app.database import (
    Base,
    SessionLocal,
    engine,
)

import app.models

from app.models.user import User
from app.models.parent_profile import (
    ParentProfile,
)


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
    # CHECK PROFILE
    # =====================================================

    existing = (
        db.query(ParentProfile)
        .filter(
            ParentProfile.user_id
            == parent.id
        )
        .first()
    )


    if existing:

        print(
            "Parent profile already exists."
        )

    else:

        profile = ParentProfile(
            user_id=
                parent.id,

            phone=
                "9876543210",

            alternate_phone=
                "9876501234",

            occupation=
                "Business",

            address=
                "12, Main Road",

            city=
                "Chennai",

            state=
                "Tamil Nadu",

            pincode=
                "600001",

            profile_image_url=
                None,
        )


        db.add(
            profile
        )

        db.commit()


        print(
            "Parent profile created successfully."
        )


except Exception as error:

    db.rollback()

    print(
        "Parent profile seed failed:"
    )

    print(error)

    raise


finally:

    db.close()