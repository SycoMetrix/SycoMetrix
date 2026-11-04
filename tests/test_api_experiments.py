"""Experiment API endpoint tests."""

from tests.factories import make_experiment, make_test_case


def test_experiment_lifecycle(client):
    """Test the lifecycle of an experiment via the API.
    Parameters:
        client: The test client to use for making the API requests.
    Returns:
        None
    """
    created = client.post(
        "/api/experiments",
        json={"name": " Baseline ", "description": "First questions"},
    )
    assert created.status_code == 201
    experiment = created.get_json()
    assert experiment["name"] == "Baseline"
    assert experiment["description"] == "First questions"
    assert experiment["test_case_count"] == 0

    fetched = client.get(f"/api/experiments/{experiment['id']}")
    assert fetched.status_code == 200
    assert fetched.get_json()["test_cases"] == []

    patched = client.patch(
        f"/api/experiments/{experiment['id']}",
        json={"name": "Updated", "description": None},
    )
    assert patched.status_code == 200
    assert patched.get_json()["name"] == "Updated"
    assert patched.get_json()["description"] is None

    listed = client.get("/api/experiments")
    assert listed.status_code == 200
    assert listed.get_json()[0]["name"] == "Updated"

    deleted = client.delete(f"/api/experiments/{experiment['id']}")
    assert deleted.status_code == 204
    assert deleted.data == b""
    assert client.get(f"/api/experiments/{experiment['id']}").status_code == 404


def test_experiment_list_is_newest_first_and_counts_cases(client):
    """Test that the experiment list is ordered by newest first and counts test cases correctly.
    Parameters:
        client: The test client to use for making the API requests.
    Returns:
        None
    """
    older = make_experiment("Older")
    newer = make_experiment("Newer")
    make_test_case(older)
    make_test_case(newer)
    make_test_case(newer, question="Is water wet?")

    response = client.get("/api/experiments")
    assert [(item["name"], item["test_case_count"]) for item in response.get_json()] == [
        ("Newer", 2),
        ("Older", 1),
    ]


def test_experiment_creation_requires_name(client):
    """Test that creating an experiment without a valid name returns a validation error.
    Parameters:
        client: The test client to use for making the API request.
    Returns:
        None
    """
    for body in ({}, {"name": "  "}):
        response = client.post("/api/experiments", json=body)
        assert response.status_code == 400
        assert response.get_json()["error"]["code"] == "validation_error"
        assert "name" in response.get_json()["error"]["message"]


def test_missing_experiment_routes_return_not_found(client):
    """Test that API routes for missing experiments return a 404 not found error.
    Parameters:
        client: The test client to use for making the API requests.
    Returns:
        None
    """
    for method, path in (
        ("get", "/api/experiments/999"),
        ("patch", "/api/experiments/999"),
        ("delete", "/api/experiments/999"),
    ):
        response = getattr(client, method)(path, json={} if method == "patch" else None)
        assert response.status_code == 404
        assert response.get_json()["error"]["code"] == "not_found"


def test_deleting_experiment_deletes_test_cases(client, app):
    """Test that deleting an experiment also deletes its associated test cases.
    Parameters:
        client: The test client to use for making the API requests.
        app: The Flask application instance.
    Returns:
        None
    """
    experiment = make_experiment()
    test_case = make_test_case(experiment)
    test_case_id = test_case.id

    response = client.delete(f"/api/experiments/{experiment.id}")
    assert response.status_code == 204
    assert client.get(f"/api/test-cases/{test_case_id}").status_code == 404


def test_create_test_case_under_experiment_returns_generated_prompts(client):
    """Test that creating a test case under an experiment returns generated prompts.
    Parameters:
        client: The test client to use for making the API request.
    Returns:
        None
    """
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
    assert response.status_code == 201
    assert [prompt["condition"] for prompt in response.get_json()["prompts"]] == [
        "neutral",
        "correct_belief",
        "incorrect_belief",
    ]


def test_create_test_case_under_missing_experiment_returns_not_found(client):
    """Test that creating a test case under a non-existent experiment returns a 404 not found error.
    Parameters:
        client: The test client to use for making the API request.
    Returns:
        None
    """
    response = client.post(
        "/api/experiments/999/test-cases",
        json={
            "question": "Question",
            "correct_answer": "Correct",
            "incorrect_belief": "Incorrect",
        },
    )
    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "not_found"
