import math
from typing import Annotated
from fastapi import APIRouter, Query, status
from fastapi.responses import JSONResponse

from .customer_dependencies import CustomerDep, CustomerServiceDep

# adjust this import to wherever your CurrentOrganization dependency lives
from app.modules.organization.organization_dependencies import CurrentOrganization
from app.modules.customer.customer_schemas import (
    CustomerCreate,
    CustomerList,
    CustomerOverview,
    CustomerRead,
    CustomerUpdate,
    Pagination,
)
from app.utils.response import APIResponse, success_response

router = APIRouter(prefix="/customers", tags=["Customers"])


@router.post(
    "", status_code=status.HTTP_201_CREATED, response_model=APIResponse[CustomerRead]
)
async def create_customer(
    data: CustomerCreate, org: CurrentOrganization, service: CustomerServiceDep
) -> JSONResponse:
    customer = await service.create(org.id, data)
    return success_response(
        CustomerRead.model_validate(customer),
        "Customer created",
        status.HTTP_201_CREATED,
    )


@router.get("", response_model=APIResponse[CustomerList])
async def list_customers(
    org: CurrentOrganization,
    service: CustomerServiceDep,
    search: Annotated[
        str | None,
        Query(
            max_length=120, description="Part of name, mobile,or  city/area"
        ),
    ] = None,
    customer_type: Annotated[
        str | None,
        Query(max_length=20, description="individual | business | contractor"),
    ] = None,
    is_active: bool | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> JSONResponse:
    customers, total = await service.list(
        org.id,
        search=search,
        customer_type=customer_type,
        is_active=is_active,
        page=page,
        limit=limit,
    )
    data = CustomerList(
        customers=[CustomerRead.model_validate(c) for c in customers],
        pagination=Pagination(
                    total=total, page=page, limit=limit, total_pages=math.ceil(total / limit)
                ),
    )
    return success_response(data, "Customers fetched")


@router.get("/overview", response_model=APIResponse[CustomerOverview])
async def customers_overview(
    org: CurrentOrganization, service: CustomerServiceDep
) -> JSONResponse:
    data = await service.overview(org.id)
    return success_response(CustomerOverview(**data), "Customers overview fetched")


@router.get("/{customer_id}", response_model=APIResponse[CustomerRead])
async def get_customer_detail(customer: CustomerDep) -> JSONResponse:
    return success_response(CustomerRead.model_validate(customer), "Customer fetched")


@router.patch("/{customer_id}", response_model=APIResponse[CustomerRead])
async def update_customer(
    data: CustomerUpdate, customer: CustomerDep, service: CustomerServiceDep
) -> JSONResponse:
    updated = await service.update(customer, data)
    return success_response(CustomerRead.model_validate(updated), "Customer updated")


@router.delete("/{customer_id}", response_model=APIResponse[None])
async def delete_customer(
    customer: CustomerDep, service: CustomerServiceDep
) -> JSONResponse:
    await service.delete(customer)
    return success_response(None, "Customer deleted")
