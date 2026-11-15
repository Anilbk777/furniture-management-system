import uuid
import re
import jwt
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool



from ...helper.security import (
    hash_password,
    hash_token,
    create_access_token,
    create_refresh_token,
    verify_password,
    decode_refresh_token,
)
from ...utils.exceptions import (
    ConflictException,
    NotFoundException,
    UnauthorizedException,
    ForbiddenException
)
from .auth_models import User
from .auth_repository import UserRepository, RefreshTokenRepository
from .auth_schemas import UserCreate, UserUpdate, TokenPair

from app.utils.logger import get_logger
logger = get_logger(__name__)


class UserService:
    def __init__(self, db: AsyncSession, repository: UserRepository):
        self.db = db
        self.repository = repository

    async def get_user(self, user_id: uuid.UUID) -> User:
        user = await self.repository.get_by_id(user_id)
        if not user:
            raise NotFoundException(
                message="User not found",
            )
        return user

    async def create_user(self, payload: UserCreate) -> User:
        async with self.db.begin():
            # Business Rule 1: Phone must be unique
            existing_phone = await self.repository.get_by_phone(payload.phone)
            if existing_phone:
                raise ConflictException(
                    message="A user with this phone number already exists"
                )

            # Business Rule 2: Email must be unique if provided
            if payload.email:
                existing_email = await self.repository.get_by_email(payload.email)
                if existing_email:
                    raise ConflictException(
                        message="A user with this email already exists",
                    )

            # Business Rule 3: Hash plain password before saving
            user_dict = payload.model_dump(exclude={"password"})
            user_dict["password_hash"] = await run_in_threadpool(hash_password, payload.password)


            user = await self.repository.create_user(user_dict)
        logger.info(f"User registered: {user.id}")
        return user

    async def update_user(self, user_id: uuid.UUID, payload: UserUpdate) -> User:
        async with self.db.begin():
            user = await self.get_user(user_id)

            # Only extract fields that were actually sent in the request
            update_data = payload.model_dump(exclude_unset=True)

            # Check phone uniqueness if phone is being changed
            if "phone" in update_data and update_data["phone"] != user.phone:
                if await self.repository.get_by_phone(update_data["phone"]):
                    raise ConflictException(
                        message="Phone number is already in use",
                    )

            # Check email uniqueness if email is being changed
            if "email" in update_data and update_data["email"] != user.email:
                if update_data["email"] and await self.repository.get_by_email(
                    update_data["email"]
                ):
                    raise ConflictException(
                        message="Email is already in use",
                    )

            updated_user = await self.repository.update(user, update_data)
        logger.info({"id": user.id}, "User register sucessfully")
        return updated_user


class AuthService:
    def __init__(self, users: UserRepository, tokens: RefreshTokenRepository):
        self.users = users
        self.tokens = tokens
    # ---------- helpers ----------
    async def _find_user(self, identifier: str) -> User | None:
        if "@" in identifier:
            return await self.users.get_by_email(identifier.lower())
        return await self.users.get_by_phone(re.sub(r"[\s\-()]", "", identifier))

    async def _issue_tokens(
        self, user_id:uuid.UUID, user_agent: str | None, ip: str | None
    ) -> TokenPair:
        access = create_access_token(user_id)
        refresh, expires_at = create_refresh_token(user_id)
        await self.tokens.create(
            user_id=user_id,
            token_hash=hash_token(refresh),
            expires_at=expires_at,
            user_agent=(user_agent or "")[:255] or None,
            ip_address=ip,
        )
        return TokenPair(
            access_token=access,
            refresh_token=refresh,
        )

    # ---------- use cases ----------
    async def login(
        self, identifier: str, password: str, *, user_agent: str | None, ip: str | None
    ) -> tuple[User, TokenPair]:
        user = await self._find_user(identifier)
        # Always run a hash check (argon2 is CPU-heavy, so keep it off the event loop)
        password_ok = await run_in_threadpool(
            verify_password, password, user.password_hash if user else "DUMMY_HASH"
        )
        if not user or not password_ok:
            logger.warning(f"Failed login from ip={ip}")
            raise UnauthorizedException("Invalid credentials")
        if not user.is_active:
            raise ForbiddenException("Account is disabled")

        tokens = await self._issue_tokens(user.id, user_agent, ip)
        await self.tokens.commit()
        logger.info(f"Login sucessful for user={user.id}")
        return user, tokens

    async def refresh(
        self, refresh_token: str, user_agent: str | None, ip: str | None
    ) -> TokenPair:
        try:
            user_id = uuid.UUID(decode_refresh_token(refresh_token)["sub"])
        except (jwt.InvalidTokenError, ValueError):
            raise UnauthorizedException("Invalid or expired refresh token")

        stored = await self.tokens.get_by_hash(hash_token(refresh_token))
        if stored is None or stored.revoked_at is not None:
            # Correctly signed but unknown or already used: it may have been stolen.
            # End every session of this user so both the thief and the owner must log in again.
            await self.tokens.revoke_all_for_user(user_id)
            await self.tokens.commit()
            logger.warning(f"Refresh token reuse detected: user={user_id}")
            raise UnauthorizedException("Invalid refresh token")

        user = await self.users.get_by_id(user_id)
        if not user or not user.is_active:
            raise UnauthorizedException("Invalid refresh token")

        # Rotation: the old token dies, a new pair is issued, all in one transaction
        if not await self.tokens.revoke_if_active(stored.id):
            raise UnauthorizedException(
                "Invalid refresh token"
            )  # lost a race with a parallel refresh
        tokens = await self._issue_tokens(user.id, user_agent, ip)
        await self.tokens.commit()
        return tokens

    async def logout(self, refresh_token: str | None) -> None:
        """Ends the current session. Never fails, so the client can always 'log out'."""
        if not refresh_token:
            return
        stored = await self.tokens.get_by_hash(hash_token(refresh_token))
        if stored:
            await self.tokens.revoke_if_active(stored.id)
            await self.tokens.commit()

    async def logout_all(self, user_id: uuid.UUID) -> None:
        await self.tokens.revoke_all_for_user(user_id)
        await self.tokens.commit()
