import uuid
from uuid6 import uuid7
from datetime import time
from decimal import Decimal

from sqlalchemy import (
    JSON,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.helper.base import Base, TimestampMixin

# JSONB on PostgreSQL, plain JSON everywhere else (for example SQLite in tests)
JsonList = JSON().with_variant(JSONB(), "postgresql")


class Order(TimestampMixin, Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid7)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE")
    )
    # Human-friendly number customers can quote (1, 2, 3 ...), counted per organization.
    # The service generates it; the unique constraint below keeps it safe.
    order_number: Mapped[int] = mapped_column(Integer)

    # ---------- what is being made ----------
    title: Mapped[str] = mapped_column(String(150))
    category: Mapped[str] = mapped_column(String(50))  # bed, sofa, door, wardrobe ...
    description: Mapped[str | None] = mapped_column(Text)
    hardwood_species: Mapped[str |None] = mapped_column(String(50))  # sal, teak, sisau ...
    # Image URLs or storage keys, in display order. A list inside the row is enough for
    # reference photos; move to an order_photos table if you ever need captions per photo.
    photos: Mapped[list[str]] = mapped_column(
        JsonList, default=list, server_default=text("'[]'")
    )

    # ---------- money ----------
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    advance_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), server_default=text("0")
    )
    # How the advance was paid (cash | bank | esewa | khalti). Empty when there is no advance.
    payment_method: Mapped[str | None] = mapped_column(String(20))

    # ---------- delivery ----------
    delivery_bs_date: Mapped[str] = mapped_column(String(10))  # 'YYYY-MM-DD' in BS
    delivery_time: Mapped[time | None] = mapped_column(Time)  # stored as 24-hour time
    priority: Mapped[str] = mapped_column(
        String(20), default="standard", server_default="standard"
    )  # standard | urgent | special_order
    handover_type: Mapped[str] = mapped_column(
        String(20)
    )  # workshop_pickup | site_delivery
    delivery_address: Mapped[str | None] = mapped_column(
        String(500)
    )  # the site, when site_delivery

    # ---------- progress ----------
    status: Mapped[str] = mapped_column(
        String(20), default="new", server_default="new"
    )  # new | in_progress | ready | delivered | cancelled

    # ---------- customer ----------
    # Optional link. When the customer is deleted the database sets it to NULL and the order
    # stays, because everything needed for the history is copied below at order time.
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("customers.id", ondelete="SET NULL")
    )
    customer_name: Mapped[str] = mapped_column(String(150))
    customer_type: Mapped[str] = mapped_column(
        String(20)
    )  # individual | business | contractor
    customer_mobile: Mapped[str] = mapped_column(String(20))
    customer_city_area: Mapped[str | None] = mapped_column(
        String(100)
    )  # may be empty for walk-ins
    customer_landmark: Mapped[str | None] = mapped_column(String(255))

    # ---------- audit ----------
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )

    @property
    def remaining_amount(self) -> Decimal:
        return self.total_amount - self.advance_amount

    __table_args__ = (
        UniqueConstraint(
            "organization_id", "order_number", name="uq_orders_org_number"
        ),
        CheckConstraint("total_amount >= 0", name="ck_orders_total_not_negative"),
        CheckConstraint(
            "advance_amount >= 0 AND advance_amount <= total_amount",
            name="ck_orders_advance_within_total",
        ),
        CheckConstraint("length(trim(title)) > 0", name="ck_orders_title_not_blank"),
        Index("ix_orders_org_delivery", "organization_id", "delivery_bs_date"),
        Index("ix_orders_org_status", "organization_id", "status"),
        Index("ix_orders_customer", "customer_id"),
    )
