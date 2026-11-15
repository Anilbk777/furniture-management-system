import uuid
import math
from typing import Annotated

from fastapi import APIRouter, Query, status
from fastapi.responses import JSONResponse

from app.utils.response import APIResponse, success_response
from app.modules.organization.organization_dependencies import CurrentOrganization
from .party_dependencies import (
    PartyServiceDep,
    PartyTypeServiceDep,
)
from .party_schemas import (
    PartyCreate,
    PartyRead,
    PartyTypeCreate,
    PartyTypeRead,
    PartyTypeUpdate,
    PartyUpdate,
    PartyList,
    Pagination
)

parties = APIRouter(prefix="/parties", tags=["parties"])
party_types = APIRouter(prefix="/party-types", tags=["party types"])


# ------------------------------ party types ----------------------------------
@party_types.get("", response_model=APIResponse[list[PartyTypeRead]])
async def list_party_types(
    org: CurrentOrganization, service: PartyTypeServiceDep
) -> JSONResponse:
    types = await service.list(org.id)
    return success_response(
        [PartyTypeRead.model_validate(t) for t in types], "Party types fetched"
    )


@party_types.post(
    "", response_model=APIResponse[PartyTypeRead], status_code=status.HTTP_201_CREATED
)
async def create_party_type(
    data: PartyTypeCreate, org: CurrentOrganization, service: PartyTypeServiceDep
) -> JSONResponse:
    party_type = await service.create(org.id, data)
    return success_response(
        PartyTypeRead.model_validate(party_type),
        "Party type created",
        status.HTTP_201_CREATED,
    )


@party_types.patch("/{type_id}", response_model=APIResponse[PartyTypeRead])
async def rename_party_type(
    type_id: uuid.UUID,
    data: PartyTypeUpdate,
    org: CurrentOrganization,
    service: PartyTypeServiceDep,
) -> JSONResponse:
    party_type = await service.update(org.id, type_id, data)
    return success_response(
        PartyTypeRead.model_validate(party_type), "Party type updated"
    )


@party_types.delete("/{type_id}", response_model=APIResponse[None])
async def delete_party_type(
    type_id: uuid.UUID, org: CurrentOrganization, service: PartyTypeServiceDep
) -> JSONResponse:
    await service.delete(org.id, type_id)
    return success_response(None, "Party type deleted")


# ------------------------------ parties ------------------------------
@parties.post(
    "", response_model=APIResponse[PartyRead], status_code=status.HTTP_201_CREATED
)
async def create_party(
    data: PartyCreate, org: CurrentOrganization, service: PartyServiceDep
) -> JSONResponse:
    party = await service.create(org.id, data)
    return success_response(
        PartyRead.model_validate(party), "Party created", status.HTTP_201_CREATED
    )

@parties.get("", response_model=APIResponse[PartyList])
async def list_parties(
    org: CurrentOrganization,
    service: PartyServiceDep,
    search: Annotated[
        str | None, Query(max_length=120, description="Part of name or phone")
    ] = None,
    party_type_id: uuid.UUID | None = None,
    is_active: bool | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> JSONResponse:
    parties_, total = await service.list(
        org.id,
        search=search,
        party_type_id=party_type_id,
        is_active=is_active,
        page=page,
        limit=limit,
    )
    data = PartyList(
        parties=[PartyRead.model_validate(p) for p in parties_],
        pagination=Pagination(
            total=total, page=page, limit=limit, total_pages=math.ceil(total / limit)
        ),
    )
    return success_response(data, "Parties fetched")

@parties.get("/{party_id}", response_model=APIResponse[PartyRead])
async def get_party(
    party_id: uuid.UUID, org: CurrentOrganization, service: PartyServiceDep
) -> JSONResponse:
    party = await service.get(org.id, party_id)
    return success_response(PartyRead.model_validate(party), "Party fetched")


@parties.patch("/{party_id}", response_model=APIResponse[PartyRead])
async def update_party(
    party_id: uuid.UUID,
    data: PartyUpdate,
    org: CurrentOrganization,
    service: PartyServiceDep,
) -> JSONResponse:
    party = await service.update(org.id, party_id, data)
    return success_response(PartyRead.model_validate(party), "Party updated")


@parties.delete("/{party_id}", response_model=APIResponse[None])
async def delete_party(
    party_id: uuid.UUID, org: CurrentOrganization, service: PartyServiceDep
) -> JSONResponse:
    await service.delete(org.id, party_id)
    return success_response(None, "Party deleted")

