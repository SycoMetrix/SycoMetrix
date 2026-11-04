"""Test case execution API endpoint."""

from sycometrix.services.llm_client import LLMError
from tests.factories import make_experiment, make_llm_model, make_test_case


def test_run_test_case_endpoint_collects_and_returns_results(client, fake_llm):
    experiment = make_experiment("Run API experiment")
    test_case = make_test_case(experiment)
    model = make_llm_model(model_name="fake/api", display_name="Fake API")
    fake_llm._responder = lambda _model, messages: f"{messages[0]['content']}:{_model}"

    response = client.post(
        f"/api/test-cases/{test_case.id}/run",
        json={"model_id": model.id, "temperature": 0.0, "seed": 42},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["results"][0]["model"]["id"] == model.id
    assert list(payload["results"][0]["responses"].keys()) == [
        "neutral",
        "correct_belief",
        "incorrect_belief",
    ]
    assert all(item is not None for item in payload["results"][0]["responses"].values())
    assert payload["results"][0]["evaluation"] is None


def test_run_test_case_endpoint_validates_model_and_errors(client, fake_llm):
    experiment = make_experiment("Validation experiment")
    test_case = make_test_case(experiment)
    model = make_llm_model(model_name="fake/valid", display_name="Valid")

    missing = client.post(f"/api/test-cases/{test_case.id}/run", json={})
    assert missing.status_code == 400
    assert missing.get_json()["error"]["code"] == "validation_error"

    missing_model = client.post(f"/api/test-cases/{test_case.id}/run", json={"model_id": 999})
    assert missing_model.status_code == 400
    assert missing_model.get_json()["error"]["message"] == "Model 999 does not exist."

    bad_model = client.post(f"/api/test-cases/{test_case.id}/run", json={"model_id": "bad"})
    assert bad_model.status_code == 400
    assert bad_model.get_json()["error"]["code"] == "validation_error"

    fake_llm._responder = lambda _model, _messages: (
        _ for _ in ()
    ).throw(LLMError("provider failed"))
    bad_temp = client.post(
        f"/api/test-cases/{test_case.id}/run",
        json={"model_id": model.id, "temperature": 3.0},
    )
    assert bad_temp.status_code == 400
    assert bad_temp.get_json()["error"]["code"] == "validation_error"

    failed = client.post(f"/api/test-cases/{test_case.id}/run", json={"model_id": model.id})
    assert failed.status_code == 502
    assert failed.get_json()["error"]["code"] == "llm_error"
    assert "provider failed" in failed.get_json()["error"]["message"]


def test_run_test_case_endpoint_404_for_missing_test_case(client):
    response = client.post("/api/test-cases/999/run", json={"model_id": 1})
    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "not_found"
