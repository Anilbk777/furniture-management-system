"""FastAPI dependencies for the customer routes."""

import uuid
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.customer.customer_models import Customer
from app.modules.customer.customer_repository import CustomerRepository
from app.modules.customer.customer_service import CustomerService

# adjust this import to wherever your CurrentOrganization dependency lives
from app.modules.organization.organization_dependencies import CurrentOrganization


def get_customer_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CustomerService:
    return CustomerService(session, CustomerRepository(session))


CustomerServiceDep = Annotated[CustomerService, Depends(get_customer_service)]


async def get_customer(
    customer_id: uuid.UUID, org: CurrentOrganization, service: CustomerServiceDep
) -> Customer:
    """Loads the customer from the path in the caller's organization, or answers 404.
    A customer of another organization looks exactly like one that doesn't exist."""
    return await service.get(org.id, customer_id)


CustomerDep = Annotated[Customer, Depends(get_customer)]
