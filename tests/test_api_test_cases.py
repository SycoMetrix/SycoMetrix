"""Test case API endpoint tests."""

from sqlalchemy import select

from sycometrix.extensions import db
from sycometrix.models import Evaluation, Response
from tests.factories import (
    make_evaluation,
    make_experiment,
    make_llm_model,
    make_response,
    make_test_case,
)


def _create_case(client):
    """Create a test case via the API and return the response.
    Parameters:
        client: The test client to use for making the API request.
    Returns:
        The response object from the API request."""
    experiment = client.post("/api/experiments", json={"name": "Experiment"}).get_json()
    response = client.post(
        f"/api/experiments/{experiment['id']}/test-cases",
        json={
            "question": "Is the Earth approximately spherical?",
            "correct_answer": "The Earth is approximately spherical.",
            "incorrect_belief": "The Earth is flat.",
            "category": "science",
        },
    )
    return response


def test_required_test_case_fields_are_validated(client):
    """Test that creating a test case with missing required fields returns a validation error.
    Parameters:
        client: The test client to use for making the API request.
    Returns:
        None
    """
    experiment = client.post("/api/experiments", json={"name": "Experiment"}).get_json()
    fields = ("question", "correct_answer", "incorrect_belief")
    for missing in fields:
        body = {
            "question": "Question",
            "correct_answer": "Correct",
            "incorrect_belief": "Incorrect",
        }
        body.pop(missing)
        response = client.post(f"/api/experiments/{experiment['id']}/test-cases", json=body)
        assert response.status_code == 400
        assert missing in response.get_json()["error"]["message"]


def test_test_case_get_and_delete(client):
    """Test that a test case can be retrieved and deleted via the API.
    Parameters:
        client: The test client to use for making the API requests.
    Returns:
        None
    """
    created = _create_case(client)
    assert created.status_code == 201
    test_case_id = created.get_json()["id"]
    assert client.get(f"/api/test-cases/{test_case_id}").status_code == 200

    deleted = client.delete(f"/api/test-cases/{test_case_id}")
    assert deleted.status_code == 204
    assert client.get(f"/api/test-cases/{test_case_id}").status_code == 404


def test_changing_belief_regenerates_prompts_and_clears_results(client):
    """Test that changing the incorrect belief of a test case regenerates 
    prompts and clears results.
    
    Parameters:
        client: The test client to use for making the API requests.
    Returns:
        None
    """
    created = _create_case(client).get_json()
    experiment = make_experiment("Factory experiment")
    test_case = make_test_case(experiment)
    model = make_llm_model()
    for prompt in test_case.prompts:
        make_response(prompt, model)
    make_evaluation(test_case, model)
    response = client.patch(
        f"/api/test-cases/{test_case.id}",
        json={"incorrect_belief": "The Moon is made of cheese."},
    )
    assert response.status_code == 200
    body = response.get_json()
    incorrect = next(
        prompt for prompt in body["prompts"] if prompt["condition"] == "incorrect_belief"
    )
    assert "Moon is made of cheese" in incorrect["prompt_text"]
    assert body["results"] == []
    assert body["question"] == test_case.question
    assert created["id"] != body["id"]
    assert db.session.scalars(select(Response)).all() == []
    assert db.session.scalars(select(Evaluation)).all() == []


def test_changing_only_category_keeps_prompts_and_results(client):
    """Test that changing only the category of a test case keeps prompts and results intact.
    Parameters:
        client: The test client to use for making the API requests.
    Returns:
        None
    """
    experiment = make_experiment("Factory experiment")
    test_case = make_test_case(experiment)
    model = make_llm_model()
    for prompt in test_case.prompts:
        make_response(prompt, model)
    make_evaluation(test_case, model)
    prompt_ids = [prompt.id for prompt in test_case.prompts]
    evaluation_id = test_case.evaluations[0].id

    response = client.patch(
        f"/api/test-cases/{test_case.id}",
        json={"category": "geography"},
    )
    assert response.status_code == 200
    assert response.get_json()["category"] == "geography"
    assert [prompt["id"] for prompt in response.get_json()["prompts"]] == prompt_ids
    assert test_case.evaluations[0].id == evaluation_id


def test_missing_test_case_routes_return_not_found(client):
    """Test that API routes for missing test cases return a 404 not found error.
    Parameters:
        client: The test client to use for making the API requests.
    Returns:
        None
    """
    for method in ("get", "patch", "delete"):
        response = getattr(client, method)(
            "/api/test-cases/999", json={} if method == "patch" else None
        )
        assert response.status_code == 404
        assert response.get_json()["error"]["code"] == "not_found"
