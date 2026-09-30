from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.orm import Session

from app.database import get_db

from app.models.user import User
from app.models.student import Student
from app.models.parent_student import ParentStudent

from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    UserResponse,
)

from app.core.security import (
    verify_password,
    create_access_token,
)

from app.dependencies import get_current_user


router = APIRouter(
    prefix="/api/v1/auth",
    tags=["Authentication"],
)


# =========================================================
# LOGIN
# POST /api/v1/auth/login
# =========================================================
@router.post(
    "/login",
    response_model=LoginResponse,
)
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
):
    username = payload.username.strip()

    selected_role = (
        payload.role
        .strip()
        .upper()
    )

    user = None

    # -----------------------------------------------------
    # PARENT LOGIN USING STUDENT ADMISSION NUMBER
    # -----------------------------------------------------
    if selected_role == "PARENT":

        student = (
            db.query(Student)
            .filter(
                Student.admission_no == username
            )
            .first()
        )

        if student:

            parent_link = (
                db.query(ParentStudent)
                .filter(
                    ParentStudent.student_id
                    == student.id
                )
                .order_by(
                    ParentStudent.id.asc()
                )
                .first()
            )

            if parent_link:

                user = (
                    db.query(User)
                    .filter(
                        User.id
                        == parent_link.parent_user_id
                    )
                    .first()
                )

    # -----------------------------------------------------
    # NORMAL LOGIN
    # Admin / Teacher / Existing Parent Username
    # -----------------------------------------------------
    if user is None:

        user = (
            db.query(User)
            .filter(
                User.username == username
            )
            .first()
        )

    # -----------------------------------------------------
    # USER EXISTS
    # -----------------------------------------------------
    if not user:
        raise HTTPException(
            status_code=
                status.HTTP_401_UNAUTHORIZED,
            detail=
                "Invalid username or password",
        )

    # -----------------------------------------------------
    # PASSWORD
    # -----------------------------------------------------
    if not verify_password(
        payload.password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=
                status.HTTP_401_UNAUTHORIZED,
            detail=
                "Invalid username or password",
        )

    # -----------------------------------------------------
    # ACTIVE STATUS
    # -----------------------------------------------------
    if not user.is_active:
        raise HTTPException(
            status_code=
                status.HTTP_403_FORBIDDEN,
            detail=
                "User account is inactive",
        )

    # -----------------------------------------------------
    # ROLE
    # -----------------------------------------------------
    user_role = (
        user.role
        .strip()
        .upper()
    )

    if user_role != selected_role:
        raise HTTPException(
            status_code=
                status.HTTP_403_FORBIDDEN,
            detail=(
                f"This account is not a "
                f"{selected_role.lower()} account"
            ),
        )

    # -----------------------------------------------------
    # JWT
    # -----------------------------------------------------
    access_token = create_access_token(
        {
            "sub": str(user.id),
            "role": user_role,
            "username": user.username,
        }
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user,
    }


# =========================================================
# CURRENT LOGGED-IN USER
# GET /api/v1/auth/me
# =========================================================
@router.get(
    "/me",
    response_model=UserResponse,
)
def get_me(
    current_user: User = Depends(
        get_current_user
    ),
):
    return current_user