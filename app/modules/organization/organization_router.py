from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.utils.response import APIResponse, success_response
from app.modules.auth.auth_dependencies import CurrentUser  # your get_current_user
from .organization_dependencies import OrganizationServiceDep
from .organization_schemas import (
    OrganizationCreate,
    OrganizationRead,
    OrganizationUpdate,
)

# One organization per user, so the endpoints work on "me" (no id in the URL).
router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.post(
    "",
    response_model=APIResponse[OrganizationRead],
    status_code=status.HTTP_201_CREATED,
)
async def create_organization(
    data: OrganizationCreate, user: CurrentUser, service: OrganizationServiceDep
) -> JSONResponse:
    organization = await service.create(user.id, data)
    return success_response(
        OrganizationRead.model_validate(organization),
        "Organization created",
        status.HTTP_201_CREATED,
    )


@router.get("", response_model=APIResponse[OrganizationRead])
async def get_my_organization(
    user: CurrentUser, service: OrganizationServiceDep
) -> JSONResponse:
    organization = await service.get_mine(user.id)
    return success_response(
        OrganizationRead.model_validate(organization), "Organization fetched"
    )


@router.patch("", response_model=APIResponse[OrganizationRead])
async def update_my_organization(
    data: OrganizationUpdate, user: CurrentUser, service: OrganizationServiceDep
) -> JSONResponse:
    organization = await service.update_mine(user.id, data)
    return success_response(
        OrganizationRead.model_validate(organization), "Organization updated"
    )


@router.delete("", response_model=APIResponse[None])
async def deactivate_my_organization(
    user: CurrentUser, service: OrganizationServiceDep
) -> JSONResponse:
    await service.deactivate_mine(user.id)
    return success_response(None, "Organization deactivated")
