"""Domain exceptions plus the global Flask error handlers."""

import logging
from typing import Any

from werkzeug.exceptions import HTTPException

from app.utils.responses import fail

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base class for expected, client-facing failures."""

    code = "APP_ERROR"
    status = 400

    def __init__(self, message: str, details: Any = None, status: int | None = None):
        super().__init__(message)
        self.message = message
        self.details = details
        if status is not None:
            self.status = status


class ValidationError(AppError):
    code = "VALIDATION_ERROR"
    status = 400


class NotFoundError(AppError):
    code = "NOT_FOUND"
    status = 404


class InsufficientStockError(AppError):
    code = "INSUFFICIENT_STOCK"
    status = 409


class ConflictError(AppError):
    code = "CONFLICT"
    status = 409


def register_error_handlers(app) -> None:
    """Attach handlers so no traceback ever leaks to a client."""

    @app.errorhandler(AppError)
    def _handle_app_error(exc: AppError):
        logger.warning("AppError %s: %s", exc.code, exc.message)
        return fail(exc.code, exc.message, exc.status, exc.details)

    @app.errorhandler(HTTPException)
    def _handle_http_error(exc: HTTPException):
        return fail(
            code=(exc.name or "HTTP_ERROR").upper().replace(" ", "_"),
            message=exc.description or "HTTP error",
            status=exc.code or 500,
        )

    @app.errorhandler(Exception)
    def _handle_unexpected(exc: Exception):
        logger.exception("Unhandled exception: %s", exc)
        return fail(
            "INTERNAL_SERVER_ERROR",
            "An unexpected error occurred.",
            500,
        )
