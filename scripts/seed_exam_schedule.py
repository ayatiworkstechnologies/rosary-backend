from datetime import (
    date,
    time,
)

from app.database import (
    Base,
    SessionLocal,
    engine,
)

from app.models.exam import Exam
from app.models.exam_schedule import ExamSchedule
from app.models.school_class import SchoolClass


Base.metadata.create_all(
    bind=engine
)


db = SessionLocal()


try:

    # =====================================================
    # GET VIII - A
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

    if not school_class:
        raise Exception(
            "VIII - A class not found."
        )


    # =====================================================
    # GET QUARTERLY EXAM
    # =====================================================

    exam = (
        db.query(Exam)
        .filter(
            Exam.name
            == "Quarterly Examination",

            Exam.academic_year
            == "2026-2027",
        )
        .first()
    )

    if not exam:
        raise Exception(
            "Quarterly Examination not found. "
            "Run python -m scripts.seed_exams first."
        )


    # =====================================================
    # SCHEDULE
    # =====================================================

    schedules = [
        {
            "subject":
                "Mathematics",

            "exam_date":
                date(
                    2026,
                    9,
                    14
                ),

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

            "room":
                "Room 201",

            "instructions":
                "Bring geometry box and hall ticket.",
        },

        {
            "subject":
                "English",

            "exam_date":
                date(
                    2026,
                    9,
                    16
                ),

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

            "room":
                "Room 201",

            "instructions":
                "Bring hall ticket.",
        },

        {
            "subject":
                "Science",

            "exam_date":
                date(
                    2026,
                    9,
                    18
                ),

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

            "room":
                "Room 201",

            "instructions":
                "Bring required stationery.",
        },

        {
            "subject":
                "Social Science",

            "exam_date":
                date(
                    2026,
                    9,
                    21
                ),

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

            "room":
                "Room 201",

            "instructions":
                "Bring hall ticket.",
        },

        {
            "subject":
                "Tamil",

            "exam_date":
                date(
                    2026,
                    9,
                    23
                ),

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

            "room":
                "Room 201",

            "instructions":
                "Bring hall ticket.",
        },
    ]


    # =====================================================
    # CREATE
    # =====================================================

    for item in schedules:

        existing = (
            db.query(
                ExamSchedule
            )
            .filter(
                ExamSchedule.exam_id
                == exam.id,

                ExamSchedule.class_id
                == school_class.id,

                ExamSchedule.subject
                == item["subject"],

                ExamSchedule.exam_date
                == item["exam_date"],
            )
            .first()
        )

        if existing:
            print(
                "Already exists:",
                item["subject"],
            )

            continue


        schedule = ExamSchedule(
            exam_id=
                exam.id,

            class_id=
                school_class.id,

            subject=
                item["subject"],

            exam_date=
                item["exam_date"],

            start_time=
                item["start_time"],

            end_time=
                item["end_time"],

            room=
                item["room"],

            instructions=
                item["instructions"],
        )

        db.add(
            schedule
        )

        print(
            "Created schedule:",
            item["subject"],
        )


    db.commit()

    print(
        "\nExam schedule seed completed."
    )


finally:
    db.close()