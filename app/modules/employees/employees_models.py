from decimal import Decimal
import uuid
from sqlalchemy import Boolean, CheckConstraint, Numeric, String, Text, true,ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column

from app.helper.base import (
    BS_DATE_LENGTH,
    Base,
    SoftDeleteMixin,
    TimestampMixin,
    bs_date_check,
)


class Employee(TimestampMixin, SoftDeleteMixin, Base):
    """A person who works for ONE owner's shop. Money given to them lives in `transactions`.

    owner_id    = the user (account) this employee belongs to; every query filters by it
    is_active   = still works here (False = left the job, history stays visible)
    deleted_at  = removed from the lists (history rows are kept)
    """

    __tablename__ = "employees"
    __table_args__ = (
        CheckConstraint(
            "monthly_salary IS NULL OR monthly_salary >= 0", name="salary_non_negative"
        ),
        bs_date_check("joined_date_bs", nullable=True, name="joined_date_bs_format"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(20))
    role_title: Mapped[str | None] = mapped_column(String(80))  # e.g. कारीगर, हेल्पर
    monthly_salary: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    joined_date_bs: Mapped[str | None] = mapped_column(
        String(BS_DATE_LENGTH)
    )  # "2080-01-15"
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=true())
    note: Mapped[str | None] = mapped_column(Text)