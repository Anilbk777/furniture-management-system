import datetime as dt
import uuid
from collections.abc import Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from .party_models import Party, PartyType

DEFAULT_PARTY_TYPES = ("Supplier","Customer")

class PartyTypeRepository:
    """Database access for party types. Always scoped to one organization."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self, organization_id: uuid.UUID) -> Sequence[PartyType]:
        stmt = (
            select(PartyType)
            .where(PartyType.organization_id == organization_id)
            .order_by(PartyType.created_at.desc())
        )
        return (await self.session.execute(stmt)).scalars().all()

    async def get(
        self, organization_id: uuid.UUID, type_id: uuid.UUID
    ) -> PartyType | None:
        stmt = select(PartyType).where(
            PartyType.id == type_id, PartyType.organization_id == organization_id
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_name(
        self, organization_id: uuid.UUID, name: str
    ) -> PartyType | None:
        """Case-insensitive, to stop 'Supplier' and 'supplier' both existing."""
        stmt = select(PartyType).where(
            PartyType.organization_id == organization_id,
            func.lower(PartyType.name) == name.lower(),
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def create(self, organization_id: uuid.UUID, name: str) -> PartyType:
        party_type = PartyType(organization_id=organization_id, name=name)
        self.session.add(party_type)
        await self.session.flush()
        return party_type

    async def create_defaults(self, organization_id: uuid.UUID)-> Sequence[PartyType]:
        """Call from the REGISTER service (inside its transaction, it does not commit)."""
        created = [
            PartyType(organization_id=organization_id, name=name)
            for name in DEFAULT_PARTY_TYPES
        ]
        self.session.add_all(created)
        await self.session.flush()
        return created

    async def rename(self, party_type: PartyType, name: str) -> PartyType:
        party_type.name = name
        await self.session.flush()
        return party_type

    async def count_parties(self, type_id: uuid.UUID) -> int:
        """Counts deleted parties too: they still point at this type (foreign key)."""
        stmt = (
            select(func.count())
            .select_from(Party)
            .where(Party.party_type_id == type_id)
        )
        return (await self.session.execute(stmt)).scalar_one()

    async def delete(self, party_type: PartyType) -> None:
        await self.session.delete(party_type)
        await self.session.flush()


class PartyRepository:
    """Database access for parties. Every read is scoped to ONE organization."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _fetch(self, party_id: uuid.UUID) -> Party:
        """Reload one party from the database, with its type, refreshing every column."""
        stmt = (
            select(Party)
            .options(joinedload(Party.party_type))
            .where(Party.id == party_id)
            .execution_options(populate_existing=True)
        )
        return (await self.session.execute(stmt)).scalar_one()

    async def get_by_name(
            self, organization_id: uuid.UUID, name: str
        ) -> Party| None:
            """Case-insensitive, to stop 'Supplier' and 'supplier' both existing."""
            stmt = (
                select(Party)
                .where(
                    Party.organization_id == organization_id,
                    func.lower(Party.name) == name.lower(),
                )
                .limit(1)
            )
            return (await self.session.scalars(stmt)).first()
    

    async def create(self, organization_id: uuid.UUID, **values) -> Party:
        party = Party(organization_id=organization_id, **values)
        self.session.add(party)
        await self.session.flush()
        return await self._fetch(party.id)

    async def get(
        self, organization_id: uuid.UUID, party_id: uuid.UUID
    ) -> Party | None:
        stmt = (
            select(Party)
            .options(joinedload(Party.party_type))
            .where(
                Party.id == party_id,
                Party.organization_id == organization_id,
                Party.deleted_at.is_(None),
            )
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list(
        self,
        organization_id: uuid.UUID,
        *,
        search: str | None = None,
        party_type_id: uuid.UUID | None = None,
        is_active: bool | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> tuple[Sequence[Party], int]:
        filters = [Party.organization_id == organization_id, Party.deleted_at.is_(None)]
        if search:
            filters.append(
                or_(
                    Party.name.icontains(search, autoescape=True),
                    Party.phone.icontains(search, autoescape=True),
                )
            )
        if party_type_id is not None:
            filters.append(Party.party_type_id == party_type_id)
        if is_active is not None:
            filters.append(Party.is_active.is_(is_active))

        total = await self.session.scalar(
            select(func.count()).select_from(Party).where(*filters)
        )
        rows = await self.session.scalars(
            select(Party)
            .options(joinedload(Party.party_type))
            .where(*filters)
            .order_by(Party.created_at.desc())
            .limit(limit)
            .offset((page - 1) * limit)
        )
        return rows.all(), total or 0
    async def update(self, party: Party, values: dict) -> Party:
        for field, value in values.items():
            setattr(party, field, value)
        await self.session.flush()
        return await self._fetch(party.id)  # fresh updated_at and party_type

    async def soft_delete(self, party: Party) -> None:
        party.deleted_at = dt.datetime.now(dt.UTC)
        await self.session.flush()
