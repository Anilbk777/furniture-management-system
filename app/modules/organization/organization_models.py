import uuid

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint, true,text
from sqlalchemy.orm import Mapped, mapped_column

from app.helper.base import Base, TimestampMixin


class Organization(TimestampMixin, Base):
    """The business (e.g. the furniture shop). All business data hangs off organization_id.

    user_id = the owner account. UNIQUE for now = one organization per user.
    (Drop uq_organizations_user_id if one user may own several shops later.)
    """

    __tablename__ = "organizations"
    __table_args__ = (UniqueConstraint("user_id", name="uq_organizations_user_id"),)
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=true())
