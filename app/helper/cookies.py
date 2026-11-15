"""Auth cookie helpers (used for the web app; mobile uses the response body)."""

from fastapi import Response

from app.core.config import settings

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
REFRESH_COOKIE_PATH = (
    "/api/v1/auth"  # refresh cookie is only sent to the auth endpoints
)


def _common() -> dict:
    return {
        "httponly": True,  # JavaScript can't read it, so XSS can't steal it
        "secure": settings.cookie_secure,
        "samesite": settings.cookie_samesite,
        "domain": settings.cookie_domain,
    }


def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    response.set_cookie(
        ACCESS_COOKIE,
        access_token,
        path="/",
        max_age=settings.access_token_expire_minutes * 60,
        **_common(),
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        path=REFRESH_COOKIE_PATH,
        max_age=settings.refresh_token_expire_days * 86400,
        **_common(),
    )


def clear_auth_cookies(response: Response) -> None:
    # Path/domain must match the ones used when the cookie was set
    response.delete_cookie(ACCESS_COOKIE, path="/", **_common())
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_COOKIE_PATH, **_common())