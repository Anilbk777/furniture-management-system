import uuid
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.logger import get_logger

from ...utils.exceptions import NotFoundException
from .employees_models import Employee
from .employees_repository import EmployeeRepository
from .employees_schemas import EmployeeCreate, EmployeeUpdate

logger = get_logger(__name__)


class EmployeeService:
    """Business rules and the commit. `organization_id` is always the logged-in user's id."""

    def __init__(self, session: AsyncSession, repo: EmployeeRepository) -> None:
        self.session = session
        self.repo = repo

    async def create(
        self, organization_id: uuid.UUID, data: EmployeeCreate
    ) -> Employee:
        employee = await self.repo.create(organization_id, **data.model_dump())
        await self.session.commit()
        return employee

    async def get(self, organization_id: uuid.UUID, employee_id: uuid.UUID) -> Employee:
        employee = await self.repo.get(organization_id, employee_id)
        if employee is None:  
            raise NotFoundException(message="Employee not found")
        return employee

    async def list(
        self,
        organization_id: uuid.UUID,
        *,
        search: str | None,
        is_active: bool | None,
        page: int,
        limit: int,
    ) -> tuple[Sequence[Employee], int]:
        return await self.repo.list(
            organization_id, search=search, is_active=is_active, page=page, limit=limit
        )

    async def update(
        self, organization_id: uuid.UUID, employee_id: uuid.UUID, data: EmployeeUpdate
    ) -> Employee:
        employee = await self.get(organization_id, employee_id)
        values = data.model_dump(exclude_unset=True)  # only what the client sent
        if values:
            employee = await self.repo.update(employee, values)
            await self.session.commit()
        return employee

    async def delete(self, organization_id: uuid.UUID, employee_id: uuid.UUID) -> None:
        """Soft delete: hidden from lists, but past transactions stay intact."""
        employee = await self.get(organization_id, employee_id)
        await self.repo.soft_delete(employee)
        await self.session.commit()
