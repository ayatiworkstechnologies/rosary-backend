from datetime import date

from app.database import (
    Base,
    SessionLocal,
    engine,
)

import app.models

from app.models.download_form import (
    DownloadForm,
)

from app.models.school_class import (
    SchoolClass,
)


Base.metadata.create_all(
    bind=engine
)


db = SessionLocal()


try:

    # =====================================================
    # CLASS VIII-A
    # =====================================================

    school_class = (
        db.query(SchoolClass)
        .filter(
            SchoolClass.name
            == "VIII",

            SchoolClass.section
            == "A",
        )
        .first()
    )


    # =====================================================
    # SAMPLE FORMS
    # =====================================================

    forms = [
        {
            "title":
                "Leave Application Form",

            "category":
                "APPLICATION",

            "description":
                (
                    "Download and complete "
                    "this form when applying "
                    "for student leave."
                ),

            "audience":
                "ALL",

            "class_id":
                None,

            "file_name":
                "leave-application.pdf",

            "file_url":
                "/forms/leave-application.pdf",

            "published_date":
                date(
                    2026,
                    9,
                    10
                ),
        },

        {
            "title":
                "Bonafide Certificate Request",

            "category":
                "CERTIFICATE",

            "description":
                (
                    "Request form for obtaining "
                    "a bonafide certificate "
                    "from the school."
                ),

            "audience":
                "PARENT",

            "class_id":
                None,

            "file_name":
                "bonafide-request.pdf",

            "file_url":
                "/forms/bonafide-request.pdf",

            "published_date":
                date(
                    2026,
                    9,
                    10
                ),
        },

        {
            "title":
                "Transfer Certificate Request",

            "category":
                "CERTIFICATE",

            "description":
                (
                    "Application form for "
                    "requesting a Transfer "
                    "Certificate."
                ),

            "audience":
                "PARENT",

            "class_id":
                None,

            "file_name":
                "tc-request.pdf",

            "file_url":
                "/forms/tc-request.pdf",

            "published_date":
                date(
                    2026,
                    9,
                    10
                ),
        },

        {
            "title":
                "VIII-A Transport Update Form",

            "category":
                "TRANSPORT",

            "description":
                (
                    "Transport information "
                    "update form for VIII-A."
                ),

            "audience":
                "CLASS",

            "class_id":
                (
                    school_class.id
                    if school_class
                    else None
                ),

            "file_name":
                "transport-form.pdf",

            "file_url":
                "/forms/transport-form.pdf",

            "published_date":
                date(
                    2026,
                    9,
                    10
                ),
        },
    ]


    # =====================================================
    # CREATE
    # =====================================================

    for item in forms:

        existing = (
            db.query(DownloadForm)
            .filter(
                DownloadForm.title
                == item["title"]
            )
            .first()
        )

        if existing:

            print(
                "Already exists:",
                item["title"],
            )

            continue


        form = DownloadForm(
            title=
                item["title"],

            category=
                item["category"],

            description=
                item["description"],

            audience=
                item["audience"],

            class_id=
                item["class_id"],

            file_name=
                item["file_name"],

            file_url=
                item["file_url"],

            published_date=
                item[
                    "published_date"
                ],

            is_active=
                True,
        )


        db.add(
            form
        )


        print(
            "Created:",
            item["title"],
        )


    db.commit()


    print(
        "\nDownload forms seed completed."
    )


except Exception as error:

    db.rollback()

    print(
        "\nDownload forms seed failed:"
    )

    print(error)

    raise


finally:

    db.close()