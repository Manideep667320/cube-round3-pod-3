"""Consistent API error handling."""
from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

import jwt


class AppError(Exception):
    """Base class for safe, user-facing application errors."""

    def __init__(self, message: str, code: str = "app_error", status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found.", code: str = "not_found"):
        super().__init__(message, code=code, status_code=404)


class AuthError(AppError):
    def __init__(self, message: str = "Authentication failed.", code: str = "auth_failed"):
        super().__init__(message, code=code, status_code=401)


class ForbiddenError(AppError):
    def __init__(self, message: str = "You do not have access to this resource.", code: str = "forbidden"):
        super().__init__(message, code=code, status_code=403)


class ConflictError(AppError):
    def __init__(self, message: str = "Conflict with the current state.", code: str = "conflict"):
        super().__init__(message, code=code, status_code=409)


class RateLimitedError(AppError):
    def __init__(self, message: str = "Too many requests. Please try again later.", code: str = "rate_limited"):
        super().__init__(message, code=code, status_code=429)


class PayloadTooLargeError(AppError):
    def __init__(self, message: str = "Payload too large.", code: str = "payload_too_large"):
        super().__init__(message, code=code, status_code=413)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_request: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_request: Request, exc: RequestValidationError):
        # Do not echo submitted values (may contain secrets).
        errors = [
            {"field": ".".join(str(p) for p in e.get("loc", []) if p != "body"), "message": e.get("msg", "invalid")}
            for e in exc.errors()[:10]
        ]
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": {"code": "validation_error", "message": "Request validation failed.", "details": errors}},
        )

    @app.exception_handler(jwt.PyJWTError)
    async def _jwt_error(_request: Request, _exc: jwt.PyJWTError):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"error": {"code": "invalid_token", "message": "Invalid or expired token."}},
        )

    @app.exception_handler(Exception)
    async def _unhandled(_request: Request, _exc: Exception):
        # Never leak internals to the client; the traceback goes to server logs.
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": {"code": "internal_error", "message": "An unexpected error occurred."}},
        )
