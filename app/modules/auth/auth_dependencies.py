from typing import Annotated
import uuid
import jwt
from fastapi import Cookie, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.helper.security import decode_access_token
from app.utils.exceptions import ForbiddenException, UnauthorizedException

from .auth_models import User
from .auth_repository import UserRepository, RefreshTokenRepository
from .auth_service import UserService, AuthService


def get_user_service(db: AsyncSession = Depends(get_db)) -> UserService:
    repository = UserRepository(db)
    return UserService(db=db, repository=repository)

bearer_scheme = HTTPBearer(auto_error=False)  # shows the "Authorize" button in Swagger


async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    access_cookie: Annotated[str | None, Cookie(alias="access_token")] = None,
) -> User:
    """Mobile: `Authorization: Bearer <token>`. Web: the HttpOnly access cookie."""
    token = credentials.credentials if credentials else access_cookie
    if not token:
        raise UnauthorizedException("Not authenticated")
    try:
        user_id = uuid.UUID(decode_access_token(token)["sub"])
    except jwt.ExpiredSignatureError:
        raise UnauthorizedException(
            "Access token expired"
        )  # client should call /auth/refresh
    except (jwt.InvalidTokenError, ValueError):
        raise UnauthorizedException("Invalid access token")

    # Loaded from the DB on every request, so a disabled user or changed role applies immediately
    user = await UserRepository(db).get_by_id(user_id)
    if not user or not user.is_active:
        raise UnauthorizedException("User not found or inactive")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: str):
    """Usage: @router.delete("/x", dependencies=[Depends(require_roles("admin"))])"""

    async def checker(user: CurrentUser) -> User:
        if user.role not in roles:
            raise ForbiddenException("You don't have permission to do this")
        return user

    return checker

def get_auth_service(db: Annotated[AsyncSession, Depends(get_db)]) -> AuthService:
    return AuthService(UserRepository(db), RefreshTokenRepository(db))

ServiceDep = Annotated[AuthService, Depends(get_auth_service)]