import uuid
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.exceptions import (
    BadRequestException,
    ConflictException,
    NotFoundException,
)

from .party_models import Party, PartyType
from .party_repository import PartyRepository, PartyTypeRepository
from .party_schemas import (
    PartyCreate,
    PartyOverview,
    PartyTypeCreate,
    PartyTypeUpdate,
    PartyUpdate,
)


class PartyTypeService:
    """Rules for party types. `organization_id` is the logged-in user's organization."""

    def __init__(self, session: AsyncSession, repo: PartyTypeRepository) -> None:
        self.session = session
        self.repo = repo

    async def list(self, organization_id: uuid.UUID) -> Sequence[PartyType]:
        return await self.repo.list(organization_id)

    async def get(self, organization_id: uuid.UUID, type_id: uuid.UUID) -> PartyType:
        party_type = await self.repo.get(organization_id, type_id)
        if party_type is None:
            raise NotFoundException(message="Party type not found")
        return party_type

    async def create(
        self, organization_id: uuid.UUID, data: PartyTypeCreate
    ) -> PartyType:
        if await self.repo.get_by_name(organization_id, data.name):
            raise ConflictException(message="This party type already exists")
        party_type = await self.repo.create(organization_id, data.name)
        await self.session.commit()
        return party_type

    async def update(
        self, organization_id: uuid.UUID, type_id: uuid.UUID, data: PartyTypeUpdate
    ) -> PartyType:
        party_type = await self.get(organization_id, type_id)
        existing = await self.repo.get_by_name(organization_id, data.name)
        if existing and existing.id != party_type.id:
            raise ConflictException(message="This party type already exists")
        await self.repo.rename(party_type, data.name)
        await self.session.commit()
        return party_type

    async def delete(self, organization_id: uuid.UUID, type_id: uuid.UUID) -> None:
        party_type = await self.get(organization_id, type_id)
        if await self.repo.count_parties(party_type.id):
            raise ConflictException(
                message="Parties still use this type. Move or remove them first"
            )
        await self.repo.delete(party_type)
        await self.session.commit()


class PartyService:
    """Rules for parties. `organization_id` is the logged-in user's organization."""

    def __init__(
        self,
        session: AsyncSession,
        repo: PartyRepository,
        type_repo: PartyTypeRepository,
    ) -> None:
        self.session = session
        self.repo = repo
        self.type_repo = type_repo

    async def _check_type(
        self, organization_id: uuid.UUID, party_type_id: uuid.UUID
    ) -> None:
        """The chosen type must be one of THIS organization's types."""
        if await self.type_repo.get(organization_id, party_type_id) is None:
            raise BadRequestException(message="Party type not found")

    async def _check_party_name(self, organization_id: uuid.UUID, name: str) -> None:
        existing_name = await self.repo.get_by_name(organization_id, name)
        if existing_name:
            raise ConflictException(message=f"{name} already exist.")

    async def create(self, organization_id: uuid.UUID, data: PartyCreate) -> Party:
        await self._check_party_name(organization_id, data.name)
        await self._check_type(organization_id, data.party_type_id)
        party = await self.repo.create(organization_id, **data.model_dump())
        await self.session.commit()
        return party

    async def get(self, organization_id: uuid.UUID, party_id: uuid.UUID) -> Party:
        party = await self.repo.get(organization_id, party_id)
        if party is None:  # also what another shop's id looks like
            raise NotFoundException(message="Party not found")
        return party

    async def list(
        self,
        organization_id: uuid.UUID,
        *,
        search: str | None,
        party_type_id: uuid.UUID | None,
        is_active: bool | None,
        page: int,
        limit: int,
    ) -> tuple[Sequence[Party], int]:
        return await self.repo.list(
            organization_id,
            search=search,
            party_type_id=party_type_id,
            is_active=is_active,
            page=page,
            limit=limit,
        )

    async def overview(self, organization_id: uuid.UUID) -> PartyOverview:
        total, active, inactive = await self.repo.overview(organization_id)
        return PartyOverview(total=total, active=active, inactive=inactive)

    async def update(
        self, organization_id: uuid.UUID, party_id: uuid.UUID, data: PartyUpdate
    ) -> Party:
        party = await self.get(organization_id, party_id)
        values = data.model_dump(exclude_unset=True)  # only what the client sent
        if "party_type_id" in values:
            await self._check_type(organization_id, values["party_type_id"])
        if "name" in values and party.name != values["name"]:
            await self._check_party_name(organization_id, values["name"])
        if values:
            party = await self.repo.update(party, values)
            await self.session.commit()
        return party

    async def delete(self, organization_id: uuid.UUID, party_id: uuid.UUID) -> None:
        """Soft delete: hidden from lists, but past transactions stay intact."""
        party = await self.get(organization_id, party_id)
        await self.repo.soft_delete(party)
        await self.session.commit()
