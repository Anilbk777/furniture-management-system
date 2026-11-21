"""Business rules for staff attendance."""

import uuid
from collections.abc import Sequence
from datetime import time
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.exceptions import (
    BadRequestException,
    ConflictException,
    NotFoundException,
)
from app.utils.logger import get_logger

from .attendance_models import Attendance
from .attendance_repository import AttendanceRepository
from .attendance_schemas import (
    AttendanceCreate,
    AttendanceUpdate,
    EmployeeAttendanceSummary,
)
from .attendance_types import (
    MAX_RANGE_DAYS,
    NO_WORK_STATUSES,
    STATUSES,
    bs_days_between,
)

logger = get_logger(__name__)


def normalize_status(value: str) -> str:
    """'Half Day', 'half-day' and 'HALF_DAY' all become 'half_day'."""
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def check_attendance(
    status: str, check_in: time | None, check_out: time | None, overtime_hours: Decimal
) -> str | None:
    """Rules for the FINAL combination of values. Returns an error message or None."""
    if status not in STATUSES:
        return f"Status must be one of: {', '.join(STATUSES)}"
    if status in NO_WORK_STATUSES and (check_in or check_out or overtime_hours > 0):
        return "Absent and leave days can't have check-in, check-out or overtime"
    if check_out and not check_in:
        return "Check-out needs a check-in time"
    if check_in and check_out and check_out <= check_in:
        return "Check-out must be after check-in"
    return None


def check_range(from_date: str, to_date: str) -> int:
    """Returns the number of days in the range (both ends included)."""
    if from_date > to_date:  # zero-padded BS dates compare correctly as text
        raise BadRequestException(message="From date must not be after to date")
    days = bs_days_between(from_date, to_date) + 1
    if days > MAX_RANGE_DAYS:
        raise BadRequestException(
            message=f"Date range can't be longer than {MAX_RANGE_DAYS} days"
        )
    return days


class AttendanceService:
    def __init__(self, session: AsyncSession, repo: AttendanceRepository):
        self.session = session
        self.repo = repo

    # ---------- helpers ----------
    async def _employee(
        self,
        org_id: uuid.UUID,
        employee_id: uuid.UUID,
        *,
        include_deleted: bool = False,
    ):
        employee = await self.repo.get_employee(
            org_id, employee_id, include_deleted=include_deleted
        )
        if not employee:
            raise NotFoundException(message="Employee not found")
        return employee

    @staticmethod
    def _validate(status: str, check_in, check_out, overtime_hours) -> None:
        if error := check_attendance(status, check_in, check_out, overtime_hours):
            raise BadRequestException(message=error)

    # ---------- CRUD ----------
    async def create(self, org_id: uuid.UUID, data: AttendanceCreate) -> Attendance:
        employee = await self._employee(
            org_id, data.employee_id
        )  # deleted employees can't be marked
        status = normalize_status(data.status)
        self._validate(status, data.check_in, data.check_out, data.overtime_hours)

        if await self.repo.get_by_employee_date(org_id, employee.id, data.bs_date):
            raise ConflictException(
                message=f"Attendance for {employee.name} on {data.bs_date} already exists"
            )
        try:
            record = await self.repo.create(
                org_id,
                employee,
                bs_date=data.bs_date,
                status=status,
                check_in=data.check_in,
                check_out=data.check_out,
                overtime_hours=data.overtime_hours,
                note=data.note,
            )
            await self.session.commit()
        except IntegrityError:  # two identical requests at the same moment
            await self.session.rollback()
            raise ConflictException(
                message=f"Attendance for {employee.name} on {data.bs_date} already exists"
            )
        except Exception:
            await self.session.rollback()
            logger.exception(
                "Failed to create attendance org=%s employee=%s", org_id, employee.id
            )
            raise
        logger.info(
            "Attendance created id=%s employee=%s date=%s",
            record.id,
            employee.id,
            data.bs_date,
        )
        return await self.get(
            org_id, record.id
        )  # reload: employee + server-set timestamps

    async def get(self, org_id: uuid.UUID, attendance_id: uuid.UUID) -> Attendance:
        record = await self.repo.get(org_id, attendance_id)
        if not record:
            raise NotFoundException(message="Attendance record not found")
        return record

    async def list(
        self,
        org_id: uuid.UUID,
        *,
        employee_id: uuid.UUID | None,
        status: str | None,
        from_date: str | None,
        to_date: str | None,
        page: int,
        limit: int,
    ) -> tuple[Sequence[Attendance], int]:
        if from_date and to_date:
            check_range(from_date, to_date)
        return await self.repo.list(
            org_id,
            employee_id=employee_id,
            status=normalize_status(status) if status else None,
            from_date=from_date,
            to_date=to_date,
            page=page,
            limit=limit,
        )

    async def update(
        self, org_id: uuid.UUID, attendance_id: uuid.UUID, data: AttendanceUpdate
    ) -> Attendance:
        record = await self.get(org_id, attendance_id)
        values = data.model_dump(exclude_unset=True)  # only what the client sent
        if not values:
            return record
        if "status" in values:
            values["status"] = normalize_status(values["status"])

        # Validate the FINAL combination (existing row + the changes), same rules as create
        final = {
            f: values.get(f, getattr(record, f))
            for f in ("status", "check_in", "check_out", "overtime_hours")
        }
        self._validate(**final)

        new_date = values.get("bs_date")
        if new_date and new_date != record.bs_date:
            if await self.repo.get_by_employee_date(
                org_id, record.employee_id, new_date
            ):
                raise ConflictException(
                    message=f"Attendance for {record.employee_name} on {new_date} already exists"
                )
        try:
            await self.repo.update(record, values)
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            raise ConflictException(
                message="Attendance for this employee on this date already exists"
            )
        except Exception:
            await self.session.rollback()
            logger.exception(
                "Failed to update attendance %s org=%s", attendance_id, org_id
            )
            raise
        logger.info("Attendance updated id=%s fields=%s", attendance_id, sorted(values))
        return await self.get(org_id, attendance_id)

    async def delete(self, org_id: uuid.UUID, attendance_id: uuid.UUID) -> None:
        """Permanent delete."""
        record = await self.get(org_id, attendance_id)
        summary = (record.employee_id, record.bs_date, record.status)
        try:
            await self.repo.delete(record)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            logger.exception(
                "Failed to delete attendance %s org=%s", attendance_id, org_id
            )
            raise
        logger.info(
            "Attendance permanently deleted id=%s employee=%s date=%s status=%s",
            attendance_id,
            *summary,
        )

    # ---------- one employee over a date range ----------
    async def employee_details(
        self, org_id: uuid.UUID, employee_id: uuid.UUID, from_date: str, to_date: str
    ):
        """Every attendance record of the employee between the two BS dates, oldest first."""
        check_range(from_date, to_date)
        employee = await self._employee(
            org_id, employee_id, include_deleted=True
        )  # history stays readable
        records = await self.repo.list_for_employee(
            org_id, employee.id, from_date, to_date
        )
        summary = await self.employee_summary(org_id, employee_id, from_date, to_date)
        return employee, summary, records

    async def employee_summary(
        self, org_id: uuid.UUID, employee_id: uuid.UUID, from_date: str, to_date: str
    ) -> EmployeeAttendanceSummary:
        """Totals for the employee between the two BS dates."""
        total_days = check_range(from_date, to_date)
        employee = await self._employee(org_id, employee_id, include_deleted=False)

        counts = dict.fromkeys(STATUSES, 0)
        overtime = Decimal("0")
        for status, days, hours in await self.repo.summary_rows(
            org_id, employee.id, from_date, to_date
        ):
            if status in counts:  # ignore any unknown legacy status
                counts[status] = days
                overtime += Decimal(str(hours or 0))
        recorded = sum(counts.values())

        return EmployeeAttendanceSummary(
            # employee=EmployeeBrief.model_validate(employee),
            from_date=from_date,
            to_date=to_date,
            total_days=total_days,
            recorded_days=recorded,
            unmarked_days=total_days - recorded,
            worked_days=counts["present"] + counts["half_day"] / 2,
            total_overtime_hours=overtime,
            **counts,
        )
