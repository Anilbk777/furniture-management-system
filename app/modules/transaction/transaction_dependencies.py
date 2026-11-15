from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from ..employees.employees_repository import EmployeeRepository
from ..party.party_repository import PartyRepository
from .transaction_repository import TransactionRepository
from .transaction_service import TransactionService


def get_transaction_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TransactionService:
    return TransactionService(
        db, TransactionRepository(db), EmployeeRepository(db), PartyRepository(db)
    )


TransactionServiceDep = Annotated[TransactionService, Depends(get_transaction_service)]
