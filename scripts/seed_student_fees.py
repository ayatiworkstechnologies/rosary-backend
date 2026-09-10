from datetime import date

from app.database import (
    Base,
    SessionLocal,
    engine,
)

import app.models

from app.models.student import Student
from app.models.student_fee import StudentFee


Base.metadata.create_all(
    bind=engine
)


db = SessionLocal()


try:

    # =====================================================
    # STUDENT
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
    # SAMPLE FEES
    # =====================================================

    fees = [
        {
            "fee_title":
                "Term 1 Tuition Fee",

            "fee_type":
                "TUITION",

            "amount":
                15000,

            "paid_amount":
                15000,

            "due_date":
                date(
                    2026,
                    6,
                    15
                ),

            "paid_date":
                date(
                    2026,
                    6,
                    10
                ),

            "receipt_no":
                "ROS-REC-001",

            "payment_mode":
                "ONLINE",

            "remarks":
                "Paid successfully",
        },

        {
            "fee_title":
                "Term 2 Tuition Fee",

            "fee_type":
                "TUITION",

            "amount":
                15000,

            "paid_amount":
                5000,

            "due_date":
                date(
                    2026,
                    9,
                    15
                ),

            "paid_date":
                date(
                    2026,
                    9,
                    5
                ),

            "receipt_no":
                "ROS-REC-002",

            "payment_mode":
                "ONLINE",

            "remarks":
                "Partial payment",
        },

        {
            "fee_title":
                "Term 3 Tuition Fee",

            "fee_type":
                "TUITION",

            "amount":
                15000,

            "paid_amount":
                0,

            "due_date":
                date(
                    2027,
                    1,
                    15
                ),

            "paid_date":
                None,

            "receipt_no":
                None,

            "payment_mode":
                None,

            "remarks":
                None,
        },

        {
            "fee_title":
                "Annual Activity Fee",

            "fee_type":
                "ACTIVITY",

            "amount":
                3000,

            "paid_amount":
                3000,

            "due_date":
                date(
                    2026,
                    7,
                    1
                ),

            "paid_date":
                date(
                    2026,
                    6,
                    25
                ),

            "receipt_no":
                "ROS-REC-003",

            "payment_mode":
                "CASH",

            "remarks":
                "Paid",
        },
    ]


    # =====================================================
    # CREATE
    # =====================================================

    for item in fees:

        existing = (
            db.query(StudentFee)
            .filter(
                StudentFee.student_id
                == student.id,

                StudentFee.academic_year
                == "2026-2027",

                StudentFee.fee_title
                == item[
                    "fee_title"
                ],
            )
            .first()
        )


        if existing:

            print(
                "Already exists:",
                item[
                    "fee_title"
                ],
            )

            continue


        fee = StudentFee(
            student_id=
                student.id,

            academic_year=
                "2026-2027",

            fee_title=
                item[
                    "fee_title"
                ],

            fee_type=
                item[
                    "fee_type"
                ],

            amount=
                item[
                    "amount"
                ],

            paid_amount=
                item[
                    "paid_amount"
                ],

            due_date=
                item[
                    "due_date"
                ],

            paid_date=
                item[
                    "paid_date"
                ],

            receipt_no=
                item[
                    "receipt_no"
                ],

            payment_mode=
                item[
                    "payment_mode"
                ],

            remarks=
                item[
                    "remarks"
                ],

            is_active=True,
        )


        db.add(
            fee
        )


        print(
            "Created:",
            item[
                "fee_title"
            ],
        )


    db.commit()


    print(
        "\nStudent fee seed completed."
    )


except Exception as error:

    db.rollback()

    print(
        "\nStudent fee seed failed:"
    )

    print(error)

    raise


finally:

    db.close()