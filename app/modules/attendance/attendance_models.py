import uuid
from datetime import time
from decimal import Decimal
from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Numeric,
    String,
    Time,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.helper.base import Base, TimestampMixin

# adjust the path to wherever your Employee model lives
from app.modules.employees.employees_models import Employee


class Attendance(TimestampMixin, Base):
    """One row per employee per day."""

    __tablename__ = "attendances"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE")
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("employees.id", ondelete="CASCADE")
    )
    bs_date: Mapped[str] = mapped_column(String(10))  # 'YYYY-MM-DD' in BS
    status: Mapped[str] = mapped_column(
        String(20)
    )  # present | half_day | absent | leave
    check_in: Mapped[time | None] = mapped_column(Time)  # stored as 24-hour time
    check_out: Mapped[time | None] = mapped_column(Time)
    overtime_hours: Mapped[Decimal] = mapped_column(
        Numeric(4, 2), default=Decimal("0"), server_default=text("0")
    )
    note: Mapped[str | None] = mapped_column(String(500))

    employee: Mapped["Employee"] = relationship()

    @property
    def employee_name(
        self,
    ) -> str:  # needs the employee loaded (the repository always does)
        return self.employee.name

    __table_args__ = (
        UniqueConstraint("employee_id", "bs_date", name="uq_attendances_employee_date"),
        Index("ix_attendances_org_date", "organization_id", "bs_date"),
        CheckConstraint(
            "overtime_hours >= 0 AND overtime_hours <= 24",
            name="ck_attendances_overtime_range",
        ),
        CheckConstraint(
            "check_out IS NULL OR check_in IS NULL OR check_out > check_in",
            name="ck_attendances_check_order",
        ),
    )
