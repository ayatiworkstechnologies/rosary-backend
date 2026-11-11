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
from app.core.security import hash_password

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
    search: str | None = Query(default=None),
    class_id: int | None = Query(default=None),
    is_active: bool | None = Query(default=None),

    page: int | None = Query(
        default=None,
        ge=1,
    ),

    page_size: int | None = Query(
        default=None,
        ge=1,
        le=5000,
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

        # -----------------------------------------
        # TOTAL COUNT
        # -----------------------------------------

        total_result = db.execute(
            text(
                f"""
                SELECT COUNT(*) AS total
                FROM students AS s
                {where_clause}
                """
            ),
            params,
        )

        total = total_result.scalar() or 0

        # -----------------------------------------
        # PAGINATION
        # -----------------------------------------

        # Listing screens send page/page_size explicitly. Older dropdown
        # consumers do not, and historically received every student.
        effective_page = page or 1
        effective_page_size = (
            page_size
            if page_size is not None
            else (25 if page is not None else max(total, 1))
        )

        offset = (
            effective_page - 1
        ) * effective_page_size

        query_params = {
            **params,
            "limit": effective_page_size,
            "offset": offset,
        }

        # -----------------------------------------
        # STUDENTS
        # -----------------------------------------

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

                    (
                        SELECT u.email
                        FROM parent_students AS ps
                        JOIN users AS u
                            ON u.id = ps.parent_user_id
                        WHERE ps.student_id = s.id
                          AND UPPER(u.role) = 'PARENT'
                        ORDER BY ps.id ASC
                        LIMIT 1
                    ) AS parent_email,

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

                LIMIT :limit
                OFFSET :offset
                """
            ),
            query_params,
        )

        rows = result.mappings().all()

        students = []

        for row in rows:
            students.append(
                {
                    "id": row["id"],
                    "admission_no": row["admission_no"],
                    "roll_no": row["roll_no"],
                    "full_name": row["full_name"],
                    "date_of_birth": row["date_of_birth"],
                    "parent_email": row["parent_email"],
                    "gender": row["gender"],
                    "class_id": row["class_id"],
                    "is_active": bool(
                        row["is_active"]
                    ),

                    "class": (
                        {
                            "id": row["class_id"],
                            "name": row["class_name"],
                            "section": row["section"],
                            "academic_year": row[
                                "academic_year"
                            ],
                        }
                        if row["class_id"]
                        is not None
                        else None
                    ),
                }
            )

        total_pages = (
            (total + effective_page_size - 1)
            // effective_page_size
        )

        return {
            "success": True,
            # Keep compatibility with clients deployed before pagination.
            "total": total,
            "data": students,

            "pagination": {
                "page": effective_page,
                "page_size": effective_page_size,
                "total": total,
                "total_pages": total_pages,
                "has_next": effective_page < total_pages,
                "has_previous": effective_page > 1,
            },
        }

    except Exception as e:
        print(
            "Admin students list error:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to load students",
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

                    (
                        SELECT u.email
                        FROM parent_students AS ps
                        JOIN users AS u
                            ON u.id = ps.parent_user_id
                        WHERE ps.student_id = s.id
                          AND UPPER(u.role) = 'PARENT'
                        ORDER BY ps.id ASC
                        LIMIT 1
                    ) AS parent_email,

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
                "parent_email": (
                    row["parent_email"]
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

        parent_email = (
            str(payload.parent_email)
            .strip()
            .lower()
            if payload.parent_email
            else None
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

        # Reuse an existing parent account when siblings share the same email.
        # Admission-number authentication still uses each student's own DOB.
        existing_email_user = None

        if parent_email:
            existing_email_user = db.execute(
                text(
                    """
                    SELECT id, role, is_active
                    FROM users
                    WHERE LOWER(email) = LOWER(:email)
                    LIMIT 1
                    """
                ),
                {
                    "email": parent_email,
                },
            ).mappings().first()

            if (
                existing_email_user
                and existing_email_user["role"].upper()
                != "PARENT"
            ):
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Email address is already used "
                        "by a non-parent account"
                    ),
                )

        # The admission number is the parent-facing login identifier. Keep a
        # separate internal username because users.username is globally unique.
        parent_username = f"PARENT_{admission_no}"

        if not existing_email_user:
            existing_parent_username = db.execute(
                text(
                    """
                    SELECT id
                    FROM users
                    WHERE LOWER(username) = LOWER(:username)
                    LIMIT 1
                    """
                ),
                {
                    "username": parent_username,
                },
            ).first()

            if existing_parent_username:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "A parent login already exists "
                        "for this admission number"
                    ),
                )

        login_password = (
            payload.date_of_birth.strftime(
                "%d%m%Y"
            )
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

        student_id = result.lastrowid

        # Create the login, profile, and link in the same transaction as the
        # student so a partial account can never be left behind.
        if existing_email_user:
            parent_user_id = (
                existing_email_user["id"]
            )
        else:
            parent_result = db.execute(
                text(
                    """
                    INSERT INTO users
                    (
                        name,
                        username,
                        email,
                        password_hash,
                        role,
                        is_active
                    )
                    VALUES
                    (
                        :name,
                        :username,
                        :email,
                        :password_hash,
                        'PARENT',
                        :is_active
                    )
                    """
                ),
                {
                    "name": f"Parent of {full_name}",
                    "username": parent_username,
                    "email": parent_email,
                    "password_hash": hash_password(
                        login_password
                    ),
                    "is_active": (
                        1
                        if payload.is_active
                        else 0
                    ),
                },
            )

            parent_user_id = (
                parent_result.lastrowid
            )

            db.execute(
                text(
                    """
                    INSERT INTO parent_profiles
                    (user_id)
                    VALUES (:user_id)
                    """
                ),
                {
                    "user_id": parent_user_id,
                },
            )

        db.execute(
            text(
                """
                INSERT INTO parent_students
                (
                    parent_user_id,
                    student_id,
                    relationship
                )
                VALUES
                (
                    :parent_user_id,
                    :student_id,
                    'Guardian'
                )
                """
            ),
            {
                "parent_user_id":
                    parent_user_id,
                "student_id": student_id,
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
                "id": student_id,
                "admission_no":
                    admission_no,
                "roll_no":
                    roll_no,
                "full_name":
                    full_name,
                "date_of_birth":
                    payload.date_of_birth,
                "parent_email":
                    parent_email,
                "gender":
                    gender,
                "class_id":
                    payload.class_id,
                "is_active":
                    payload.is_active,
                "login_username":
                    admission_no,
                "initial_password":
                    login_password,
                "parent_account_reused":
                    bool(existing_email_user),
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
                SELECT
                    s.id,
                    (
                        SELECT ps.parent_user_id
                        FROM parent_students AS ps
                        WHERE ps.student_id = s.id
                        ORDER BY ps.id ASC
                        LIMIT 1
                    ) AS parent_user_id,
                    (
                        SELECT u.email
                        FROM parent_students AS ps
                        JOIN users AS u
                            ON u.id = ps.parent_user_id
                        WHERE ps.student_id = s.id
                          AND UPPER(u.role) = 'PARENT'
                        ORDER BY ps.id ASC
                        LIMIT 1
                    ) AS parent_email
                FROM students AS s
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

        parent_email_was_provided = (
            "parent_email"
            in payload.model_fields_set
        )

        parent_email = (
            (
                str(payload.parent_email)
                .strip()
                .lower()
                if payload.parent_email
                else None
            )
            if parent_email_was_provided
            else student["parent_email"]
        )

        parent_user_id = (
            student["parent_user_id"]
        )

        if parent_email and not parent_user_id:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Link a parent account before "
                    "adding a parent email"
                ),
            )

        if parent_email:
            duplicate_email = db.execute(
                text(
                    """
                    SELECT id
                    FROM users
                    WHERE LOWER(email) = LOWER(:email)
                      AND id != :parent_user_id
                    LIMIT 1
                    """
                ),
                {
                    "email": parent_email,
                    "parent_user_id":
                        parent_user_id,
                },
            ).first()

            if duplicate_email:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Email address is already used "
                        "by another account"
                    ),
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

        if (
            parent_user_id
            and parent_email_was_provided
        ):
            db.execute(
                text(
                    """
                    UPDATE users
                    SET
                        email_verified_at = CASE
                            WHEN COALESCE(email, '')
                                != COALESCE(:email, '')
                            THEN NULL
                            ELSE email_verified_at
                        END,
                        email_notifications_enabled = CASE
                            WHEN COALESCE(email, '')
                                != COALESCE(:email, '')
                            THEN 0
                            ELSE email_notifications_enabled
                        END,
                        email = :email
                    WHERE id = :parent_user_id
                      AND UPPER(role) = 'PARENT'
                    """
                ),
                {
                    "email": parent_email,
                    "parent_user_id":
                        parent_user_id,
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
                "parent_email":
                    parent_email,
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
