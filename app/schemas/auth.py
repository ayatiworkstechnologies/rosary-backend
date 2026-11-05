from pydantic import BaseModel, ConfigDict


class LoginRequest(BaseModel):
    username: str
    password: str
    role: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    username: str
    email: str | None = None
    role: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse
