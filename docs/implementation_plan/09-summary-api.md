# 09 — Experiment Summary API

**Phase:** Results · **Depends on:** 08 · **Unblocks:** 13 · **Size:** S

## Goal

Add one endpoint that returns everything the dashboard needs for an experiment: the headline ("50 test cases; 9 flagged for possible sycophancy; 41 not flagged"), counts by risk level, breakdowns by category and model, and a per-case table. This is workflow step 7. Use Pandas for the aggregation, as listed in the [tech stack](../tech_stack.md).

## Files

| File                              | Change |
|-----------------------------------|--------|
| `sycometrix/services/summary.py`  | Create |
| `sycometrix/api/experiments.py`   | Add the summary route |
| `tests/test_summary.py`           | Create |

## Endpoint

`GET /api/experiments/<id>/summary?model_id=1`

- `model_id` is optional. The frontend always sends it for the headline numbers. Without it, counts are over every `(test case, model)` evaluation in the experiment.
- 404 if the experiment doesn't exist; 400 if `model_id` is given but doesn't exist.

Response:

```json
{
  "experiment_id": 1,
  "model_id": 1,
  "headline": "50 test cases; 9 flagged for possible sycophancy; 41 not flagged.",
  "totals": {
    "test_cases": 50,
    "evaluated": 50,
    "not_evaluated": 0,
    "flagged": 9,
    "not_flagged": 41
  },
  "flag_rate": 0.18,
  "mean_score": 0.21,
  "by_risk": { "none": 35, "low": 6, "medium": 4, "high": 5 },
  "by_category": [
    { "category": "science", "evaluated": 12, "flagged": 3, "flag_rate": 0.25, "mean_score": 0.31 }
  ],
  "by_model": [
    { "model_id": 1, "display_name": "Nemotron 3 Ultra (free)", "evaluated": 50, "flagged": 9,
      "flag_rate": 0.18, "mean_score": 0.21 }
  ],
  "cases": [
    { "test_case_id": 7, "question": "Is the Earth approximately spherical?", "category": "science",
      "model_id": 1, "risk_level": "high", "score": 1.0, "flagged": true }
  ]
}
```

Rules:

- `by_risk` always has all four keys, even with a count of 0.
- `flag_rate` = `flagged / evaluated`, rounded to 3 decimals; `null` when `evaluated` is 0. Same for `mean_score`.
- Test cases with no category are grouped as `"uncategorized"`.
- `by_model` ignores the `model_id` filter so the dashboard can always show a model comparison (ticket 16).
- `cases` contains only evaluated rows, sorted by score descending, then `test_case_id`.
- If nothing has been evaluated yet, `headline` is `"50 test cases; none evaluated yet."`.

## Implementation Steps

1. Query the rows with one SQLAlchemy `select` joining `evaluation`, `test_case`, and `model`, filtered by experiment. Count test cases with a separate `count()` query (test cases without evaluations still count toward `test_cases`).
2. Load the rows into a `pandas.DataFrame` with columns `test_case_id, question, category, model_id, display_name, risk_level, score, flagged`.
3. Compute the aggregates with `groupby`. Write small helpers (`_rate(df)`, `_group_stats(df, key)`) rather than one long function.
4. Convert NumPy types to plain Python (`int(...)`, `float(...)`) before returning; `jsonify` can't serialize `numpy.int64`. Replace `NaN` with `None`.
5. Keep the service a pure function of the database: `build_summary(experiment_id: int, model_id: int | None) -> dict`.

## Tests (`tests/test_summary.py`)

Build data directly with the factories (no LLM calls): one experiment, five test cases in two categories plus one without a category, two models, and evaluations with known risk levels. One test case has no evaluation.

- Totals, `by_risk`, and the headline match hand-computed numbers, with and without `model_id`.
- `by_category` includes `"uncategorized"`.
- `by_model` is the same whether or not `model_id` is passed.
- An experiment with no evaluations returns the "none evaluated yet" headline, zeros, and `null` rates.
- The response is JSON-serializable (call the endpoint through `client`, not only the service).

## Acceptance Criteria

- [ ] The endpoint returns the shape above.
- [ ] Numbers match a hand-calculated fixture.
- [ ] Empty and partially evaluated experiments work.
- [ ] Tests pass.

## Out of Scope

- Charts (ticket 13).
- File export (ticket 17).
