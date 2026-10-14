from sycometrix import create_app
from sycometrix.api import ApiError
from sycometrix.config import TestingConfig


def test_health_returns_ok(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_unknown_api_route_returns_json_404(client):
    response = client.get("/api/does-not-exist")

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "not_found"
    assert response.get_json()["error"]["message"]


def test_wrong_method_returns_json_405(client):
    response = client.post("/api/health")

    assert response.status_code == 405
    assert response.get_json()["error"]["code"] == "method_not_allowed"


def test_non_api_404_is_not_json(client):
    response = client.get("/not-an-api-route")

    assert response.status_code == 404
    assert response.is_json is False


def test_api_error_becomes_json_response():
    app = create_app(TestingConfig)

    @app.get("/api/_raise-api-error")
    def raise_api_error():
        raise ApiError(409, "conflict", "Experiment 1 is already running.")

    response = app.test_client().get("/api/_raise-api-error")

    assert response.status_code == 409
    assert response.get_json() == {
        "error": {"code": "conflict", "message": "Experiment 1 is already running."}
    }


def test_unhandled_exception_returns_json_500_without_details():
    app = create_app(TestingConfig)
    app.config["PROPAGATE_EXCEPTIONS"] = False

    @app.get("/api/_boom")
    def boom():
        raise RuntimeError("secret internal detail")

    response = app.test_client().get("/api/_boom")

    assert response.status_code == 500
    body = response.get_json()
    assert body["error"]["code"] == "internal_error"
    assert "secret internal detail" not in response.get_data(as_text=True)
