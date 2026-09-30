from typing import ClassVar

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse


class DomainError(Exception):
    status_code = status.HTTP_400_BAD_REQUEST
    headers: ClassVar[dict[str, str] | None] = None

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class NotFoundError(DomainError):
    status_code = status.HTTP_404_NOT_FOUND


class AuthenticationError(DomainError):
    status_code = status.HTTP_401_UNAUTHORIZED
    headers: ClassVar[dict[str, str] | None] = {"WWW-Authenticate": "Bearer"}


class PermissionDeniedError(DomainError):
    status_code = status.HTTP_403_FORBIDDEN


async def _handle_domain_error(_: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers)


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, _handle_domain_error)
