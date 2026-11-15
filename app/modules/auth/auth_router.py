from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Header, Request

from app.helper.cookies import clear_auth_cookies, set_auth_cookies

from ...utils.exceptions import UnauthorizedException
from ...utils.response import APIResponse, error_response, success_response
from .auth_dependencies import CurrentUser, ServiceDep, get_user_service
from .auth_schemas import (
    LoginOut,
    LoginRequest,
    RefreshRequest,
    TokenPair,
    UserCreate,
    UserResponse,
)
from .auth_service import UserService

ClientType = Annotated[str | None, Header()]  # header: X-Client-Type: mobile
RefreshCookie = Annotated[str | None, Cookie(alias="refresh_token")]


def _client_info(request: Request) -> dict:
    return {
        "user_agent": request.headers.get("user-agent"),
        "ip": request.client.host if request.client else None,
    }


def _is_mobile(x_client_type: str | None) -> bool:
    return (x_client_type or "").lower() == "mobile"


router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/register",
    summary="Register a new user",
    responses={201: {"model": APIResponse[UserResponse]}},
)
async def create_user(
    payload: UserCreate,
    service: UserService = Depends(get_user_service),
):
    data = await service.create_user(payload)
    return success_response(
        status_code=201,
        message="User Register Sucessfully",
        data=UserResponse.model_validate(data),
    )


@router.post("/login", responses={200: {"model": APIResponse[LoginOut]}})
async def login(
    payload: LoginRequest,
    request: Request,
    service: ServiceDep,
    x_client_type: ClientType = None,
):
    """Log in with phone number OR email + password.

    - Web: tokens are set as HttpOnly cookies (not readable by JavaScript).
    - Mobile (header `X-Client-Type: mobile`): tokens are returned in the response body.
    """
    user, tokens = await service.login(
        payload.identifier, payload.password, **_client_info(request)
    )
    mobile = _is_mobile(x_client_type)
    response = success_response(
        LoginOut(
            user=UserResponse.model_validate(user), tokens=tokens if mobile else None
        ),
        "Login successful",
    )
    if not mobile:
        set_auth_cookies(response, tokens.access_token, tokens.refresh_token)
    return response


@router.post("/refresh", responses={200: {"model": APIResponse[TokenPair]}})
async def refresh(
    current_user:CurrentUser,
    request: Request,
    service: ServiceDep,
    payload: RefreshRequest | None = None,
    refresh_cookie: RefreshCookie = None,
):
    """Rotate tokens. Web: reads the refresh cookie. Mobile: send `refresh_token` in the body."""
    body_token = payload.refresh_token if payload else None
    token = body_token or refresh_cookie
    try:
        if not token:
            raise UnauthorizedException("Refresh token missing")
        tokens = await service.refresh(token, **_client_info(request))
    except UnauthorizedException as exc:
        response = error_response(exc.message, exc.status_code)
        clear_auth_cookies(
            response
        )  # drop dead cookies so the web app goes to the login page
        return response

    if body_token:  # mobile
        return success_response(tokens, "Token refreshed")
    response = success_response(message="Token refreshed")
    set_auth_cookies(response, tokens.access_token, tokens.refresh_token)
    return response


@router.post("/logout")
async def logout(
    current_user:CurrentUser,
    service: ServiceDep,
    payload: RefreshRequest | None = None,
    refresh_cookie: RefreshCookie = None,
):
    await service.logout((payload.refresh_token if payload else None) or refresh_cookie)
    response = success_response(message="Logged out")
    clear_auth_cookies(response)
    return response


@router.post("/logout-all")
async def logout_all(current_user: CurrentUser, service: ServiceDep):
    """Ends every session of this user (all devices)."""
    await service.logout_all(current_user.id)
    response = success_response(message="Logged out from all devices")
    clear_auth_cookies(response)
    return response


@router.get(
    "/me",
    summary="Get a user information",
    responses={201: {"model": APIResponse[UserResponse]}},
)
async def get_user(current_user: CurrentUser):
    return success_response(
        status_code=201,
        message="User data fetch Sucessfully",
        data=UserResponse.model_validate(current_user),
    )
