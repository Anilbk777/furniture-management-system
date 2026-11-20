import datetime as dt
import uuid
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ...utils.response import Pagination


# ------------------------------------------------------------------ party types
class PartyTypeCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=60)


class PartyTypeUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=60)


class PartyTypeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str


# --------------------------------------------------------------------- parties
class PartyCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=120)
    phone: str | None = Field(None, max_length=20)
    address: str | None = Field(None, max_length=255)
    party_type_id: uuid.UUID
    note: str | None = None

    @field_validator("phone")
    @classmethod
    def validate_phone_digits(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        if not value.isdigit():
            raise ValueError("Phone number must contain only digits")
        return value


class PartyUpdate(BaseModel):
    """PATCH: send only the fields you want to change."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(None, min_length=1, max_length=120)
    phone: str | None = Field(None, max_length=20)
    address: str | None = Field(None, max_length=255)
    party_type_id: uuid.UUID | None = None
    is_active: bool | None = None
    note: str | None = None

    @field_validator("phone")
    @classmethod
    def validate_phone_digits(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        if not value.isdigit():
            raise ValueError("Phone number must contain only digits")
        return value

    @model_validator(mode="after")
    def required_fields_not_null(self) -> Self:
        for field in ("name", "party_type_id", "is_active"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class PartyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    phone: str | None
    address: str | None
    party_type: PartyTypeRead
    is_active: bool
    note: str | None
    created_at: dt.datetime
    updated_at: dt.datetime


class PartyList(BaseModel):
    parties: list[PartyRead]
    pagination: Pagination


class PartyOverview(BaseModel):
    """Headline numbers for the parties screens."""

    total: int
    active: int
    inactive: int
