from datetime import date
import app.models
from app.database import (
    Base,
    SessionLocal,
    engine,
)

# =========================================================
# IMPORTANT:
# Import every model referenced by ForeignKey
# =========================================================

from app.models.user import User
from app.models.school_class import SchoolClass
from app.models.circular import Circular


# =========================================================
# CREATE TABLES IF THEY DO NOT EXIST
# =========================================================

Base.metadata.create_all(
    bind=engine
)


db = SessionLocal()


try:

    # =====================================================
    # FIND VIII - A
    # =====================================================

    school_class = (
        db.query(SchoolClass)
        .filter(
            SchoolClass.name == "VIII",
            SchoolClass.section == "A",
        )
        .first()
    )


    if not school_class:
        print(
            "Warning: VIII - A class not found."
        )


    # =====================================================
    # SAMPLE CIRCULARS
    # =====================================================

    circulars = [
        {
            "title":
                "Quarterly Examination Instructions",

            "category":
                "Academic",

            "description":
                (
                    "Quarterly examinations will begin "
                    "from 14 September 2026. Students "
                    "must bring their hall ticket and "
                    "required stationery."
                ),

            "published_date":
                date(
                    2026,
                    9,
                    8
                ),

            "audience":
                "ALL",

            "class_id":
                None,

            "attachment_url":
                None,
        },

        {
            "title":
                "Staff Coordination Meeting",

            "category":
                "Meeting",

            "description":
                (
                    "All teaching staff are requested "
                    "to attend the coordination meeting "
                    "in the conference hall."
                ),

            "published_date":
                date(
                    2026,
                    9,
                    7
                ),

            "audience":
                "TEACHER",

            "class_id":
                None,

            "attachment_url":
                None,
        },

        {
            "title":
                "VIII-A Mathematics Revision Session",

            "category":
                "Academic",

            "description":
                (
                    "A mathematics revision session "
                    "has been scheduled for students "
                    "of VIII-A before the quarterly "
                    "examination."
                ),

            "published_date":
                date(
                    2026,
                    9,
                    6
                ),

            "audience":
                "CLASS",

            "class_id":
                (
                    school_class.id
                    if school_class
                    else None
                ),

            "attachment_url":
                None,
        },

        {
            "title":
                "School Holiday Notice",

            "category":
                "Holiday",

            "description":
                (
                    "The school will remain closed "
                    "on the announced public holiday."
                ),

            "published_date":
                date(
                    2026,
                    9,
                    5
                ),

            "audience":
                "ALL",

            "class_id":
                None,

            "attachment_url":
                None,
        },
    ]


    # =====================================================
    # CREATE CIRCULARS
    # =====================================================

    for item in circulars:

        existing = (
            db.query(Circular)
            .filter(
                Circular.title
                == item["title"],

                Circular.published_date
                == item["published_date"],
            )
            .first()
        )


        if existing:

            print(
                "Already exists:",
                item["title"],
            )

            continue


        circular = Circular(
            title=
                item["title"],

            category=
                item["category"],

            description=
                item["description"],

            published_date=
                item["published_date"],

            audience=
                item["audience"],

            class_id=
                item["class_id"],

            attachment_url=
                item["attachment_url"],

            created_by=
                None,

            is_active=
                True,
        )


        db.add(
            circular
        )


        print(
            "Created:",
            item["title"],
        )


    # =====================================================
    # COMMIT
    # =====================================================

    db.commit()


    print(
        "\nCircular seed completed successfully."
    )


except Exception as error:

    db.rollback()

    print(
        "\nCircular seed failed:"
    )

    print(
        error
    )

    raise


finally:

    db.close()


{
    "title":
        "Parent Teacher Meeting Notice",

    "category":
        "Meeting",

    "description":
        (
            "Parents are requested to attend "
            "the Parent Teacher Meeting to "
            "discuss student academic progress."
        ),

    "published_date":
        date(
            2026,
            9,
            9
        ),

    "audience":
        "PARENT",

    "class_id":
        None,

    "attachment_url":
        None,
},