"""Collect and replace model responses for a test case."""

from sqlalchemy import select

from sycometrix.extensions import db
from sycometrix.models import Condition, Evaluation, Response
from sycometrix.services.collection import collect_responses
from sycometrix.services.llm_client import FakeLLMClient, LLMError
from tests.factories import make_evaluation, make_experiment, make_llm_model, make_test_case


def test_collect_responses_saves_three_independent_answers_and_tracks_sampling(fake_llm):
    experiment = make_experiment("Collection experiment")
    test_case = make_test_case(experiment)
    model = make_llm_model(model_name="fake/one", display_name="Fake One")

    def responder(model_name: str, messages: list[dict[str, str]]) -> str:
        return f"{model_name}:{messages[0]['content']}"

    fake_llm._responder = responder

    rows = collect_responses(
        test_case,
        model,
        fake_llm,
        temperature=0.5,
        seed=7,
        max_tokens=128,
    )

    assert len(fake_llm.calls) == 3
    assert all(
        len(call["messages"]) == 1 and call["messages"][0]["role"] == "user"
        for call in fake_llm.calls
    )
    assert [call["messages"][0]["content"] for call in fake_llm.calls] == [
        prompt.prompt_text
        for prompt in sorted(
            test_case.prompts,
            key=lambda item: list(Condition).index(item.condition),
        )
    ]
    assert len(rows) == 3
    assert len(db.session.scalars(select(Response)).all()) == 3
    assert {row.prompt.condition.value for row in db.session.scalars(select(Response)).all()} == {
        "neutral",
        "correct_belief",
        "incorrect_belief",
    }
    assert all(row.temperature == 0.5 for row in db.session.scalars(select(Response)).all())
    assert all(row.seed == 7 for row in db.session.scalars(select(Response)).all())


def test_collect_responses_replaces_existing_rows_and_deletes_stale_evaluation(fake_llm):
    experiment = make_experiment("Collection experiment")
    test_case = make_test_case(experiment)
    model = make_llm_model(model_name="fake/two", display_name="Fake Two")
    first = collect_responses(
        test_case,
        model,
        FakeLLMClient(lambda _model, _messages: "old"),
        temperature=0.0,
        seed=1,
        max_tokens=12,
    )
    assert len(first) == 3
    make_evaluation(test_case, model)
    db.session.commit()

    fake_llm._responder = lambda _model, _messages: "new"
    collect_responses(
        test_case,
        model,
        fake_llm,
        temperature=0.1,
        seed=2,
        max_tokens=30,
    )
    db.session.commit()

    responses = db.session.scalars(select(Response)).all()
    assert len(responses) == 3
    assert {response.response_text for response in responses} == {"new"}
    assert db.session.scalar(
        select(Evaluation.id).where(
            Evaluation.test_case_id == test_case.id,
            Evaluation.model_id == model.id,
        )
    ) is None


def test_collect_responses_rolls_back_on_later_failure(fake_llm):
    experiment = make_experiment("Collection experiment")
    test_case = make_test_case(experiment)
    model = make_llm_model(model_name="fake/three", display_name="Fake Three")

    def responder(model_name: str, messages: list[dict[str, str]]) -> str:
        if model_name == model.model_name and len(fake_llm.calls) == 2:
            raise LLMError("third call failed")
        return "keep me"

    fake_llm._responder = responder
    collect_responses(
        test_case,
        model,
        FakeLLMClient(lambda _model, _messages: "original"),
        temperature=0.0,
        seed=1,
        max_tokens=10,
    )
    db.session.commit()

    try:
        collect_responses(
            test_case,
            model,
            fake_llm,
            temperature=0.0,
            seed=2,
            max_tokens=10,
        )
    except LLMError:
        pass
    else:
        raise AssertionError("Expected LLMError")

    rows = db.session.scalars(select(Response)).all()
    assert len(rows) == 3
    assert {row.response_text for row in rows} == {"original"}
    assert all(row.temperature == 0.0 for row in rows)
    assert all(row.seed == 1 for row in rows)
