from decimal import Decimal

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db

from app.schemas.admin_fee import (
    AdminFeeCreate,
    AdminFeeUpdate,
    AdminFeePaymentUpdate,
    AdminFeeStatusUpdate,
)


router = APIRouter(
    prefix="/admin/fees",
    tags=["Admin Fees"],
)


# ============================================================
# HELPERS
# ============================================================

def get_payment_status(
    amount,
    paid_amount,
):
    amount = Decimal(str(amount))
    paid_amount = Decimal(
        str(paid_amount)
    )

    if paid_amount >= amount:
        return "PAID"

    if paid_amount > Decimal("0"):
        return "PARTIAL"

    return "UNPAID"


def validate_student(
    student_id: int,
    db: Session,
):
    student = db.execute(
        text(
            """
            SELECT
                s.id,
                s.admission_no,
                s.roll_no,
                s.full_name,
                s.class_id,
                s.is_active,

                sc.name AS class_name,
                sc.section AS class_section,
                sc.academic_year
                    AS class_academic_year

            FROM students AS s

            LEFT JOIN school_classes AS sc
                ON sc.id = s.class_id

            WHERE s.id = :student_id

            LIMIT 1
            """
        ),
        {
            "student_id": student_id,
        },
    ).mappings().first()

    if not student:
        raise HTTPException(
            status_code=404,
            detail="Student not found",
        )

    if not bool(
        student["is_active"]
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Cannot assign fees "
                "to an inactive student"
            ),
        )

    return student


def get_fee_or_404(
    fee_id: int,
    db: Session,
):
    fee = db.execute(
        text(
            """
            SELECT
                id,
                student_id,
                amount,
                paid_amount,
                is_active

            FROM student_fees

            WHERE id = :fee_id

            LIMIT 1
            """
        ),
        {
            "fee_id": fee_id,
        },
    ).mappings().first()

    if not fee:
        raise HTTPException(
            status_code=404,
            detail="Fee record not found",
        )

    return fee


# ============================================================
# GET ALL FEES
# ============================================================

@router.get("")
def get_admin_fees(
    search: str | None = None,

    student_id: int | None = None,

    class_id: int | None = None,

    academic_year: str | None = None,

    fee_type: str | None = None,

    payment_status: str | None = None,

    is_active: bool | None = Query(
        default=None
    ),

    db: Session = Depends(get_db),
):
    try:
        sql = """
            SELECT
                sf.id,
                sf.student_id,
                sf.academic_year,
                sf.fee_title,
                sf.fee_type,
                sf.amount,
                sf.paid_amount,
                sf.due_date,
                sf.paid_date,
                sf.receipt_no,
                sf.payment_mode,
                sf.remarks,
                sf.is_active,
                sf.created_at,
                sf.updated_at,

                s.admission_no,
                s.roll_no,
                s.full_name,
                s.class_id,

                sc.name AS class_name,
                sc.section AS class_section,
                sc.academic_year
                    AS class_academic_year

            FROM student_fees AS sf

            INNER JOIN students AS s
                ON s.id = sf.student_id

            LEFT JOIN school_classes AS sc
                ON sc.id = s.class_id

            WHERE 1 = 1
        """

        params = {}

        # --------------------------------------------
        # SEARCH
        # --------------------------------------------

        if search:
            sql += """
                AND (
                    sf.fee_title LIKE :search

                    OR sf.fee_type LIKE :search

                    OR sf.academic_year LIKE :search

                    OR sf.receipt_no LIKE :search

                    OR s.full_name LIKE :search

                    OR s.admission_no LIKE :search
                )
            """

            params["search"] = (
                f"%{search.strip()}%"
            )

        # --------------------------------------------
        # STUDENT
        # --------------------------------------------

        if student_id is not None:
            sql += """
                AND sf.student_id =
                    :student_id
            """

            params["student_id"] = (
                student_id
            )

        # --------------------------------------------
        # CLASS
        # --------------------------------------------

        if class_id is not None:
            sql += """
                AND s.class_id =
                    :class_id
            """

            params["class_id"] = (
                class_id
            )

        # --------------------------------------------
        # ACADEMIC YEAR
        # --------------------------------------------

        if academic_year:
            sql += """
                AND sf.academic_year =
                    :academic_year
            """

            params["academic_year"] = (
                academic_year.strip()
            )

        # --------------------------------------------
        # FEE TYPE
        # --------------------------------------------

        if fee_type:
            sql += """
                AND sf.fee_type =
                    :fee_type
            """

            params["fee_type"] = (
                fee_type.strip()
            )

        # --------------------------------------------
        # PAYMENT STATUS
        # --------------------------------------------

        if payment_status:
            normalized_status = (
                payment_status
                .strip()
                .upper()
            )

            if normalized_status == "PAID":
                sql += """
                    AND sf.paid_amount
                        >= sf.amount
                """

            elif (
                normalized_status
                == "PARTIAL"
            ):
                sql += """
                    AND sf.paid_amount > 0
                    AND sf.paid_amount
                        < sf.amount
                """

            elif (
                normalized_status
                == "UNPAID"
            ):
                sql += """
                    AND sf.paid_amount = 0
                """

            else:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "payment_status must "
                        "be PAID, PARTIAL or "
                        "UNPAID"
                    ),
                )

        # --------------------------------------------
        # ACTIVE
        # --------------------------------------------

        if is_active is not None:
            sql += """
                AND sf.is_active =
                    :is_active
            """

            params["is_active"] = (
                is_active
            )

        sql += """
            ORDER BY
                sf.due_date DESC,
                sf.id DESC
        """

        rows = db.execute(
            text(sql),
            params,
        ).mappings().all()

        fees = []

        for row in rows:
            amount = Decimal(
                str(row["amount"])
            )

            paid_amount = Decimal(
                str(row["paid_amount"])
            )

            balance_amount = (
                amount - paid_amount
            )

            fees.append(
                {
                    "id":
                        row["id"],

                    "student_id":
                        row["student_id"],

                    "student": {
                        "id":
                            row[
                                "student_id"
                            ],

                        "admission_no":
                            row[
                                "admission_no"
                            ],

                        "roll_no":
                            row["roll_no"],

                        "full_name":
                            row["full_name"],

                        "class_id":
                            row["class_id"],

                        "class": (
                            {
                                "id":
                                    row[
                                        "class_id"
                                    ],

                                "name":
                                    row[
                                        "class_name"
                                    ],

                                "section":
                                    row[
                                        "class_section"
                                    ],

                                "academic_year":
                                    row[
                                        "class_academic_year"
                                    ],
                            }
                            if row["class_id"]
                            else None
                        ),
                    },

                    "academic_year":
                        row[
                            "academic_year"
                        ],

                    "fee_title":
                        row["fee_title"],

                    "fee_type":
                        row["fee_type"],

                    "amount":
                        amount,

                    "paid_amount":
                        paid_amount,

                    "balance_amount":
                        balance_amount,

                    "payment_status":
                        get_payment_status(
                            amount,
                            paid_amount,
                        ),

                    "due_date":
                        row["due_date"],

                    "paid_date":
                        row["paid_date"],

                    "receipt_no":
                        row["receipt_no"],

                    "payment_mode":
                        row[
                            "payment_mode"
                        ],

                    "remarks":
                        row["remarks"],

                    "is_active":
                        bool(
                            row["is_active"]
                        ),

                    "created_at":
                        row["created_at"],

                    "updated_at":
                        row["updated_at"],
                }
            )

        return {
            "success": True,
            "total": len(fees),
            "data": fees,
        }

    except HTTPException:
        raise

    except Exception as e:
        print(
            "Admin fee list error:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to load fees",
        )


# ============================================================
# GET SINGLE FEE
# ============================================================

@router.get("/{fee_id}")
def get_admin_fee(
    fee_id: int,
    db: Session = Depends(get_db),
):
    try:
        row = db.execute(
            text(
                """
                SELECT
                    sf.id,
                    sf.student_id,
                    sf.academic_year,
                    sf.fee_title,
                    sf.fee_type,
                    sf.amount,
                    sf.paid_amount,
                    sf.due_date,
                    sf.paid_date,
                    sf.receipt_no,
                    sf.payment_mode,
                    sf.remarks,
                    sf.is_active,
                    sf.created_at,
                    sf.updated_at,

                    s.admission_no,
                    s.roll_no,
                    s.full_name,
                    s.class_id,

                    sc.name AS class_name,
                    sc.section
                        AS class_section,
                    sc.academic_year
                        AS class_academic_year

                FROM student_fees AS sf

                INNER JOIN students AS s
                    ON s.id =
                        sf.student_id

                LEFT JOIN school_classes AS sc
                    ON sc.id =
                        s.class_id

                WHERE sf.id = :fee_id

                LIMIT 1
                """
            ),
            {
                "fee_id": fee_id,
            },
        ).mappings().first()

        if not row:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Fee record not found"
                ),
            )

        amount = Decimal(
            str(row["amount"])
        )

        paid_amount = Decimal(
            str(row["paid_amount"])
        )

        return {
            "success": True,
            "data": {
                "id":
                    row["id"],

                "student_id":
                    row["student_id"],

                "student": {
                    "id":
                        row["student_id"],

                    "admission_no":
                        row[
                            "admission_no"
                        ],

                    "roll_no":
                        row["roll_no"],

                    "full_name":
                        row["full_name"],

                    "class_id":
                        row["class_id"],

                    "class": (
                        {
                            "id":
                                row[
                                    "class_id"
                                ],

                            "name":
                                row[
                                    "class_name"
                                ],

                            "section":
                                row[
                                    "class_section"
                                ],

                            "academic_year":
                                row[
                                    "class_academic_year"
                                ],
                        }
                        if row["class_id"]
                        else None
                    ),
                },

                "academic_year":
                    row["academic_year"],

                "fee_title":
                    row["fee_title"],

                "fee_type":
                    row["fee_type"],

                "amount":
                    amount,

                "paid_amount":
                    paid_amount,

                "balance_amount":
                    amount - paid_amount,

                "payment_status":
                    get_payment_status(
                        amount,
                        paid_amount,
                    ),

                "due_date":
                    row["due_date"],

                "paid_date":
                    row["paid_date"],

                "receipt_no":
                    row["receipt_no"],

                "payment_mode":
                    row[
                        "payment_mode"
                    ],

                "remarks":
                    row["remarks"],

                "is_active":
                    bool(
                        row["is_active"]
                    ),

                "created_at":
                    row["created_at"],

                "updated_at":
                    row["updated_at"],
            },
        }

    except HTTPException:
        raise

    except Exception as e:
        print(
            "Admin fee detail error:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to load "
                "fee record"
            ),
        )


# ============================================================
# CREATE FEE
# ============================================================

@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
)
def create_admin_fee(
    payload: AdminFeeCreate,
    db: Session = Depends(get_db),
):
    try:
        validate_student(
            payload.student_id,
            db,
        )

        amount = Decimal(
            str(payload.amount)
        )

        paid_amount = Decimal(
            str(payload.paid_amount)
        )

        if amount <= Decimal("0"):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Fee amount must be "
                    "greater than zero"
                ),
            )

        if paid_amount > amount:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Paid amount cannot be "
                    "greater than fee amount"
                ),
            )

        # Payment information required
        # when money has already been paid.
        if (
            paid_amount
            > Decimal("0")
            and payload.paid_date
            is None
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "paid_date is required "
                    "when paid_amount is "
                    "greater than zero"
                ),
            )

        # If unpaid, clear payment data.
        paid_date = (
            payload.paid_date
            if paid_amount
            > Decimal("0")
            else None
        )

        receipt_no = (
            payload.receipt_no.strip()
            if (
                paid_amount
                > Decimal("0")
                and payload.receipt_no
            )
            else None
        )

        payment_mode = (
            payload.payment_mode.strip()
            if (
                paid_amount
                > Decimal("0")
                and payload.payment_mode
            )
            else None
        )

        result = db.execute(
            text(
                """
                INSERT INTO student_fees
                (
                    student_id,
                    academic_year,
                    fee_title,
                    fee_type,
                    amount,
                    paid_amount,
                    due_date,
                    paid_date,
                    receipt_no,
                    payment_mode,
                    remarks,
                    is_active,
                    created_at,
                    updated_at
                )

                VALUES
                (
                    :student_id,
                    :academic_year,
                    :fee_title,
                    :fee_type,
                    :amount,
                    :paid_amount,
                    :due_date,
                    :paid_date,
                    :receipt_no,
                    :payment_mode,
                    :remarks,
                    :is_active,
                    NOW(),
                    NOW()
                )
                """
            ),
            {
                "student_id":
                    payload.student_id,

                "academic_year":
                    payload
                    .academic_year
                    .strip(),

                "fee_title":
                    payload
                    .fee_title
                    .strip(),

                "fee_type":
                    payload
                    .fee_type
                    .strip()
                    .upper(),

                "amount":
                    amount,

                "paid_amount":
                    paid_amount,

                "due_date":
                    payload.due_date,

                "paid_date":
                    paid_date,

                "receipt_no":
                    receipt_no,

                "payment_mode":
                    payment_mode,

                "remarks":
                    (
                        payload.remarks.strip()
                        if payload.remarks
                        else None
                    ),

                "is_active":
                    payload.is_active,
            },
        )

        fee_id = result.lastrowid

        db.commit()

        return {
            "success": True,
            "message":
                "Fee created successfully",
            "data": {
                "id":
                    fee_id,

                "student_id":
                    payload.student_id,

                "amount":
                    amount,

                "paid_amount":
                    paid_amount,

                "balance_amount":
                    amount - paid_amount,

                "payment_status":
                    get_payment_status(
                        amount,
                        paid_amount,
                    ),
            },
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()

        print(
            "Create fee error:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to create fee"
            ),
        )


# ============================================================
# UPDATE FEE DETAILS
# ============================================================

@router.put("/{fee_id}")
def update_admin_fee(
    fee_id: int,
    payload: AdminFeeUpdate,
    db: Session = Depends(get_db),
):
    try:
        existing = get_fee_or_404(
            fee_id,
            db,
        )

        validate_student(
            payload.student_id,
            db,
        )

        new_amount = Decimal(
            str(payload.amount)
        )

        current_paid = Decimal(
            str(
                existing[
                    "paid_amount"
                ]
            )
        )

        if new_amount <= Decimal("0"):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Fee amount must be "
                    "greater than zero"
                ),
            )

        if new_amount < current_paid:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Fee amount cannot be "
                    "less than the amount "
                    "already paid"
                ),
            )

        db.execute(
            text(
                """
                UPDATE student_fees

                SET
                    student_id =
                        :student_id,

                    academic_year =
                        :academic_year,

                    fee_title =
                        :fee_title,

                    fee_type =
                        :fee_type,

                    amount =
                        :amount,

                    due_date =
                        :due_date,

                    remarks =
                        :remarks,

                    updated_at =
                        NOW()

                WHERE id =
                    :fee_id
                """
            ),
            {
                "student_id":
                    payload.student_id,

                "academic_year":
                    payload
                    .academic_year
                    .strip(),

                "fee_title":
                    payload
                    .fee_title
                    .strip(),

                "fee_type":
                    payload
                    .fee_type
                    .strip()
                    .upper(),

                "amount":
                    new_amount,

                "due_date":
                    payload.due_date,

                "remarks":
                    (
                        payload.remarks.strip()
                        if payload.remarks
                        else None
                    ),

                "fee_id":
                    fee_id,
            },
        )

        db.commit()

        return {
            "success": True,
            "message":
                "Fee updated successfully",
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()

        print(
            "Update fee error:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to update fee"
            ),
        )


# ============================================================
# UPDATE PAYMENT
# ============================================================

@router.patch(
    "/{fee_id}/payment"
)
def update_admin_fee_payment(
    fee_id: int,
    payload: AdminFeePaymentUpdate,
    db: Session = Depends(get_db),
):
    try:
        existing = get_fee_or_404(
            fee_id,
            db,
        )

        total_amount = Decimal(
            str(existing["amount"])
        )

        paid_amount = Decimal(
            str(payload.paid_amount)
        )

        if paid_amount > total_amount:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Paid amount cannot be "
                    "greater than total "
                    "fee amount"
                ),
            )

        if (
            paid_amount
            > Decimal("0")
            and payload.paid_date
            is None
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "paid_date is required "
                    "when paid_amount is "
                    "greater than zero"
                ),
            )

        if paid_amount == Decimal("0"):
            paid_date = None
            receipt_no = None
            payment_mode = None

        else:
            paid_date = (
                payload.paid_date
            )

            receipt_no = (
                payload.receipt_no.strip()
                if payload.receipt_no
                else None
            )

            payment_mode = (
                payload
                .payment_mode
                .strip()
                .upper()
                if payload.payment_mode
                else None
            )

        db.execute(
            text(
                """
                UPDATE student_fees

                SET
                    paid_amount =
                        :paid_amount,

                    paid_date =
                        :paid_date,

                    receipt_no =
                        :receipt_no,

                    payment_mode =
                        :payment_mode,

                    remarks =
                        :remarks,

                    updated_at =
                        NOW()

                WHERE id =
                    :fee_id
                """
            ),
            {
                "paid_amount":
                    paid_amount,

                "paid_date":
                    paid_date,

                "receipt_no":
                    receipt_no,

                "payment_mode":
                    payment_mode,

                "remarks":
                    (
                        payload.remarks.strip()
                        if payload.remarks
                        else None
                    ),

                "fee_id":
                    fee_id,
            },
        )

        db.commit()

        return {
            "success": True,
            "message":
                "Fee payment updated successfully",

            "data": {
                "id":
                    fee_id,

                "amount":
                    total_amount,

                "paid_amount":
                    paid_amount,

                "balance_amount":
                    (
                        total_amount
                        - paid_amount
                    ),

                "payment_status":
                    get_payment_status(
                        total_amount,
                        paid_amount,
                    ),
            },
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()

        print(
            "Update fee payment error:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to update "
                "fee payment"
            ),
        )


# ============================================================
# ACTIVE / INACTIVE
# ============================================================

@router.patch(
    "/{fee_id}/status"
)
def update_admin_fee_status(
    fee_id: int,
    payload: AdminFeeStatusUpdate,
    db: Session = Depends(get_db),
):
    try:
        get_fee_or_404(
            fee_id,
            db,
        )

        db.execute(
            text(
                """
                UPDATE student_fees

                SET
                    is_active =
                        :is_active,

                    updated_at =
                        NOW()

                WHERE id =
                    :fee_id
                """
            ),
            {
                "is_active":
                    payload.is_active,

                "fee_id":
                    fee_id,
            },
        )

        db.commit()

        return {
            "success": True,
            "message": (
                "Fee activated successfully"
                if payload.is_active
                else
                "Fee deactivated successfully"
            ),
            "data": {
                "id":
                    fee_id,

                "is_active":
                    payload.is_active,
            },
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()

        print(
            "Fee status update error:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to update "
                "fee status"
            ),
        )