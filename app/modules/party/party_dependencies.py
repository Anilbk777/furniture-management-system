from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from .party_repository import PartyRepository, PartyTypeRepository
from .party_service import PartyService, PartyTypeService


def get_party_service(db: Annotated[AsyncSession, Depends(get_db)]) -> PartyService:
    return PartyService(db, PartyRepository(db), PartyTypeRepository(db))


def get_party_type_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PartyTypeService:
    return PartyTypeService(db, PartyTypeRepository(db))


PartyServiceDep = Annotated[PartyService, Depends(get_party_service)]
PartyTypeServiceDep = Annotated[PartyTypeService, Depends(get_party_type_service)]
