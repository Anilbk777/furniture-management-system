import uuid
from datetime import datetime
from sqlalchemy import select, delete, update, func,or_
from sqlalchemy.ext.asyncio import AsyncSession

from .auth_models import User, RefreshToken,PasswordResetToken


class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_user(self, user: User) -> User:
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_phone(self, phone: str) -> User | None:
        stmt = select(User).where(User.phone == phone)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all(self, skip: int = 0, limit: int = 100) -> list[User]:
        stmt = select(User).offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update(self, user: User, update_data: dict) -> User:
        for field, value in update_data.items():
            setattr(user, field, value)
        await self.db.flush()
        return user

    async def delete(self, user: User) -> None:
        await self.db.delete(user)
        await self.db.flush()

    async def find_by_phone_or_email(self, phone: str, email: str) -> list[User]:
        """Up to two rows: one matching the phone, one matching the email (maybe the same)."""
        result = await self.db.scalars(
            select(User).where(
                or_(User.phone == phone, func.lower(User.email) == email.lower())
            )
        )
        return list(result.all())

    async def rollback(self) -> None:
        await self.db.rollback()

    async def commit(self) -> None:
            await self.db.commit()
    


class RefreshTokenRepository:
    """Methods flush but don't commit: the service commits once per use case."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        user_id: uuid.UUID,
        token_hash: str,
        expires_at: datetime,
        user_agent: str | None,
        ip_address: str | None,
    ) -> RefreshToken:
        row = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        self.db.add(row)
        await self.db.flush()
        return row

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        result = await self.db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def revoke_if_active(self, token_id: uuid.UUID) -> bool:
        """Atomic: returns False if it was already revoked, so two concurrent
        requests can never both rotate the same refresh token."""
        result = await self.db.execute(
            update(RefreshToken)
            .where(RefreshToken.id == token_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=func.now())
        )
        return result.rowcount == 1   # type: ignore

    async def revoke_all_for_user(self, user_id: uuid.UUID) -> None:
        await self.db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=func.now())
        )

    async def delete_expired(self) -> int:
        """Housekeeping: run from a scheduled job (cron, Celery beat, ...)."""
        result = await self.db.execute(
            delete(RefreshToken).where(RefreshToken.expires_at < func.now())
        )
        return result.rowcount  # type: ignore

    async def commit(self) -> None:
        await self.db.commit()


class PasswordResetRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self, *, user_id: uuid.UUID, token_hash: str, expires_at: datetime
    ) -> None:
        self.db.add(
            PasswordResetToken(
                user_id=user_id, token_hash=token_hash, expires_at=expires_at
            )
        )
        await self.db.flush()

    async def get_valid_by_hash(self, token_hash: str) -> PasswordResetToken | None:
        """Unused and not expired (expiry is checked with the database clock)."""
        result = await self.db.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.token_hash == token_hash,
                PasswordResetToken.used.is_(False),
                PasswordResetToken.expires_at > func.now(),
            )
        )
        return result.scalar_one_or_none()

    async def mark_used_if_unused(self, token_id: uuid.UUID) -> bool:
        """Atomic: False if another request already used it, so a link works exactly once."""
        result = await self.db.execute(
            update(PasswordResetToken)
            .where(
                PasswordResetToken.id == token_id, PasswordResetToken.used.is_(False)
            )
            .values(used=True)
        )
        return result.rowcount == 1 #type: ignore

    async def invalidate_all_for_user(self, user_id: uuid.UUID) -> None:
        await self.db.execute(
            update(PasswordResetToken)
            .where(
                PasswordResetToken.user_id == user_id,
                PasswordResetToken.used.is_(False),
            )
            .values(used=True)
        )

    async def delete_expired(self) -> int:
        """Housekeeping: run from a scheduled job."""
        result = await self.db.execute(
            delete(PasswordResetToken).where(PasswordResetToken.expires_at < func.now())
        )
        return result.rowcount  # type: ignore

    async def commit(self) -> None:
        await self.db.commit()