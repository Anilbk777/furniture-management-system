import datetime as dt

from sqlalchemy import CheckConstraint, DateTime, MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Stable constraint names make Alembic migrations predictable.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TimestampMixin:
    """created_at / updated_at are real timestamps in UTC (system audit info).
    Show them in Nepal time / BS on the frontend. They are NOT the business date."""

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SoftDeleteMixin:
    """Rows are never really deleted; deleted_at hides them (and allows undo)."""

    deleted_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


# ---------------------------------------------------------------- BS dates
# A BS date is stored as TEXT "YYYY-MM-DD" (e.g. "2083-07-27"), zero-padded.
#  - sorts correctly:      ORDER BY bs_date
#  - ranges work:          bs_date BETWEEN '2083-07-01' AND '2083-07-32'   (= whole Kartik)
#  - needs no conversion library to store or read.
# (Do not use a Postgres DATE: BS months have 29-32 days and many BS dates are invalid there.)
BS_DATE_LENGTH = 10
BS_DATE_REGEX = "^[0-9]{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[0-2])$"


def bs_date_check(
    column: str = "bs_date", *, nullable: bool = False, name: str = "bs_date_format"
) -> CheckConstraint:
    """CHECK that a text column holds a well-formed BS date (NULL allowed if nullable)."""
    expr = f"{column} ~ '{BS_DATE_REGEX}'"
    if nullable:
        expr = f"{column} IS NULL OR {expr}"
    return CheckConstraint(expr, name=name)
