from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
)


# =========================================================
# CREATE USER
# =========================================================

class AdminUserCreate(BaseModel):
    name: str = Field(
        ...,
        min_length=2,
        max_length=150,
    )

    username: str = Field(
        ...,
        min_length=3,
        max_length=100,
    )

    email: EmailStr | None = None

    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
    )

    role: str

    is_active: bool = True

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str):
        role = value.strip().upper()

        allowed_roles = {
            "ADMIN",
            "TEACHER",
            "PARENT",
        }

        if role not in allowed_roles:
            raise ValueError(
                "Role must be ADMIN, TEACHER or PARENT"
            )

        return role


# =========================================================
# UPDATE USER
# =========================================================

class AdminUserUpdate(BaseModel):
    name: str | None = Field(
        default=None,
        min_length=2,
        max_length=150,
    )

    username: str | None = Field(
        default=None,
        min_length=3,
        max_length=100,
    )

    email: EmailStr | None = None

    role: str | None = None

    is_active: bool | None = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, value):
        if value is None:
            return value

        role = value.strip().upper()

        allowed_roles = {
            "ADMIN",
            "TEACHER",
            "PARENT",
        }

        if role not in allowed_roles:
            raise ValueError(
                "Role must be ADMIN, TEACHER or PARENT"
            )

        return role


# =========================================================
# STATUS
# =========================================================

class AdminUserStatusUpdate(BaseModel):
    is_active: bool


# =========================================================
# RESET PASSWORD
# =========================================================

class AdminUserPasswordReset(BaseModel):
    new_password: str = Field(
        ...,
        min_length=8,
        max_length=128,
    )


# =========================================================
# RESPONSE
# =========================================================

class AdminUserResponse(BaseModel):
    id: int

    name: str
    username: str
    email: str | None = None

    role: str
    is_active: bool | None = None

    created_at: datetime | None = None

    model_config = ConfigDict(
        from_attributes=True
    )