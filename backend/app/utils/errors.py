"""业务异常与统一响应封装。

成功：{"code": 0, "message": "ok", "data": {...}}
失败：{"code": <业务码>, "message": "...", "data": null}
分页：data = {"items": [...], "total": N, "page": P, "size": S}
"""
from typing import Any, Generic, TypeVar

from fastapi import status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

T = TypeVar("T")

# 业务错误码
CODE_OK = 0
CODE_BAD_REQUEST = 40000
CODE_UNAUTHORIZED = 40100
CODE_FORBIDDEN = 40300
CODE_NOT_FOUND = 40400
CODE_CONFLICT = 40900
CODE_VALIDATION = 42200
CODE_INTERNAL = 50000


class AppError(Exception):
    """所有业务异常的基类。"""

    code = CODE_INTERNAL
    http_status = status.HTTP_500_INTERNAL_SERVER_ERROR

    def __init__(self, message: str, *, data: Any = None):
        super().__init__(message)
        self.message = message
        self.data = data


class BadRequestError(AppError):
    code = CODE_BAD_REQUEST
    http_status = status.HTTP_400_BAD_REQUEST


class UnauthorizedError(AppError):
    code = CODE_UNAUTHORIZED
    http_status = status.HTTP_401_UNAUTHORIZED


class ForbiddenError(AppError):
    code = CODE_FORBIDDEN
    http_status = status.HTTP_403_FORBIDDEN


class NotFoundError(AppError):
    code = CODE_NOT_FOUND
    http_status = status.HTTP_404_NOT_FOUND


class ConflictError(AppError):
    code = CODE_CONFLICT
    http_status = status.HTTP_409_CONFLICT


class ValidationError(AppError):
    code = CODE_VALIDATION
    http_status = 422


def ok(data: Any = None, message: str = "ok") -> dict:
    """构造成功响应体。"""
    return {"code": CODE_OK, "message": message, "data": data}


def fail(code: int, message: str, data: Any = None) -> dict:
    """构造失败响应体。"""
    return {"code": code, "message": message, "data": data}


class Page(BaseModel, Generic[T]):
    """分页响应信封。"""

    items: list[T] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    size: int = 20

    @classmethod
    def build(cls, items: list, total: int, page: int, size: int) -> dict:
        return {"items": items, "total": total, "page": page, "size": size}


def error_response(code: int, message: str, http_status: int) -> JSONResponse:
    """构造统一格式的错误响应。"""
    return JSONResponse(
        status_code=http_status,
        content=fail(code, message),
    )
