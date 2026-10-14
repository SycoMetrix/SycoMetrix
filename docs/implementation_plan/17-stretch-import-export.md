# 17 — Stretch: Import and Export

**Phase:** Stretch · **Depends on:** 15 · **Size:** M

## Goal

The client listed "importing large datasets" and "exporting results" as stretch goals. Add CSV/JSON import of test cases through the UI and API, and export of experiment results for analysis in other tools (Excel, Python notebooks).

## Import

### Endpoint

`POST /api/experiments/<id>/import` with `multipart/form-data`, field `file` (`.csv` or `.json`, max 5 MB).

- **JSON:** the same format as `data/seed_questions.json` (ticket 14).
- **CSV:** header row with `question,correct_answer,incorrect_belief,category`. `category` is optional. Read with `pandas.read_csv(..., dtype=str, keep_default_na=False)` so empty cells become `""` instead of `NaN`.
- Trim whitespace in every field.

### Behavior

- Validate every row before writing anything. On any errors, return `400 validation_error` with a list:

  ```json
  { "error": { "code": "validation_error", "message": "3 rows have errors.",
               "details": [ { "row": 4, "message": "question is required." } ] } }
  ```

  Row numbers match what the user sees in a spreadsheet (header = row 1).
- Skip rows whose question already exists in the experiment, and report how many were skipped.
- On success, create everything in one transaction using `create_test_case` and return `{"created": 48, "skipped": 2}`.
- Refactor `flask seed-demo` (ticket 14) to share the same parsing and validation code.

### UI

On the experiment page, an **Import** button opens a file picker with a short description of the expected columns and a link to download a template CSV (`/static/templates/test_cases_template.csv`). Show the result or the per-row errors.

## Export

### Endpoint

`GET /api/experiments/<id>/export?format=csv|json&model_id=` (model optional; all models if omitted).

One row per `(test case, model)`, with columns:

```
experiment_id, experiment_name, test_case_id, category, question, correct_answer, incorrect_belief,
model_name, neutral_prompt, neutral_response, neutral_stance,
correct_belief_prompt, correct_belief_response, correct_belief_stance,
incorrect_belief_prompt, incorrect_belief_response, incorrect_belief_stance,
risk_level, score, flagged, explanation, judge_model, exported_at
```

- Build with Pandas and return with `Content-Disposition: attachment; filename="sycometrix-experiment-<id>-<YYYYMMDD>.csv"`.
- CSV must be UTF-8 with a BOM (`encoding="utf-8-sig"`) so Excel shows accented characters correctly.
- **Guard against CSV formula injection:** LLM responses could begin with `=`, `+`, `-`, or `@`, which spreadsheet apps execute as formulas. Prefix such cells with a single quote (`'`).
- JSON export returns the same rows as a list of objects, plus the summary from ticket 09 under a `summary` key.

### UI

An **Export** dropdown on the experiment page (CSV / JSON) that downloads for the currently selected model, or all models.

## Tests

- Import: valid CSV and JSON create the right test cases; bad rows return per-row errors and create nothing; duplicates are skipped; a non-CSV/JSON file → 400.
- Export: CSV has the header above and one row per evaluated `(test case, model)`; a response starting with `=` is escaped; JSON includes `summary`.
- Round trip: export as CSV, import the `question/correct_answer/incorrect_belief/category` columns into a new experiment, and get the same test cases.

## Acceptance Criteria

- [ ] Users can import test cases from CSV or JSON with clear per-row errors.
- [ ] Users can export results as CSV or JSON from the UI.
- [ ] Exports are safe to open in Excel.
- [ ] Tests pass.
