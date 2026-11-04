"""Convert database models to the shared JSON API shapes."""

from datetime import UTC

from sycometrix.models import Experiment, LLMModel, TestCase


def _timestamp(value) -> str:
    """Serialize a database timestamp as a UTC ISO 8601 string.
    Parameters:
        value: The database timestamp to serialize.
    Returns:
        str: The serialized timestamp as a UTC ISO 8601 string.
    """
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def serialize_experiment_summary(experiment: Experiment, 
                                 test_case_count: int | None = None) -> dict:
    """Serialize an experiment summary.

    Parameters:
        experiment (Experiment): The experiment to serialize.
        test_case_count (int | None, optional): The number of test cases in the experiment.
            Defaults to None.

    Returns:
        dict: The serialized experiment summary.
    """
    return {
        "id": experiment.id,
        "name": experiment.name,
        "description": experiment.description,
        "created_at": _timestamp(experiment.created_at),
        "test_case_count": len(experiment.test_cases)
        if test_case_count is None else test_case_count,
    }

def serialize_test_case_summary(test_case: TestCase) -> dict:
    """Serialize a test case summary.
    Parameters:
        test_case (TestCase): The test case to serialize.
    Returns:
        dict: The serialized test case summary.
    """
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
    """Serialize an experiment detail.
    
    Parameters:
        experiment (Experiment): The experiment to serialize.
    
    Returns:
        dict: The serialized experiment detail.
    """
    
    return {
        **serialize_experiment_summary(experiment),
        "test_cases": [
            serialize_test_case_summary(test_case) for test_case in experiment.test_cases
        ],
    }

def serialize_test_case_detail(test_case: TestCase) -> dict:
    """Serialize a test case detail.
    Parameters:
        test_case (TestCase): The test case to serialize.
    Returns:
        dict: The serialized test case detail.
    """
    condition_order = {"neutral": 0, "correct_belief": 1, "incorrect_belief": 2}
    prompts = sorted(test_case.prompts, key=lambda prompt: condition_order[prompt.condition.value])
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
        "results": [],
    }


def serialize_llm_model(model: LLMModel) -> dict:
    """Serialize an LLM model.
    Parameters:
        model (LLMModel): The LLM model to serialize.
    Returns:
        dict: The serialized LLM model.
    """
    return {
        "id": model.id,
        "provider": model.provider,
        "model_name": model.model_name,
        "display_name": model.display_name,
    }
