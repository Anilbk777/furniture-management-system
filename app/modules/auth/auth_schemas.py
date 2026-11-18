import re
import uuid
from datetime import datetime

from typing import Annotated,Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

_PASSWORD_RULES = [
    (r"[A-Z]", "uppercase letter"),
    (r"[a-z]", "lowercase letter"),
    (r"\d", "number"),
    (r"[^\w\s]|_", "special character"),
]


def _strong_password(value: str) -> str:
    for pattern, label in _PASSWORD_RULES:
        if not re.search(pattern, value):
            raise ValueError(f"Password must contain at least one {label}")
    return value


Password = Annotated[
    str, Field(min_length=8, max_length=120), AfterValidator(_strong_password)
]


def validate_phone(value: str) -> str:
    if not value.isascii() or not value.isdigit() or len(value) != 10:
        raise ValueError("Phone number must contain exactly 10 digits")
    return value


def disallow_null(value: str | None) -> str:
    if value is None:
        raise ValueError("Field cannot be null")
    return value

PhoneStr = Annotated[str, AfterValidator(validate_phone)]
NonNullPhoneStr = Annotated[
    str | None, AfterValidator(disallow_null), AfterValidator(validate_phone)
]


class UserBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(title="Name", min_length=1, max_length=100)
    phone: PhoneStr = Field(title="Phone")
    email: EmailStr = Field(title="Email", max_length=120)

    @field_validator("email", check_fields=False)
    @classmethod
    def _normalize_email(cls, v: str | None) -> str | None:
        return v.lower() if v is not None else v


class UserCreate(UserBase):
    password: Password 



class UserUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(default=None, title="Name", min_length=1, max_length=100)
    phone: NonNullPhoneStr = Field(default=None, title="Phone")
    email: Annotated[EmailStr | None, AfterValidator(disallow_null)] = Field(
        default=None, title="Email", max_length=120
    )
    @field_validator("email", check_fields=False)
    @classmethod
    def _normalize_email(cls, v: str | None) -> str | None:
        return v.lower() if v is not None else v


class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: str
    is_active: bool
    must_change_password: bool = False
    email_verified_at: datetime | None = None

class OrganizationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    is_active: bool

class UserOrganizationInfo(UserResponse):
    organization: OrganizationResponse | None = None


class LoginRequest(BaseModel):
    identifier: str = Field(
        title="Phone or Email", max_length=255, description="Phone number or email"
    )
    password: str = Field(title="Password", min_length=1, max_length=120)

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


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    code: str = Field(title="code", pattern=r"^\d{6}$")


class ResendOtpRequest(BaseModel):
    email: EmailStr


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    new_password: Password

class ChangePasswordRequest(BaseModel):
    """current_password is only required once a real password has been set."""

    current_password: str | None = Field(None, max_length=128)
    new_password: Password

    @model_validator(mode="after")
    def _must_differ(self) -> Self:
        if self.current_password == self.new_password:
            raise ValueError("New password must be different from the current one")
        return self