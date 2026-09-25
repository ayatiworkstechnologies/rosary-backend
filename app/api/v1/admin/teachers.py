from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.security import hash_password

from app.schemas.admin_teacher import (
    AdminTeacherCreate,
    AdminTeacherUpdate,
    AdminTeacherStatusUpdate,
    AdminTeacherPasswordUpdate,
    AdminTeacherClassCreate,
    AdminTeacherClassUpdate,
)


router = APIRouter(
    prefix="/admin/teachers",
    tags=["Admin Teachers"],
)


# ============================================================
# HELPER - GET TEACHER PROFILE
# ============================================================

def get_teacher_profile_or_404(
    teacher_id: int,
    db: Session,
):
    teacher = db.execute(
        text(
            """
            SELECT
                tp.id,
                tp.user_id,
                tp.employee_id
            FROM teacher_profiles AS tp
            WHERE tp.id = :teacher_id
            LIMIT 1
            """
        ),
        {
            "teacher_id": teacher_id,
        },
    ).mappings().first()

    if not teacher:
        raise HTTPException(
            status_code=404,
            detail="Teacher not found",
        )

    return teacher


# ============================================================
# GET ALL TEACHERS
# ============================================================

@router.get("")
def get_admin_teachers(
    db: Session = Depends(get_db),
):
    try:
        rows = db.execute(
            text(
                """
                SELECT
                    tp.id AS teacher_id,
                    tp.user_id,
                    tp.employee_id,
                    tp.date_of_birth,
                    tp.gender,
                    tp.phone,
                    tp.designation,
                    tp.department,
                    tp.qualification,
                    tp.specialization,
                    tp.experience_years,
                    tp.joining_date,
                    tp.profile_image_url,
                    tp.created_at,
                    tp.updated_at,

                    u.name,
                    u.username,
                    u.email,
                    u.role,
                    u.is_active,

                    COUNT(tc.id) AS class_count

                FROM teacher_profiles AS tp

                INNER JOIN users AS u
                    ON u.id = tp.user_id

                LEFT JOIN teacher_classes AS tc
                    ON tc.teacher_user_id = tp.user_id

                WHERE u.role = 'TEACHER'

                GROUP BY
                    tp.id,
                    tp.user_id,
                    tp.employee_id,
                    tp.date_of_birth,
                    tp.gender,
                    tp.phone,
                    tp.designation,
                    tp.department,
                    tp.qualification,
                    tp.specialization,
                    tp.experience_years,
                    tp.joining_date,
                    tp.profile_image_url,
                    tp.created_at,
                    tp.updated_at,
                    u.name,
                    u.username,
                    u.email,
                    u.role,
                    u.is_active

                ORDER BY u.name ASC
                """
            )
        ).mappings().all()

        teachers = []

        for row in rows:
            teachers.append(
                {
                    "id": row["teacher_id"],
                    "user_id": row["user_id"],
                    "name": row["name"],
                    "username": row["username"],
                    "email": row["email"],
                    "role": row["role"],
                    "is_active": bool(
                        row["is_active"]
                    ),
                    "employee_id":
                        row["employee_id"],
                    "date_of_birth":
                        row["date_of_birth"],
                    "gender":
                        row["gender"],
                    "phone":
                        row["phone"],
                    "designation":
                        row["designation"],
                    "department":
                        row["department"],
                    "qualification":
                        row["qualification"],
                    "specialization":
                        row["specialization"],
                    "experience_years":
                        row["experience_years"],
                    "joining_date":
                        row["joining_date"],
                    "profile_image_url":
                        row["profile_image_url"],
                    "class_count":
                        row["class_count"],
                    "created_at":
                        row["created_at"],
                    "updated_at":
                        row["updated_at"],
                }
            )

        return {
            "success": True,
            "total": len(teachers),
            "data": teachers,
        }

    except HTTPException:
        raise

    except Exception as e:
        print(
            "Admin get teachers error:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to load teachers",
        )


# ============================================================
# GET SINGLE TEACHER
# ============================================================

@router.get("/{teacher_id}")
def get_admin_teacher(
    teacher_id: int,
    db: Session = Depends(get_db),
):
    try:
        row = db.execute(
            text(
                """
                SELECT
                    tp.id AS teacher_id,
                    tp.user_id,
                    tp.employee_id,
                    tp.date_of_birth,
                    tp.gender,
                    tp.phone,
                    tp.designation,
                    tp.department,
                    tp.qualification,
                    tp.specialization,
                    tp.experience_years,
                    tp.joining_date,
                    tp.profile_image_url,
                    tp.created_at,
                    tp.updated_at,

                    u.name,
                    u.username,
                    u.email,
                    u.role,
                    u.is_active

                FROM teacher_profiles AS tp

                INNER JOIN users AS u
                    ON u.id = tp.user_id

                WHERE tp.id = :teacher_id
                  AND u.role = 'TEACHER'

                LIMIT 1
                """
            ),
            {
                "teacher_id": teacher_id,
            },
        ).mappings().first()

        if not row:
            raise HTTPException(
                status_code=404,
                detail="Teacher not found",
            )

        return {
            "success": True,
            "data": {
                "id": row["teacher_id"],
                "user_id": row["user_id"],
                "name": row["name"],
                "username": row["username"],
                "email": row["email"],
                "role": row["role"],
                "is_active": bool(
                    row["is_active"]
                ),
                "employee_id":
                    row["employee_id"],
                "date_of_birth":
                    row["date_of_birth"],
                "gender":
                    row["gender"],
                "phone":
                    row["phone"],
                "designation":
                    row["designation"],
                "department":
                    row["department"],
                "qualification":
                    row["qualification"],
                "specialization":
                    row["specialization"],
                "experience_years":
                    row["experience_years"],
                "joining_date":
                    row["joining_date"],
                "profile_image_url":
                    row["profile_image_url"],
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
            "Admin get teacher error:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to load teacher",
        )


# ============================================================
# CREATE TEACHER
# ============================================================

@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
)
def create_admin_teacher(
    payload: AdminTeacherCreate,
    db: Session = Depends(get_db),
):
    try:
        name = payload.name.strip()
        username = payload.username.strip()
        employee_id = (
            payload.employee_id.strip()
        )

        email = (
            payload.email.strip()
            if payload.email
            else None
        )

        # ----------------------------------------------------
        # CHECK USERNAME
        # ----------------------------------------------------

        existing_username = db.execute(
            text(
                """
                SELECT id
                FROM users
                WHERE username = :username
                LIMIT 1
                """
            ),
            {
                "username": username,
            },
        ).first()

        if existing_username:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Username already exists"
                ),
            )

        # ----------------------------------------------------
        # CHECK EMAIL
        # ----------------------------------------------------

        if email:
            existing_email = db.execute(
                text(
                    """
                    SELECT id
                    FROM users
                    WHERE email = :email
                    LIMIT 1
                    """
                ),
                {
                    "email": email,
                },
            ).first()

            if existing_email:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Email already exists"
                    ),
                )

        # ----------------------------------------------------
        # CHECK EMPLOYEE ID
        # ----------------------------------------------------

        existing_employee = db.execute(
            text(
                """
                SELECT id
                FROM teacher_profiles
                WHERE employee_id =
                    :employee_id
                LIMIT 1
                """
            ),
            {
                "employee_id":
                    employee_id,
            },
        ).first()

        if existing_employee:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Employee ID already exists"
                ),
            )

        # ----------------------------------------------------
        # HASH PASSWORD
        # ----------------------------------------------------

        password_hash = hash_password(
            payload.password
        )

        # ----------------------------------------------------
        # CREATE USER
        # ----------------------------------------------------

        user_result = db.execute(
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
                    'TEACHER',
                    :is_active
                )
                """
            ),
            {
                "name": name,
                "username": username,
                "email": email,
                "password_hash":
                    password_hash,
                "is_active":
                    payload.is_active,
            },
        )

        teacher_user_id = (
            user_result.lastrowid
        )

        # ----------------------------------------------------
        # CREATE TEACHER PROFILE
        # ----------------------------------------------------

        profile_result = db.execute(
            text(
                """
                INSERT INTO teacher_profiles
                (
                    user_id,
                    employee_id,
                    date_of_birth,
                    gender,
                    phone,
                    designation,
                    department,
                    qualification,
                    specialization,
                    experience_years,
                    joining_date,
                    profile_image_url
                )
                VALUES
                (
                    :user_id,
                    :employee_id,
                    :date_of_birth,
                    :gender,
                    :phone,
                    :designation,
                    :department,
                    :qualification,
                    :specialization,
                    :experience_years,
                    :joining_date,
                    :profile_image_url
                )
                """
            ),
            {
                "user_id":
                    teacher_user_id,

                "employee_id":
                    employee_id,

                "date_of_birth":
                    payload.date_of_birth,

                "gender":
                    payload.gender.strip()
                    if payload.gender
                    else None,

                "phone":
                    payload.phone.strip()
                    if payload.phone
                    else None,

                "designation":
                    payload.designation.strip()
                    if payload.designation
                    else None,

                "department":
                    payload.department.strip()
                    if payload.department
                    else None,

                "qualification":
                    payload.qualification.strip()
                    if payload.qualification
                    else None,

                "specialization":
                    payload.specialization.strip()
                    if payload.specialization
                    else None,

                "experience_years":
                    payload.experience_years,

                "joining_date":
                    payload.joining_date,

                "profile_image_url":
                    payload.profile_image_url.strip()
                    if payload.profile_image_url
                    else None,
            },
        )

        teacher_id = (
            profile_result.lastrowid
        )

        db.commit()

        return {
            "success": True,
            "message":
                "Teacher created successfully",
            "data": {
                "id": teacher_id,
                "user_id":
                    teacher_user_id,
                "name": name,
                "username": username,
                "email": email,
                "role": "TEACHER",
                "employee_id":
                    employee_id,
                "date_of_birth":
                    payload.date_of_birth,
                "gender":
                    (
                        payload.gender.strip()
                        if payload.gender
                        else None
                    ),
                "specialization":
                    (
                        payload.specialization.strip()
                        if payload.specialization
                        else None
                    ),
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
            "Admin create teacher error:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to create teacher",
        )


# ============================================================
# UPDATE TEACHER
# ============================================================

@router.put("/{teacher_id}")
def update_admin_teacher(
    teacher_id: int,
    payload: AdminTeacherUpdate,
    db: Session = Depends(get_db),
):
    try:
        teacher = (
            get_teacher_profile_or_404(
                teacher_id,
                db,
            )
        )

        user_id = teacher["user_id"]

        name = payload.name.strip()
        username = payload.username.strip()

        employee_id = (
            payload.employee_id.strip()
        )

        email = (
            payload.email.strip()
            if payload.email
            else None
        )

        # ----------------------------------------------------
        # USERNAME DUPLICATE
        # ----------------------------------------------------

        duplicate_username = db.execute(
            text(
                """
                SELECT id
                FROM users
                WHERE username = :username
                  AND id != :user_id
                LIMIT 1
                """
            ),
            {
                "username": username,
                "user_id": user_id,
            },
        ).first()

        if duplicate_username:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Username already exists"
                ),
            )

        # ----------------------------------------------------
        # EMAIL DUPLICATE
        # ----------------------------------------------------

        if email:
            duplicate_email = db.execute(
                text(
                    """
                    SELECT id
                    FROM users
                    WHERE email = :email
                      AND id != :user_id
                    LIMIT 1
                    """
                ),
                {
                    "email": email,
                    "user_id": user_id,
                },
            ).first()

            if duplicate_email:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Email already exists"
                    ),
                )

        # ----------------------------------------------------
        # EMPLOYEE ID DUPLICATE
        # ----------------------------------------------------

        duplicate_employee = db.execute(
            text(
                """
                SELECT id
                FROM teacher_profiles
                WHERE employee_id =
                    :employee_id
                  AND id != :teacher_id
                LIMIT 1
                """
            ),
            {
                "employee_id":
                    employee_id,
                "teacher_id":
                    teacher_id,
            },
        ).first()

        if duplicate_employee:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Employee ID already exists"
                ),
            )

        # ----------------------------------------------------
        # UPDATE USER
        # ----------------------------------------------------

        db.execute(
            text(
                """
                UPDATE users
                SET
                    name = :name,
                    username = :username,
                    email = :email
                WHERE id = :user_id
                  AND role = 'TEACHER'
                """
            ),
            {
                "name": name,
                "username": username,
                "email": email,
                "user_id": user_id,
            },
        )

        # ----------------------------------------------------
        # UPDATE PROFILE
        # ----------------------------------------------------

        db.execute(
            text(
                """
                UPDATE teacher_profiles
                SET
                    employee_id =
                        :employee_id,

                    date_of_birth =
                        :date_of_birth,

                    gender =
                        :gender,

                    phone =
                        :phone,

                    designation =
                        :designation,

                    department =
                        :department,

                    qualification =
                        :qualification,

                    specialization =
                        :specialization,

                    experience_years =
                        :experience_years,

                    joining_date =
                        :joining_date,

                    profile_image_url =
                        :profile_image_url

                WHERE id = :teacher_id
                """
            ),
            {
                "employee_id":
                    employee_id,

                "date_of_birth":
                    payload.date_of_birth,

                "gender":
                    payload.gender.strip()
                    if payload.gender
                    else None,

                "phone":
                    payload.phone.strip()
                    if payload.phone
                    else None,

                "designation":
                    payload.designation.strip()
                    if payload.designation
                    else None,

                "department":
                    payload.department.strip()
                    if payload.department
                    else None,

                "qualification":
                    payload.qualification.strip()
                    if payload.qualification
                    else None,

                "specialization":
                    payload.specialization.strip()
                    if payload.specialization
                    else None,

                "experience_years":
                    payload.experience_years,

                "joining_date":
                    payload.joining_date,

                "profile_image_url":
                    payload.profile_image_url.strip()
                    if payload.profile_image_url
                    else None,

                "teacher_id":
                    teacher_id,
            },
        )

        db.commit()

        return {
            "success": True,
            "message":
                "Teacher updated successfully",
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()

        print(
            "Admin update teacher error:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to update teacher",
        )


# ============================================================
# ACTIVATE / DEACTIVATE TEACHER
# ============================================================

@router.patch(
    "/{teacher_id}/status"
)
def update_admin_teacher_status(
    teacher_id: int,
    payload: AdminTeacherStatusUpdate,
    db: Session = Depends(get_db),
):
    try:
        teacher = (
            get_teacher_profile_or_404(
                teacher_id,
                db,
            )
        )

        db.execute(
            text(
                """
                UPDATE users
                SET is_active = :is_active
                WHERE id = :user_id
                  AND role = 'TEACHER'
                """
            ),
            {
                "is_active":
                    payload.is_active,
                "user_id":
                    teacher["user_id"],
            },
        )

        db.commit()

        return {
            "success": True,
            "message": (
                "Teacher activated successfully"
                if payload.is_active
                else
                "Teacher deactivated successfully"
            ),
            "data": {
                "teacher_id":
                    teacher_id,
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
            "Teacher status error:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to update "
                "teacher status"
            ),
        )


# ============================================================
# RESET TEACHER PASSWORD
# ============================================================

@router.patch(
    "/{teacher_id}/password"
)
def update_admin_teacher_password(
    teacher_id: int,
    payload: AdminTeacherPasswordUpdate,
    db: Session = Depends(get_db),
):
    try:
        teacher = (
            get_teacher_profile_or_404(
                teacher_id,
                db,
            )
        )

        new_password_hash = (
            hash_password(
                payload.password
            )
        )

        db.execute(
            text(
                """
                UPDATE users
                SET password_hash =
                    :password_hash
                WHERE id = :user_id
                  AND role = 'TEACHER'
                """
            ),
            {
                "password_hash":
                    new_password_hash,

                "user_id":
                    teacher["user_id"],
            },
        )

        db.commit()

        return {
            "success": True,
            "message":
                "Teacher password updated successfully",
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()

        print(
            "Teacher password error:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to update "
                "teacher password"
            ),
        )


# ============================================================
# GET TEACHER CLASS ASSIGNMENTS
# ============================================================

@router.get(
    "/{teacher_id}/classes"
)
def get_admin_teacher_classes(
    teacher_id: int,
    db: Session = Depends(get_db),
):
    try:
        teacher = (
            get_teacher_profile_or_404(
                teacher_id,
                db,
            )
        )

        rows = db.execute(
            text(
                """
                SELECT
                    tc.id,
                    tc.teacher_user_id,
                    tc.class_id,
                    tc.subject,
                    tc.is_class_teacher,

                    sc.name AS class_name,
                    sc.section,
                    sc.academic_year,
                    sc.is_active

                FROM teacher_classes AS tc

                INNER JOIN school_classes AS sc
                    ON sc.id = tc.class_id

                WHERE tc.teacher_user_id =
                    :teacher_user_id

                ORDER BY
                    sc.name ASC,
                    sc.section ASC
                """
            ),
            {
                "teacher_user_id":
                    teacher["user_id"],
            },
        ).mappings().all()

        assignments = []

        for row in rows:
            assignments.append(
                {
                    "id": row["id"],
                    "teacher_user_id":
                        row[
                            "teacher_user_id"
                        ],
                    "class_id":
                        row["class_id"],
                    "subject":
                        row["subject"],
                    "is_class_teacher":
                        bool(row["is_class_teacher"]),
                    "class": {
                        "id":
                            row["class_id"],
                        "name":
                            row["class_name"],
                        "section":
                            row["section"],
                        "academic_year":
                            row[
                                "academic_year"
                            ],
                        "is_active":
                            bool(
                                row[
                                    "is_active"
                                ]
                            ),
                    },
                }
            )

        return {
            "success": True,
            "total":
                len(assignments),
            "data":
                assignments,
        }

    except HTTPException:
        raise

    except Exception as e:
        print(
            "Get teacher classes error:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to load teacher classes"
            ),
        )


# ============================================================
# ASSIGN CLASS TO TEACHER
# ============================================================

@router.post(
    "/{teacher_id}/classes",
    status_code=status.HTTP_201_CREATED,
)
def create_admin_teacher_class(
    teacher_id: int,
    payload: AdminTeacherClassCreate,
    db: Session = Depends(get_db),
):
    try:
        teacher = (
            get_teacher_profile_or_404(
                teacher_id,
                db,
            )
        )

        teacher_user_id = (
            teacher["user_id"]
        )

        # ----------------------------------------------------
        # CLASS EXISTS
        # ----------------------------------------------------

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
                "class_id":
                    payload.class_id,
            },
        ).mappings().first()

        if not school_class:
            raise HTTPException(
                status_code=404,
                detail="Class not found",
            )

        if not bool(
            school_class["is_active"]
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Cannot assign an "
                    "inactive class"
                ),
            )

        subject = (
            payload.subject.strip()
            if payload.subject
            else None
        )

        # ----------------------------------------------------
        # DUPLICATE
        # Teacher + class + subject must be unique.
        # MySQL <=> safely compares NULL values too.
        # ----------------------------------------------------

        duplicate = db.execute(
            text(
                """
                SELECT id
                FROM teacher_classes
                WHERE teacher_user_id =
                    :teacher_user_id
                  AND class_id =
                    :class_id
                  AND subject <=> :subject
                LIMIT 1
                """
            ),
            {
                "teacher_user_id":
                    teacher_user_id,

                "class_id":
                    payload.class_id,

                "subject":
                    subject,
            },
        ).first()

        if duplicate:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Teacher is already assigned "
                    "to this class and subject"
                ),
            )

        result = db.execute(
            text(
                """
                INSERT INTO teacher_classes
                (
                    teacher_user_id,
                    class_id,
                    subject,
                    is_class_teacher
                )
                VALUES
                (
                    :teacher_user_id,
                    :class_id,
                    :subject,
                    :is_class_teacher
                )
                """
            ),
            {
                "teacher_user_id":
                    teacher_user_id,

                "class_id":
                    payload.class_id,

                "subject":
                    subject,

                "is_class_teacher":
                    (
                        1
                        if payload.is_class_teacher
                        else 0
                    ),
            },
        )

        db.commit()

        return {
            "success": True,
            "message":
                "Class assigned successfully",
            "data": {
                "id":
                    result.lastrowid,
                "teacher_user_id":
                    teacher_user_id,
                "class_id":
                    payload.class_id,
                "subject":
                    subject,
                "is_class_teacher":
                    payload.is_class_teacher,
            },
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()

        print(
            "Assign teacher class error:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to assign class",
        )


# ============================================================
# UPDATE CLASS ASSIGNMENT
# ============================================================

@router.put(
    "/{teacher_id}/classes/{assignment_id}"
)
def update_admin_teacher_class(
    teacher_id: int,
    assignment_id: int,
    payload: AdminTeacherClassUpdate,
    db: Session = Depends(get_db),
):
    try:
        teacher = (
            get_teacher_profile_or_404(
                teacher_id,
                db,
            )
        )

        assignment = db.execute(
            text(
                """
                SELECT
                    id,
                    class_id
                FROM teacher_classes
                WHERE id = :assignment_id
                  AND teacher_user_id =
                    :teacher_user_id
                LIMIT 1
                """
            ),
            {
                "assignment_id":
                    assignment_id,

                "teacher_user_id":
                    teacher["user_id"],
            },
        ).mappings().first()

        if not assignment:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Class assignment "
                    "not found"
                ),
            )

        subject = (
            payload.subject.strip()
            if payload.subject
            else None
        )

        # ----------------------------------------------------
        # DUPLICATE AFTER SUBJECT CHANGE
        # ----------------------------------------------------

        duplicate = db.execute(
            text(
                """
                SELECT id
                FROM teacher_classes
                WHERE teacher_user_id =
                    :teacher_user_id
                  AND class_id =
                    :class_id
                  AND subject <=> :subject
                  AND id != :assignment_id
                LIMIT 1
                """
            ),
            {
                "teacher_user_id":
                    teacher["user_id"],

                "class_id":
                    assignment["class_id"],

                "subject":
                    subject,

                "assignment_id":
                    assignment_id,
            },
        ).first()

        if duplicate:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Teacher already has this "
                    "subject assigned to the class"
                ),
            )

        db.execute(
            text(
                """
                UPDATE teacher_classes
                SET
                    subject = :subject,
                    is_class_teacher =
                        :is_class_teacher
                WHERE id = :assignment_id
                """
            ),
            {
                "subject":
                    subject,

                "is_class_teacher":
                    (
                        1
                        if payload.is_class_teacher
                        else 0
                    ),

                "assignment_id":
                    assignment_id,
            },
        )

        db.commit()

        return {
            "success": True,
            "message":
                "Class assignment updated successfully",
            "data": {
                "id":
                    assignment_id,
                "class_id":
                    assignment["class_id"],
                "subject":
                    subject,
                "is_class_teacher":
                    payload.is_class_teacher,
            },
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()

        print(
            "Update teacher class error:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to update "
                "class assignment"
            ),
        )


# ============================================================
# REMOVE CLASS ASSIGNMENT
# ============================================================

@router.delete(
    "/{teacher_id}/classes/{assignment_id}"
)
def delete_admin_teacher_class(
    teacher_id: int,
    assignment_id: int,
    db: Session = Depends(get_db),
):
    try:
        teacher = (
            get_teacher_profile_or_404(
                teacher_id,
                db,
            )
        )

        assignment = db.execute(
            text(
                """
                SELECT id
                FROM teacher_classes
                WHERE id = :assignment_id
                  AND teacher_user_id =
                    :teacher_user_id
                LIMIT 1
                """
            ),
            {
                "assignment_id":
                    assignment_id,

                "teacher_user_id":
                    teacher["user_id"],
            },
        ).first()

        if not assignment:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Class assignment "
                    "not found"
                ),
            )

        db.execute(
            text(
                """
                DELETE FROM teacher_classes
                WHERE id = :assignment_id
                """
            ),
            {
                "assignment_id":
                    assignment_id,
            },
        )

        db.commit()

        return {
            "success": True,
            "message":
                "Class assignment removed successfully",
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()

        print(
            "Delete teacher class error:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to remove "
                "class assignment"
            ),
        )
