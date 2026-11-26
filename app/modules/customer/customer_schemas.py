import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Self

from app.utils.response import Pagination
from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
    model_validator,
)


def validate_digits_only(value: str) -> str:
    if not value.isdigit():
        raise ValueError("Number should be only digit")
    return value


Amount = Annotated[
    Decimal,
    Field(ge=0, max_digits=14, decimal_places=2),
    PlainSerializer(float, return_type=float, when_used="json"),
]
# Reusable digit-only phone type (10 to 20 digits)
PhoneStr = Annotated[
    str,
    Field(
        min_length=10,
        max_length=20,
        description="Must contain digits only (0-9)",
    ),
    AfterValidator(validate_digits_only),
]


class CustomerCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    customer_type: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=150, title="Name")
    mobile: PhoneStr = Field(title="Mobile")
    alt_phone: PhoneStr | None = Field(default=None, title="alternative mobile number")
    city_area: str = Field(min_length=1, max_length=100, title="city area")
    landmark: str | None = Field(default=None, max_length=255, title="landmark")
    opening_balance: Amount = Decimal("0")
    khata_note: str | None = Field(default=None, max_length=500)


class CustomerUpdate(BaseModel):
    """PATCH: send only what changes. Send alt_phone / khata_note as null to clear them."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    customer_type: str | None = Field(default=None, min_length=1, max_length=20)
    name: str | None = Field(default=None, min_length=1, max_length=150)
    mobile: PhoneStr | None = Field(default=None, title="Mobile")
    alt_phone: PhoneStr | None = Field(default=None, title="Alternative mobile number")
    city_area: str | None = Field(default=None, min_length=1, max_length=100)
    landmark: str | None = Field(default=None, max_length=255)
    opening_balance: Amount | None = None
    khata_note: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None

    @model_validator(mode="after")
    def required_fields_not_null(self) -> Self:
        required = (
            "customer_type",
            "name",
            "mobile",
            "city_area",
            "is_active",
        )
        for field in required:
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


# ---------- responses ----------
class CustomerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    customer_type: str
    name: str
    mobile: str
    alt_phone: str | None
    city_area: str
    landmark: str | None
    opening_balance: Amount
    khata_note: str | None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CustomerList(BaseModel):
    customers: list[CustomerRead]
    pagination: Pagination


class CustomerOverview(BaseModel):
    total: int
    active: int
    inactive: int
