import re
import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(title="Name", min_length=1, max_length=100)
    phone: str = Field(title="Phone")
    email: EmailStr | None = Field(
        default=None, title="Email", max_length=120
    )  # Setting default=None makes the field optional AND defaults to None


class UserCreate(UserBase):
    password: str = Field(title="Password", min_length=8, max_length=120)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        if not re.search(r"[A-Z]", value):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", value):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", value):
            raise ValueError("Password must contain at least one number")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>_\-+=\[\]\\/'~`;]", value):
            raise ValueError("Password must contain at least one special character")
        return value


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, title="Name", min_length=1, max_length=100)
    phone: str | None = Field(default=None, title="Phone")
    email: EmailStr | None = Field(
        default=None, title="Email", max_length=120
    )  # Setting default=None makes the field optional AND defaults to None


class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: str
    is_active: bool


class LoginRequest(BaseModel):
    identifier: str = Field(title="Phone or Email",max_length=255, description="Phone number or email")
    password: str = Field(title="Password",min_length=1, max_length=120)

    @field_validator("identifier")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class LoginOut(BaseModel):
    user: UserResponse
    tokens: TokenPair | None = None  # only filled for mobile clients


class RefreshRequest(BaseModel):
    """Mobile sends the refresh token here; the web app uses the cookie instead."""

    refresh_token: str | None = None