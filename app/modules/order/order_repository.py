import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.customer.customer_models import Customer
from .order_models import Order
from .order_schemas import ORDER_STATUSES


class OrderRepository:
    """Every query is scoped to one organization. Methods flush; the service commits."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, org_id: uuid.UUID, order_id: uuid.UUID) -> Order | None:
        stmt = select(Order).where(
            Order.id == order_id, Order.organization_id == org_id
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_customer(
        self, org_id: uuid.UUID, customer_id: uuid.UUID
    ) -> Customer | None:
        stmt = select(Customer).where(
            Customer.id == customer_id, Customer.organization_id == org_id
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def next_order_number(self, org_id: uuid.UUID) -> int:
        """Highest number in the organization + 1. Two requests at the same moment can get
        the same number; the unique constraint rejects one and the service retries."""
        stmt = select(func.coalesce(func.max(Order.order_number), 0) + 1).where(
            Order.organization_id == org_id
        )
        return (await self.session.execute(stmt)).scalar_one()

    async def create(self, org_id: uuid.UUID, **values: Any) -> Order:
        order = Order(organization_id=org_id, **values)
        self.session.add(order)
        await self.session.flush()
        return order

    async def update(self, order: Order, values: dict[str, Any]) -> None:
        for field, value in values.items():
            setattr(order, field, value)
        await self.session.flush()

    async def delete(self, order: Order) -> None:
        await self.session.delete(order)
        await self.session.flush()

    async def overview(self, org_id: uuid.UUID) -> dict[str, int]:
        stmt = (
            select(Order.status, func.count().label("count"))
            .where(Order.organization_id == org_id)
            .group_by(Order.status)
        )
        rows = (await self.session.execute(stmt)).all()
        counts = {status: 0 for status in ORDER_STATUSES}
        for status, count in rows:
            counts[status] = count
        counts["total"] = sum(counts.values())
        return counts

    # keep `list` last: inside this class the name `list` now means this method
    async def list(
        self,
        org_id: uuid.UUID,
        *,
        search: str | None,
        status: str | None,
        priority: str | None,
        handover_type: str | None,
        category: str | None,
        customer_id: uuid.UUID | None,
        delivery_from: str | None,
        delivery_to: str | None,
        page: int,
        limit: int,
    ) -> tuple[Sequence[Order], int]:
        filters: Any = [Order.organization_id == org_id]
        if search:
            matches = [
                Order.title.icontains(search, autoescape=True),
                Order.customer_name.icontains(search, autoescape=True),
                Order.customer_mobile.icontains(search, autoescape=True),
            ]
            if (
                search.isdigit() and len(search) <= 9
            ):  # typing an order number finds that order
                matches.append(Order.order_number == int(search))
            filters.append(or_(*matches))
        if status:
            filters.append(Order.status == status)
        if priority:
            filters.append(Order.priority == priority)
        if handover_type:
            filters.append(Order.handover_type == handover_type)
        if category:
            filters.append(Order.category.icontains(category, autoescape=True))
        if customer_id:
            filters.append(Order.customer_id == customer_id)
        if delivery_from:
            filters.append(
                Order.delivery_bs_date >= delivery_from
            )  # zero-padded text sorts like dates
        if delivery_to:
            filters.append(Order.delivery_bs_date <= delivery_to)

        total = await self.session.scalar(
            select(func.count()).select_from(Order).where(*filters)
        )
        rows = await self.session.scalars(
            select(Order)
            .where(*filters)
            .order_by(Order.order_number.desc())
            .limit(limit)
            .offset((page - 1) * limit)
        )
        return rows.all(), total or 0
