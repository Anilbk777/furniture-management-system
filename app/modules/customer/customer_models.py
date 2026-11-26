import uuid
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Numeric,
    String,
    Uuid,
    text,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.helper.base import Base, TimestampMixin


class Customer(TimestampMixin, Base):
    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE")
    )
    customer_type: Mapped[str] = mapped_column(
        String(20)
    )  # individual | business | contractor
    name: Mapped[str] = mapped_column(String(150))  # full name, or the business name
    mobile: Mapped[str] = mapped_column(
        String(20), unique=True
    )  # 10 digits, e.g. 9841234567
    alt_phone: Mapped[str | None] = mapped_column(String(20))
    city_area: Mapped[str] = mapped_column(String(100))
    landmark: Mapped[str | None] = mapped_column(
        String(255)
    )  # detailed landmark / tole
    # Signed: positive = the customer owes the shop (baki), negative = the shop owes the
    # customer (advance). Only the starting figure: later movements belong in the ledger.
    opening_balance: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), server_default=text("0")
    )
    khata_note: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=true()
    )

    __table_args__ = (
        Index("ix_customers_org_name", "organization_id", "name"),
        CheckConstraint("length(trim(name)) > 0", name="ck_customers_name_not_blank"),
    )
