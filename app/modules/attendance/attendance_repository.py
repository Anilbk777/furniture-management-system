import uuid
from collections.abc import Sequence
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.modules.employees.employees_models import Employee
from .attendance_models import Attendance


class AttendanceRepository:
    """Every query is scoped to one organization. Methods flush; the service commits."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ---------- employees ----------
    async def get_employee(
        self,
        org_id: uuid.UUID,
        employee_id: uuid.UUID,
        *,
        include_deleted: bool = False,
    ) -> Employee | None:
        stmt = select(Employee).where(
            Employee.id == employee_id, Employee.organization_id == org_id
        )
        if not include_deleted:
            stmt = stmt.where(Employee.deleted_at.is_(None))
        return (await self.session.execute(stmt)).scalar_one_or_none()

    # ---------- single record ----------
    async def get(
        self, org_id: uuid.UUID, attendance_id: uuid.UUID
    ) -> Attendance | None:
        stmt = (
            select(Attendance)
            .options(joinedload(Attendance.employee))
            .where(Attendance.id == attendance_id, Attendance.organization_id == org_id)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_employee_date(
        self, org_id: uuid.UUID, employee_id: uuid.UUID, bs_date: str
    ) -> Attendance | None:
        stmt = select(Attendance).where(
            Attendance.organization_id == org_id,
            Attendance.employee_id == employee_id,
            Attendance.bs_date == bs_date,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    # ---------- lists ----------
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
        filters: list[Any] = [Attendance.organization_id == org_id]
        if employee_id:
            filters.append(Attendance.employee_id == employee_id)
        if status:
            filters.append(Attendance.status == status)
        if from_date:
            filters.append(
                Attendance.bs_date >= from_date
            )  # zero-padded text sorts like dates
        if to_date:
            filters.append(Attendance.bs_date <= to_date)

        total = await self.session.scalar(
            select(func.count()).select_from(Attendance).where(*filters)
        )
        rows = await self.session.scalars(
            select(Attendance)
            .options(joinedload(Attendance.employee))
            .where(*filters)
            .order_by(Attendance.bs_date.desc(), Attendance.created_at.desc())
            .limit(limit)
            .offset((page - 1) * limit)
        )
        return rows.all(), total or 0

    async def daily_roster(
        self, org_id: uuid.UUID, bs_date: str, *, page: int, limit: int
    ) -> tuple[Sequence[tuple[Employee, Attendance | None]], int]:
        """Every employee with their attendance row for bs_date (None when not marked)."""
        filters: list[Any] = [
            Employee.organization_id == org_id,
            Employee.deleted_at.is_(None),
        ]
        total = await self.session.scalar(
            select(func.count()).select_from(Employee).where(*filters)
        )
        rows = await self.session.execute(
            select(Employee, Attendance)
            .outerjoin(
                Attendance,
                (Attendance.employee_id == Employee.id)
                & (Attendance.organization_id == org_id)
                & (Attendance.bs_date == bs_date),
            )
            .where(*filters)
            .order_by(Employee.name.asc(), Employee.id.asc())
            .limit(limit)
            .offset((page - 1) * limit)
        )
        return [(employee, record) for employee, record in rows.all()], total or 0

    async def list_for_employee(
        self, org_id: uuid.UUID, employee_id: uuid.UUID, from_date: str, to_date: str
    ) -> Sequence[Attendance]:
        rows = await self.session.scalars(
            select(Attendance)
            .options(joinedload(Attendance.employee))
            .where(
                Attendance.organization_id == org_id,
                Attendance.employee_id == employee_id,
                Attendance.bs_date >= from_date,
                Attendance.bs_date <= to_date,
            )
            .order_by(Attendance.bs_date)
        )
        return rows.all()

    async def summary_rows(
        self, org_id: uuid.UUID, employee_id: uuid.UUID, from_date: str, to_date: str
    ) -> Sequence[tuple[str, int, Decimal]]:
        """One tuple per status: (status, number of days, total overtime hours)."""
        stmt = (
            select(
                Attendance.status,
                func.count(),
                func.coalesce(func.sum(Attendance.overtime_hours), 0),
            )
            .where(
                Attendance.organization_id == org_id,
                Attendance.employee_id == employee_id,
                Attendance.bs_date >= from_date,
                Attendance.bs_date <= to_date,
            )
            .group_by(Attendance.status)
        )
        result = await self.session.execute(stmt)
        return [(status, days, hours) for status, days, hours in result.all()]

    # ---------- writes ----------
    async def create(
        self, org_id: uuid.UUID, employee: Employee, **values: Any
    ) -> Attendance:
        record = Attendance(
            organization_id=org_id, employee_id=employee.id, employee=employee, **values
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def update(self, record: Attendance, values: dict[str, Any]) -> None:
        for field, value in values.items():
            setattr(record, field, value)
        await self.session.flush()

    async def delete(self, record: Attendance) -> None:
        await self.session.delete(record)
        await self.session.flush()
