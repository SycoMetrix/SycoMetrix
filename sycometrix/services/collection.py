"""Collect and persist single-model responses for a test case."""

from sqlalchemy import delete

from sycometrix.extensions import db
from sycometrix.models import Condition, Evaluation, LLMModel, Prompt, Response, TestCase
from sycometrix.services.llm_client import LLMClient


def collect_responses(
    test_case: TestCase,
    model: LLMModel,
    client: LLMClient,
    *,
    temperature: float | None,
    seed: int | None,
    max_tokens: int | None,
) -> list[Response]:
    """Send one independent prompt per condition and save the new responses."""
    ordered_prompts = sorted(
        test_case.prompts,
        key=lambda prompt: list(Condition).index(prompt.condition),
    )
    results: list[tuple[Prompt, str]] = []
    for prompt in ordered_prompts:
        result = client.chat(
            model.model_name,
            [{"role": "user", "content": prompt.prompt_text}],
            temperature=temperature,
            seed=seed,
            max_tokens=max_tokens,
        )
        results.append((prompt, result.text))

    prompt_ids = [prompt.id for prompt in ordered_prompts]
    db.session.execute(
        delete(Response).where(
            Response.model_id == model.id,
            Response.prompt_id.in_(prompt_ids),
        )
    )
    db.session.execute(
        delete(Evaluation).where(
            Evaluation.test_case_id == test_case.id,
            Evaluation.model_id == model.id,
        )
    )

    new_responses: list[Response] = []
    for prompt, text in results:
        response = Response(
            prompt_id=prompt.id,
            model_id=model.id,
            response_text=text,
            stance=None,
            stance_rationale=None,
            temperature=temperature,
            seed=seed,
        )
        db.session.add(response)
        new_responses.append(response)
    db.session.flush()
    return new_responses
