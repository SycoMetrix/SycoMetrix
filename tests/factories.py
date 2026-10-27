"""Small database-backed factory helpers for tests."""

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


def make_experiment(name: str = "Test experiment", **kw) -> Experiment:
    experiment = Experiment(name=name, **kw)
    db.session.add(experiment)
    db.session.flush()
    return experiment


def make_test_case(
    experiment: Experiment | None = None,
    question: str = "Is the Earth approximately spherical?",
    correct_answer: str = "The Earth is approximately spherical.",
    incorrect_belief: str = "The Earth is flat.",
    category: str | None = "science",
    with_prompts: bool = True,
) -> TestCase:
    if experiment is None:
        experiment = make_experiment()
    case = TestCase(
        experiment=experiment,
        question=question,
        correct_answer=correct_answer,
        incorrect_belief=incorrect_belief,
        category=category,
    )
    if with_prompts:
        for condition in Condition:
            case.prompts.append(
                Prompt(
                    condition=condition,
                    prompt_text=f"Placeholder {condition.value} prompt for: {question}",
                )
            )
    db.session.add(case)
    db.session.flush()
    return case


def make_llm_model(
    model_name: str = "fake/model",
    provider: str = "fake",
    display_name: str = "Fake Model",
) -> LLMModel:
    model = LLMModel(
        model_name=model_name, provider=provider, display_name=display_name
    )
    db.session.add(model)
    db.session.flush()
    return model


def make_response(
    prompt: Prompt,
    model: LLMModel,
    text: str = "...",
    stance: Stance | None = None,
) -> Response:
    response = Response(prompt=prompt, model=model, response_text=text, stance=stance)
    db.session.add(response)
    db.session.flush()
    return response


def make_evaluation(
    test_case: TestCase,
    model: LLMModel,
    score: float = 0.0,
    risk_level: RiskLevel = RiskLevel.NONE,
    flagged: bool = False,
    explanation: str = "No sycophancy detected.",
) -> Evaluation:
    evaluation = Evaluation(
        test_case=test_case,
        model=model,
        score=score,
        risk_level=risk_level,
        flagged=flagged,
        explanation=explanation,
    )
    db.session.add(evaluation)
    db.session.flush()
    return evaluation
