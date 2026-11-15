import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .organization_models import Organization


class OrganizationRepository:
    """Database access for organizations (shops). No business rules, no commits."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_user_id(self, user_id: uuid.UUID) -> Organization | None:
        stmt = select(Organization).where(Organization.user_id == user_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def create(self, user_id: uuid.UUID, **values) -> Organization:
        """Also callable from the REGISTER service (it does not commit)."""
        organization = Organization(user_id=user_id, **values)
        self.session.add(organization)
        await self.session.flush()
        await self.session.refresh(
            organization
        )  # load server defaults (timestamps, is_active)
        return organization

    async def update(self, organization: Organization, values: dict) -> Organization:
        for field, value in values.items():
            setattr(organization, field, value)
        await self.session.flush()
        await self.session.refresh(organization)  # updated_at is set by the database
        return organization
