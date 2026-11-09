"""Convert database models to the shared JSON API shapes."""

from datetime import UTC

from sqlalchemy import select

from sycometrix.extensions import db
from sycometrix.models import Condition, Experiment, LLMModel, Response, TestCase
from sycometrix.services.scoring import headline


def _timestamp(value) -> str:
    """Serialize a database timestamp as a UTC ISO 8601 string."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def serialize_experiment_summary(
    experiment: Experiment,
    test_case_count: int | None = None,
) -> dict:
    """Serialize an experiment summary."""
    return {
        "id": experiment.id,
        "name": experiment.name,
        "description": experiment.description,
        "created_at": _timestamp(experiment.created_at),
        "test_case_count": (
            len(experiment.test_cases) if test_case_count is None else test_case_count
        ),
    }


def serialize_test_case_summary(test_case: TestCase) -> dict:
    """Serialize a test case summary."""
    return {
        "id": test_case.id,
        "question": test_case.question,
        "category": test_case.category,
        "evaluations": [
            {
                "model_id": evaluation.model_id,
                "risk_level": evaluation.risk_level.value,
                "score": evaluation.score,
                "flagged": evaluation.flagged,
            }
            for evaluation in test_case.evaluations
        ],
    }


def serialize_experiment_detail(experiment: Experiment) -> dict:
    """Serialize an experiment detail."""
    return {
        **serialize_experiment_summary(experiment),
        "test_cases": [
            serialize_test_case_summary(test_case) for test_case in experiment.test_cases
        ],
    }


def serialize_response(response: Response | None) -> dict | None:
    """Serialize a single response or return None when the response is missing."""
    if response is None:
        return None
    return {
        "id": response.id,
        "response_text": response.response_text,
        "stance": response.stance.value if response.stance is not None else None,
        "stance_rationale": response.stance_rationale,
        "temperature": response.temperature,
        "seed": response.seed,
        "created_at": _timestamp(response.created_at),
    }


def serialize_test_case_results(test_case: TestCase) -> list[dict]:
    """Serialize a test case's per-model collection results."""
    model_ids = {
        response.model_id
        for prompt in test_case.prompts
        for response in prompt.responses
    }
    if not model_ids:
        return []

    models = list(
        db.session.scalars(
            select(LLMModel)
            .where(LLMModel.id.in_(sorted(model_ids)))
            .order_by(LLMModel.display_name, LLMModel.id)
        )
    )
    results: list[dict] = []
    for model in models:
        responses = test_case.responses_for(model.id)
        ordered_responses = {
            condition_name: serialize_response(responses[Condition(condition_name)])
            for condition_name in ("neutral", "correct_belief", "incorrect_belief")
        }
        evaluation = test_case.evaluation_for(model.id)
        evaluation_payload = None
        if evaluation is not None:
            evaluation_payload = {
                "id": evaluation.id,
                "risk_level": evaluation.risk_level.value,
                "score": evaluation.score,
                "flagged": evaluation.flagged,
                "explanation": evaluation.explanation,
                "headline": headline(evaluation.risk_level, evaluation.explanation),
                "created_at": _timestamp(evaluation.created_at),
            }
        results.append(
            {
                "model": serialize_llm_model(model),
                "responses": ordered_responses,
                "evaluation": evaluation_payload,
            }
        )
    return results


def serialize_test_case_detail(test_case: TestCase) -> dict:
    """Serialize a test case detail."""
    condition_order = {"neutral": 0, "correct_belief": 1, "incorrect_belief": 2}
    prompts = sorted(
        test_case.prompts,
        key=lambda prompt: condition_order[prompt.condition.value],
    )
    return {
        "id": test_case.id,
        "experiment_id": test_case.experiment_id,
        "question": test_case.question,
        "correct_answer": test_case.correct_answer,
        "incorrect_belief": test_case.incorrect_belief,
        "category": test_case.category,
        "prompts": [
            {
                "id": prompt.id,
                "condition": prompt.condition.value,
                "prompt_text": prompt.prompt_text,
            }
            for prompt in prompts
        ],
        "results": serialize_test_case_results(test_case),
    }


def serialize_llm_model(model: LLMModel) -> dict:
    """Serialize an LLM model."""
    return {
        "id": model.id,
        "provider": model.provider,
        "model_name": model.model_name,
        "display_name": model.display_name,
    }
