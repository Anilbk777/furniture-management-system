import datetime as dt
import uuid
from decimal import Decimal
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.helper.base import BS_DATE_REGEX
from app.utils.response import (
    Pagination,
)

# from .transaction_enums import PaymentMethod, TxKind
from .transaction_enums import PaymentMethod, TxKind
from .transaction_rules import check_shape

# BS date as text, e.g. "2083-07-27" (the frontend date picker sends this)
BsDate = Annotated[str, Field(pattern=BS_DATE_REGEX, examples=["2083-07-27"])]
Money = Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=2)]


def _checked_kind(value: str) -> str:
    try:
        return TxKind(value).value
    except ValueError as exc:
        raise ValueError("unknown transaction kind") from exc


def _checked_method(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        return PaymentMethod(value).value
    except ValueError as exc:
        raise ValueError("unknown payment method") from exc


class TransactionCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    kind: str
    bs_date: BsDate
    amount: Money
    payment_method: str | None = None
    employee_id: uuid.UUID | None = None
    party_id: uuid.UUID | None = None
    note: str | None = Field(None, max_length=1000)

    @field_validator("kind")
    @classmethod
    def valid_kind(cls, value: str) -> str:
        return _checked_kind(value)

    @field_validator("payment_method")
    @classmethod
    def valid_payment_method(cls, value: str | None) -> str | None:
        return _checked_method(value)

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

    @field_validator("kind")
    @classmethod
    def valid_kind(cls, value: str | None) -> str | None:
        return None if value is None else _checked_kind(value)

    @field_validator("payment_method")
    @classmethod
    def valid_payment_method(cls, value: str | None) -> str | None:
        return _checked_method(value)

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
    role_title: str | None
    is_active: bool


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


class TransactionTotals(BaseModel):
    """Sums for the current filter (e.g. one employee's current BS month)."""

    count: int
    amounts: dict[str, Decimal]


class TransactionList(BaseModel):
    """One page of transactions plus the filtered employee and their totals.

    Everything the employee detail screen needs comes back in this single call.
    """

    transactions: list[TransactionRead]
    pagination: Pagination
    employee: EmployeeBrief | None = None
    totals: TransactionTotals
