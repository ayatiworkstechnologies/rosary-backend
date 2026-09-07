from datetime import date

from app.database import (
    Base,
    SessionLocal,
    engine,
)

from app.models.exam import Exam


Base.metadata.create_all(
    bind=engine
)


db = SessionLocal()


try:
    exams = [
        {
            "name":
                "Unit Test 1",

            "academic_year":
                "2026-2027",

            "start_date":
                date(2026, 7, 15),

            "end_date":
                date(2026, 7, 18),
        },
        {
            "name":
                "Quarterly Examination",

            "academic_year":
                "2026-2027",

            "start_date":
                date(2026, 9, 14),

            "end_date":
                date(2026, 9, 25),
        },
        {
            "name":
                "Half-Yearly Examination",

            "academic_year":
                "2026-2027",

            "start_date":
                date(2026, 12, 7),

            "end_date":
                date(2026, 12, 18),
        },
    ]

    for item in exams:
        existing = (
            db.query(Exam)
            .filter(
                Exam.name
                == item["name"],

                Exam.academic_year
                == item[
                    "academic_year"
                ],
            )
            .first()
        )

        if existing:
            print(
                "Already exists:",
                item["name"],
            )

            continue

        exam = Exam(
            name=
                item["name"],

            academic_year=
                item["academic_year"],

            start_date=
                item["start_date"],

            end_date=
                item["end_date"],

            is_active=True,
        )

        db.add(exam)

        print(
            "Created:",
            item["name"],
        )

    db.commit()

    print(
        "\nExam seed completed."
    )

finally:
    db.close()