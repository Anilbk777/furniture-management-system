from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from .organization_models import Organization
from app.modules.auth.auth_dependencies import CurrentUser  # your get_current_user
from .organization_repository import OrganizationRepository
from .organization_service import OrganizationService
from ..party.party_repository import PartyTypeRepository
from app.utils.exceptions import ForbiddenException


def get_organization_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OrganizationService:
    return OrganizationService(db, OrganizationRepository(db), PartyTypeRepository(db))


OrganizationServiceDep = Annotated[
    OrganizationService, Depends(get_organization_service)
]


async def get_current_organization(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Organization:
    """The shop of the logged-in user. Employees, parties and transactions depend on this,
    so all their data is automatically limited to this organization.
    (The organization endpoints themselves do NOT use it, so an inactive shop can be reactivated.)"""
    organization = await OrganizationRepository(db).get_by_user_id(user.id)
    if organization is None:
        raise ForbiddenException(message="Create your organization first")
    if not organization.is_active:
        raise ForbiddenException(message="This organization is inactive")
    return organization


CurrentOrganization = Annotated[Organization, Depends(get_current_organization)]
