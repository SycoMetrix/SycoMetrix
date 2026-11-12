"""Database-backed experiment summary, with no model calls."""
from collections import defaultdict
from sqlalchemy import select
from sycometrix.extensions import db
from sycometrix.models import Evaluation, TestCase, LLMModel

RISKS = ("none", "low", "medium", "high")

def _stats(rows):
    evaluated = len(rows)
    flagged = sum(bool(r["flagged"]) for r in rows)
    return {"evaluated":evaluated,"flagged":flagged,"flag_rate":round(flagged/evaluated,3) if evaluated else None,"mean_score":round(sum(r["score"] for r in rows)/evaluated,3) if evaluated else None}

def build_summary(experiment_id: int, model_id: int | None = None) -> dict:
    cases = db.session.scalars(select(TestCase).where(TestCase.experiment_id == experiment_id)).all()
    case_ids = [case.id for case in cases]
    records = []
    if case_ids:
        rows = db.session.execute(select(Evaluation, TestCase, LLMModel).join(TestCase, Evaluation.test_case_id == TestCase.id).join(LLMModel, Evaluation.model_id == LLMModel.id).where(Evaluation.test_case_id.in_(case_ids))).all()
        for evaluation, case, model in rows:
            records.append({"test_case_id":case.id,"question":case.question,"category":case.category or "uncategorized","model_id":model.id,"display_name":model.display_name,"risk_level":evaluation.risk_level.value,"score":evaluation.score,"flagged":evaluation.flagged})
    filtered = [r for r in records if model_id is None or r["model_id"] == model_id]
    stats = _stats(filtered)
    total = len(cases) if model_id is not None else len(cases) * max(1, len({r["model_id"] for r in records}))
    # Without a model filter, the denominator covers each case/model pair represented.
    not_evaluated = max(0,total-stats["evaluated"])
    totals = {"test_cases":len(cases),"evaluated":stats["evaluated"],"not_evaluated":not_evaluated,"flagged":stats["flagged"],"not_flagged":stats["evaluated"]-stats["flagged"]}
    headline = (f"{len(cases)} test cases; none evaluated yet." if not stats["evaluated"] else f"{len(cases)} test cases; {stats['flagged']} flagged for possible sycophancy; {totals['not_flagged']} not flagged.")
    categories = defaultdict(list)
    for r in filtered: categories[r["category"]].append(r)
    by_category = [{"category":key,**_stats(group)} for key,group in sorted(categories.items())]
    models = defaultdict(list)
    for r in records: models[(r["model_id"],r["display_name"])].append(r)
    by_model = [{"model_id":mid,"display_name":name,**_stats(group)} for (mid,name),group in sorted(models.items())]
    return {"experiment_id":experiment_id,"model_id":model_id,"headline":headline,"totals":totals,"flag_rate":stats["flag_rate"],"mean_score":stats["mean_score"],"by_risk":{risk:sum(r["risk_level"]==risk for r in filtered) for risk in RISKS},"by_category":by_category,"by_model":by_model,"cases":sorted(({k:r[k] for k in ("test_case_id","question","category","model_id","risk_level","score","flagged")} for r in filtered),key=lambda r:(-r["score"],r["test_case_id"]))}
