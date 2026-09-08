from datetime import (
    date,
    time,
)

from app.database import (
    Base,
    SessionLocal,
    engine,
)

import app.models

from app.models.school_class import SchoolClass
from app.models.school_event import SchoolEvent


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
            SchoolClass.name
            == "VIII",

            SchoolClass.section
            == "A",
        )
        .first()
    )


    # =====================================================
    # SAMPLE EVENTS
    # =====================================================

    events = [
        {
            "title":
                "Quarterly Examination Begins",

            "event_type":
                "EXAM",

            "description":
                (
                    "Quarterly examinations begin "
                    "for students."
                ),

            "start_date":
                date(
                    2026,
                    9,
                    14
                ),

            "end_date":
                date(
                    2026,
                    9,
                    25
                ),

            "start_time":
                None,

            "end_time":
                None,

            "location":
                None,

            "audience":
                "ALL",

            "class_id":
                None,
        },

        {
            "title":
                "Teachers Coordination Meeting",

            "event_type":
                "MEETING",

            "description":
                (
                    "Monthly coordination meeting "
                    "for teaching staff."
                ),

            "start_date":
                date(
                    2026,
                    9,
                    12
                ),

            "end_date":
                None,

            "start_time":
                time(
                    15,
                    30
                ),

            "end_time":
                time(
                    16,
                    30
                ),

            "location":
                "Conference Hall",

            "audience":
                "TEACHER",

            "class_id":
                None,
        },

        {
            "title":
                "VIII-A Revision Day",

            "event_type":
                "ACADEMIC",

            "description":
                (
                    "Special revision session "
                    "for VIII-A students."
                ),

            "start_date":
                date(
                    2026,
                    9,
                    11
                ),

            "end_date":
                None,

            "start_time":
                time(
                    10,
                    0
                ),

            "end_time":
                time(
                    12,
                    0
                ),

            "location":
                "VIII-A Classroom",

            "audience":
                "CLASS",

            "class_id":
                (
                    school_class.id
                    if school_class
                    else None
                ),
        },

        {
            "title":
                "School Holiday",

            "event_type":
                "HOLIDAY",

            "description":
                "School holiday.",

            "start_date":
                date(
                    2026,
                    9,
                    17
                ),

            "end_date":
                None,

            "start_time":
                None,

            "end_time":
                None,

            "location":
                None,

            "audience":
                "ALL",

            "class_id":
                None,
        },

        {
            "title":
                "Teachers Day Celebration",

            "event_type":
                "EVENT",

            "description":
                (
                    "School Teachers Day "
                    "celebration programme."
                ),

            "start_date":
                date(
                    2026,
                    9,
                    5
                ),

            "end_date":
                None,

            "start_time":
                time(
                    9,
                    30
                ),

            "end_time":
                time(
                    12,
                    30
                ),

            "location":
                "School Auditorium",

            "audience":
                "ALL",

            "class_id":
                None,
        },
    ]


    # =====================================================
    # CREATE EVENTS
    # =====================================================

    for item in events:

        existing = (
            db.query(SchoolEvent)
            .filter(
                SchoolEvent.title
                == item["title"],

                SchoolEvent.start_date
                == item["start_date"],
            )
            .first()
        )

        if existing:

            print(
                "Already exists:",
                item["title"],
            )

            continue


        event = SchoolEvent(
            title=
                item["title"],

            event_type=
                item["event_type"],

            description=
                item["description"],

            start_date=
                item["start_date"],

            end_date=
                item["end_date"],

            start_time=
                item["start_time"],

            end_time=
                item["end_time"],

            location=
                item["location"],

            audience=
                item["audience"],

            class_id=
                item["class_id"],

            created_by=
                None,

            is_active=
                True,
        )


        db.add(
            event
        )


        print(
            "Created:",
            item["title"],
        )


    db.commit()


    print(
        "\nSchool calendar seed completed."
    )


except Exception as error:

    db.rollback()

    print(
        "\nSchool calendar seed failed:"
    )

    print(error)

    raise


finally:

    db.close()