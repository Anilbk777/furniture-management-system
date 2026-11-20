import datetime as dt
import uuid
from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .employees_models import Employee


class EmployeeRepository:
    """Database access only. Every read is scoped to ONE organization, so an owner can never
    see or touch another owner's employees (a wrong id simply finds nothing)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, organization_id: uuid.UUID, **values) -> Employee:
        employee = Employee(organization_id=organization_id, **values)
        self.session.add(employee)
        await self.session.flush()
        return employee

    async def get(
        self, organization_id: uuid.UUID, employee_id: uuid.UUID
    ) -> Employee | None:
        stmt = select(Employee).where(
            Employee.id == employee_id,
            Employee.organization_id == organization_id,
            Employee.deleted_at.is_(None),
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list(
        self,
        organization_id: uuid.UUID,
        *,
        search: str | None = None,
        is_active: bool | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> tuple[Sequence[Employee], int]:
        filters = [
            Employee.organization_id == organization_id,
            Employee.deleted_at.is_(None),
        ]
        if search:
            filters.append(Employee.name.icontains(search, autoescape=True))
        if is_active is not None:
            filters.append(Employee.is_active.is_(is_active))

        total = await self.session.scalar(
            select(func.count()).select_from(Employee).where(*filters)
        )
        rows = await self.session.scalars(
            select(Employee)
            .where(*filters)
            .order_by(Employee.created_at.desc())
            .limit(limit)
            .offset((page - 1) * limit)
        )
        return rows.all(), total or 0

    async def overview(
        self, organization_id: uuid.UUID
    ) -> tuple[int, int, int, Decimal, Decimal]:
        """Counts and monthly-salary totals for one organization, in a single query."""
        stmt = select(
            func.count(),
            func.count().filter(Employee.is_active.is_(True)),
            func.count().filter(Employee.is_active.is_(False)),
            func.coalesce(
                func.sum(
                    case(
                        (Employee.is_active.is_(True), Employee.monthly_salary),
                        else_=Decimal("0"),
                    )
                ),
                Decimal("0"),
            ),
            func.coalesce(
                func.sum(
                    case(
                        (Employee.is_active.is_(False), Employee.monthly_salary),
                        else_=Decimal("0"),
                    )
                ),
                Decimal("0"),
            ),
        ).where(
            Employee.organization_id == organization_id,
            Employee.deleted_at.is_(None),
        )
        total, active, inactive, active_salary, inactive_salary = (
            await self.session.execute(stmt)
        ).one()
        return (
            int(total or 0),
            int(active or 0),
            int(inactive or 0),
            Decimal(active_salary or 0),
            Decimal(inactive_salary or 0),
        )

    async def update(self, employee: Employee, values: dict) -> Employee:
        for field, value in values.items():
            setattr(employee, field, value)
        await self.session.flush()
        await self.session.refresh(employee)  # updated_at is set by the database
        return employee

    async def soft_delete(self, employee: Employee) -> None:
        employee.deleted_at = dt.datetime.now(dt.UTC)
        await self.session.flush()