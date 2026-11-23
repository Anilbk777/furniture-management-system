import math
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Self

from app.modules.attendance.attendance_types import BsDate, Hours, Time12, TotalHours
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Pagination(BaseModel):  # use your shared Pagination if you have one
    total: int
    page: int
    limit: int
    total_pages: int

    @classmethod
    def build(cls, *, total: int, page: int, limit: int) -> "Pagination":
        return cls(
            total=total, page=page, limit=limit, total_pages=math.ceil(total / limit)
        )


# ---------- requests ----------
class AttendanceCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    employee_id: uuid.UUID
    bs_date: BsDate
    status: str = Field(
        min_length=1, max_length=20
    )  # present | half_day | absent | leave
    check_in: Time12 | None = None
    check_out: Time12 | None = None
    overtime_hours: Hours = Decimal("0")
    note: str | None = Field(None, max_length=500)


class AttendanceUpdate(BaseModel):
    """PATCH: send only what changes. The final combination is re-validated by the service.
    Send check_in / check_out / note as null to clear them. The employee can't be changed."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    bs_date: BsDate | None = None
    status: str | None = Field(None, min_length=1, max_length=20)
    check_in: Time12 | None = None
    check_out: Time12 | None = None
    overtime_hours: Hours | None = None
    note: str | None = Field(None, max_length=500)

    @model_validator(mode="after")
    def required_fields_not_null(self) -> Self:
        for field in ("bs_date", "status", "overtime_hours"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


# ---------- responses ----------
class AttendanceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    employee_id: uuid.UUID
    employee_name: str
    bs_date: str
    status: str
    check_in: Time12 | None
    check_out: Time12 | None
    overtime_hours: Hours
    note: str | None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AttendanceList(BaseModel):
    attendances: list[AttendanceRead]
    pagination: Pagination


class EmployeeDayAttendance(BaseModel):
    """One employee plus their attendance for a single BS date (nulls = not marked)."""

    employee_id: uuid.UUID
    attendance_id: uuid.UUID | None
    name: str
    role: str | None
    phone: str | None
    status: str | None
    bs_date: str
    check_in: Time12 | None
    check_out: Time12 | None
    overtime_hours: Hours
    note: str | None = None


class TodayAttendanceList(BaseModel):
    bs_date: str  # today's BS date, the day this roster covers
    employees: list[EmployeeDayAttendance]
    pagination: Pagination


class EmployeeBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str


class EmployeeAttendanceSummary(BaseModel):
    # employee: EmployeeBrief
    from_date: str
    to_date: str
    total_days: int  # calendar days in the range, both ends included
    recorded_days: int  # days that have an attendance record
    unmarked_days: (
        int  # total_days - recorded_days (weekly offs and holidays land here too)
    )
    present: int
    half_day: int
    absent: int
    leave: int
    worked_days: float  # present + half_day / 2
    total_overtime_hours: TotalHours


class EmployeeAttendanceDetails(BaseModel):
    employee: EmployeeBrief
    from_date: str
    to_date: str
    total_records: int
    summary: EmployeeAttendanceSummary
    records: list[AttendanceRead]  # oldest day first
