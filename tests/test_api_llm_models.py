"""Model registry API and CLI behavior using the in-memory database."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

from sycometrix import cli
from sycometrix.extensions import db
from sycometrix.models import LLMModel
from sycometrix.services import llm_models
from sycometrix.services.llm_client import LLMError
from tests.factories import make_llm_model


def test_create_list_and_default_display_name(client):
    assert client.get("/api/models").get_json() == []
    response = client.post(
        "/api/models", json={"provider": " openrouter ", "model_name": " example/model "}
    )
    assert response.status_code == 201
    model = response.get_json()
    assert model == {
        "id": model["id"],
        "provider": "openrouter",
        "model_name": "example/model",
        "display_name": "example/model",
    }
    assert isinstance(model["id"], int)
    listing = client.get("/api/models")
    assert listing.status_code == 200
    assert listing.get_json() == [model]


def test_list_orders_by_display_name(client):
    for name, label in [("second", "Zulu"), ("first", "Alpha")]:
        result = client.post(
            "/api/models",
            json={
                "provider": "fake",
                "model_name": name,
                "display_name": label,
            },
        )
        assert result.status_code == 201
    assert [model["display_name"] for model in client.get("/api/models").get_json()] == [
        "Alpha",
        "Zulu",
    ]


def test_duplicate_returns_conflict_and_keeps_original(client):
    body = {"provider": "openrouter", "model_name": "example/model", "display_name": "Original"}
    assert client.post("/api/models", json=body).status_code == 201
    body["display_name"] = "Replacement"
    response = client.post("/api/models", json=body)
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "conflict"
    assert response.get_json()["error"]["message"]
    models = client.get("/api/models").get_json()
    assert len(models) == 1
    assert models[0]["display_name"] == "Original"


def test_same_model_name_with_different_provider_is_allowed(client):
    for provider in ("fake", "openrouter"):
        response = client.post("/api/models", json={"provider": provider, "model_name": "shared"})
        assert response.status_code == 201
    assert len(client.get("/api/models").get_json()) == 2


@pytest.mark.parametrize(
    "body, field",
    [
        ({}, "provider"),
        ({"provider": "fake"}, "model_name"),
        ({"provider": "fake", "model_name": "  "}, "model_name"),
        ({"provider": "fake", "model_name": 12}, "model_name"),
        ({"provider": " ", "model_name": "m"}, "provider"),
        ({"provider": "x" * 51, "model_name": "m"}, "provider"),
        ({"provider": "fake", "model_name": "x" * 201}, "model_name"),
        ({"provider": "fake", "model_name": "m", "display_name": ""}, "display_name"),
        ({"provider": "fake", "model_name": "m", "display_name": "x" * 201}, "display_name"),
    ],
)
def test_invalid_fields_return_validation_error(client, body, field):
    response = client.post("/api/models", json=body)
    assert response.status_code == 400
    error = response.get_json()["error"]
    assert error["code"] == "validation_error"
    assert field in error["message"]
    assert client.get("/api/models").get_json() == []


@pytest.mark.parametrize("body", ["[]", "null", "broken json"])
def test_body_must_be_a_json_object(client, body):
    response = client.post("/api/models", data=body, content_type="application/json")
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "validation_error"


def test_model_api_does_not_return_credentials(app, client):
    app.config["OPENROUTER_API_KEY"] = "private-test-key"
    result = client.post(
        "/api/models",
        json={
            "provider": "openrouter",
            "model_name": "example/model",
            "api_key": "private-test-key",
        },
    )
    assert result.status_code == 201
    for response in (result, client.get("/api/models")):
        assert "private-test-key" not in response.get_data(as_text=True)
        assert "api_key" not in response.get_data(as_text=True)


def test_duplicate_race_returns_conflict_and_recovers_session(app, client, monkeypatch):
    make_llm_model(provider="openrouter", model_name="example/model")
    db.session.commit()
    original_find = llm_models.find_model
    calls = 0

    def miss_first_lookup(provider, model_name):
        nonlocal calls
        calls += 1
        return None if calls == 1 else original_find(provider, model_name)

    monkeypatch.setattr(llm_models, "find_model", miss_first_lookup)
    response = client.post(
        "/api/models",
        json={
            "provider": "openrouter",
            "model_name": "example/model",
        },
    )
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "conflict"
    assert len(client.get("/api/models").get_json()) == 1


def test_seed_models_is_idempotent_and_preserves_existing_label(app, client):
    app.config["DEFAULT_MODEL"] = "example/default"
    runner = app.test_cli_runner()
    first = runner.invoke(args=["seed-models"])
    assert first.exit_code == 0
    assert "Added model" in first.output
    model = db.session.scalar(select(LLMModel))
    model.display_name = "Custom label"
    db.session.commit()
    second = runner.invoke(args=["seed-models"])
    assert second.exit_code == 0
    assert "already exists" in second.output
    assert db.session.scalar(select(func.count()).select_from(LLMModel)) == 1
    assert client.get("/api/models").get_json() == [
        {
            "id": model.id,
            "provider": "openrouter",
            "model_name": "example/default",
            "display_name": "Custom label",
        }
    ]


def test_llm_ping_uses_injected_client_and_prints_reply_and_latency(app, fake_llm):
    app.config.update(DEFAULT_MODEL="fake/test", DEFAULT_TEMPERATURE=0.0, MAX_RESPONSE_TOKENS=64)
    result = app.test_cli_runner().invoke(args=["llm-ping"])
    assert result.exit_code == 0
    assert "[fake:fake/test] Reply with the word pong." in result.output
    assert "Latency: 0 ms" in result.output
    assert fake_llm.calls == [
        {
            "model": "fake/test",
            "messages": [{"role": "user", "content": "Reply with the word pong."}],
            "temperature": 0.0,
            "seed": None,
            "max_tokens": 64,
        }
    ]


def test_llm_ping_uses_testing_fake_without_manual_injection(app):
    result = app.test_cli_runner().invoke(args=["llm-ping"])
    assert result.exit_code == 0
    assert "[fake:" in result.output


def test_llm_ping_missing_key_has_clear_error(app):
    app.config.update(LLM_PROVIDER="openrouter", OPENROUTER_API_KEY=None)
    result = app.test_cli_runner().invoke(args=["llm-ping"])
    assert result.exit_code != 0
    assert "OPENROUTER_API_KEY" in result.output
    assert ".env" in result.output
    assert "Traceback" not in result.output


def test_llm_ping_reports_client_failure(app, fake_llm, monkeypatch):
    def fail(*args, **kwargs):
        raise LLMError("Model returned an empty response")

    monkeypatch.setattr(fake_llm, "chat", fail)
    result = app.test_cli_runner().invoke(args=["llm-ping"])
    assert result.exit_code != 0
    assert "Model returned an empty response" in result.output


def test_seed_models_database_failure_has_safe_setup_hint(app, monkeypatch):
    def fail(*args):
        raise OperationalError("secret connection details", {}, Exception("database unavailable"))

    monkeypatch.setattr(cli, "seed_default_model", fail)
    result = app.test_cli_runner().invoke(args=["seed-models"])
    assert result.exit_code != 0
    assert "flask db upgrade" in result.output
    assert "secret connection details" not in result.output
