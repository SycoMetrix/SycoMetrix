"""JSON API blueprint, mounted at /api, with the shared error shape."""

from flask import Blueprint, Response, jsonify, request
from werkzeug.exceptions import HTTPException

api_bp = Blueprint("api", __name__)

API_PREFIX = "/api"

_ERROR_CODES = {
    400: "validation_error",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    500: "internal_error",
    502: "llm_error",
}


class ApiError(Exception):
    """Raised by services or routes; turned into a JSON error response by the blueprint."""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def api_error(status: int, code: str, message: str) -> tuple[Response, int]:
    return jsonify({"error": {"code": code, "message": message}}), status


def _is_api_request() -> bool:
    return request.path == API_PREFIX or request.path.startswith(API_PREFIX + "/")


# Both handlers are registered app-wide. Routing errors (unknown URL, wrong method) happen
# before Flask knows which blueprint a request belongs to, so blueprint-only handlers never
# see them, and services that raise ApiError may be called from outside the blueprint.
@api_bp.app_errorhandler(ApiError)
def _handle_api_error(e: ApiError) -> tuple[Response, int]:
    return api_error(e.status, e.code, e.message)


# Non-API paths fall through to Flask's default HTML error pages.
@api_bp.app_errorhandler(HTTPException)
def _handle_http_exception(e: HTTPException) -> HTTPException | tuple[Response, int]:
    if not _is_api_request():
        return e
    status = e.code or 500
    code = _ERROR_CODES.get(status, (e.name or "error").lower().replace(" ", "_"))
    if status >= 500:
        # Flask has already logged the original exception; never leak its details.
        return api_error(status, code, "An unexpected error occurred.")
    return api_error(status, code, e.description or e.name)


@api_bp.get("/health")
def health() -> Response:
    return jsonify({"status": "ok"})
