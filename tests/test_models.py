"""Model, relationship, constraint, and enum tests."""

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


def test_models_relationships_and_enum_round_trip(app):
    experiment = make_experiment()
    case = make_test_case(experiment)
    model = make_llm_model()

    assert len(experiment.test_cases) == 1
    assert case.experiment is experiment
    assert len(case.prompts) == 3

    responses = [
        make_response(prompt, model, text=f"Response for {prompt.condition.value}")
        for prompt in case.prompts
    ]
    evaluation = make_evaluation(case, model, score=0.25, risk_level=RiskLevel.LOW)

    db.session.commit()
    db.session.expire_all()

    loaded_case = db.session.get(TestCase, case.id)
    assert loaded_case is not None
    assert loaded_case.responses_for(model.id)[Condition.NEUTRAL].stance is None
    assert {prompt.condition for prompt in loaded_case.prompts} == set(Condition)
    assert evaluation.test_case_id == loaded_case.id
    assert len(responses) == 3

    loaded_response = responses[0]
    db.session.refresh(loaded_response)
    assert isinstance(loaded_response.stance, (Stance, type(None)))
    assert db.session.get(Evaluation, evaluation.id).risk_level is RiskLevel.LOW


def test_duplicate_prompt_condition_raises_integrity_error(app):
    case = make_test_case()
    case.prompts.append(
        type(case.prompts[0])(
            condition=Condition.NEUTRAL,
            prompt_text="Duplicate neutral prompt",
        )
    )
    import pytest

    with pytest.raises(IntegrityError):
        db.session.flush()


def test_duplicate_response_prompt_model_raises_integrity_error(app):
    case = make_test_case()
    model = make_llm_model()
    prompt = case.prompts[0]
    make_response(prompt, model)

    db.session.add(Response(prompt=prompt, model=model, response_text="duplicate"))
    import pytest

    with pytest.raises(IntegrityError):
        db.session.flush()


def test_deleting_experiment_cascades_children_but_keeps_model(app):
    experiment = make_experiment()
    case = make_test_case(experiment)
    model = make_llm_model()

    prompts = list(case.prompts)

    for prompt in prompts:
        make_response(prompt, model)
    make_evaluation(case, model)

    # Save IDs before deleting the experiment because SQLAlchemy
    # may expire ORM objects after the commit.
    experiment_id = experiment.id
    case_id = case.id
    model_id = model.id
    prompt_ids = [prompt.id for prompt in prompts]

    db.session.delete(experiment)
    db.session.commit()

    # The experiment and its test case should be deleted.
    assert db.session.get(Experiment, experiment_id) is None
    assert db.session.get(TestCase, case_id) is None

    # Its prompts should also be deleted.
    for prompt_id in prompt_ids:
        assert db.session.get(Prompt, prompt_id) is None

    # The model is independent and should remain.
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


def test_enum_values_are_lowercase_strings(app):
    case = make_test_case()
    model = make_llm_model()
    response = make_response(case.prompts[0], model, stance=Stance.DISAGREES)
    db.session.commit()

    raw_value = db.session.execute(
        text("SELECT stance FROM response WHERE id = :id"), {"id": response.id}
    ).scalar_one()
    assert raw_value == "disagrees"
