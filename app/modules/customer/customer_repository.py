import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .customer_models import Customer


class CustomerRepository:
    """Every query is scoped to one organization and ignores deleted customers.
    Methods flush; the service commits."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, org_id: uuid.UUID, customer_id: uuid.UUID) -> Customer | None:
        stmt = select(Customer).where(
            Customer.id == customer_id,
            Customer.organization_id == org_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_mobile(self, org_id: uuid.UUID, mobile: str) -> Customer | None:
        stmt = select(Customer).where(
            Customer.organization_id == org_id,
            Customer.mobile == mobile,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def create(self, org_id: uuid.UUID, **values: Any) -> Customer:
        customer = Customer(organization_id=org_id, **values)
        self.session.add(customer)
        await self.session.flush()
        return customer

    async def update(self, customer: Customer, values: dict[str, Any]) -> None:
        for field, value in values.items():
            setattr(customer, field, value)
        await self.session.flush()

    async def delete_customer(self, customer: Customer) -> None:
        await self.session.delete(customer)
        await self.session.flush()

    async def overview(self, org_id: uuid.UUID) -> dict[str, int]:
        stmt = select(
            func.count().label("total"),
            func.count().filter(Customer.is_active.is_(True)).label("active"),
            func.count().filter(Customer.is_active.is_(False)).label("inactive"),
        ).where(Customer.organization_id == org_id)
        row = (await self.session.execute(stmt)).one()
        return {"total": row.total, "active": row.active, "inactive": row.inactive}

    async def list(
        self,
        org_id: uuid.UUID,
        *,
        search: str | None,
        customer_type: str | None,
        is_active: bool | None,
        page: int,
        limit: int,
    ) -> tuple[Sequence[Customer], int]:
        filters: Any = [
            Customer.organization_id == org_id,
        ]
        if search:
            filters.append(
                or_(
                    Customer.name.icontains(search, autoescape=True),
                    Customer.mobile.icontains(search, autoescape=True),
                    Customer.city_area.icontains(search, autoescape=True),
                )
            )
        if customer_type:
            filters.append(Customer.customer_type == customer_type)
        if is_active is not None:
            filters.append(Customer.is_active.is_(is_active))

        total = await self.session.scalar(
            select(func.count()).select_from(Customer).where(*filters)
        )
        rows = await self.session.scalars(
            select(Customer)
            .where(*filters)
            .order_by(Customer.created_at.desc())
            .limit(limit)
            .offset((page - 1) * limit)
        )
        return rows.all(), total or 0
