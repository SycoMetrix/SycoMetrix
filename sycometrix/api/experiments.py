"""Experiment JSON API routes."""

from flask import Response, jsonify
from sqlalchemy import func, select

from sycometrix.api import ApiError, api_bp
from sycometrix.api.serializers import (
    serialize_experiment_detail,
    serialize_experiment_summary,
    serialize_test_case_detail,
)
from sycometrix.api.validation import get_json_body, optional_str, require_str
from sycometrix.extensions import db
from sycometrix.models import Experiment, TestCase
from sycometrix.services.test_cases import create_test_case


def _get_experiment(experiment_id: int) -> Experiment:
    experiment = db.session.get(Experiment, experiment_id)
    if experiment is None:
        raise ApiError(404, "not_found", f"Experiment {experiment_id} does not exist.")
    return experiment


@api_bp.get("/experiments")
def list_experiments() -> Response:
    rows = db.session.execute(
        select(Experiment, func.count(TestCase.id))
        .outerjoin(TestCase)
        .group_by(Experiment.id)
        .order_by(Experiment.created_at.desc(), Experiment.id.desc())
    ).all()
    return jsonify([serialize_experiment_summary(experiment, count) for experiment, count in rows])


@api_bp.post("/experiments")
def create_experiment() -> tuple[Response, int]:
    body = get_json_body()
    experiment = Experiment(
        name=require_str(body, "name", 200),
        description=optional_str(body, "description", 2000),
    )
    db.session.add(experiment)
    db.session.commit()
    return jsonify(serialize_experiment_detail(experiment)), 201


@api_bp.get("/experiments/<int:experiment_id>")
def get_experiment(experiment_id: int) -> Response:
    return jsonify(serialize_experiment_detail(_get_experiment(experiment_id)))


@api_bp.patch("/experiments/<int:experiment_id>")
def update_experiment(experiment_id: int) -> Response:
    experiment = _get_experiment(experiment_id)
    body = get_json_body()
    if "name" in body:
        experiment.name = require_str(body, "name", 200)
    if "description" in body:
        experiment.description = optional_str(body, "description", 2000)
    db.session.commit()
    return jsonify(serialize_experiment_detail(experiment))


@api_bp.delete("/experiments/<int:experiment_id>")
def delete_experiment(experiment_id: int) -> tuple[str, int]:
    experiment = _get_experiment(experiment_id)
    db.session.delete(experiment)
    db.session.commit()
    return "", 204


@api_bp.post("/experiments/<int:experiment_id>/test-cases")
def create_experiment_test_case(experiment_id: int) -> tuple[Response, int]:
    experiment = _get_experiment(experiment_id)
    body = get_json_body()
    test_case = create_test_case(
        experiment,
        require_str(body, "question", 2000),
        require_str(body, "correct_answer", 2000),
        require_str(body, "incorrect_belief", 2000),
        optional_str(body, "category", 100),
    )
    db.session.commit()
    return jsonify(serialize_test_case_detail(test_case)), 201


@api_bp.get("/experiments/<int:experiment_id>/summary")
def experiment_summary(experiment_id: int) -> Response:
    from flask import request

    from sycometrix.models import LLMModel
    from sycometrix.services.summary import build_summary

    _get_experiment(experiment_id)

    raw = request.args.get("model_id")
    model_id = None

    if raw is not None:
        if not raw.isdecimal() or int(raw) < 1:
            raise ApiError(
                400,
                "validation_error",
                "model_id must be a valid integer.",
            )

        model_id = int(raw)

        if db.session.get(LLMModel, model_id) is None:
            raise ApiError(
                400,
                "validation_error",
                f"Model {model_id} does not exist.",
            )

    return jsonify(build_summary(experiment_id, model_id))
