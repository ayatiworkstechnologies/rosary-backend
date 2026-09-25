from pydantic import (
    BaseModel,
    EmailStr,
    Field,
)


# =========================================================
# CREATE PARENT
# =========================================================

class AdminParentCreate(BaseModel):
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

    phone: str | None = Field(
        default=None,
        max_length=30,
    )

    alternate_phone: str | None = Field(
        default=None,
        max_length=30,
    )

    occupation: str | None = Field(
        default=None,
        max_length=150,
    )

    address: str | None = None

    city: str | None = Field(
        default=None,
        max_length=100,
    )

    state: str | None = Field(
        default=None,
        max_length=100,
    )

    pincode: str | None = Field(
        default=None,
        max_length=20,
    )

    profile_image_url: str | None = Field(
        default=None,
        max_length=500,
    )

    is_active: bool = True


# =========================================================
# UPDATE PARENT
# =========================================================

class AdminParentUpdate(BaseModel):
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

    phone: str | None = Field(
        default=None,
        max_length=30,
    )

    alternate_phone: str | None = Field(
        default=None,
        max_length=30,
    )

    occupation: str | None = Field(
        default=None,
        max_length=150,
    )

    address: str | None = None

    city: str | None = Field(
        default=None,
        max_length=100,
    )

    state: str | None = Field(
        default=None,
        max_length=100,
    )

    pincode: str | None = Field(
        default=None,
        max_length=20,
    )

    profile_image_url: str | None = Field(
        default=None,
        max_length=500,
    )


# =========================================================
# STATUS
# =========================================================

class AdminParentStatusUpdate(BaseModel):
    is_active: bool


# =========================================================
# PASSWORD
# =========================================================

class AdminParentPasswordUpdate(BaseModel):
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
    )