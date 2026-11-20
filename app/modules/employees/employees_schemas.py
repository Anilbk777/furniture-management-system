import datetime as dt
from decimal import Decimal
from typing import Annotated, Self
import uuid
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.helper.base import BS_DATE_REGEX
from app.utils.response import Pagination

# BS date as text, e.g. "2080-01-15" (the frontend date picker sends this)
BsDate = Annotated[str, Field(pattern=BS_DATE_REGEX, examples=["2080-01-15"])]


class EmployeeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    phone: str | None = Field(None, max_length=20)
    role_title: str | None = Field(None, max_length=80)
    monthly_salary: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=2)
    joined_date_bs: BsDate | None = None
    note: str | None = None


class EmployeeUpdate(BaseModel):
    """PATCH: send only the fields you want to change."""

    name: str | None = Field(None, min_length=1, max_length=120)
    phone: str | None = Field(None, max_length=20)
    role_title: str | None = Field(None, max_length=80)
    monthly_salary: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=2)
    joined_date_bs: BsDate | None = None
    is_active: bool | None = None  # False = left the job
    note: str | None = None

    @model_validator(mode="after")
    def required_fields_not_null(self) -> Self:
        for field in ("name", "is_active"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class EmployeeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    phone: str | None
    role_title: str | None
    monthly_salary: Decimal | None
    joined_date_bs: str | None
    is_active: bool
    note: str | None
    created_at: dt.datetime
    updated_at: dt.datetime

class EmployeeList(BaseModel):
    employees: list[EmployeeRead]
    pagination: Pagination


class EmployeeOverview(BaseModel):
    """Headline numbers for the employees dashboard card."""

    total: int
    active: int
    inactive: int
    active_salary_total: Decimal
    inactive_salary_total: Decimal