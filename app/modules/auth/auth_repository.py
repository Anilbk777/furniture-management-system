import uuid
from datetime import datetime
from sqlalchemy import select, delete, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from .auth_models import User, RefreshToken


class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_user(self, user_data: dict) -> User:
        user = User(**user_data)
        self.db.add(user)
        # Flush writes to DB inside the transaction and loads server_default values
        await self.db.flush()
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