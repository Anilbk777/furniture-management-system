import re
import secrets
import uuid
from datetime import datetime,timedelta, timezone
import jwt
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.utils.logger import get_logger

from ...helper.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)
from ...utils.exceptions import (
    BadRequestException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
    UnauthorizedException,
)
from .auth_models import User
from .auth_otp_service import OtpService
from .auth_repository import (
    RefreshTokenRepository,
    UserRepository,
    PasswordResetRepository,
)
from .auth_schemas import TokenPair,UserUpdate, UserCreate
from app.core.config import settings

logger = get_logger(__name__)


RESET_TOKEN_TTL = timedelta(seconds=settings.reset_token_ttl_seconds)

class UserService:
    def __init__(self, db: AsyncSession, repository: UserRepository, otp: OtpService):
        self.db = db
        self.repository = repository
        self.otp = otp

    async def get_user(self, user_id: uuid.UUID) -> User:
        user = await self.repository.get_by_id(user_id)
        if not user:
            raise NotFoundException(
                message="User not found",
            )
        return user

    async def create_user(self, payload: UserCreate) -> tuple[User, str]:
        """Saves the account (email not verified yet) and returns (user, otp_code) for emailing."""
        logger.info("User registration started")

        await self.otp.rate_limit(payload.email)
        rows = await self.repository.find_by_phone_or_email(payload.phone, payload.email)
        by_email = next((u for u in rows if u.email.lower() == payload.email), None)
        by_phone = next((u for u in rows if u.phone == payload.phone), None)
        if by_phone and (not by_email or by_phone.id != by_email.id):
            raise ConflictException("A user with this phone number already exists")

        if by_email and (by_email.email_verified_at or not by_email.is_active):
            # A verified account is real, and a suspended one is never touched by a registration
            raise ConflictException("A user with this email already exists")

        password_hash = await run_in_threadpool(hash_password, payload.password)
        try:
            if by_email:
                # Unfinished registration for this email (never verified, not suspended). The
                # newest registration wins, because only the owner of the inbox can finish it:
                # nobody can pre-register someone else's email and keep their own password on it.
                user = await self.repository.update(
                    by_email,
                    {
                        "name": payload.name,
                        "phone": payload.phone,
                        "password_hash": password_hash,
                    },
                )
            else:
                user = await self.repository.create_user(
                    User(
                        name=payload.name,
                        phone=payload.phone,
                        email=payload.email,
                        password_hash=password_hash,
                    )
                )
        except IntegrityError:  # two identical registrations at the same moment
            await self.repository.rollback()
            raise ConflictException(
                "A user with this phone number or email already exists"
            )
       
        logger.info(f"User registered, waiting for email verification: {user.id}")
        code = await self.otp.create(user.email)
        return user, code

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
    def __init__(
        self,
        users: UserRepository,
        tokens: RefreshTokenRepository,
        otp: OtpService,
        resets: PasswordResetRepository,
    ):
        self.users = users
        self.tokens = tokens
        self.otp = otp
        self.resets = resets

    # ---------- helpers ----------
    async def _find_by_identifier(self, identifier: str) -> User | None:
        if "@" in identifier:
            return await self.users.get_by_email(identifier.lower())
        return await self.users.get_by_phone(re.sub(r"[\s\-()]", "", identifier))

    async def _issue_tokens(
        self, user_id: uuid.UUID, user_agent: str | None, ip: str | None
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

    async def verify_email(self, email: str, code: str) -> None:
        """The right code marks the email as verified. The user then logs in normally."""
        invalid = "Invalid or expired code"
        if not await self.otp.verify(email, code):
            raise BadRequestException(invalid)
        user = await self.users.get_by_email(email)
        # Never verify (or otherwise touch) a suspended account
        if not user or user.email_verified_at or not user.is_active:
            raise BadRequestException(invalid)
        await self.users.update(user, {"email_verified_at": datetime.now(timezone.utc)})
        await self.users.commit()
        logger.info(f"Email verified: {user.id}")

    async def resend_verification(self, email: str) -> str | None:
        """Same limits and same answer whether or not the account exists."""
        await self.otp.rate_limit(email)
        user = await self.users.get_by_email(email)
        if user and not user.email_verified_at and user.is_active:
            return await self.otp.create(email)
        return None

      # ---------- login / sessions ----------
    async def login(
        self, identifier: str, password: str, *, user_agent: str | None, ip: str | None
    ) -> tuple[User, TokenPair]:
        user = await self._find_by_identifier(identifier)
        # Always run a hash check (argon2 is CPU-heavy, so keep it off the event loop)
        password_ok = await run_in_threadpool(
            verify_password, password, user.password_hash if user else "DUMMY_HASH"
        )
        if not user or not password_ok:
            logger.warning(f"Failed login from ip={ip}")
            raise UnauthorizedException("Invalid credentials")
        # Only reached with the right password, so it is safe to say why login is refused
        if not user.is_active:
            raise ForbiddenException(
                "Your account has been suspended", data={"code": "ACCOUNT_SUSPENDED"}
            )
        if not user.email_verified_at:
            raise ForbiddenException(
                "Please verify your email before logging in", data={"code": "EMAIL_NOT_VERIFIED"}
            )

        tokens = await self._issue_tokens(user.id, user_agent, ip)
        await self.tokens.commit()
        logger.info(f"Login: user={user.id}")
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
            await self.tokens.revoke_all_for_user(user_id)
            await self.tokens.commit()
            logger.warning(f"Refresh token reuse detected: user={user_id}")
            raise UnauthorizedException("Invalid refresh token")

        user = await self.users.get_by_id(user_id)
        if not user or not user.is_active:
            raise UnauthorizedException("Invalid refresh token")

        if not await self.tokens.revoke_if_active(stored.id):
            raise UnauthorizedException("Invalid refresh token")  # lost a race with a parallel refresh
        tokens = await self._issue_tokens(user.id, user_agent, ip)
        await self.tokens.commit()
        return tokens

    async def logout(self, refresh_token: str | None) -> None:
        """Ends the current session. Never fails."""
        if not refresh_token:
            return
        stored = await self.tokens.get_by_hash(hash_token(refresh_token))
        if stored:
            await self.tokens.revoke_if_active(stored.id)
            await self.tokens.commit()

    async def logout_all(self, user_id: uuid.UUID) -> None:
        await self.tokens.revoke_all_for_user(user_id)
        await self.tokens.commit()

    async def change_password(
        self,
        user: User,
        new_password: str,
        current_password: str | None,
        *,
        user_agent: str | None,
        ip: str | None,
    ) -> TokenPair:
        """Logged-in change. Needs the current password, except when must_change_password is
        set (an admin-forced change). Every other session is signed out afterwards."""
        if not user.must_change_password:
            if not current_password or not await run_in_threadpool(
                verify_password, current_password, user.password_hash
            ):
                raise BadRequestException("Current password is incorrect")

        new_hash = await run_in_threadpool(hash_password, new_password)
        await self.users.update(
            user, {"password_hash": new_hash, "must_change_password": False}
        )
        await self.tokens.revoke_all_for_user(user.id)
        tokens = await self._issue_tokens(user.id, user_agent, ip)
        await self.tokens.commit()
        logger.info(f"Password changed: user={user.id}")
        return tokens

    # ---------- forgot / reset password ----------
    async def forgot_password(self, email: str) -> str | None:
        """Returns the raw token to put in the emailed link, or None. Same answer to the
        caller either way, so this can't be used to find out which emails are registered."""
        await self.otp.rate_limit(email, scope="reset")
        user = await self.users.get_by_email(email)
        if not user or not user.is_active or not user.email_verified_at:
            return None  # unverified and suspended accounts can't reset

        await self.resets.invalidate_all_for_user(user.id)  # only the newest link works
        token = secrets.token_urlsafe(32)
        await self.resets.create(
            user_id=user.id,
            token_hash=hash_token(token),
            expires_at=datetime.now(timezone.utc) + RESET_TOKEN_TTL,
        )
        await self.resets.commit()
        return token

    async def reset_password(self, token: str, new_password: str) -> None:
        invalid = "This reset link is invalid or has expired"
        row = await self.resets.get_valid_by_hash(hash_token(token))
        if not row:
            raise BadRequestException(invalid)
        user = await self.users.get_by_id(row.user_id)
        if not user or not user.is_active or not user.email_verified_at:
            raise BadRequestException(invalid)
        if not await self.resets.mark_used_if_unused(
            row.id
        ):  # lost a race: link already used
            raise BadRequestException(invalid)

        # One transaction: new password, flag cleared, link used, every session signed out
        user.password_hash = await run_in_threadpool(hash_password, new_password)
        user.must_change_password = False
        await self.tokens.revoke_all_for_user(user.id)
        await self.resets.commit()
        logger.info(f"Password reset: user={user.id}")
