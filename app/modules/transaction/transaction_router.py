import math
import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status
from fastapi.responses import JSONResponse

from app.utils.response import APIResponse, success_response
from app.helper.base import BS_DATE_REGEX
# from .transaction_enums  import PaymentMethod, TxKind
from app.modules.auth.auth_dependencies import CurrentUser  
from app.modules.organization.organization_dependencies import CurrentOrganization
from app.modules.transaction.transaction_dependencies import TransactionServiceDep
from app.modules.transaction.transaction_schemas import (
    Pagination,
    TransactionCreate,
    TransactionList,
    TransactionRead,
    TransactionUpdate,
)

router = APIRouter(prefix="/transactions", tags=["transactions"])

BsDateQuery = Annotated[
    str | None, Query(pattern=BS_DATE_REGEX, description="BS date YYYY-MM-DD")
]


@router.post(
    "", response_model=APIResponse[TransactionRead], status_code=status.HTTP_201_CREATED
)
async def create_transaction(
    data: TransactionCreate,
    user: CurrentUser,
    org: CurrentOrganization,
    service: TransactionServiceDep,
) -> JSONResponse:
    transaction = await service.create(org.id, user.id, data)
    return success_response(
        TransactionRead.model_validate(transaction),
        "Transaction created",
        status.HTTP_201_CREATED,
    )


@router.get("", response_model=APIResponse[TransactionList])
async def list_transactions(
    org: CurrentOrganization,
    service: TransactionServiceDep,
    kind: Annotated[
        str | None,
        Query(description="Repeat the parameter to filter several kinds"),
    ] = None,
    employee_id: uuid.UUID | None = None,
    party_id: uuid.UUID | None = None,
    payment_method: str | None = None,
    date_from: BsDateQuery = None,
    date_to: BsDateQuery = None,
    search: Annotated[
        str | None, Query(max_length=120, description="Part of the note")
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> JSONResponse:
    transactions, total = await service.list(
        org.id,
        kinds=kind,
        employee_id=employee_id,
        party_id=party_id,
        payment_method=payment_method,
        date_from=date_from,
        date_to=date_to,
        search=search,
        page=page,
        limit=limit,
    )
    data = TransactionList(
        transactions=[TransactionRead.model_validate(t) for t in transactions],
        pagination=Pagination(
            total=total, page=page, limit=limit, total_pages=math.ceil(total / limit)
        ),
    )
    return success_response(data, "Transactions fetched")


@router.get("/{transaction_id}", response_model=APIResponse[TransactionRead])
async def get_transaction(
    transaction_id: uuid.UUID, org: CurrentOrganization, service: TransactionServiceDep
) -> JSONResponse:
    transaction = await service.get(org.id, transaction_id)
    return success_response(
        TransactionRead.model_validate(transaction), "Transaction fetched"
    )


@router.patch("/{transaction_id}", response_model=APIResponse[TransactionRead])
async def update_transaction(
    transaction_id: uuid.UUID,
    data: TransactionUpdate,
    org: CurrentOrganization,
    service: TransactionServiceDep,
) -> JSONResponse:
    transaction = await service.update(org.id, transaction_id, data)
    return success_response(
        TransactionRead.model_validate(transaction), "Transaction updated"
    )


@router.delete("/{transaction_id}", response_model=APIResponse[None])
async def delete_transaction(
    transaction_id: uuid.UUID, org: CurrentOrganization, service: TransactionServiceDep
) -> JSONResponse:
    await service.delete(org.id, transaction_id)
    return success_response(None, "Transaction deleted")
