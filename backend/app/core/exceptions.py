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

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class ValidationAppError(AppError):
    status_code = 422
    code = "validation_error"
