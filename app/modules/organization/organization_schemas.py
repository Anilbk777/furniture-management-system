import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict, Field


class OrganizationCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=120)  # the furniture shop's name


class OrganizationUpdate(BaseModel):
    """PATCH: send only the fields you want to change."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(None, min_length=1, max_length=120)


class OrganizationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    is_active: bool
    created_at: dt.datetime
    updated_at: dt.datetime
