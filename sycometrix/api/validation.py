"""Validation helpers for JSON API request bodies."""

from flask import request

from sycometrix.api import ApiError


def get_json_body() -> dict:
    """Return the request JSON object or raise a validation error.
    Returns:
        dict: The request JSON object.
    Raises:
        ApiError: If the request body is not a JSON object.
    """
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise ApiError(400, "validation_error", "Request body must be a JSON object.")
    return body


def require_str(body: dict, key: str, max_len: int) -> str:
    """Return a required, stripped string field.
    Parameters:
        body (dict): The request JSON object.
        key (str): The key to look up in the JSON object.
        max_len (int): The maximum length of the string.
    Returns:
        str: The required, stripped string field.
    Raises:
        ApiError: If the field is missing or not a string.
    """
    value = body.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ApiError(400, "validation_error", f"{key} is required.")
    value = value.strip()
    if len(value) > max_len:
        raise ApiError(400, "validation_error", f"{key} must be at most {max_len} characters.")
    return value


def optional_str(body: dict, key: str, max_len: int) -> str | None:
    """Return an optional, stripped string field.
    Parameters:
        body (dict): The request JSON object.
        key (str): The key to look up in the JSON object.
        max_len (int): The maximum length of the string.
    Returns:
        str | None: The optional, stripped string field, or None if it's missing.
    Raises:
        ApiError: If the field is not a string.
    """
    value = body.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ApiError(400, "validation_error", f"{key} must be a string.")
    value = value.strip()
    if len(value) > max_len:
        raise ApiError(400, "validation_error", f"{key} must be at most {max_len} characters.")
    return value or None
