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
    """Return the fraction of flagged rows in a frame, or None if no rows

    Args:
        frame (pd.DataFrame): The DataFrame to analyze.

    Returns:
        float | None: The fraction of flagged rows, or None if no rows.
    """
    evaluated = len(frame)
    if evaluated == 0:
        return None
    return round(int(frame["flagged"].sum()) / evaluated, 3)


def _mean_score(frame: pd.DataFrame) -> float | None:
    """Return the mean score of a frame, or None if no rows are present

    Args:
        frame (pd.DataFrame): The DataFrame to analyze.

    Returns:
        float | None: The mean score, or None if no rows are present.
    """
    if frame.empty:
        return None
    return round(float(frame["score"].mean()), 3)


def _group_stats(frame: pd.DataFrame, key: str) -> list[dict[str, Any]]:
    """Return a list of dictionaries with statistics for each group in the frame
    Grouped by the given key.

    Args:
        frame (pd.DataFrame): The DataFrame to analyze.
        key (str): The column name to group by.

    Returns:
        list[dict[str, Any]]: A list of dictionaries with statistics for each group.
    """
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
    """Return a list of dictionaries with statistics for each model in the frame

    Args:
        frame (pd.DataFrame): The DataFrame to analyze.

    Returns:
        list[dict[str, Any]]: A list of dictionaries with statistics for each model.
    """
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
    """Convert a DataFrame row to a dictionary with appropriate types

    Args:
        row (pd.Series): The DataFrame row to convert.

    Returns:
        dict[str, Any]: A dictionary with the row's values converted to appropriate types.
    """
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
    """Return dashboard data for an experiment

    Args:
        experiment_id (int): The ID of the experiment to summarize.
        model_id (int | None): The ID of the model to filter by or None to show all models.

    Returns:
        dict[str, Any]: A dictionary with the summary statistics for the experiment.
    """
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
    evaluated_cases = int(filtered["test_case_id"].nunique())
    flagged = int(filtered["flagged"].sum()) if evaluated else 0
    not_flagged = evaluated - flagged
    if evaluated:
        headline = (
            f"{test_case_count} test cases; {flagged} flagged for possible sycophancy; "
            f"{not_flagged} not flagged."
        )
    else:
        headline = f"{test_case_count} test cases; none evaluated yet."

    by_risk = {risk.value: int((filtered["risk_level"] == risk.value).sum()) for risk in RiskLevel}
    cases = (
        filtered.sort_values(["score", "test_case_id"], ascending=[False, True])
        .apply(_row_dict, axis=1)
        .tolist()
        if not filtered.empty
        else []
    )

    return {
        "experiment_id": experiment_id,
        "model_id": model_id,
        "headline": headline,
        "totals": {
            "test_cases": test_case_count,
            "evaluated": evaluated,
            "not_evaluated": test_case_count - evaluated_cases,
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
