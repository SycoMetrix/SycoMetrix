"""Commands for demo data, model setup, connectivity checks, and experiment runs."""

import time
from pathlib import Path

import click
from flask import current_app
from flask.cli import with_appcontext
from sqlalchemy.exc import SQLAlchemyError

from sycometrix.extensions import db
from sycometrix.models import Experiment, LLMModel
from sycometrix.services.llm_client import LLMError, get_llm_client
from sycometrix.services.llm_models import seed_default_model
from sycometrix.services.pipeline import run_test_case
from sycometrix.services.scoring import evaluate_test_case
from sycometrix.services.seed import read_seed_cases
from sycometrix.services.stance import classify_test_case
from sycometrix.services.test_cases import create_test_case


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


@click.command("seed-demo")
@click.option("--name", default="Demo: factual questions", show_default=True)
@click.option(
    "--file",
    "seed_file",
    type=click.Path(path_type=Path, dir_okay=False),
    help="JSON input file. Defaults to the bundled data/seed_questions.json.",
)
@with_appcontext
def seed_demo(name: str, seed_file: Path | None) -> None:
    """Load factual questions and their three prompt variations into a new experiment."""
    if seed_file is None:
        seed_file = Path(current_app.root_path).parent / "data" / "seed_questions.json"
    try:
        cases = read_seed_cases(seed_file)
    except ValueError as error:
        raise click.ClickException(str(error)) from error

    name = name.strip()
    if not 1 <= len(name) <= 200:
        raise click.BadParameter("use 1–200 characters", param_hint="--name")
    model_name = _default_model()
    try:
        seed_default_model(model_name)
        experiment = Experiment(name=name, description="Seeded from data/seed_questions.json")
        db.session.add(experiment)
        for case in cases:
            create_test_case(experiment, **case)
        db.session.flush()
        experiment_id = experiment.id
        db.session.commit()
    except SQLAlchemyError as error:
        db.session.rollback()
        raise click.ClickException(
            "Could not save the demo. Check DATABASE_URL and run 'flask db upgrade'."
        ) from error

    click.echo(f"Created experiment {experiment_id} with {len(cases)} test cases.")
    click.echo(f"/experiments/{experiment_id}")


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


@click.command("run-experiment")
@click.argument("experiment_id", type=int)
@click.option(
    "--model-id",
    type=int,
    required=True,
    help="Model to run for every test case.",
)
@click.option(
    "--only-pending",
    is_flag=True,
    default=False,
    help="Skip cases already complete for this model.",
)
@click.option("--temperature", type=float, default=None, help="Optional temperature override.")
@click.option("--seed", type=int, default=None, help="Optional seed override.")
@with_appcontext
def run_experiment(
    experiment_id: int,
    model_id: int,
    only_pending: bool,
    temperature: float | None,
    seed: int | None,
) -> None:
    """Run a single model across all test cases in an experiment."""
    experiment = db.session.get(Experiment, experiment_id)
    if experiment is None:
        raise click.ClickException(f"Experiment {experiment_id} does not exist.")
    model = db.session.get(LLMModel, model_id)
    if model is None:
        raise click.ClickException(f"Model {model_id} does not exist.")

    cases = list(experiment.test_cases)
    if not cases:
        click.echo("0 succeeded, 0 failed.")
        return

    succeeded = 0
    failed = 0
    try:
        for index, test_case in enumerate(cases, start=1):
            if only_pending and all(
                response is not None for response in test_case.responses_for(model.id).values()
            ):
                continue
            started = time.perf_counter()
            try:
                run_test_case(
                    test_case,
                    model,
                    client=get_llm_client(),
                    temperature=temperature,
                    seed=seed,
                )
            except Exception as exc:  # noqa: BLE001 - CLI prints failures and keeps processing.
                failed += 1
                click.echo(f"[{index}/{len(cases)}] #{test_case.id} FAILED: {exc}")
            else:
                succeeded += 1
                elapsed = time.perf_counter() - started
                click.echo(f"[{index}/{len(cases)}] #{test_case.id} ok ({elapsed:.1f}s)")
    except KeyboardInterrupt:
        click.echo("Interrupted.")

    click.echo(f"{succeeded} succeeded, {failed} failed.")
    if failed:
        raise SystemExit(1)


@click.command("classify-experiment")
@click.argument("experiment_id", type=int)
@click.option(
    "--model-id",
    type=int,
    required=True,
    help="Model whose responses should be re-classified.",
)
@click.option(
    "--only-unclassified",
    is_flag=True,
    default=False,
    help="Skip cases whose responses already all have stances.",
)
@with_appcontext
def classify_experiment(
    experiment_id: int,
    model_id: int,
    only_unclassified: bool,
) -> None:
    """Re-run the judge over existing responses without recollecting them."""
    experiment = db.session.get(Experiment, experiment_id)
    if experiment is None:
        raise click.ClickException(f"Experiment {experiment_id} does not exist.")
    model = db.session.get(LLMModel, model_id)
    if model is None:
        raise click.ClickException(f"Model {model_id} does not exist.")

    cases = list(experiment.test_cases)
    if not cases:
        click.echo("0 succeeded, 0 failed.")
        return

    succeeded = 0
    failed = 0
    try:
        for index, test_case in enumerate(cases, start=1):
            responses = test_case.responses_for(model.id)
            if only_unclassified and all(
                response is not None and response.stance is not None
                for response in responses.values()
            ):
                continue
            started = time.perf_counter()
            try:
                classify_test_case(
                    test_case,
                    model,
                    get_llm_client(),
                    current_app.config["JUDGE_MODEL"],
                )
                db.session.commit()
            except Exception as exc:  # noqa: BLE001 - CLI prints failures and keeps processing.
                db.session.rollback()
                failed += 1
                click.echo(f"[{index}/{len(cases)}] #{test_case.id} FAILED: {exc}")
            else:
                succeeded += 1
                elapsed = time.perf_counter() - started
                click.echo(f"[{index}/{len(cases)}] #{test_case.id} ok ({elapsed:.1f}s)")
    except KeyboardInterrupt:
        click.echo("Interrupted.")

    click.echo(f"{succeeded} succeeded, {failed} failed.")
    if failed:
        raise SystemExit(1)


@click.command("evaluate-experiment")
@click.argument("experiment_id", type=int)
@click.option(
    "--model-id",
    type=int,
    required=True,
    help="Model whose responses should be scored.",
)
@with_appcontext
def evaluate_experiment(experiment_id: int, model_id: int) -> None:
    """Re-score existing stances for every test case in an experiment."""
    experiment = db.session.get(Experiment, experiment_id)
    if experiment is None:
        raise click.ClickException(f"Experiment {experiment_id} does not exist.")
    model = db.session.get(LLMModel, model_id)
    if model is None:
        raise click.ClickException(f"Model {model_id} does not exist.")

    cases = list(experiment.test_cases)
    if not cases:
        click.echo("0 succeeded, 0 failed.")
        return

    succeeded = 0
    failed = 0
    try:
        for index, test_case in enumerate(cases, start=1):
            started = time.perf_counter()
            try:
                evaluate_test_case(test_case, model)
                db.session.commit()
            except Exception as exc:  # noqa: BLE001 - CLI prints failures and keeps processing.
                db.session.rollback()
                failed += 1
                click.echo(f"[{index}/{len(cases)}] #{test_case.id} FAILED: {exc}")
            else:
                succeeded += 1
                elapsed = time.perf_counter() - started
                click.echo(f"[{index}/{len(cases)}] #{test_case.id} ok ({elapsed:.1f}s)")
    except KeyboardInterrupt:
        click.echo("Interrupted.")

    click.echo(f"{succeeded} succeeded, {failed} failed.")
    if failed:
        raise SystemExit(1)
