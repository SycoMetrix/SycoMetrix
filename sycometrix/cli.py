"""Commands for model setup and a single chat connectivity check."""

import click
from flask import current_app
from flask.cli import with_appcontext
from sqlalchemy.exc import SQLAlchemyError

from sycometrix.extensions import db
from sycometrix.services.llm_client import LLMError, get_llm_client
from sycometrix.services.llm_models import seed_default_model


def _default_model() -> str:
    model = current_app.config.get("DEFAULT_MODEL")
    if not isinstance(model, str) or not model.strip() or len(model.strip()) > 200:
        raise click.ClickException("Set DEFAULT_MODEL in .env to a model ID of 1–200 characters.")
    return model.strip()


@click.command("seed-models")
@with_appcontext
def seed_models() -> None:
    """Register DEFAULT_MODEL once, using provider openrouter."""
    model_name = _default_model()
    try:
        model, created = seed_default_model(model_name)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise click.ClickException(
            "Could not access the model registry. Check DATABASE_URL and run 'flask db upgrade'."
        ) from None
    action = "Added model" if created else "Model already exists"
    click.echo(f"{action}: {model.model_name} (id={model.id}).")


@click.command("llm-ping")
@with_appcontext
def llm_ping() -> None:
    """Ask DEFAULT_MODEL to reply with pong, then print its reply and latency."""
    model_name = _default_model()
    try:
        result = get_llm_client().chat(
            model_name,
            [{"role": "user", "content": "Reply with the word pong."}],
            temperature=current_app.config["DEFAULT_TEMPERATURE"],
            max_tokens=current_app.config["MAX_RESPONSE_TOKENS"],
        )
    except LLMError as error:
        raise click.ClickException(str(error)) from None
    click.echo(result.text)
    click.echo(f"Latency: {result.latency_ms} ms")
