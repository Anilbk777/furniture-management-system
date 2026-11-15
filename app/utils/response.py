"""Standard API response format.

{
    "success": true,
    "status_code": 200,
    "message": "message here",
    "data": ...
}
"""

from typing import Any, Generic, Optional, TypeVar

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    success: bool
    status_code: int
    message: str
    data: Optional[T] = None

class Pagination(BaseModel):
    total: int
    page: int
    limit: int
    total_pages: int


def success_response(
    data: Any = None,
    message: str = "Success",
    status_code: int = 200,
) -> JSONResponse:
    body = APIResponse[Any](
        success=True, status_code=status_code, message=message, data=data
    )
    return JSONResponse(status_code=status_code, content=jsonable_encoder(body))


def error_response(
    message: str = "Something went wrong",
    status_code: int = 500,
    data: Any = None,
) -> JSONResponse:
    body = APIResponse[Any](
        success=False, status_code=status_code, message=message, data=data
    )
    return JSONResponse(status_code=status_code, content=jsonable_encoder(body))