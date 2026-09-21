"""
Domain-level exceptions and their HTTP mapping.

Design decision: services raise these typed exceptions instead of
FastAPI's HTTPException directly. This keeps the service layer
transport-agnostic (a service could just as easily be called from a
CLI script or a background worker later, not only from an HTTP route)
and means every route gets the exact same error JSON shape for free,
via one exception handler registered in main.py, instead of each route
hand-building error responses.
"""


class AppError(Exception):
    status_code: int = 400
    code: str = "bad_request"
    headers: dict[str, str] | None = None

    def __init__(self, message: str, code: str | None = None) -> None:
        self.message = message
        # A more specific machine-readable code (e.g. "slot_unavailable")
        # the frontend can translate; defaults to the class's generic code.
        if code is not None:
            self.code = code
        super().__init__(message)


class UnauthorizedError(AppError):
    """Missing, invalid or expired credentials (401)."""

    status_code = 401
    code = "unauthorized"
    headers = {"WWW-Authenticate": "Bearer"}


class ForbiddenError(AppError):
    """Authenticated, but this role may not perform the action (403)."""

    status_code = 403
    code = "forbidden"


class TooManyRequestsError(AppError):
    status_code = 429
    code = "rate_limited"
    # Tells a well-behaved client when to come back (Sprint 17).
    headers = {"Retry-After": "300"}


class PaymentProviderError(AppError):
    """The payment gateway couldn't be reached or refused the request."""

    status_code = 502
    code = "payment_provider_error"


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class ValidationAppError(AppError):
    status_code = 422
    code = "validation_error"
