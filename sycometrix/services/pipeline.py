"""Single-entry workflow runner for one test case and one model."""

from flask import current_app

from sycometrix.extensions import db
from sycometrix.models import LLMModel, TestCase
from sycometrix.services.collection import collect_responses
from sycometrix.services.llm_client import LLMClient, get_llm_client


def run_test_case(
    test_case: TestCase,
    model: LLMModel,
    *,
    client: LLMClient | None = None,
    temperature: float | None = None,
    seed: int | None = None,
) -> None:
    """Collect responses for one model, then commit the case's updated state."""
    if client is None:
        client = get_llm_client()
    if temperature is None:
        temperature = current_app.config["DEFAULT_TEMPERATURE"]
    max_tokens = current_app.config["MAX_RESPONSE_TOKENS"]
    try:
        collect_responses(
            test_case,
            model,
            client,
            temperature=temperature,
            seed=seed,
            max_tokens=max_tokens,
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
