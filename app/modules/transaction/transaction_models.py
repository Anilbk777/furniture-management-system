import uuid
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Index, Numeric, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.helper.base import (
    BS_DATE_LENGTH,
    Base,
    SoftDeleteMixin,
    TimestampMixin,
    bs_date_check,
)
from ..employees.employees_models import Employee
from ..party.party_models import Party


class Transaction(TimestampMixin, SoftDeleteMixin, Base):
    """Every entry in the shop: his own income/expense, and anything with an employee or party.

    * kind / payment_method are validated in the API (see transaction_rules.py)
    * payment_method empty = no money moved (udharo) or goods only
    * Service-level rule (spans tables): employee / party must belong to the same organization_id
    """

    __tablename__ = "transactions"
    __table_args__ = (
        bs_date_check(),
        CheckConstraint("amount > 0", name="positive_amount"),
        CheckConstraint(
            "employee_id IS NULL OR party_id IS NULL", name="single_counterparty"
        ),
        Index("ix_transactions_organization_id_bs_date", "organization_id", "bs_date"),
        Index("ix_transactions_employee_id_bs_date", "employee_id", "bs_date"),
        Index("ix_transactions_party_id_bs_date", "party_id", "bs_date"),
    )
    id: Mapped[uuid.UUID] = mapped_column(
            primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
        )

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    bs_date: Mapped[str] = mapped_column(String(BS_DATE_LENGTH))  # "2083-07-27"
    kind: Mapped[str] = mapped_column(String(30))  # see TxKind
    amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2)
    )  # always positive; kind decides direction
    payment_method: Mapped[str | None] = mapped_column(String(20))  # see PaymentMethod
    note: Mapped[str | None] = mapped_column(Text)
    employee_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("employees.id"))
    party_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("parties.id"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))

    # Always load with joinedload(...) in queries (async: no lazy loading).
    employee: Mapped[Employee | None] = relationship()
    party: Mapped[Party | None] = relationship()
