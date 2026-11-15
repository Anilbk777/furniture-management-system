import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from ...utils.exceptions import ConflictException, NotFoundException
from .organization_models import Organization
from .organization_repository import OrganizationRepository
from .organization_schemas import (
    OrganizationCreate,
    OrganizationUpdate,
)
from ..party.party_repository import PartyTypeRepository


class OrganizationService:
    """Rules for organizations. A user has at most ONE organization (their shop)."""

    def __init__(
        self,
        session: AsyncSession,
        repo: OrganizationRepository,
        party_type_repo: PartyTypeRepository,
    ) -> None:
        self.session = session
        self.repo = repo
        self.party_type_repo = party_type_repo

    async def create(
        self, user_id: uuid.UUID, data: OrganizationCreate
    ) -> Organization:
        """Organization + the default party types, in ONE transaction."""
        if await self.repo.get_by_user_id(user_id):
            raise ConflictException(message="You already have an organization")
        organization = await self.repo.create(user_id, **data.model_dump())
        await self.party_type_repo.create_defaults(organization.id)
        await self.session.commit()
        return organization

    async def get_mine(self, user_id: uuid.UUID) -> Organization:
        organization = await self.repo.get_by_user_id(user_id)
        if organization is None:
            raise NotFoundException(
                message="Organization not found"
            )  # frontend: show 'create your shop'
        return organization

    async def update_mine(
        self, user_id: uuid.UUID, data: OrganizationUpdate
    ) -> Organization:
        organization = await self.get_mine(user_id)
        values = data.model_dump(exclude_unset=True)  # only what the client sent
        if values:
            organization = await self.repo.update(organization, values)
            await self.session.commit()
        return organization

    async def deactivate_mine(self, user_id: uuid.UUID) -> None:
        """'Delete' = deactivate. The data is kept; PATCH is_active=true brings it back."""
        organization = await self.get_mine(user_id)
        await self.repo.update(organization, {"is_active": False})
        await self.session.commit()
