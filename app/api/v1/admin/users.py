from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)

from sqlalchemy import or_, text
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.database import get_db
from app.models.user import User

from app.schemas.admin_user import (
    AdminUserCreate,
    AdminUserPasswordReset,
    AdminUserResponse,
    AdminUserStatusUpdate,
    AdminUserUpdate,
)


router = APIRouter(
    prefix="/api/v1/admin/users",
    tags=["Admin Users"],
)


# =========================================================
# HELPERS
# =========================================================

def normalize_username(value: str) -> str:
    return value.strip().upper()


def normalize_email(
    value: str | None,
) -> str | None:
    if not value:
        return None

    return value.strip().lower()


def get_user_or_404(
    db: Session,
    user_id: int,
) -> User:
    user = (
        db.query(User)
        .filter(
            User.id == user_id
        )
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=
                status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return user


# =========================================================
# LINK CHECKS
# =========================================================

def get_user_links(
    db: Session,
    user_id: int,
):
    """
    Check tables that can cascade-delete important
    Teacher / Parent data if a user is hard deleted.
    """

    teacher_profile_count = db.execute(
        text(
            """
            SELECT COUNT(*)
            FROM teacher_profiles
            WHERE user_id = :user_id
            """
        ),
        {
            "user_id": user_id
        },
    ).scalar() or 0

    teacher_class_count = db.execute(
        text(
            """
            SELECT COUNT(*)
            FROM teacher_classes
            WHERE teacher_user_id = :user_id
            """
        ),
        {
            "user_id": user_id
        },
    ).scalar() or 0

    homework_count = db.execute(
        text(
            """
            SELECT COUNT(*)
            FROM homework
            WHERE teacher_user_id = :user_id
            """
        ),
        {
            "user_id": user_id
        },
    ).scalar() or 0

    parent_profile_count = db.execute(
        text(
            """
            SELECT COUNT(*)
            FROM parent_profiles
            WHERE user_id = :user_id
            """
        ),
        {
            "user_id": user_id
        },
    ).scalar() or 0

    parent_student_count = db.execute(
        text(
            """
            SELECT COUNT(*)
            FROM parent_students
            WHERE parent_user_id = :user_id
            """
        ),
        {
            "user_id": user_id
        },
    ).scalar() or 0

    return {
        "teacher_profile":
            int(
                teacher_profile_count
            ),

        "teacher_classes":
            int(
                teacher_class_count
            ),

        "homework":
            int(
                homework_count
            ),

        "parent_profile":
            int(
                parent_profile_count
            ),

        "parent_students":
            int(
                parent_student_count
            ),
    }


def has_teacher_links(
    links: dict,
) -> bool:
    return any(
        [
            links[
                "teacher_profile"
            ],
            links[
                "teacher_classes"
            ],
            links[
                "homework"
            ],
        ]
    )


def has_parent_links(
    links: dict,
) -> bool:
    return any(
        [
            links[
                "parent_profile"
            ],
            links[
                "parent_students"
            ],
        ]
    )


# =========================================================
# GET ALL USERS
# =========================================================

@router.get(
    "",
    response_model=
        list[AdminUserResponse],
)
def get_admin_users(
    search: str | None = Query(
        default=None
    ),

    role: str | None = Query(
        default=None
    ),

    is_active: bool | None = Query(
        default=None
    ),

    db: Session = Depends(get_db),
):
    query = db.query(User)

    # -----------------------------------------------------
    # SEARCH
    # -----------------------------------------------------

    if search:
        search_value = (
            f"%{search.strip()}%"
        )

        query = query.filter(
            or_(
                User.name.ilike(
                    search_value
                ),
                User.username.ilike(
                    search_value
                ),
                User.email.ilike(
                    search_value
                ),
            )
        )

    # -----------------------------------------------------
    # ROLE
    # -----------------------------------------------------

    if role:
        query = query.filter(
            User.role
            == role.strip().upper()
        )

    # -----------------------------------------------------
    # STATUS
    # -----------------------------------------------------

    if is_active is not None:
        query = query.filter(
            User.is_active
            == is_active
        )

    users = (
        query
        .order_by(
            User.id.desc()
        )
        .all()
    )

    return users


# =========================================================
# GET SINGLE USER
# =========================================================

@router.get(
    "/{user_id}",
    response_model=
        AdminUserResponse,
)
def get_admin_user(
    user_id: int,
    db: Session = Depends(get_db),
):
    return get_user_or_404(
        db,
        user_id,
    )


# =========================================================
# CREATE USER
# =========================================================

@router.post(
    "",
    response_model=
        AdminUserResponse,
    status_code=
        status.HTTP_201_CREATED,
)
def create_admin_user(
    payload: AdminUserCreate,
    db: Session = Depends(get_db),
):
    username = (
        normalize_username(
            payload.username
        )
    )

    email = normalize_email(
        payload.email
    )

    # -----------------------------------------------------
    # USERNAME UNIQUE
    # -----------------------------------------------------

    existing_username = (
        db.query(User)
        .filter(
            User.username
            == username
        )
        .first()
    )

    if existing_username:
        raise HTTPException(
            status_code=
                status.HTTP_409_CONFLICT,
            detail=(
                "Username already exists"
            ),
        )

    # -----------------------------------------------------
    # EMAIL UNIQUE
    # -----------------------------------------------------

    if email:
        existing_email = (
            db.query(User)
            .filter(
                User.email
                == email
            )
            .first()
        )

        if existing_email:
            raise HTTPException(
                status_code=
                    status.HTTP_409_CONFLICT,
                detail=(
                    "Email already exists"
                ),
            )

    # -----------------------------------------------------
    # HASH PASSWORD
    # -----------------------------------------------------

    password_hash = (
        hash_password(
            payload.password
        )
    )

    # -----------------------------------------------------
    # CREATE
    # -----------------------------------------------------

    user = User(
        name=
            payload.name.strip(),

        username=
            username,

        email=
            email,

        password_hash=
            password_hash,

        role=
            payload.role.strip().upper(),

        is_active=
            payload.is_active,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


# =========================================================
# UPDATE USER
# =========================================================

@router.put(
    "/{user_id}",
    response_model=
        AdminUserResponse,
)
def update_admin_user(
    user_id: int,
    payload: AdminUserUpdate,
    db: Session = Depends(get_db),
):
    user = get_user_or_404(
        db,
        user_id,
    )

    # -----------------------------------------------------
    # NAME
    # -----------------------------------------------------

    if payload.name is not None:
        user.name = (
            payload.name.strip()
        )

    # -----------------------------------------------------
    # USERNAME
    # -----------------------------------------------------

    if (
        payload.username
        is not None
    ):
        username = (
            normalize_username(
                payload.username
            )
        )

        duplicate_username = (
            db.query(User)
            .filter(
                User.id != user_id,
                User.username
                == username,
            )
            .first()
        )

        if duplicate_username:
            raise HTTPException(
                status_code=
                    status.HTTP_409_CONFLICT,
                detail=(
                    "Username already exists"
                ),
            )

        user.username = (
            username
        )

    # -----------------------------------------------------
    # EMAIL
    # -----------------------------------------------------

    if (
        "email"
        in payload.model_fields_set
    ):
        email = (
            normalize_email(
                payload.email
            )
        )

        if email:
            duplicate_email = (
                db.query(User)
                .filter(
                    User.id != user_id,
                    User.email
                    == email,
                )
                .first()
            )

            if duplicate_email:
                raise HTTPException(
                    status_code=
                        status.HTTP_409_CONFLICT,
                    detail=(
                        "Email already exists"
                    ),
                )

        user.email = email

    # -----------------------------------------------------
    # ROLE
    # -----------------------------------------------------

    if payload.role is not None:
        new_role = (
            payload.role
            .strip()
            .upper()
        )

        if new_role != user.role:
            links = get_user_links(
                db,
                user.id,
            )

            if (
                has_teacher_links(
                    links
                )
                and
                new_role != "TEACHER"
            ):
                raise HTTPException(
                    status_code=
                        status.HTTP_409_CONFLICT,
                    detail=(
                        "This user is linked "
                        "to teacher records. "
                        "Remove teacher links "
                        "before changing role."
                    ),
                )

            if (
                has_parent_links(
                    links
                )
                and
                new_role != "PARENT"
            ):
                raise HTTPException(
                    status_code=
                        status.HTTP_409_CONFLICT,
                    detail=(
                        "This user is linked "
                        "to parent records. "
                        "Remove parent links "
                        "before changing role."
                    ),
                )

        user.role = new_role

    # -----------------------------------------------------
    # STATUS
    # -----------------------------------------------------

    if (
        payload.is_active
        is not None
    ):
        user.is_active = (
            payload.is_active
        )

    db.commit()
    db.refresh(user)

    return user


# =========================================================
# UPDATE STATUS
# =========================================================

@router.patch(
    "/{user_id}/status",
    response_model=
        AdminUserResponse,
)
def update_admin_user_status(
    user_id: int,
    payload:
        AdminUserStatusUpdate,
    db: Session = Depends(get_db),
):
    user = get_user_or_404(
        db,
        user_id,
    )

    user.is_active = (
        payload.is_active
    )

    db.commit()
    db.refresh(user)

    return user


# =========================================================
# RESET PASSWORD
# =========================================================

@router.patch(
    "/{user_id}/password",
)
def reset_admin_user_password(
    user_id: int,
    payload:
        AdminUserPasswordReset,
    db: Session = Depends(get_db),
):
    user = get_user_or_404(
        db,
        user_id,
    )

    user.password_hash = (
        hash_password(
            payload.new_password
        )
    )

    db.commit()

    return {
        "message":
            "Password reset successfully"
    }


# =========================================================
# DELETE USER
# =========================================================

@router.delete(
    "/{user_id}",
)
def delete_admin_user(
    user_id: int,
    db: Session = Depends(get_db),
):
    user = get_user_or_404(
        db,
        user_id,
    )

    links = get_user_links(
        db,
        user.id,
    )

    # -----------------------------------------------------
    # TEACHER LINK PROTECTION
    # -----------------------------------------------------

    if has_teacher_links(
        links
    ):
        raise HTTPException(
            status_code=
                status.HTTP_409_CONFLICT,
            detail=(
                "This user is linked to "
                "teacher records. "
                "Deactivate the user "
                "instead of deleting."
            ),
        )

    # -----------------------------------------------------
    # PARENT LINK PROTECTION
    # -----------------------------------------------------

    if has_parent_links(
        links
    ):
        raise HTTPException(
            status_code=
                status.HTTP_409_CONFLICT,
            detail=(
                "This user is linked to "
                "parent records. "
                "Deactivate the user "
                "instead of deleting."
            ),
        )

    db.delete(user)
    db.commit()

    return {
        "message":
            "User deleted successfully"
    }