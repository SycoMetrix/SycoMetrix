"""Convert database models to the shared JSON API shapes."""

from sycometrix.models import LLMModel


def serialize_llm_model(model: LLMModel) -> dict:
    return {
        "id": model.id,
        "provider": model.provider,
        "model_name": model.model_name,
        "display_name": model.display_name,
    }
