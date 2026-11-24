from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import UserRole


class UserLogin(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class UserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    username: str = Field(min_length=3, max_length=100)
    full_name: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    role: UserRole = UserRole.ANALYST


class UserOut(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    email: str
    username: str
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str | None = None
    role: str | None = None
