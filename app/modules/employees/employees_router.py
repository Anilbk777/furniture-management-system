from typing import Annotated
import uuid
import math
from fastapi import APIRouter, Query, status
from fastapi.responses import JSONResponse
from ...utils.response import APIResponse, success_response,Pagination
from .employees_dependencies import EmployeeServiceDep
from .employees_schemas import (
    EmployeeCreate,
    EmployeeList,
    EmployeeOverview,
    EmployeeRead,
    EmployeeUpdate,
)
# from ..auth.auth_dependencies import CurrentUser
from ..organization.organization_dependencies import CurrentOrganization

router = APIRouter(prefix="/employees", tags=["employees"])


@router.post(
    "", response_model=APIResponse[EmployeeRead], status_code=status.HTTP_201_CREATED
)
async def create_employee(
    data: EmployeeCreate, org: CurrentOrganization, service: EmployeeServiceDep
) -> JSONResponse:
    employee = await service.create(org.id, data)
    return success_response(
        EmployeeRead.model_validate(employee),
        "Employee created",
        status.HTTP_201_CREATED,
    )


@router.get("", response_model=APIResponse[EmployeeList])
async def list_employees(
    org: CurrentOrganization,
    service: EmployeeServiceDep,
    search: Annotated[
        str | None, Query(max_length=120, description="Part of the name")
    ] = None,
    is_active: bool | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
) -> JSONResponse:
    employees, total = await service.list(
        org.id, search=search, is_active=is_active, page=page, limit=limit
    )
    data = EmployeeList(
        employees=[EmployeeRead.model_validate(e) for e in employees],
        pagination=Pagination(
            total=total, page=page, limit=limit, total_pages=math.ceil(total / limit)
        ),
    )
    return success_response(data, "Employees fetched")

@router.get("/overview", response_model=APIResponse[EmployeeOverview])
async def employees_overview(
    org: CurrentOrganization, service: EmployeeServiceDep
) -> JSONResponse:
    """Headline counts and salary totals (declared before /{employee_id})."""
    data = await service.overview(org.id)
    return success_response(data, "Employee overview fetched")


@router.get("/{employee_id}", response_model=APIResponse[EmployeeRead])
async def get_employee(
    employee_id: uuid.UUID, org: CurrentOrganization, service: EmployeeServiceDep
) -> JSONResponse:
    employee = await service.get(org.id, employee_id)
    return success_response(EmployeeRead.model_validate(employee), "Employee fetched")


@router.patch("/{employee_id}", response_model=APIResponse[EmployeeRead])
async def update_employee(
    employee_id: uuid.UUID,
    data: EmployeeUpdate,
    org: CurrentOrganization,
    service: EmployeeServiceDep,
) -> JSONResponse:
    employee = await service.update(org.id, employee_id, data)
    return success_response(EmployeeRead.model_validate(employee), "Employee updated")


@router.delete("/{employee_id}", response_model=APIResponse[None])
async def delete_employee(
    employee_id: uuid.UUID, org: CurrentOrganization, service: EmployeeServiceDep
) -> JSONResponse:
    await service.delete(org.id, employee_id)
    return success_response(None, "Employee deleted")