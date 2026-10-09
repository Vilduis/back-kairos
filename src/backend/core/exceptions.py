from typing import ClassVar

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

HTTP_ERROR_MESSAGES = {
    status.HTTP_404_NOT_FOUND: "Recurso no encontrado",
    status.HTTP_405_METHOD_NOT_ALLOWED: "Método no permitido",
}


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


async def _handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        {"detail": "Los datos enviados no son válidos", "errors": jsonable_encoder(exc.errors())},
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
    )


async def _handle_http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    detail = HTTP_ERROR_MESSAGES.get(exc.status_code, "Error en la solicitud")
    return JSONResponse({"detail": detail}, status_code=exc.status_code, headers=exc.headers)


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, _handle_domain_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_error)
