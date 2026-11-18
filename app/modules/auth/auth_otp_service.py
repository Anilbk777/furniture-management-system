"""6-digit email OTP stored in Redis, with attempt limits and send limits."""

import hmac
import secrets

from redis.asyncio import Redis


from app.utils.exceptions import AppException

OTP_TTL = 600  # a code is valid for 10 minutes
MAX_ATTEMPTS = 5  # wrong guesses before the code is thrown away
RESEND_COOLDOWN = 60  # seconds between two codes for the same email
MAX_SENDS_PER_HOUR = 5


class OtpService:
    def __init__(self, redis: Redis):
        self.redis = redis

    async def rate_limit(self, email: str, scope: str = "otp") -> None:
        """Raises 429 if this email asked too recently / too often. `scope` keeps separate
        counters for separate features (e.g. "otp" and "reset")."""
        if not await self.redis.set(
            f"{scope}:cooldown:{email}", 1, nx=True, ex=RESEND_COOLDOWN
        ):
            raise AppException(
                "Please wait a minute before trying again", status_code=429
            )
        sends_key = f"{scope}:sends:{email}"
        sends = await self.redis.incr(sends_key) #type: ignore
        if sends == 1:
            await self.redis.expire(sends_key, 3600)
        if sends > MAX_SENDS_PER_HOUR:
            raise AppException(
                "Too many requests. Try again in an hour", status_code=429
            )

    async def create(self, email: str) -> str:
        """Stores a fresh code (replacing any old one) and returns it for emailing."""
        code = f"{secrets.randbelow(10**6):06d}"
        await self.redis.set(f"otp:code:{email}", code, ex=OTP_TTL)
        await self.redis.delete(f"otp:attempts:{email}")
        return code

    async def verify(self, email: str, code: str) -> bool:
        """True only for the right, unexpired code. A code works once."""
        code_key, attempts_key = f"otp:code:{email}", f"otp:attempts:{email}"
        stored = await self.redis.get(code_key)
        if stored is None:  # expired, used, or never sent
            return False
        attempts = await self.redis.incr(attempts_key) #type: ignore
        if attempts == 1:
            await self.redis.expire(attempts_key, OTP_TTL)
        if (
            attempts > MAX_ATTEMPTS
        ):  # brute-force guard: 6 digits = only 1,000,000 options
            await self.redis.delete(code_key, attempts_key)
            return False
        if not hmac.compare_digest(stored, code):  # type: ignore
            return False
        await self.redis.delete(code_key, attempts_key)
        return True
