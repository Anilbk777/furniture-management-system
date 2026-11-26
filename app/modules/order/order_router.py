import math
import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status
from fastapi.responses import JSONResponse

from ...utils.response import APIResponse, Pagination, success_response
from ..attendance.attendance_types import BsDate
from ..auth.auth_dependencies import CurrentUser
from ..organization.organization_dependencies import CurrentOrganization
from .order_dependencies import OrderServiceDep
from .order_schemas import (
    OrderCreate,
    OrderList,
    OrderListItem,
    OrderOverview,
    OrderRead,
    OrderStatusUpdate,
    OrderUpdate,
)

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.post(
    "", response_model=APIResponse[OrderRead], status_code=status.HTTP_201_CREATED
)
async def create_order(
    data: OrderCreate,
    current_user: CurrentUser,
    org: CurrentOrganization,
    service: OrderServiceDep,
) -> JSONResponse:
    order = await service.create(org.id, current_user.id, data)
    return success_response(
        OrderRead.model_validate(order),
        "Order created",
        status.HTTP_201_CREATED,
    )


@router.get("", response_model=APIResponse[OrderList])
async def list_orders(
    org: CurrentOrganization,
    service: OrderServiceDep,
    search: Annotated[
        str | None,
        Query(max_length=120, description="Part of title, customer name or mobile"),
    ] = None,
    order_status: Annotated[
        str | None,
        Query(alias="status", max_length=20, description="new | in_progress | ready | delivered | cancelled"),
    ] = None,
    priority: Annotated[
        str | None,
        Query(max_length=20, description="standard | urgent | special_order"),
    ] = None,
    handover_type: Annotated[
        str | None,
        Query(max_length=20, description="workshop_pickup | site_delivery"),
    ] = None,
    category: Annotated[str | None, Query(max_length=50)] = None,
    customer_id: uuid.UUID | None = None,
    delivery_from: Annotated[
        BsDate | None, Query(description="BS date, e.g. 2081-04-01")
    ] = None,
    delivery_to: Annotated[
        BsDate | None, Query(description="BS date, e.g. 2081-04-30")
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> JSONResponse:
    orders, total = await service.list(
        org.id,
        search=search,
        status=order_status,
        priority=priority,
        handover_type=handover_type,
        category=category,
        customer_id=customer_id,
        delivery_from=delivery_from,
        delivery_to=delivery_to,
        page=page,
        limit=limit,
    )
    data = OrderList(
        orders=[OrderListItem.model_validate(o) for o in orders],
        pagination=Pagination(
            total=total, page=page, limit=limit, total_pages=math.ceil(total / limit)
        ),
    )
    return success_response(data, "Orders fetched")


@router.get("/overview", response_model=APIResponse[OrderOverview])
async def orders_overview(
    org: CurrentOrganization, service: OrderServiceDep
) -> JSONResponse:
    data = await service.overview(org.id)
    return success_response(OrderOverview(**data), "Orders overview fetched")


@router.get("/{order_id}", response_model=APIResponse[OrderRead])
async def get_order_detail(
    order_id: uuid.UUID, org: CurrentOrganization, service: OrderServiceDep
) -> JSONResponse:
    order = await service.get(org.id, order_id)
    return success_response(OrderRead.model_validate(order), "Order fetched")


@router.patch("/{order_id}", response_model=APIResponse[OrderRead])
async def update_order(
    order_id: uuid.UUID,
    data: OrderUpdate,
    org: CurrentOrganization,
    service: OrderServiceDep,
) -> JSONResponse:
    order = await service.update(org.id, order_id, data)
    return success_response(OrderRead.model_validate(order), "Order updated")


@router.post("/{order_id}/status", response_model=APIResponse[OrderRead])
async def change_order_status(
    order_id: uuid.UUID,
    data: OrderStatusUpdate,
    org: CurrentOrganization,
    service: OrderServiceDep,
) -> JSONResponse:
    order = await service.change_status(org.id, order_id, data)
    return success_response(OrderRead.model_validate(order), "Order status updated")


@router.delete("/{order_id}", response_model=APIResponse[None])
async def delete_order(
    order_id: uuid.UUID, org: CurrentOrganization, service: OrderServiceDep
) -> JSONResponse:
    await service.delete(org.id, order_id)
    return success_response(None, "Order deleted")
