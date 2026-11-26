"""Business rules for orders."""

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.customer.customer_service import normalize_type
from .order_models import Order
from app.modules.order.order_repository import OrderRepository
from .order_schemas import (
    HANDOVER_TYPES,
    ORDER_STATUSES,
    PAYMENT_METHODS,
    PRIORITIES,
    OrderCreate,
    OrderStatusUpdate,
    OrderUpdate,
)
from app.utils.exceptions import (
    BadRequestException,
    ConflictException,
    NotFoundException,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)

# status -> the statuses it may move to
STATUS_TRANSITIONS = {
    "new": ("in_progress", "ready", "cancelled"),
    "in_progress": ("ready", "cancelled"),
    "ready": ("in_progress", "delivered", "cancelled"),  # back to in_progress = rework
    "delivered": (),
    "cancelled": (),
}
LOCKED_STATUSES = ("delivered", "cancelled")  # finished orders can't be edited
DELETABLE_STATUSES = ("new", "cancelled")  # anything else must be cancelled first
ORDER_NUMBER_ATTEMPTS = 3

# order field -> the Customer attribute it is copied from
CUSTOMER_COPY = {
    "customer_name": "name",
    "customer_type": "customer_type",
    "customer_mobile": "mobile",
    "customer_city_area": "city_area",
    "customer_landmark": "landmark",
}
NORMALIZED_FIELDS = ("payment_method", "priority", "handover_type")


def normalize(value: str) -> str:
    """'Special Order', 'special-order' and 'SPECIAL_ORDER' all become 'special_order'."""
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def check_order(f: dict[str, Any]) -> dict[str, Any]:
    """`f` holds the FINAL values of the order. Raises BadRequestException for a broken
    combination and returns the clean-ups to apply: no advance -> no payment method,
    workshop pickup -> no delivery address."""
    fixes: dict[str, Any] = {}
    if f["priority"] not in PRIORITIES:
        raise BadRequestException(
            message=f"Priority must be one of: {', '.join(PRIORITIES)}"
        )
    if f["handover_type"] not in HANDOVER_TYPES:
        raise BadRequestException(
            message=f"Handover type must be one of: {', '.join(HANDOVER_TYPES)}"
        )
    if f["advance_amount"] > f["total_amount"]:
        raise BadRequestException(message="Advance can't be more than the total amount")

    if f["advance_amount"] == 0:
        if f["payment_method"]:
            fixes["payment_method"] = None
    elif f["payment_method"] not in PAYMENT_METHODS:
        raise BadRequestException(
            message=f"Choose how the advance was paid: {', '.join(PAYMENT_METHODS)}"
        )

    if f["handover_type"] == "workshop_pickup":
        if f["delivery_address"]:
            fixes["delivery_address"] = None
    elif not f["delivery_address"]:
        raise BadRequestException(message="Site delivery needs a delivery address")
    return fixes


class OrderService:
    def __init__(self, session: AsyncSession, repo: OrderRepository):
        self.session = session
        self.repo = repo

    # ---------- helpers ----------
    async def _customer_copy(
        self, org_id: uuid.UUID, customer_id: uuid.UUID
    ) -> dict[str, Any]:
        """The customer's details as they are right now, keyed by the order's field names."""
        customer = await self.repo.get_customer(org_id, customer_id)
        if not customer:
            raise NotFoundException(message="Customer not found")
        return {field: getattr(customer, attr) for field, attr in CUSTOMER_COPY.items()}

    @staticmethod
    def _normalize(values: dict[str, Any]) -> None:
        for field in NORMALIZED_FIELDS:
            if values.get(field):
                values[field] = normalize(values[field])
        if values.get("customer_type"):
            values["customer_type"] = normalize_type(values["customer_type"])

    # ---------- CRUD ----------
    async def get(self, org_id: uuid.UUID, order_id: uuid.UUID) -> Order:
        order = await self.repo.get(org_id, order_id)
        if not order:
            raise NotFoundException(message="Order not found")
        return order

    async def create(
        self, org_id: uuid.UUID, user_id: uuid.UUID | None, data: OrderCreate
    ) -> Order:
        values = data.model_dump()
        if values["customer_id"]:
            # A linked customer is copied onto the order, so the history survives the customer
            # being deleted. Anything the caller sent explicitly wins over the copy.
            for field, copied in (
                await self._customer_copy(org_id, values["customer_id"])
            ).items():
                if values[field] is None:
                    values[field] = copied
        self._normalize(values)
        values.update(check_order(values))
        values.update(status="new", created_by_id=user_id)

        # `values` is plain data, so it survives the rollback in the retry below
        for attempt in range(1, ORDER_NUMBER_ATTEMPTS + 1):
            try:
                number = await self.repo.next_order_number(org_id)
                order = await self.repo.create(org_id, order_number=number, **values)
                await self.session.commit()
                break
            except IntegrityError as exc:
                await self.session.rollback()
                taken = "order_number" in str(
                    exc.orig
                ) or "uq_orders_org_number" in str(exc.orig)
                if taken and attempt < ORDER_NUMBER_ATTEMPTS:
                    continue  # someone else took this number a moment ago: take the next one
                logger.exception("Failed to create order org=%s", org_id)
                raise ConflictException(
                    message="The order could not be saved, please try again"
                )
            except Exception:
                await self.session.rollback()
                logger.exception("Failed to create order org=%s", org_id)
                raise
        logger.info(
            "Order created id=%s number=%s org=%s", order.id, order.order_number, org_id
        )
        return await self.get(org_id, order.id)  # reload: server-set timestamps

    async def update(
        self, org_id: uuid.UUID, order_id: uuid.UUID, data: OrderUpdate
    ) -> Order:
        order = await self.get(org_id, order_id)
        if order.status in LOCKED_STATUSES:
            raise BadRequestException(message=f"A {order.status} order can't be edited")
        values = data.model_dump(exclude_unset=True)  # only what the client sent
        if not values:
            return order

        new_customer = values.get("customer_id")
        if new_customer and new_customer != order.customer_id:
            # Linked to a different customer: refresh the copy (explicit values still win)
            for field, copied in (
                await self._customer_copy(org_id, new_customer)
            ).items():
                values.setdefault(field, copied)
        self._normalize(values)

        # Validate the FINAL combination (existing row + the changes), same rules as create
        fields = (
            "total_amount",
            "advance_amount",
            "payment_method",
            "priority",
            "handover_type",
            "delivery_address",
        )
        final = {f: values[f] if f in values else getattr(order, f) for f in fields}
        values.update(check_order(final))

        order_number = order.order_number
        try:
            await self.repo.update(order, values)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            logger.exception("Failed to update order %s org=%s", order_id, org_id)
            raise
        logger.info(
            "Order updated id=%s number=%s fields=%s",
            order_id,
            order_number,
            sorted(values),
        )
        return await self.get(org_id, order_id)

    async def overview(self, org_id: uuid.UUID) -> dict[str, int]:
        return await self.repo.overview(org_id)

    async def change_status(
        self, org_id: uuid.UUID, order_id: uuid.UUID, data: OrderStatusUpdate
    ) -> Order:
        order = await self.get(org_id, order_id)
        new_status = normalize(data.status)
        if new_status not in ORDER_STATUSES:
            raise BadRequestException(
                message=f"Status must be one of: {', '.join(ORDER_STATUSES)}"
            )
        if new_status == order.status:
            return order
        if new_status not in STATUS_TRANSITIONS[order.status]:
            raise BadRequestException(
                message=f"A {order.status} order can't be changed to {new_status}"
            )

        old_status = order.status
        try:
            await self.repo.update(order, {"status": new_status})
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            logger.exception(
                "Failed to change status of order %s org=%s", order_id, org_id
            )
            raise
        logger.info("Order status id=%s %s -> %s", order_id, old_status, new_status)
        return await self.get(org_id, order_id)

    async def delete(self, org_id: uuid.UUID, order_id: uuid.UUID) -> None:
        """Permanent delete, only for orders that never started or were cancelled."""
        order = await self.get(org_id, order_id)
        if order.status not in DELETABLE_STATUSES:
            raise BadRequestException(
                message=f"Only new or cancelled orders can be deleted. Cancel this {order.status} order instead"
            )
        summary = (
            order.order_number,
            order.title,
            order.total_amount,
            order.advance_amount,
        )
        try:
            await self.repo.delete(order)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            logger.exception("Failed to delete order %s org=%s", order_id, org_id)
            raise
        logger.info(
            "Order permanently deleted id=%s number=%s title=%s total=%s advance=%s",
            order_id,
            *summary,
        )

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
        if delivery_from and delivery_to and delivery_from > delivery_to:
            raise BadRequestException(message="From date must not be after to date")
        return await self.repo.list(
            org_id,
            search=search,
            status=normalize(status) if status else None,
            priority=normalize(priority) if priority else None,
            handover_type=normalize(handover_type) if handover_type else None,
            category=category,
            customer_id=customer_id,
            delivery_from=delivery_from,
            delivery_to=delivery_to,
            page=page,
            limit=limit,
        )
