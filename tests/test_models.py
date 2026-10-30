"""Model, relationship, constraint, and enum tests."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from sycometrix.extensions import db
from sycometrix.models import (
    Condition,
    Evaluation,
    Experiment,
    LLMModel,
    Prompt,
    Response,
    RiskLevel,
    Stance,
    TestCase,
)
from tests.factories import (
    make_evaluation,
    make_experiment,
    make_llm_model,
    make_response,
    make_test_case,
)


def test_models_relationships_navigate_both_ways(app):
    experiment = make_experiment()
    case = make_test_case(experiment)
    model = make_llm_model()
    for prompt in case.prompts:
        make_response(prompt, model, text=f"Response for {prompt.condition.value}")
    make_evaluation(case, model, score=0.25, risk_level=RiskLevel.LOW)

    db.session.commit()
    db.session.expire_all()

    loaded_experiment = db.session.get(Experiment, experiment.id)
    loaded_model = db.session.get(LLMModel, model.id)

    # Parent -> children
    [loaded_case] = loaded_experiment.test_cases
    assert {prompt.condition for prompt in loaded_case.prompts} == set(Condition)
    assert len(loaded_model.responses) == 3
    [evaluation] = loaded_case.evaluations
    assert loaded_model.evaluations == [evaluation]

    # Child -> parent
    assert loaded_case.experiment is loaded_experiment
    for prompt in loaded_case.prompts:
        [response] = prompt.responses
        assert response.prompt is prompt
        assert response.model is loaded_model
        assert prompt.test_case is loaded_case
    assert evaluation.test_case is loaded_case
    assert evaluation.model is loaded_model


def test_duplicate_prompt_condition_raises_integrity_error(app):
    case = make_test_case()
    db.session.add(
        Prompt(test_case=case, condition=Condition.NEUTRAL, prompt_text="Duplicate neutral prompt")
    )

    with pytest.raises(IntegrityError):
        db.session.flush()


def test_duplicate_response_prompt_model_raises_integrity_error(app):
    case = make_test_case()
    model = make_llm_model()
    prompt = case.prompts[0]
    make_response(prompt, model)

    db.session.add(Response(prompt=prompt, model=model, response_text="duplicate"))

    with pytest.raises(IntegrityError):
        db.session.flush()


def test_deleting_experiment_cascades_children_but_keeps_model(app):
    experiment = make_experiment()
    case = make_test_case(experiment)
    model = make_llm_model()
    responses = [make_response(prompt, model) for prompt in case.prompts]
    evaluation = make_evaluation(case, model)

    # Save IDs before deleting, since the ORM objects expire on commit.
    experiment_id = experiment.id
    case_id = case.id
    model_id = model.id
    prompt_ids = [prompt.id for prompt in case.prompts]
    response_ids = [response.id for response in responses]
    evaluation_id = evaluation.id

    db.session.delete(experiment)
    db.session.commit()

    assert db.session.get(Experiment, experiment_id) is None
    assert db.session.get(TestCase, case_id) is None
    for prompt_id in prompt_ids:
        assert db.session.get(Prompt, prompt_id) is None
    for response_id in response_ids:
        assert db.session.get(Response, response_id) is None
    assert db.session.get(Evaluation, evaluation_id) is None
    assert db.session.get(LLMModel, model_id) is not None


def test_responses_for_returns_each_condition_and_missing_as_none(app):
    case = make_test_case()
    model = make_llm_model()
    neutral_prompt = case.prompt_for(Condition.NEUTRAL)
    assert neutral_prompt is not None
    make_response(neutral_prompt, model, stance=Stance.AGREES)

    results = case.responses_for(model.id)
    assert set(results) == set(Condition)
    assert results[Condition.NEUTRAL].stance is Stance.AGREES
    assert results[Condition.CORRECT_BELIEF] is None
    assert results[Condition.INCORRECT_BELIEF] is None
    assert case.evaluation_for(model.id) is None


def test_enum_columns_round_trip_and_store_lowercase_values(app):
    case = make_test_case()
    model = make_llm_model()
    prompt = case.prompt_for(Condition.INCORRECT_BELIEF)
    response = make_response(prompt, model, stance=Stance.DISAGREES)
    evaluation = make_evaluation(case, model, risk_level=RiskLevel.HIGH)
    db.session.commit()
    db.session.expire_all()

    assert db.session.get(Prompt, prompt.id).condition is Condition.INCORRECT_BELIEF
    assert db.session.get(Response, response.id).stance is Stance.DISAGREES
    assert db.session.get(Evaluation, evaluation.id).risk_level is RiskLevel.HIGH

    def raw(sql: str, row_id: int) -> str:
        return db.session.execute(text(sql), {"id": row_id}).scalar_one()

    assert raw("SELECT condition FROM prompt WHERE id = :id", prompt.id) == "incorrect_belief"
    assert raw("SELECT stance FROM response WHERE id = :id", response.id) == "disagrees"
    assert raw("SELECT risk_level FROM evaluation WHERE id = :id", evaluation.id) == "high"
