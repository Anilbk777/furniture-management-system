"""Schemas for the order module.

Customer rule: send `customer_id` to link an existing customer (anything you also send in the
customer_* fields overrides the copied value), or leave it out for a walk-in customer and send
customer_name, customer_type and customer_mobile yourself.

The service checks the rules that need the whole order (advance <= total, advance needs a
payment method, site delivery needs an address, allowed values) for create AND update."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
    StringConstraints,
    computed_field,
    model_validator,
    BeforeValidator
)

# Shared types. Ideally move these into one shared file (for example app/helper/types.py)
# and import them from there everywhere.
from app.modules.attendance.attendance_types import BsDate, Time12
from app.modules.customer.customer_schemas import PhoneStr
from app.utils.response import Pagination


def _blank_to_none(value):
    """The frontend often sends '' for an empty optional field."""
    return None if isinstance(value, str) and not value.strip() else value
OptionalText = Annotated[str | None, BeforeValidator(_blank_to_none)]

# Allowed values. Plain strings in the schemas and the database; the service checks them.
PAYMENT_METHODS = ("cash", "bank", "esewa", "khalti", "fonepay")
PRIORITIES = ("standard", "urgent", "special_order")
HANDOVER_TYPES = ("workshop_pickup", "site_delivery")
ORDER_STATUSES = ("new", "in_progress", "ready", "delivered", "cancelled")
MAX_PHOTOS = 10

# Exact decimal in the database, plain JSON number for clients. Never negative.
Money = Annotated[
    Decimal,
    Field(ge=0, max_digits=14, decimal_places=2),
    PlainSerializer(float, return_type=float, when_used="json"),
]
PositiveMoney = Annotated[Money, Field(gt=0)]

Photo = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
]


def _drop_duplicates(photos: list[str]) -> list[str]:
    return list(dict.fromkeys(photos))  # keeps the order


# Image URLs or storage keys, in display order
Photos = Annotated[
    list[Photo], Field(max_length=MAX_PHOTOS), AfterValidator(_drop_duplicates)
]


# ---------- requests ----------
class OrderCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    # what is being made
    title: str = Field(min_length=1, max_length=150)
    category: str = Field(min_length=1, max_length=50)
    description: OptionalText = None
    hardwood_species: str | None = Field(default=None, min_length=1, max_length=50)
    photos: Photos = Field(default_factory=list)

    # money
    total_amount: PositiveMoney
    advance_amount: Money = Decimal("0")
    payment_method: OptionalText = Field(
        None, max_length=20, description="cash | bank | esewa | khalti |Fonepay"
    )

    # delivery
    delivery_bs_date: BsDate
    delivery_time: Time12 | None = None
    priority: str = Field(
        "standard",
        min_length=1,
        max_length=20,
        description="standard | urgent | special_order",
    )
    handover_type: str = Field(
        min_length=1, max_length=20, description="workshop_pickup | site_delivery"
    )
    delivery_address: OptionalText = Field(None, max_length=500)

    # customer: an existing one, or typed in for a walk-in
    customer_id: uuid.UUID | None = None
    customer_name: str | None = Field(None, min_length=1, max_length=150)
    customer_type: str | None = Field(
        None,
        min_length=1,
        max_length=20,
        description="individual | business | contractor",
    )
    customer_mobile: PhoneStr | None = None
    customer_city_area: OptionalText = Field(None, max_length=100)
    customer_landmark: OptionalText = Field(None, max_length=255)

    @model_validator(mode="after")
    def customer_info_needed(self) -> Self:
        if self.customer_id is None and not (
            self.customer_name and self.customer_type and self.customer_mobile
        ):
            raise ValueError(
                "Customer name, type and mobile are required when no customer is selected"
            )
        return self


class OrderUpdate(BaseModel):
    """PATCH: send only what changes. Send description, payment_method, delivery_time,
    delivery_address, customer_id, customer_city_area or customer_landmark as null to clear
    them, and photos as [] to remove every photo. Status has its own endpoint."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    title: str | None = Field(None, min_length=1, max_length=150)
    category: str | None = Field(None, min_length=1, max_length=50)
    description: OptionalText = None
    hardwood_species: str | None = Field(None, min_length=1, max_length=50)
    photos: Photos | None = None
    total_amount: PositiveMoney | None = None
    advance_amount: Money | None = None
    payment_method: OptionalText = Field(None, max_length=20)
    delivery_bs_date: BsDate | None = None
    delivery_time: Time12 | None = None
    priority: str | None = Field(None, min_length=1, max_length=20)
    handover_type: str | None = Field(None, min_length=1, max_length=20)
    delivery_address: OptionalText = Field(None, max_length=500)
    customer_id: uuid.UUID | None = None
    customer_name: str | None = Field(None, min_length=1, max_length=150)
    customer_type: str | None = Field(None, min_length=1, max_length=20)
    customer_mobile: PhoneStr | None = None
    customer_city_area: OptionalText = Field(None, max_length=100)
    customer_landmark: OptionalText = Field(None, max_length=255)

    @model_validator(mode="after")
    def required_fields_not_null(self) -> Self:
        required = (
            "title",
            "category",
            "photos",
            "total_amount",
            "advance_amount",
            "delivery_bs_date",
            "priority",
            "handover_type",
            "customer_name",
            "customer_type",
            "customer_mobile",
        )
        for field in required:
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class OrderStatusUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    status: str = Field(
        min_length=1,
        max_length=20,
        description="new | in_progress | ready | delivered | cancelled",
    )


# ---------- responses ----------
class OrderRead(BaseModel):
    """Everything about one order."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_number: int
    title: str
    category: str
    description: str | None
    hardwood_species: str |None
    photos: list[str]
    total_amount: Money
    advance_amount: Money
    remaining_amount: Money
    payment_method: str | None
    delivery_bs_date: str
    delivery_time: Time12 | None
    priority: str
    handover_type: str
    delivery_address: str | None
    status: str
    customer_id: (
        uuid.UUID | None
    )  # NULL when it was a walk-in or the customer was deleted
    customer_name: str
    customer_type: str
    customer_mobile: str
    customer_city_area: str | None
    customer_landmark: str | None
    created_by_id: uuid.UUID | None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class OrderListItem(BaseModel):
    """One row of the orders list: enough for a table or a card, without the long fields."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_number: int
    title: str
    category: str
    hardwood_species: str |None
    total_amount: Money 
    advance_amount: Money
    remaining_amount: Money
    delivery_bs_date: str
    delivery_time: Time12 | None
    priority: str
    handover_type: str
    status: str
    customer_id: uuid.UUID | None
    customer_name: str
    customer_mobile: str
    created_at: datetime | None = None
    photos: list[str] = Field(exclude=True)  # used for the two fields below, never sent

    @computed_field
    @property
    def cover_photo(self) -> str | None:
        return self.photos[0] if self.photos else None

    @computed_field
    @property
    def photo_count(self) -> int:
        return len(self.photos)


class OrderList(BaseModel):
    orders: list[OrderListItem]
    pagination: Pagination


class OrderOverview(BaseModel):
    total: int
    new: int
    in_progress: int
    ready: int
    delivered: int
    cancelled: int
