import uuid
from collections.abc import Sequence

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.customer.customer_models import Customer
from app.modules.customer.customer_repository import CustomerRepository
from app.modules.customer.customer_schemas import CustomerCreate, CustomerUpdate
from app.utils.exceptions import (
    BadRequestException,
    ConflictException,
    NotFoundException,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)

CUSTOMER_TYPES = ("individual", "business", "contractor")
MOBILE_TAKEN = "A customer with this mobile number already exists"


def normalize_type(value: str) -> str:
    """'Business' and ' CONTRACTOR ' are accepted."""
    value = value.strip().lower()
    if value not in CUSTOMER_TYPES:
        raise BadRequestException(
            message=f"Customer type must be one of: {', '.join(CUSTOMER_TYPES)}"
        )
    return value


class CustomerService:
    def __init__(self, session: AsyncSession, repo: CustomerRepository):
        self.session = session
        self.repo = repo

    async def get(self, org_id: uuid.UUID, customer_id: uuid.UUID) -> Customer:
        customer = await self.repo.get(org_id, customer_id)
        if not customer:
            raise NotFoundException(message="Customer not found")
        return customer

    async def create(self, org_id: uuid.UUID, data: CustomerCreate) -> Customer:
        values = data.model_dump()
        values["customer_type"] = normalize_type(values["customer_type"])
        if await self.repo.get_by_mobile(org_id, data.mobile):
            raise ConflictException(message=MOBILE_TAKEN)
        try:
            customer = await self.repo.create(org_id, **values)
            await self.session.commit()
        except IntegrityError:  # two identical requests at the same moment
            await self.session.rollback()
            raise ConflictException(message=MOBILE_TAKEN)
        except Exception:
            await self.session.rollback()
            logger.exception("Failed to create customer org=%s", org_id)
            raise
        logger.info(
            "Customer created id=%s type=%s org=%s",
            customer.id,
            customer.customer_type,
            org_id,
        )
        return await self.get(org_id, customer.id)  # reload: server-set timestamps

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
        return await self.repo.list(
            org_id,
            search=search,
            customer_type=normalize_type(customer_type) if customer_type else None,
            is_active=is_active,
            page=page,
            limit=limit,
        )

    async def overview(self, org_id: uuid.UUID) -> dict[str, int]:
        return await self.repo.overview(org_id)

    async def update(self, customer: Customer, data: CustomerUpdate) -> Customer:
        """`customer` comes from the get_customer dependency, so it is already known to belong
        to the caller's organization."""
        values = data.model_dump(exclude_unset=True)  # only what the client sent
        if not values:
            return customer
        if "customer_type" in values:
            values["customer_type"] = normalize_type(values["customer_type"])

        org_id, customer_id = customer.organization_id, customer.id
        if "mobile" in values and values["mobile"] != customer.mobile:
            if await self.repo.get_by_mobile(org_id, values["mobile"]):
                raise ConflictException(message=MOBILE_TAKEN)
        try:
            await self.repo.update(customer, values)
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            raise ConflictException(message=MOBILE_TAKEN)
        except Exception:
            await self.session.rollback()
            logger.exception("Failed to update customer %s org=%s", customer_id, org_id)
            raise
        logger.info("Customer updated id=%s fields=%s", customer_id, sorted(values))
        return await self.get(org_id, customer_id)

    async def delete(self, customer: Customer) -> None:
        """Soft delete: hidden everywhere and its mobile number is free again, but the row stays
        so the khata and any future sales keep pointing at a real customer."""
        org_id, customer_id = customer.organization_id, customer.id
        try:
            await self.repo.delete_customer(customer)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            logger.exception("Failed to delete customer %s org=%s", customer_id, org_id)
            raise
        logger.info("Customer deleted id=%s org=%s", customer_id, org_id)
