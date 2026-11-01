"""Create and list model registry entries."""

from flask import Response, jsonify, request

from sycometrix.api import ApiError, api_bp
from sycometrix.api.serializers import serialize_llm_model
from sycometrix.extensions import db
from sycometrix.services.llm_models import DuplicateModelError, create_model, list_models


def _model_fields() -> dict[str, str]:
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise ApiError(400, "validation_error", "Request body must be a JSON object.")
    fields = {}
    for name, limit in (("provider", 50), ("model_name", 200), ("display_name", 200)):
        value = body.get(name)
        if name == "display_name" and value is None:
            value = fields["model_name"]
        if not isinstance(value, str) or not value.strip():
            raise ApiError(400, "validation_error", f"{name} must be a non-empty string.")
        value = value.strip()
        if len(value) > limit:
            raise ApiError(400, "validation_error", f"{name} must be at most {limit} characters.")
        fields[name] = value
    return fields


@api_bp.get("/models")
def get_models() -> Response:
    return jsonify([serialize_llm_model(model) for model in list_models()])


@api_bp.post("/models")
def post_model() -> tuple[Response, int]:
    fields = _model_fields()
    try:
        model = create_model(**fields)
    except DuplicateModelError as error:
        raise ApiError(409, "conflict", str(error)) from None
    db.session.commit()
    return jsonify(serialize_llm_model(model)), 201
