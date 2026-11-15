from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from .employees_repository import EmployeeRepository
from .employees_service import EmployeeService


def get_employee_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EmployeeService:
    return EmployeeService(db, EmployeeRepository(db))


EmployeeServiceDep = Annotated[EmployeeService, Depends(get_employee_service)]
