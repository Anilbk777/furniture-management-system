"""Custom exceptions + global handlers.

Raise these anywhere (services, routes) and the handlers turn them
into the standard error response.
"""
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import re


from .logger import get_logger
from .response import error_response

logger = get_logger(__name__)


# ---------- Custom exceptions ----------
class AppException(Exception):
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    message: str = "Internal server error"

    def __init__(
        self, message: str | None = None, data=None, status_code: int | None = None
    ):
        self.message = message or self.message
        self.status_code = status_code or self.status_code
        self.data = data
        super().__init__(self.message)


class BadRequestException(AppException):
    status_code = status.HTTP_400_BAD_REQUEST
    message = "Bad request"


class UnauthorizedException(AppException):
    status_code = status.HTTP_401_UNAUTHORIZED
    message = "Unauthorized"


class ForbiddenException(AppException):
    status_code = status.HTTP_403_FORBIDDEN
    message = "Forbidden"


class NotFoundException(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    message = "Resource not found"


class ConflictException(AppException):
    status_code = status.HTTP_409_CONFLICT
    message = "Resource already exists"


# ---------- Handlers ----------
async def app_exception_handler(request: Request, exc: AppException):
    logger.warning(
        f"{request.method} {request.url.path} -> {exc.status_code}: {exc.message}"
    )
    return error_response(exc.message, exc.status_code, exc.data)


async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    message = exc.detail if isinstance(exc.detail, str) else "HTTP error"
    logger.warning(
        f"{request.method} {request.url.path} -> {exc.status_code}: {message}"
    )
    return error_response(message, exc.status_code)

def _message(err: dict) -> str:
    """Turn Pydantic's generic wording ("String should...") into "<Field> should..."."""
    field = next((p for p in reversed(err["loc"]) if isinstance(p, str)), "input")
    label = field.replace("_", " ").capitalize()
    if err["type"] == "missing":
        return f"{label} is required"
    msg = err["msg"].removeprefix("Value error, ")
    return re.sub(r"^(String|Input|[Vv]alue)\b", label, msg)


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    message = _message(exc.errors()[0])
    logger.warning(
        f"{request.method} {request.url.path} -> validation error: {message}"
    )
    return error_response(message, status.HTTP_422_UNPROCESSABLE_CONTENT)

async def unhandled_exception_handler(request: Request, exc: Exception):
    # Full traceback goes to the logs, never to the client
    logger.exception(f"Unhandled error on {request.method} {request.url.path}")
    return error_response(
        "Internal server error", status.HTTP_500_INTERNAL_SERVER_ERROR
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppException, app_exception_handler)  # type: ignore
    app.add_exception_handler(StarletteHTTPException, http_exception_handler) # type: ignore
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore
    app.add_exception_handler(Exception, unhandled_exception_handler)