import uuid
from datetime import datetime
from sqlalchemy import Boolean, String, Uuid, true,false, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.helper.base import Base, TimestampMixin


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(20), unique=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), server_default="owner")
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=true())
    # NULL until the user proves the email with the 6-digit code.
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # True until the user has chosen their own password. Existing rows default to False.
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )

class RefreshToken(TimestampMixin, Base):
    """One row per login session. Only a SHA-256 hash of the token is stored."""

    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user_agent: Mapped[str | None] = mapped_column(String(255))
    ip_address: Mapped[str | None] = mapped_column(String(45))  # fits IPv6


class PasswordResetToken(TimestampMixin, Base):
    """One row per reset email. Only a SHA-256 hash of the token is stored, so a
    database leak doesn't hand out working reset links."""

    __tablename__ = "password_reset_tokens"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )