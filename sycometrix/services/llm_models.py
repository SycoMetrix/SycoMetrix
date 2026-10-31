"""Model registry operations; callers commit successful changes."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from sycometrix.extensions import db
from sycometrix.models import LLMModel


class DuplicateModelError(Exception):
    """The provider and model name are already registered."""


def list_models() -> list[LLMModel]:
    return list(db.session.scalars(select(LLMModel).order_by(LLMModel.display_name, LLMModel.id)))


def find_model(provider: str, model_name: str) -> LLMModel | None:
    return db.session.scalar(
        select(LLMModel).where(LLMModel.provider == provider, LLMModel.model_name == model_name)
    )


def create_model(provider: str, model_name: str, display_name: str) -> LLMModel:
    """Insert a model, reporting duplicates including concurrent insertions."""
    if find_model(provider, model_name) is not None:
        raise DuplicateModelError("A model with that provider and model_name already exists.")
    model = LLMModel(provider=provider, model_name=model_name, display_name=display_name)
    db.session.add(model)
    try:
        db.session.flush()
    except IntegrityError:
        db.session.rollback()
        if find_model(provider, model_name) is not None:
            raise DuplicateModelError(
                "A model with that provider and model_name already exists."
            ) from None
        raise
    return model


def seed_default_model(model_name: str) -> tuple[LLMModel, bool]:
    """Return the default OpenRouter model and whether a row was added."""
    existing = find_model("openrouter", model_name)
    if existing is not None:
        return existing, False
    try:
        return create_model("openrouter", model_name, model_name), True
    except DuplicateModelError:
        existing = find_model("openrouter", model_name)
        if existing is None:
            raise
        return existing, False
