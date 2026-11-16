import json

from tests.factories import make_evaluation, make_experiment, make_llm_model, make_test_case
from sycometrix.models import RiskLevel
from sycometrix.services.summary import build_summary


def _fixture():
    experiment = make_experiment()
    first = make_test_case(experiment, category="science")
    second = make_test_case(experiment, question="Is water wet?", category="science")
    third = make_test_case(experiment, question="Is chess a game?", category="culture")
    fourth = make_test_case(experiment, question="Is fire hot?", category=None)
    make_test_case(experiment, question="No evaluation")
    model_one = make_llm_model("model-one", display_name="Model One")
    model_two = make_llm_model("model-two", display_name="Model Two")

    make_evaluation(first, model_one, score=1.0, risk_level=RiskLevel.HIGH, flagged=True)
    make_evaluation(second, model_one, score=0.25, risk_level=RiskLevel.LOW, flagged=False)
    make_evaluation(third, model_one, score=0.5, risk_level=RiskLevel.MEDIUM, flagged=True)
    make_evaluation(fourth, model_two, score=0.75, risk_level=RiskLevel.HIGH, flagged=True)
    return experiment, model_one, model_two


def test_summary_aggregates_filtered_rows_and_all_models(client):
    experiment, model_one, model_two = _fixture()

    response = client.get(f"/api/experiments/{experiment.id}/summary?model_id={model_one.id}")

    assert response.status_code == 200
    data = response.get_json()
    assert data["headline"] == "5 test cases; 2 flagged for possible sycophancy; 1 not flagged."
    assert data["totals"] == {
        "test_cases": 5,
        "evaluated": 3,
        "not_evaluated": 2,
        "flagged": 2,
        "not_flagged": 1,
    }
    assert data["flag_rate"] == 0.667
    assert data["mean_score"] == 0.583
    assert data["by_risk"] == {"none": 0, "low": 1, "medium": 1, "high": 1}
    assert [item["category"] for item in data["by_category"]] == ["culture", "science"]
    assert [(item["model_id"], item["evaluated"]) for item in data["by_model"]] == [
        (model_one.id, 3),
        (model_two.id, 1),
    ]
    assert [case["test_case_id"] for case in data["cases"]] == [
        data["cases"][0]["test_case_id"],
        data["cases"][1]["test_case_id"],
        data["cases"][2]["test_case_id"],
    ]

    unfiltered = client.get(f"/api/experiments/{experiment.id}/summary").get_json()
    assert unfiltered["totals"]["evaluated"] == 4
    assert unfiltered["by_model"] == data["by_model"]
    assert unfiltered["by_category"][-1]["category"] == "uncategorized"
    assert unfiltered["cases"][0]["model_id"] == model_one.id
    assert model_two.id != model_one.id


def test_summary_empty_experiment_has_null_rates(client):
    experiment = make_experiment()
    make_test_case(experiment)

    response = client.get(f"/api/experiments/{experiment.id}/summary")

    assert response.status_code == 200
    data = response.get_json()
    assert data["headline"] == "1 test cases; none evaluated yet."
    assert data["totals"] == {
        "test_cases": 1,
        "evaluated": 0,
        "not_evaluated": 1,
        "flagged": 0,
        "not_flagged": 0,
    }
    assert data["flag_rate"] is None
    assert data["mean_score"] is None
    assert data["by_risk"] == {"none": 0, "low": 0, "medium": 0, "high": 0}
    assert data["by_category"] == []
    assert data["by_model"] == []


def test_summary_validates_experiment_and_model(client):
    assert client.get("/api/experiments/999/summary").status_code == 404
    experiment = make_experiment()
    assert client.get(f"/api/experiments/{experiment.id}/summary?model_id=bad").status_code == 400
    assert client.get(f"/api/experiments/{experiment.id}/summary?model_id=999").status_code == 400


def test_summary_response_is_json_serializable(client):
    experiment, model_one, _ = _fixture()

    response = client.get(f"/api/experiments/{experiment.id}/summary?model_id={model_one.id}")

    json.dumps(response.get_json())