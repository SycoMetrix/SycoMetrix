"""Frontend page and summary smoke tests."""
from sycometrix.models import Experiment, TestCase
from sycometrix.extensions import db
from sycometrix.services.test_cases import create_test_case

def test_home_and_static(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b'id="new-form"' in response.data
    assert b'type="module"' in response.data
    assert b'experiments.js' in response.data
    for path in ("/static/js/api.js", "/static/js/experiment.js", "/static/js/test_case.js", "/static/js/summary.js", "/static/css/style.css"):
        assert client.get(path).status_code == 200

def test_detail_routes(client, app):
    with app.app_context():
        exp = Experiment(name="Frontend test", description="Test")
        db.session.add(exp)
        db.session.flush()
        case = create_test_case(exp,"Is water wet?","Water is wet.","Water is dry.","science")
        db.session.commit()
        eid, cid = exp.id, case.id
    assert client.get(f"/experiments/{eid}").status_code == 200
    assert client.get(f"/test-cases/{cid}").status_code == 200
    assert client.get("/experiments/999999").status_code == 404
    assert client.get("/test-cases/999999").status_code == 404
    result = client.get(f"/api/experiments/{eid}/summary")
    assert result.status_code == 200
    data = result.get_json()
    assert data["totals"]["test_cases"] == 1
    assert data["totals"]["evaluated"] == 0
    assert data["by_risk"] == {"none":0,"low":0,"medium":0,"high":0}
    assert client.get(f"/api/experiments/{eid}/summary?model_id=999999").status_code == 400
