import os
import threading
import time
from collections import deque

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    status,
)
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.database import get_db

from app.models.user import User
from app.models.student import Student
from app.models.parent_profile import ParentProfile
from app.models.parent_student import ParentStudent
from app.models.teacher_profile import TeacherProfile

from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    UserResponse,
)

from app.core.security import (
    verify_password,
    hash_password,
    create_access_token,
)

from app.dependencies import get_current_user


router = APIRouter(
    prefix="/api/v1/auth",
    tags=["Authentication"],
)


# Login throttling is intentionally dependency-free so it is active in every
# deployment. It limits both the normalized account/role tuple and the client
# address. State is per API process; deployments with multiple API workers
# should additionally enforce a shared limit at nginx/Redis.
_login_attempts: dict[str, deque[float]] = {}
_login_blocked_until: dict[str, float] = {}
_login_attempt_lock = threading.Lock()


def _positive_int_env(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def _login_keys(request: Request, username: str, role: str) -> tuple[str, str]:
    client_ip = request.client.host if request.client else "unknown"
    account_key = f"account:{role.lower()}:{username.strip().lower()}"
    return account_key, f"ip:{client_ip}"


def _prune_attempts(key: str, now: float, window_seconds: int) -> deque[float]:
    attempts = _login_attempts.setdefault(key, deque())
    cutoff = now - window_seconds
    while attempts and attempts[0] <= cutoff:
        attempts.popleft()
    return attempts


def _check_login_allowed(keys: tuple[str, str]) -> None:
    now = time.monotonic()
    retry_after = 0
    with _login_attempt_lock:
        for key in keys:
            blocked_until = _login_blocked_until.get(key, 0)
            if blocked_until > now:
                retry_after = max(retry_after, int(blocked_until - now) + 1)
            elif blocked_until:
                _login_blocked_until.pop(key, None)
    if retry_after:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Try again later.",
            headers={"Retry-After": str(retry_after)},
        )


def _record_failed_login(keys: tuple[str, str]) -> None:
    now = time.monotonic()
    window_seconds = _positive_int_env("LOGIN_ATTEMPT_WINDOW_SECONDS", 300)
    lockout_seconds = _positive_int_env("LOGIN_LOCKOUT_SECONDS", 900)
    thresholds = (
        _positive_int_env("LOGIN_MAX_FAILED_ATTEMPTS", 5),
        _positive_int_env("LOGIN_MAX_FAILED_ATTEMPTS_PER_IP", 25),
    )
    with _login_attempt_lock:
        for key, threshold in zip(keys, thresholds):
            attempts = _prune_attempts(key, now, window_seconds)
            attempts.append(now)
            if len(attempts) >= threshold:
                _login_blocked_until[key] = now + lockout_seconds


def _clear_failed_logins(keys: tuple[str, str]) -> None:
    with _login_attempt_lock:
        for key in keys:
            _login_attempts.pop(key, None)
            _login_blocked_until.pop(key, None)


def _reset_login_limiter_for_tests() -> None:
    """Reset process-local state; used only by isolated automated tests."""
    with _login_attempt_lock:
        _login_attempts.clear()
        _login_blocked_until.clear()


# =========================================================
# DOB PASSWORD HELPER
# Accepts the common day-first and ISO date formats so a
# parent or teacher can authenticate with their date of
# birth.
# =========================================================
def dob_password_matches(
    password: str,
    date_of_birth,
) -> bool:
    valid_dob_passwords = {
        date_of_birth.strftime(
            "%d%m%Y"
        ),
        date_of_birth.strftime(
            "%d-%m-%Y"
        ),
        date_of_birth.strftime(
            "%d/%m/%Y"
        ),
        date_of_birth.strftime(
            "%Y-%m-%d"
        ),
    }

    return (
        password.strip()
        in valid_dob_passwords
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
    request: Request,
    db: Session = Depends(get_db),
):
    username = payload.username.strip()

    selected_role = (
        payload.role
        .strip()
        .upper()
    )
    login_keys = _login_keys(request, username, selected_role)
    _check_login_allowed(login_keys)

    user = None
    login_student = None
    parent_link_created = False

    # -----------------------------------------------------
    # PARENT LOGIN USING STUDENT ADMISSION NUMBER
    # -----------------------------------------------------
    if selected_role == "PARENT":

        login_student = (
            db.query(Student)
            .filter(
                func.lower(
                    Student.admission_no
                )
                == username.lower()
            )
            .first()
        )

        if login_student:

            # Only a link to a real parent account is valid for parent login.
            # Legacy data can contain an earlier teacher/admin link for the
            # same student; selecting that row caused a misleading 403.
            user = (
                db.query(User)
                .join(
                    ParentStudent,
                    ParentStudent.parent_user_id
                    == User.id,
                )
                .filter(
                    ParentStudent.student_id
                    == login_student.id,
                    func.upper(User.role)
                    == "PARENT",
                )
                .order_by(
                    ParentStudent.id.asc()
                )
                .first()
            )

            # Some students predate automatic parent-account creation. If
            # the admission number and DOB are both correct, repair that
            # missing account/link as part of the login transaction.
            if user is None and (
                login_student.date_of_birth
                and dob_password_matches(
                    payload.password,
                    login_student.date_of_birth,
                )
            ):
                parent_username = (
                    f"PARENT_{login_student.admission_no}"
                )

                candidate_user = (
                    db.query(User)
                    .filter(
                        func.lower(User.username)
                        == parent_username.lower()
                    )
                    .first()
                )

                if (
                    candidate_user is None
                ):
                    candidate_user = User(
                        name=(
                            "Parent of "
                            f"{login_student.full_name}"
                        ),
                        username=parent_username,
                        email=None,
                        password_hash=hash_password(
                            login_student.date_of_birth.strftime(
                                "%d%m%Y"
                            )
                        ),
                        role="PARENT",
                        is_active=True,
                    )
                    db.add(candidate_user)
                    db.flush()

                    db.add(
                        ParentProfile(
                            user_id=candidate_user.id,
                        )
                    )

                elif not (
                    db.query(ParentProfile)
                    .filter(
                        ParentProfile.user_id
                        == candidate_user.id
                    )
                    .first()
                ):
                    db.add(
                        ParentProfile(
                            user_id=candidate_user.id,
                        )
                    )

                if (
                    candidate_user.role.strip().upper()
                    == "PARENT"
                ):
                    db.add(
                        ParentStudent(
                            parent_user_id=candidate_user.id,
                            student_id=login_student.id,
                            relationship="Guardian",
                        )
                    )
                    db.flush()
                    user = candidate_user
                    parent_link_created = True

    # -----------------------------------------------------
    # TEACHER LOGIN USING EMPLOYEE ID / USERNAME / EMAIL
    # -----------------------------------------------------
    if selected_role == "TEACHER":
        user = (
            db.query(User)
            .join(
                TeacherProfile,
                TeacherProfile.user_id == User.id,
            )
            .filter(
                func.upper(User.role) == "TEACHER",
                or_(
                    func.lower(User.username)
                    == username.lower(),
                    func.lower(TeacherProfile.employee_id)
                    == username.lower(),
                    func.lower(User.email)
                    == username.lower(),
                ),
            )
            .first()
        )

    # -----------------------------------------------------
    # NORMAL LOGIN
    # Admin / Teacher / Existing Parent Username
    # -----------------------------------------------------
    if (
        user is None
        and not (
            selected_role == "PARENT"
            and login_student is not None
        )
    ):

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
        _record_failed_login(login_keys)
        raise HTTPException(
            status_code=
                status.HTTP_401_UNAUTHORIZED,
            detail=
                "Invalid username or password",
        )

    # -----------------------------------------------------
    # PASSWORD
    # Parent admission-number logins use the matched student's DOB and teacher
    # logins use the teacher's DOB. A changed password (stored hash) keeps
    # matching too, so resetting a parent/teacher password never locks them
    # out of their new password.
    # -----------------------------------------------------
    password_is_valid = False

    if (
        selected_role == "PARENT"
        and login_student is not None
        and login_student.date_of_birth
    ):
        password_is_valid = (
            dob_password_matches(
                payload.password,
                login_student.date_of_birth,
            )
        )

    if (
        not password_is_valid
        and selected_role == "TEACHER"
        and user is not None
    ):
        teacher_profile = (
            db.query(TeacherProfile)
            .filter(
                TeacherProfile.user_id
                == user.id
            )
            .first()
        )

        if (
            teacher_profile
            and teacher_profile.date_of_birth
        ):
            password_is_valid = (
                dob_password_matches(
                    payload.password,
                    teacher_profile.date_of_birth,
                )
            )

    if not password_is_valid:
        password_is_valid = verify_password(
            payload.password,
            user.password_hash,
        )

    if not password_is_valid:
        _record_failed_login(login_keys)
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

    _clear_failed_logins(login_keys)

    if parent_link_created:
        db.commit()

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
