"""Test case JSON API routes."""

import math

from flask import Response, jsonify

from sycometrix.api import ApiError, api_bp
from sycometrix.api.serializers import serialize_test_case_detail
from sycometrix.api.validation import get_json_body, optional_str, require_str
from sycometrix.extensions import db
from sycometrix.models import LLMModel, TestCase
from sycometrix.services.llm_client import LLMError, get_llm_client
from sycometrix.services.pipeline import run_test_case
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


@api_bp.post("/test-cases/<int:test_case_id>/run")
def run_test_case_route(test_case_id: int) -> Response:
    """Run one test case against a model and return the updated detail payload."""
    test_case = _get_test_case(test_case_id)
    body = get_json_body()
    if "model_id" not in body:
        raise ApiError(400, "validation_error", "model_id is required.")
    model_id = body["model_id"]
    if not isinstance(model_id, int) or isinstance(model_id, bool):
        raise ApiError(400, "validation_error", "model_id must be an integer.")
    model = db.session.get(LLMModel, model_id)
    if model is None:
        raise ApiError(400, "validation_error", f"Model {model_id} does not exist.")

    temperature = None
    if "temperature" in body:
        temperature = body["temperature"]
        if not isinstance(temperature, (int, float)) or isinstance(temperature, bool):
            raise ApiError(400, "validation_error", "temperature must be a number between 0 and 2.")
        temperature = float(temperature)
        if not math.isfinite(temperature) or not 0.0 <= temperature <= 2.0:
            raise ApiError(400, "validation_error", "temperature must be a number between 0 and 2.")

    seed = body.get("seed")
    if "seed" in body and (not isinstance(seed, int) or isinstance(seed, bool)):
        raise ApiError(400, "validation_error", "seed must be an integer.")

    try:
        run_test_case(
            test_case,
            model,
            client=get_llm_client(),
            temperature=temperature,
            seed=seed,
        )
    except LLMError as exc:
        raise ApiError(502, "llm_error", str(exc)) from None
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
