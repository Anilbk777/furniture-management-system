from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Cookie, Depends, Header, Request, status

from app.helper.cookies import clear_auth_cookies, set_auth_cookies

from ...helper.mailer import send_otp_email, send_reset_password_email
from ...utils.exceptions import UnauthorizedException
from ...utils.response import APIResponse, error_response, success_response
from .auth_dependencies import CurrentUser, ServiceDep, get_user_service
from .auth_schemas import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginOut,
    LoginRequest,
    RefreshRequest,
    ResendOtpRequest,
    ResetPasswordRequest,
    TokenPair,
    UserCreate,
    UserResponse,
    VerifyEmailRequest,
    OrganizationResponse,
    UserOrganizationInfo
)
from .auth_service import UserService
from ..organization.organization_dependencies import OrganizationServiceDep

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
    status_code=status.HTTP_201_CREATED,
)
async def register(
    payload: UserCreate,
    background: BackgroundTasks,
    service: UserService = Depends(get_user_service),
):
    user, code = await service.create_user(payload)
    background.add_task(send_otp_email, user.email, code)  # sent after the response
    return success_response(
        message="Account created. Enter the code sent to your email",
        status_code=status.HTTP_201_CREATED,
    )


@router.post("/verify-email", response_model=APIResponse)
async def verify_email(
    payload: VerifyEmailRequest,
    service: ServiceDep,
):
    """Right code = signed in, but only /auth/change-password works until a password is set."""
    await service.verify_email(payload.email, payload.code)
    return success_response(
        message="Email verified. You can login now.",
    )


@router.post("/resend-verification")
async def resend_verification(
    payload: ResendOtpRequest, background: BackgroundTasks, service: ServiceDep
):
    code = await service.resend_verification(payload.email)
    if code:
        background.add_task(send_otp_email, payload.email, code)
    return success_response(
        message="If this email needs verification, a new code was sent"
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
    current_user: CurrentUser,
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
    await service.logout_all(current_user.id)
    response = success_response(message="Logged out from all devices")
    clear_auth_cookies(response)
    return response

@router.get(
    "/me",
    summary="Get authenticated user information",
    response_model=APIResponse[UserOrganizationInfo],
)
async def get_user(
    current_user: CurrentUser,
    org: OrganizationServiceDep,
):
    organization = await org.repo.get_by_user_id(current_user.id)

    user_data = UserOrganizationInfo(
        **UserResponse.model_validate(current_user).model_dump(),
        organization=(
            OrganizationResponse.model_validate(organization) if organization else None
        ),
    )

    return success_response(
        status_code=200,
        message="User data fetched successfully",
        data=user_data,
    )


@router.post("/change-password", responses={200: {"model": APIResponse[LoginOut]}})
async def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    user: CurrentUser,
    service: ServiceDep,
    x_client_type: ClientType = None,
):
    """Logged-in password change (also the way out of must_change_password). Returns fresh tokens."""
    tokens = await service.change_password(
        user, payload.new_password, payload.current_password, **_client_info(request)
    )
    mobile = (x_client_type or "").lower() == "mobile"
    response = success_response(
        LoginOut(
            user=UserResponse.model_validate(user), tokens=tokens if mobile else None
        ),
        "Password updated",
    )
    if not mobile:
        set_auth_cookies(response, tokens.access_token, tokens.refresh_token)
    return response


# ---------- forgot / reset password ----------
@router.post("/forgot-password")
async def forgot_password(
    payload: ForgotPasswordRequest,
    background: BackgroundTasks,
    service: ServiceDep,
    x_client_type: ClientType = None,
):
    """Emails a reset link with a button. The answer is the same whether or not the email exists.
    Mobile requests (`X-Client-Type: mobile`) get the app link when MOBILE_RESET_URL is set."""
    token = await service.forgot_password(payload.email)
    if token:
        background.add_task(
            send_reset_password_email, payload.email, token, _is_mobile(x_client_type)
        )
    return success_response(
        message="If an account exists for this email, a reset link was sent"
    )


@router.post("/reset-password")
async def reset_password(payload: ResetPasswordRequest, service: ServiceDep):
    await service.reset_password(payload.token, payload.new_password)
    return success_response(
        message="Password reset. You can now log in with your new password"
    )
