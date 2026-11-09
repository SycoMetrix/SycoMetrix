"""Response-level API endpoints, including stance overrides."""

from flask import Response as FlaskResponse
from flask import jsonify

from sycometrix.api import ApiError, api_bp
from sycometrix.api.serializers import serialize_test_case_detail
from sycometrix.api.validation import get_json_body
from sycometrix.extensions import db
from sycometrix.models import Response, Stance
from sycometrix.services.scoring import evaluate_test_case


@api_bp.patch("/responses/<int:response_id>")
def update_response(response_id: int) -> FlaskResponse:
    """Manually override a response stance and return the updated test case detail."""
    response = db.session.get(Response, response_id)
    if response is None:
        raise ApiError(404, "not_found", f"Response {response_id} does not exist.")

    body = get_json_body()
    if "stance" not in body:
        raise ApiError(400, "validation_error", "stance is required.")

    raw_stance = body["stance"]
    if not isinstance(raw_stance, str):
        raise ApiError(
            400,
            "validation_error",
            "stance must be one of: agrees, disagrees, unclear.",
        )

    try:
        stance = Stance(raw_stance.strip().lower())
    except ValueError as exc:
        raise ApiError(
            400,
            "validation_error",
            "stance must be one of: agrees, disagrees, unclear.",
        ) from exc

    response.stance = stance
    response.stance_rationale = "Set manually."

    test_case = response.prompt.test_case
    responses = test_case.responses_for(response.model_id)
    if all(
        response_item is not None and response_item.stance is not None
        for response_item in responses.values()
    ):
        evaluate_test_case(test_case, response.model)

    db.session.commit()
    return jsonify(serialize_test_case_detail(test_case))
