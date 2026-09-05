from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str
    role: str


class UserResponse(BaseModel):
    id: int
    name: str
    username: str
    email: str | None = None
    role: str

    class Config:
        from_attributes = True


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse