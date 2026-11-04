"""Test case JSON API routes."""

from flask import Response, jsonify

from sycometrix.api import ApiError, api_bp
from sycometrix.api.serializers import serialize_test_case_detail
from sycometrix.api.validation import get_json_body, optional_str, require_str
from sycometrix.extensions import db
from sycometrix.models import TestCase
from sycometrix.services.test_cases import update_test_case


def _get_test_case(test_case_id: int) -> TestCase:
    """Return a test case or raise a 404 error if it does not exist.
    Parameters:
        test_case_id (int): The ID of the test case to retrieve.
    Returns:
        TestCase: The retrieved test case.
    Raises:
        ApiError: If the test case does not exist.
    """
    test_case = db.session.get(TestCase, test_case_id)
    if test_case is None:
        raise ApiError(404, "not_found", f"Test case {test_case_id} does not exist.")
    return test_case


@api_bp.get("/test-cases/<int:test_case_id>")
def get_test_case(test_case_id: int) -> Response:
    """Return a test case detail.
    Parameters:
        test_case_id (int): The ID of the test case to retrieve.
    Returns:
        Response: A JSON response containing the serialized test case detail.
    """
    return jsonify(serialize_test_case_detail(_get_test_case(test_case_id)))


@api_bp.patch("/test-cases/<int:test_case_id>")
def edit_test_case(test_case_id: int) -> Response:
    """Edit a test case.
    Parameters:
        test_case_id (int): The ID of the test case to edit.
    Returns:
        Response: A JSON response containing the serialized test case detail.
    """
    test_case = _get_test_case(test_case_id)
    body = get_json_body()
    fields = {}
    for key, limit in (
        ("question", 2000),
        ("correct_answer", 2000),
        ("incorrect_belief", 2000),
    ):
        if key in body:
            fields[key] = require_str(body, key, limit)
    if "category" in body:
        fields["category"] = optional_str(body, "category", 100)
    update_test_case(test_case, **fields)
    db.session.commit()
    return jsonify(serialize_test_case_detail(test_case))


@api_bp.delete("/test-cases/<int:test_case_id>")
def delete_test_case(test_case_id: int) -> tuple[str, int]:
    """Delete a test case.
    Parameters:
        test_case_id (int): The ID of the test case to delete.
    Returns:
        tuple[str, int]: An empty string and a 204 status code indicating successful deletion.
    """
    test_case = _get_test_case(test_case_id)
    db.session.delete(test_case)
    db.session.commit()
    return "", 204
