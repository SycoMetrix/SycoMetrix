"""Build dashboard summary data for an experiment."""

from typing import Any

import pandas as pd
from sqlalchemy import func, select

from sycometrix.extensions import db
from sycometrix.models import Evaluation, LLMModel, RiskLevel, TestCase


_COLUMNS = [
    "test_case_id",
    "question",
    "category",
    "model_id",
    "display_name",
    "risk_level",
    "score",
    "flagged",
]


def _rate(frame: pd.DataFrame) -> float | None:
    evaluated = len(frame)
    if evaluated == 0:
        return None
    return round(int(frame["flagged"].sum()) / evaluated, 3)


def _mean_score(frame: pd.DataFrame) -> float | None:
    if frame.empty:
        return None
    return round(float(frame["score"].mean()), 3)


def _group_stats(frame: pd.DataFrame, key: str) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    grouped = frame.groupby(key, sort=True, dropna=False)
    return [
        {
            key: group_name,
            "evaluated": int(len(group)),
            "flagged": int(group["flagged"].sum()),
            "flag_rate": _rate(group),
            "mean_score": _mean_score(group),
        }
        for group_name, group in grouped
    ]


def _model_stats(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return [
        {
            "model_id": int(item["model_id"]),
            "display_name": str(
                frame[frame["model_id"] == item["model_id"]]["display_name"].iloc[0]
            ),
            "evaluated": item["evaluated"],
            "flagged": item["flagged"],
            "flag_rate": item["flag_rate"],
            "mean_score": item["mean_score"],
        }
        for item in _group_stats(frame, "model_id")
    ]


def _row_dict(row: pd.Series) -> dict[str, Any]:
    return {
        "test_case_id": int(row["test_case_id"]),
        "question": str(row["question"]),
        "category": str(row["category"]),
        "model_id": int(row["model_id"]),
        "risk_level": str(row["risk_level"]),
        "score": float(row["score"]),
        "flagged": bool(row["flagged"]),
    }


def build_summary(experiment_id: int, model_id: int | None = None) -> dict[str, Any]:
    """Return dashboard aggregates for an experiment."""
    test_case_count = int(
        db.session.scalar(
            select(func.count(TestCase.id)).where(TestCase.experiment_id == experiment_id)
        )
        or 0
    )

    statement = (
        select(
            TestCase.id,
            TestCase.question,
            TestCase.category,
            Evaluation.model_id,
            LLMModel.display_name,
            Evaluation.risk_level,
            Evaluation.score,
            Evaluation.flagged,
        )
        .join(Evaluation, Evaluation.test_case_id == TestCase.id)
        .join(LLMModel, LLMModel.id == Evaluation.model_id)
        .where(TestCase.experiment_id == experiment_id)
    )
    all_rows = db.session.execute(statement).all()
    frame = pd.DataFrame(
        [
            {
                "test_case_id": test_case_id,
                "question": question,
                "category": category or "uncategorized",
                "model_id": row_model_id,
                "display_name": display_name,
                "risk_level": (
                    risk_level.value if isinstance(risk_level, RiskLevel) else str(risk_level)
                ),
                "score": score,
                "flagged": flagged,
            }
            for (
                test_case_id,
                question,
                category,
                row_model_id,
                display_name,
                risk_level,
                score,
                flagged,
            ) in all_rows
        ],
        columns=_COLUMNS,
    )
    filtered = frame if model_id is None else frame[frame["model_id"] == model_id]

    evaluated = len(filtered)
    flagged = int(filtered["flagged"].sum()) if evaluated else 0
    not_flagged = evaluated - flagged
    if evaluated:
        headline = (
            f"{test_case_count} test cases; {flagged} flagged for possible sycophancy; "
            f"{not_flagged} not flagged."
        )
    else:
        headline = f"{test_case_count} test cases; none evaluated yet."

    by_risk = {
        risk.value: int((filtered["risk_level"] == risk.value).sum())
        for risk in RiskLevel
    }
    cases = (
        filtered.sort_values(["score", "test_case_id"], ascending=[False, True])
        .apply(_row_dict, axis=1)
        .tolist()
    )

    return {
        "experiment_id": experiment_id,
        "model_id": model_id,
        "headline": headline,
        "totals": {
            "test_cases": test_case_count,
            "evaluated": evaluated,
            "not_evaluated": test_case_count - evaluated,
            "flagged": flagged,
            "not_flagged": not_flagged,
        },
        "flag_rate": _rate(filtered),
        "mean_score": _mean_score(filtered),
        "by_risk": by_risk,
        "by_category": _group_stats(filtered, "category"),
        "by_model": _model_stats(frame),
        "cases": cases,
    }