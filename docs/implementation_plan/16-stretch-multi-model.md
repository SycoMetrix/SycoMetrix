# 16 — Stretch: Multi-Model Comparison

**Phase:** Stretch · **Depends on:** 15 · **Size:** M

## Goal

The client said: "If feasible, allow results to be compared across models." The data model already supports this (`model_id` on `response` and `evaluation`, `by_model` in the summary). This ticket adds the UI and small API changes to run an experiment against several models and compare them.

Start this only after the minimum goal (ticket 15) is met.

## Tasks

### 1. Choose models

Pick 2–4 models on OpenRouter that differ meaningfully (different providers or sizes). Add them with `POST /api/models` or a new `--model` option on `flask seed-models` that can be repeated. Check each one with `flask llm-ping`. Free tiers vary, so note costs in the PR.

Keep `JUDGE_MODEL` **fixed** across all models in a comparison; otherwise differences could come from the judge rather than the tested model.

### 2. Run several models (experiment page)

- Turn the model picker into a "run with" multi-select (checkboxes). Keep a separate single "view results for" selector for the table.
- The run loop runs each selected model in turn for each test case (test case outer loop, model inner loop), still one request at a time. Progress counts `(test case, model)` pairs: "34 / 100".
- `flask run-experiment` accepts `--model-id` more than once.

### 3. Model comparison on the dashboard

When the summary's `by_model` has more than one model:

- A grouped bar chart: one group per risk level, one bar per model (counts), or a single bar chart of `flag_rate` per model. Pick whichever reads more clearly with your real data.
- A small table: model, evaluated, flagged, flag rate, mean score.
- A per-category comparison: flag rate by category with one bar per model (add `by_category_by_model` to the summary endpoint in ticket 09's service, computed with a Pandas `groupby(["category", "model_id"])`).

### 4. Comparison view (test case page)

Add a **Compare models** toggle. When on, show one row per model, each with the three stance badges and the risk badge, so the user can see at a glance which models caved on this question. Clicking a row switches the main view to that model.

### 5. Disagreement list

Add `GET /api/experiments/<id>/model-disagreements` returning test cases where the models' risk levels differ (e.g. one high, one none). These are the most interesting cases to read. Link to it from the dashboard.

## Tests

- Summary with two models gives correct `by_model` and `by_category_by_model`.
- The disagreements endpoint returns exactly the test cases with differing risk levels.
- CLI with two `--model-id` values runs both.

## Acceptance Criteria

- [ ] An experiment can be run against several models from the UI and CLI.
- [ ] The dashboard compares models when more than one has results.
- [ ] The test case page can show all models at once.
- [ ] The demo script (`docs/demo/README.md`) gains a model comparison section.
