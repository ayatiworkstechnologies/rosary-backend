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

from app.schemas.admin_student import (
    AdminStudentCreate,
    AdminStudentUpdate,
    AdminStudentStatusUpdate,
)


router = APIRouter(
    prefix="/admin/students",
    tags=["Admin Students"],
)


# =========================================================
# HELPERS
# =========================================================

def clean_optional_string(value: str | None):
    if value is None:
        return None

    value = value.strip()

    return value if value else None


def validate_class(
    db: Session,
    class_id: int | None,
):
    if class_id is None:
        return

    school_class = db.execute(
        text(
            """
            SELECT
                id,
                name,
                section,
                academic_year,
                is_active
            FROM school_classes
            WHERE id = :class_id
            LIMIT 1
            """
        ),
        {
            "class_id": class_id,
        },
    ).mappings().first()

    if not school_class:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Selected class not found",
        )

    if not bool(school_class["is_active"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Selected class is inactive",
        )


# =========================================================
# GET ALL STUDENTS
# =========================================================

@router.get("")
def get_students(
    search: str | None = Query(
        default=None,
    ),
    class_id: int | None = Query(
        default=None,
    ),
    is_active: bool | None = Query(
        default=None,
    ),
    db: Session = Depends(get_db),
):
    try:
        conditions = []
        params = {}

        if search:
            conditions.append(
                """
                (
                    s.full_name LIKE :search
                    OR s.admission_no LIKE :search
                    OR s.roll_no LIKE :search
                )
                """
            )

            params["search"] = (
                f"%{search.strip()}%"
            )

        if class_id is not None:
            conditions.append(
                "s.class_id = :class_id"
            )

            params["class_id"] = class_id

        if is_active is not None:
            conditions.append(
                "s.is_active = :is_active"
            )

            params["is_active"] = (
                1 if is_active else 0
            )

        where_clause = ""

        if conditions:
            where_clause = (
                "WHERE "
                + " AND ".join(conditions)
            )

        result = db.execute(
            text(
                f"""
                SELECT
                    s.id,
                    s.admission_no,
                    s.roll_no,
                    s.full_name,
                    s.date_of_birth,
                    s.gender,
                    s.class_id,
                    s.is_active,

                    sc.name AS class_name,
                    sc.section,
                    sc.academic_year

                FROM students AS s

                LEFT JOIN school_classes AS sc
                    ON sc.id = s.class_id

                {where_clause}

                ORDER BY
                    s.full_name ASC,
                    s.id ASC
                """
            ),
            params,
        )

        rows = result.mappings().all()

        students = []

        for row in rows:
            students.append(
                {
                    "id": row["id"],
                    "admission_no": (
                        row["admission_no"]
                    ),
                    "roll_no": row["roll_no"],
                    "full_name": (
                        row["full_name"]
                    ),
                    "date_of_birth": (
                        row["date_of_birth"]
                    ),
                    "gender": row["gender"],
                    "class_id": row["class_id"],
                    "is_active": bool(
                        row["is_active"]
                    ),
                    "class": (
                        {
                            "id": row["class_id"],
                            "name": (
                                row["class_name"]
                            ),
                            "section": (
                                row["section"]
                            ),
                            "academic_year": (
                                row[
                                    "academic_year"
                                ]
                            ),
                        }
                        if row["class_id"]
                        is not None
                        else None
                    ),
                }
            )

        return {
            "success": True,
            "total": len(students),
            "data": students,
        }

    except Exception as e:
        print(
            "Admin students list error:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to load students"
            ),
        )


# =========================================================
# GET SINGLE STUDENT
# =========================================================

@router.get("/{student_id}")
def get_student(
    student_id: int,
    db: Session = Depends(get_db),
):
    try:
        row = db.execute(
            text(
                """
                SELECT
                    s.id,
                    s.admission_no,
                    s.roll_no,
                    s.full_name,
                    s.date_of_birth,
                    s.gender,
                    s.class_id,
                    s.is_active,

                    sc.name AS class_name,
                    sc.section,
                    sc.academic_year

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

        if not row:
            raise HTTPException(
                status_code=404,
                detail="Student not found",
            )

        return {
            "success": True,
            "data": {
                "id": row["id"],
                "admission_no": (
                    row["admission_no"]
                ),
                "roll_no": row["roll_no"],
                "full_name": row["full_name"],
                "date_of_birth": (
                    row["date_of_birth"]
                ),
                "gender": row["gender"],
                "class_id": row["class_id"],
                "is_active": bool(
                    row["is_active"]
                ),
                "class": (
                    {
                        "id": row["class_id"],
                        "name": (
                            row["class_name"]
                        ),
                        "section": (
                            row["section"]
                        ),
                        "academic_year": (
                            row[
                                "academic_year"
                            ]
                        ),
                    }
                    if row["class_id"]
                    is not None
                    else None
                ),
            },
        }

    except HTTPException:
        raise

    except Exception as e:
        print(
            "Admin student detail error:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to load student"
            ),
        )


# =========================================================
# CREATE STUDENT
# =========================================================

@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
)
def create_student(
    payload: AdminStudentCreate,
    db: Session = Depends(get_db),
):
    try:
        admission_no = (
            payload.admission_no.strip()
        )

        full_name = (
            payload.full_name.strip()
        )

        roll_no = clean_optional_string(
            payload.roll_no
        )

        gender = clean_optional_string(
            payload.gender
        )

        # ---------------------------------
        # Check admission number duplicate
        # ---------------------------------

        existing = db.execute(
            text(
                """
                SELECT id
                FROM students
                WHERE LOWER(admission_no)
                    = LOWER(:admission_no)
                LIMIT 1
                """
            ),
            {
                "admission_no":
                    admission_no,
            },
        ).first()

        if existing:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Admission number "
                    "already exists"
                ),
            )

        # ---------------------------------
        # Validate selected class
        # ---------------------------------

        validate_class(
            db,
            payload.class_id,
        )

        # ---------------------------------
        # Insert student
        # ---------------------------------

        result = db.execute(
            text(
                """
                INSERT INTO students
                (
                    admission_no,
                    roll_no,
                    full_name,
                    date_of_birth,
                    gender,
                    class_id,
                    is_active
                )
                VALUES
                (
                    :admission_no,
                    :roll_no,
                    :full_name,
                    :date_of_birth,
                    :gender,
                    :class_id,
                    :is_active
                )
                """
            ),
            {
                "admission_no":
                    admission_no,

                "roll_no":
                    roll_no,

                "full_name":
                    full_name,

                "date_of_birth":
                    payload.date_of_birth,

                "gender":
                    gender,

                "class_id":
                    payload.class_id,

                "is_active":
                    (
                        1
                        if payload.is_active
                        else 0
                    ),
            },
        )

        db.commit()

        return {
            "success": True,
            "message": (
                "Student created "
                "successfully"
            ),
            "data": {
                "id": result.lastrowid,
                "admission_no":
                    admission_no,
                "roll_no":
                    roll_no,
                "full_name":
                    full_name,
                "date_of_birth":
                    payload.date_of_birth,
                "gender":
                    gender,
                "class_id":
                    payload.class_id,
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
            "Admin student create error:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to create student"
            ),
        )


# =========================================================
# UPDATE STUDENT
# =========================================================

@router.put("/{student_id}")
def update_student(
    student_id: int,
    payload: AdminStudentUpdate,
    db: Session = Depends(get_db),
):
    try:
        # ---------------------------------
        # Student exists?
        # ---------------------------------

        student = db.execute(
            text(
                """
                SELECT id
                FROM students
                WHERE id = :student_id
                LIMIT 1
                """
            ),
            {
                "student_id": student_id,
            },
        ).first()

        if not student:
            raise HTTPException(
                status_code=404,
                detail="Student not found",
            )

        admission_no = (
            payload.admission_no.strip()
        )

        full_name = (
            payload.full_name.strip()
        )

        roll_no = clean_optional_string(
            payload.roll_no
        )

        gender = clean_optional_string(
            payload.gender
        )

        # ---------------------------------
        # Duplicate admission number
        # ---------------------------------

        duplicate = db.execute(
            text(
                """
                SELECT id
                FROM students

                WHERE LOWER(admission_no)
                    = LOWER(:admission_no)

                AND id != :student_id

                LIMIT 1
                """
            ),
            {
                "admission_no":
                    admission_no,

                "student_id":
                    student_id,
            },
        ).first()

        if duplicate:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Another student "
                    "already uses this "
                    "admission number"
                ),
            )

        # ---------------------------------
        # Validate class
        # ---------------------------------

        validate_class(
            db,
            payload.class_id,
        )

        # ---------------------------------
        # Update student
        # ---------------------------------

        db.execute(
            text(
                """
                UPDATE students

                SET
                    admission_no =
                        :admission_no,

                    roll_no =
                        :roll_no,

                    full_name =
                        :full_name,

                    date_of_birth =
                        :date_of_birth,

                    gender =
                        :gender,

                    class_id =
                        :class_id,

                    is_active =
                        :is_active

                WHERE id =
                    :student_id
                """
            ),
            {
                "admission_no":
                    admission_no,

                "roll_no":
                    roll_no,

                "full_name":
                    full_name,

                "date_of_birth":
                    payload.date_of_birth,

                "gender":
                    gender,

                "class_id":
                    payload.class_id,

                "is_active":
                    (
                        1
                        if payload.is_active
                        else 0
                    ),

                "student_id":
                    student_id,
            },
        )

        db.commit()

        return {
            "success": True,
            "message": (
                "Student updated "
                "successfully"
            ),
            "data": {
                "id":
                    student_id,
                "admission_no":
                    admission_no,
                "roll_no":
                    roll_no,
                "full_name":
                    full_name,
                "date_of_birth":
                    payload.date_of_birth,
                "gender":
                    gender,
                "class_id":
                    payload.class_id,
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
            "Admin student update error:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to update student"
            ),
        )


# =========================================================
# ACTIVATE / DEACTIVATE STUDENT
# =========================================================

@router.patch(
    "/{student_id}/status"
)
def update_student_status(
    student_id: int,
    payload: AdminStudentStatusUpdate,
    db: Session = Depends(get_db),
):
    try:
        student = db.execute(
            text(
                """
                SELECT id
                FROM students
                WHERE id = :student_id
                LIMIT 1
                """
            ),
            {
                "student_id": student_id,
            },
        ).first()

        if not student:
            raise HTTPException(
                status_code=404,
                detail="Student not found",
            )

        db.execute(
            text(
                """
                UPDATE students

                SET is_active =
                    :is_active

                WHERE id =
                    :student_id
                """
            ),
            {
                "is_active":
                    (
                        1
                        if payload.is_active
                        else 0
                    ),

                "student_id":
                    student_id,
            },
        )

        db.commit()

        return {
            "success": True,
            "message": (
                "Student activated "
                "successfully"
                if payload.is_active
                else
                "Student deactivated "
                "successfully"
            ),
            "data": {
                "id": student_id,
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
            "Admin student status error:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to update "
                "student status"
            ),
        )