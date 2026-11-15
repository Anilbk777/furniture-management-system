import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint, text, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.helper.base import Base, SoftDeleteMixin, TimestampMixin


class PartyType(TimestampMixin, Base):
    """The kinds of party this owner uses. He can add his own (e.g. कारीगर, ठेकेदार)."""

    __tablename__ = "party_types"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "name", name="uq_party_types_organization_id_name"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    name: Mapped[str] = mapped_column(String(60))


class Party(TimestampMixin, SoftDeleteMixin, Base):
    """Anyone this organization  has udharo / lending / advances with. History lives in `transactions`."""

    __tablename__ = "parties"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(20))
    address: Mapped[str | None] = mapped_column(String(255))
    party_type_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("party_types.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=true())
    note: Mapped[str | None] = mapped_column(Text)

    # Always load it with joinedload(...) in queries (async: no lazy loading).
    party_type: Mapped["PartyType"] = relationship()
