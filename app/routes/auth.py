from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
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
    # -----------------------------------------------------
    # 1. Clean username
    # -----------------------------------------------------
    username = payload.username.strip()

    # -----------------------------------------------------
    # 2. Find user
    # -----------------------------------------------------
    user = (
        db.query(User)
        .filter(User.username == username)
        .first()
    )

    # -----------------------------------------------------
    # 3. Check user exists
    # -----------------------------------------------------
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    # -----------------------------------------------------
    # 4. Check password
    # -----------------------------------------------------
    if not verify_password(
        payload.password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    # -----------------------------------------------------
    # 5. Check account active
    # -----------------------------------------------------
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    # -----------------------------------------------------
    # 6. Check selected role
    # -----------------------------------------------------
    selected_role = payload.role.strip().upper()

    user_role = user.role.strip().upper()

    if user_role != selected_role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"This account is not a "
                f"{selected_role.lower()} account"
            ),
        )

    # -----------------------------------------------------
    # 7. Generate JWT token
    # -----------------------------------------------------
    access_token = create_access_token(
        {
            "sub": str(user.id),
            "role": user_role,
            "username": user.username,
        }
    )

    # -----------------------------------------------------
    # 8. Return login response
    # -----------------------------------------------------
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
    current_user: User = Depends(get_current_user),
):
    return current_user