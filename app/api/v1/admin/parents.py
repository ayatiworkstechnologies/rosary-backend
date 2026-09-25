from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.database import get_db

from app.schemas.admin_parent import (
    AdminParentCreate,
    AdminParentUpdate,
    AdminParentStatusUpdate,
    AdminParentPasswordUpdate,
)


router = APIRouter(
    prefix="/admin/parents",
    tags=["Admin Parents"],
)


# ============================================================
# HELPERS
# ============================================================

def normalize_username(
    value: str,
) -> str:
    return value.strip().upper()


def normalize_email(
    value: str | None,
) -> str | None:
    if not value:
        return None

    return value.strip().lower()


def clean_optional_text(
    value: str | None,
) -> str | None:
    if value is None:
        return None

    cleaned = value.strip()

    return cleaned if cleaned else None


def get_parent_profile_or_404(
    parent_id: int,
    db: Session,
):
    parent = db.execute(
        text(
            """
            SELECT
                pp.id,
                pp.user_id
            FROM parent_profiles AS pp

            INNER JOIN users AS u
                ON u.id = pp.user_id

            WHERE pp.id = :parent_id
              AND u.role = 'PARENT'

            LIMIT 1
            """
        ),
        {
            "parent_id": parent_id,
        },
    ).mappings().first()

    if not parent:
        raise HTTPException(
            status_code=404,
            detail="Parent not found",
        )

    return parent


# ============================================================
# GET ALL PARENTS
# ============================================================

@router.get("")
def get_admin_parents(
    db: Session = Depends(get_db),
):
    try:
        rows = db.execute(
            text(
                """
                SELECT
                    pp.id AS parent_id,
                    pp.user_id,

                    pp.phone,
                    pp.alternate_phone,
                    pp.occupation,
                    pp.address,
                    pp.city,
                    pp.state,
                    pp.pincode,
                    pp.profile_image_url,
                    pp.created_at,
                    pp.updated_at,

                    u.name,
                    u.username,
                    u.email,
                    u.role,
                    u.is_active,

                    COUNT(ps.id) AS student_count

                FROM parent_profiles AS pp

                INNER JOIN users AS u
                    ON u.id = pp.user_id

                LEFT JOIN parent_students AS ps
                    ON ps.parent_user_id = pp.user_id

                WHERE u.role = 'PARENT'

                GROUP BY
                    pp.id,
                    pp.user_id,
                    pp.phone,
                    pp.alternate_phone,
                    pp.occupation,
                    pp.address,
                    pp.city,
                    pp.state,
                    pp.pincode,
                    pp.profile_image_url,
                    pp.created_at,
                    pp.updated_at,
                    u.name,
                    u.username,
                    u.email,
                    u.role,
                    u.is_active

                ORDER BY u.name ASC
                """
            )
        ).mappings().all()

        parents = []

        for row in rows:
            parents.append(
                {
                    "id": row["parent_id"],
                    "user_id": row["user_id"],

                    "name": row["name"],
                    "username": row["username"],
                    "email": row["email"],
                    "role": row["role"],

                    "is_active": bool(
                        row["is_active"]
                    ),

                    "phone": row["phone"],

                    "alternate_phone":
                        row["alternate_phone"],

                    "occupation":
                        row["occupation"],

                    "address":
                        row["address"],

                    "city":
                        row["city"],

                    "state":
                        row["state"],

                    "pincode":
                        row["pincode"],

                    "profile_image_url":
                        row["profile_image_url"],

                    "student_count":
                        row["student_count"],

                    "created_at":
                        row["created_at"],

                    "updated_at":
                        row["updated_at"],
                }
            )

        return {
            "success": True,
            "total": len(parents),
            "data": parents,
        }

    except HTTPException:
        raise

    except Exception as e:
        print(
            "Admin get parents error:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to load parents",
        )


# ============================================================
# GET SINGLE PARENT
# ============================================================

@router.get("/{parent_id}")
def get_admin_parent(
    parent_id: int,
    db: Session = Depends(get_db),
):
    try:
        row = db.execute(
            text(
                """
                SELECT
                    pp.id AS parent_id,
                    pp.user_id,

                    pp.phone,
                    pp.alternate_phone,
                    pp.occupation,
                    pp.address,
                    pp.city,
                    pp.state,
                    pp.pincode,
                    pp.profile_image_url,
                    pp.created_at,
                    pp.updated_at,

                    u.name,
                    u.username,
                    u.email,
                    u.role,
                    u.is_active

                FROM parent_profiles AS pp

                INNER JOIN users AS u
                    ON u.id = pp.user_id

                WHERE pp.id = :parent_id
                  AND u.role = 'PARENT'

                LIMIT 1
                """
            ),
            {
                "parent_id": parent_id,
            },
        ).mappings().first()

        if not row:
            raise HTTPException(
                status_code=404,
                detail="Parent not found",
            )

        students = db.execute(
            text(
                """
                SELECT
                    ps.id AS link_id,
                    ps.student_id,
                    ps.relationship,
                    ps.created_at,

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

                FROM parent_students AS ps

                INNER JOIN students AS s
                    ON s.id = ps.student_id

                LEFT JOIN school_classes AS sc
                    ON sc.id = s.class_id

                WHERE ps.parent_user_id =
                    :parent_user_id

                ORDER BY
                    s.full_name ASC
                """
            ),
            {
                "parent_user_id":
                    row["user_id"],
            },
        ).mappings().all()

        children = []

        for student in students:
            children.append(
                {
                    "link_id":
                        student["link_id"],

                    "student_id":
                        student["student_id"],

                    "admission_no":
                        student["admission_no"],

                    "roll_no":
                        student["roll_no"],

                    "full_name":
                        student["full_name"],

                    "date_of_birth":
                        student["date_of_birth"],

                    "gender":
                        student["gender"],

                    "relationship":
                        student["relationship"],

                    "is_active":
                        bool(
                            student["is_active"]
                        ),

                    "class": (
                        {
                            "id":
                                student["class_id"],

                            "name":
                                student["class_name"],

                            "section":
                                student["section"],

                            "academic_year":
                                student[
                                    "academic_year"
                                ],
                        }
                        if student["class_id"]
                        is not None
                        else None
                    ),
                }
            )

        return {
            "success": True,
            "data": {
                "id":
                    row["parent_id"],

                "user_id":
                    row["user_id"],

                "name":
                    row["name"],

                "username":
                    row["username"],

                "email":
                    row["email"],

                "role":
                    row["role"],

                "is_active":
                    bool(
                        row["is_active"]
                    ),

                "phone":
                    row["phone"],

                "alternate_phone":
                    row["alternate_phone"],

                "occupation":
                    row["occupation"],

                "address":
                    row["address"],

                "city":
                    row["city"],

                "state":
                    row["state"],

                "pincode":
                    row["pincode"],

                "profile_image_url":
                    row["profile_image_url"],

                "created_at":
                    row["created_at"],

                "updated_at":
                    row["updated_at"],

                "students":
                    children,
            },
        }

    except HTTPException:
        raise

    except Exception as e:
        print(
            "Admin get parent error:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to load parent",
        )


# ============================================================
# CREATE PARENT
# ============================================================

@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
)
def create_admin_parent(
    payload: AdminParentCreate,
    db: Session = Depends(get_db),
):
    try:
        name = payload.name.strip()

        username = normalize_username(
            payload.username
        )

        email = normalize_email(
            payload.email
        )

        # ----------------------------------------------------
        # USERNAME DUPLICATE
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
                detail="Username already exists",
            )

        # ----------------------------------------------------
        # EMAIL DUPLICATE
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
                    detail="Email already exists",
                )

        # ----------------------------------------------------
        # PASSWORD
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
                    'PARENT',
                    :is_active
                )
                """
            ),
            {
                "name":
                    name,

                "username":
                    username,

                "email":
                    email,

                "password_hash":
                    password_hash,

                "is_active":
                    payload.is_active,
            },
        )

        parent_user_id = (
            user_result.lastrowid
        )

        # ----------------------------------------------------
        # CREATE PARENT PROFILE
        # ----------------------------------------------------

        profile_result = db.execute(
            text(
                """
                INSERT INTO parent_profiles
                (
                    user_id,
                    phone,
                    alternate_phone,
                    occupation,
                    address,
                    city,
                    state,
                    pincode,
                    profile_image_url
                )
                VALUES
                (
                    :user_id,
                    :phone,
                    :alternate_phone,
                    :occupation,
                    :address,
                    :city,
                    :state,
                    :pincode,
                    :profile_image_url
                )
                """
            ),
            {
                "user_id":
                    parent_user_id,

                "phone":
                    clean_optional_text(
                        payload.phone
                    ),

                "alternate_phone":
                    clean_optional_text(
                        payload.alternate_phone
                    ),

                "occupation":
                    clean_optional_text(
                        payload.occupation
                    ),

                "address":
                    clean_optional_text(
                        payload.address
                    ),

                "city":
                    clean_optional_text(
                        payload.city
                    ),

                "state":
                    clean_optional_text(
                        payload.state
                    ),

                "pincode":
                    clean_optional_text(
                        payload.pincode
                    ),

                "profile_image_url":
                    clean_optional_text(
                        payload.profile_image_url
                    ),
            },
        )

        parent_id = (
            profile_result.lastrowid
        )

        db.commit()

        return {
            "success": True,
            "message":
                "Parent created successfully",

            "data": {
                "id":
                    parent_id,

                "user_id":
                    parent_user_id,

                "name":
                    name,

                "username":
                    username,

                "email":
                    email,

                "role":
                    "PARENT",

                "phone":
                    clean_optional_text(
                        payload.phone
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
            "Admin create parent error:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to create parent",
        )


# ============================================================
# UPDATE PARENT
# ============================================================

@router.put("/{parent_id}")
def update_admin_parent(
    parent_id: int,
    payload: AdminParentUpdate,
    db: Session = Depends(get_db),
):
    try:
        parent = (
            get_parent_profile_or_404(
                parent_id,
                db,
            )
        )

        user_id = parent["user_id"]

        name = payload.name.strip()

        username = normalize_username(
            payload.username
        )

        email = normalize_email(
            payload.email
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
                "username":
                    username,

                "user_id":
                    user_id,
            },
        ).first()

        if duplicate_username:
            raise HTTPException(
                status_code=409,
                detail="Username already exists",
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
                    "email":
                        email,

                    "user_id":
                        user_id,
                },
            ).first()

            if duplicate_email:
                raise HTTPException(
                    status_code=409,
                    detail="Email already exists",
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
                  AND role = 'PARENT'
                """
            ),
            {
                "name":
                    name,

                "username":
                    username,

                "email":
                    email,

                "user_id":
                    user_id,
            },
        )

        # ----------------------------------------------------
        # UPDATE PROFILE
        # ----------------------------------------------------

        db.execute(
            text(
                """
                UPDATE parent_profiles

                SET
                    phone =
                        :phone,

                    alternate_phone =
                        :alternate_phone,

                    occupation =
                        :occupation,

                    address =
                        :address,

                    city =
                        :city,

                    state =
                        :state,

                    pincode =
                        :pincode,

                    profile_image_url =
                        :profile_image_url

                WHERE id = :parent_id
                """
            ),
            {
                "phone":
                    clean_optional_text(
                        payload.phone
                    ),

                "alternate_phone":
                    clean_optional_text(
                        payload.alternate_phone
                    ),

                "occupation":
                    clean_optional_text(
                        payload.occupation
                    ),

                "address":
                    clean_optional_text(
                        payload.address
                    ),

                "city":
                    clean_optional_text(
                        payload.city
                    ),

                "state":
                    clean_optional_text(
                        payload.state
                    ),

                "pincode":
                    clean_optional_text(
                        payload.pincode
                    ),

                "profile_image_url":
                    clean_optional_text(
                        payload.profile_image_url
                    ),

                "parent_id":
                    parent_id,
            },
        )

        db.commit()

        return {
            "success": True,
            "message":
                "Parent updated successfully",

            "data": {
                "id":
                    parent_id,

                "user_id":
                    user_id,

                "name":
                    name,

                "username":
                    username,

                "email":
                    email,
            },
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()

        print(
            "Admin update parent error:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to update parent",
        )


# ============================================================
# ACTIVATE / DEACTIVATE PARENT
# ============================================================

@router.patch(
    "/{parent_id}/status"
)
def update_admin_parent_status(
    parent_id: int,
    payload: AdminParentStatusUpdate,
    db: Session = Depends(get_db),
):
    try:
        parent = (
            get_parent_profile_or_404(
                parent_id,
                db,
            )
        )

        db.execute(
            text(
                """
                UPDATE users

                SET is_active = :is_active

                WHERE id = :user_id
                  AND role = 'PARENT'
                """
            ),
            {
                "is_active":
                    payload.is_active,

                "user_id":
                    parent["user_id"],
            },
        )

        db.commit()

        return {
            "success": True,

            "message": (
                "Parent activated successfully"
                if payload.is_active
                else
                "Parent deactivated successfully"
            ),

            "data": {
                "parent_id":
                    parent_id,

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
            "Parent status error:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to update parent status"
            ),
        )


# ============================================================
# RESET PARENT PASSWORD
# ============================================================

@router.patch(
    "/{parent_id}/password"
)
def update_admin_parent_password(
    parent_id: int,
    payload: AdminParentPasswordUpdate,
    db: Session = Depends(get_db),
):
    try:
        parent = (
            get_parent_profile_or_404(
                parent_id,
                db,
            )
        )

        password_hash = hash_password(
            payload.password
        )

        db.execute(
            text(
                """
                UPDATE users

                SET password_hash =
                    :password_hash

                WHERE id = :user_id
                  AND role = 'PARENT'
                """
            ),
            {
                "password_hash":
                    password_hash,

                "user_id":
                    parent["user_id"],
            },
        )

        db.commit()

        return {
            "success": True,
            "message":
                "Parent password updated successfully",
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()

        print(
            "Parent password error:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to update parent password"
            ),
        )


# ============================================================
# DELETE PARENT
# ============================================================

@router.delete(
    "/{parent_id}"
)
def delete_admin_parent(
    parent_id: int,
    db: Session = Depends(get_db),
):
    try:
        parent = (
            get_parent_profile_or_404(
                parent_id,
                db,
            )
        )

        user_id = parent["user_id"]

        # ----------------------------------------------------
        # CHECK STUDENT LINKS
        # ----------------------------------------------------

        student_link_count = db.execute(
            text(
                """
                SELECT COUNT(*)

                FROM parent_students

                WHERE parent_user_id =
                    :parent_user_id
                """
            ),
            {
                "parent_user_id":
                    user_id,
            },
        ).scalar() or 0

        if student_link_count > 0:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Parent is linked to student records. "
                    "Remove the student links or deactivate "
                    "the parent instead."
                ),
            )

        # parent_profiles has ON DELETE CASCADE
        # from users through user_id.

        db.execute(
            text(
                """
                DELETE FROM users

                WHERE id = :user_id
                  AND role = 'PARENT'
                """
            ),
            {
                "user_id":
                    user_id,
            },
        )

        db.commit()

        return {
            "success": True,
            "message":
                "Parent deleted successfully",
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()

        print(
            "Delete parent error:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to delete parent",
        )