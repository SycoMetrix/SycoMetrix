"""HTML page shells; data is fetched by the browser from the JSON API."""
from flask import Blueprint, abort, render_template
from sycometrix.extensions import db
from sycometrix.models import Experiment, TestCase

pages_bp = Blueprint("pages", __name__)

@pages_bp.get("/")
def home():
    return render_template("experiments.html")

@pages_bp.get("/experiments/<int:id>")
def experiment_page(id):
    if db.session.get(Experiment, id) is None:
        abort(404)
    return render_template("experiment.html", experiment_id=id)

@pages_bp.get("/test-cases/<int:id>")
def test_case_page(id):
    if db.session.get(TestCase, id) is None:
        abort(404)
    return render_template("test_case.html", test_case_id=id)
