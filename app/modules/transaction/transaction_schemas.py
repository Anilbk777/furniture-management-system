import datetime as dt
import uuid
from decimal import Decimal
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.helper.base import BS_DATE_REGEX
from app.utils.response import (
    Pagination,
)

# from .transaction_enums import PaymentMethod, TxKind
from .transaction_rules import check_shape

# BS date as text, e.g. "2083-07-27" (the frontend date picker sends this)
BsDate = Annotated[str, Field(pattern=BS_DATE_REGEX, examples=["2083-07-27"])]
Money = Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=2)]


class TransactionCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    kind: str
    bs_date: BsDate
    amount: Money
    payment_method: str | None = None
    employee_id: uuid.UUID | None = None
    party_id: uuid.UUID | None = None
    note: str | None = Field(None, max_length=1000)

    @model_validator(mode="after")
    def check_rules(self) -> Self:
        error = check_shape(
            self.kind, self.employee_id, self.party_id, self.payment_method
        )
        if error:
            raise ValueError(error)
        return self


class TransactionUpdate(BaseModel):
    """PATCH: send only the fields you want to change. The final combination is
    re-validated by the service. To clear a field, send it as null."""

    model_config = ConfigDict(str_strip_whitespace=True)

    kind: str | None = None
    bs_date: BsDate | None = None
    amount: Money | None = None
    payment_method: str | None = None
    employee_id: uuid.UUID | None = None
    party_id: uuid.UUID | None = None
    note: str | None = Field(None, max_length=1000)

    @model_validator(mode="after")
    def required_fields_not_null(self) -> Self:
        for field in ("bs_date", "amount"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class EmployeeBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str


class PartyBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str


class TransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    bs_date: str  # "2083-07-27"
    kind: str
    amount: Decimal
    payment_method: str | None  # None = no money moved
    note: str | None
    employee: EmployeeBrief | None
    party: PartyBrief | None
    created_by: uuid.UUID | None
    created_at: dt.datetime
    updated_at: dt.datetime


class TransactionList(BaseModel):
    transactions: list[TransactionRead]
    pagination: Pagination
