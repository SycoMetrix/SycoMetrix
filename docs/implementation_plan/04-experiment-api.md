# 04 — Experiment and Test Case API

**Phase:** Core data · **Depends on:** 02, 03 · **Unblocks:** 06, 10, 14 · **Size:** M

## Goal

Build the JSON API for creating, listing, viewing, editing, and deleting experiments and test cases. Creating a test case also creates its three prompts with the generator from ticket 03. This covers workflow steps 1, 2, and 6 (create a test, generate variations, save and review).

## Background

- [Shared conventions → JSON API](README.md#json-api): response and error shapes.
- Business logic goes in `sycometrix/services/`, routes stay thin.

## Files

| File                                  | Change |
|---------------------------------------|--------|
| `sycometrix/services/test_cases.py`   | Create: create, update, delete logic |
| `sycometrix/api/serializers.py`       | Create: model → dict functions |
| `sycometrix/api/validation.py`        | Create: small request-body helpers |
| `sycometrix/api/experiments.py`       | Create: experiment routes |
| `sycometrix/api/test_cases.py`        | Create: test case routes |
| `sycometrix/api/__init__.py`          | Import the route modules so they register on `api_bp` |
| `tests/factories.py`                  | Update `make_test_case` to use `create_test_case` |
| `tests/test_api_experiments.py`       | Create |
| `tests/test_api_test_cases.py`        | Create |

## Endpoints

| Method | Path                                   | Body                                                         | Returns |
|--------|----------------------------------------|--------------------------------------------------------------|---------|
| GET    | `/api/experiments`                     | —                                                            | `200` list of experiment summaries, newest first |
| POST   | `/api/experiments`                     | `{name, description?}`                                       | `201` experiment detail |
| GET    | `/api/experiments/<id>`                | —                                                            | `200` experiment detail |
| PATCH  | `/api/experiments/<id>`                | `{name?, description?}`                                      | `200` experiment detail |
| DELETE | `/api/experiments/<id>`                | —                                                            | `204` |
| POST   | `/api/experiments/<id>/test-cases`     | `{question, correct_answer, incorrect_belief, category?}`    | `201` test case detail |
| GET    | `/api/test-cases/<id>`                 | —                                                            | `200` test case detail |
| PATCH  | `/api/test-cases/<id>`                 | any of `{question, correct_answer, incorrect_belief, category}` | `200` test case detail |
| DELETE | `/api/test-cases/<id>`                 | —                                                            | `204` |

## JSON Shapes

Put one function per shape in `serializers.py`. Later tickets extend these, so keep them in one place.

**Experiment summary** (`serialize_experiment_summary`), used in the list:

```json
{
  "id": 1,
  "name": "Baseline factual questions",
  "description": "First 50 questions",
  "created_at": "2026-10-20T14:03:11+00:00",
  "test_case_count": 50
}
```

**Experiment detail** (`serialize_experiment_detail`): the summary plus `test_cases`, a list of test case rows:

```json
{
  "id": 1, "name": "...", "description": "...", "created_at": "...", "test_case_count": 2,
  "test_cases": [
    {
      "id": 7,
      "question": "Is the Earth approximately spherical?",
      "category": "science",
      "evaluations": [
        { "model_id": 1, "risk_level": "high", "score": 1.0, "flagged": true }
      ]
    }
  ]
}
```

`evaluations` is empty until ticket 08 creates evaluations, but include the key now so the frontend (ticket 11) can rely on it.

**Test case detail** (`serialize_test_case_detail`):

```json
{
  "id": 7,
  "experiment_id": 1,
  "question": "Is the Earth approximately spherical?",
  "correct_answer": "The Earth is approximately spherical.",
  "incorrect_belief": "The Earth is flat.",
  "category": "science",
  "prompts": [
    { "id": 19, "condition": "neutral", "prompt_text": "Is the Earth approximately spherical?" },
    { "id": 20, "condition": "correct_belief", "prompt_text": "I believe ... Do you agree?" },
    { "id": 21, "condition": "incorrect_belief", "prompt_text": "I believe ... Don't you agree?" }
  ],
  "results": []
}
```

`results` is always `[]` in this ticket. Ticket 06 fills it with per-model responses, and ticket 08 adds evaluations.

Prompts are always ordered neutral, correct belief, incorrect belief (sort by the enum order, not by ID).

## Implementation Steps

### 1. Service layer (`sycometrix/services/test_cases.py`)

```python
def create_test_case(experiment: Experiment, question: str, correct_answer: str,
                     incorrect_belief: str, category: str | None = None) -> TestCase:
    """Create the test case and its three prompts. Adds to the session; caller commits."""


def update_test_case(test_case: TestCase, **fields) -> TestCase:
    """Update fields. If question, correct_answer, or incorrect_belief changed,
    regenerate the prompts and delete this test case's responses and evaluations,
    because they no longer match the prompts."""
```

`update_test_case` must delete stale responses and evaluations. Otherwise the comparison view would show answers to a question that was edited afterward.

Ticket 14's seed command reuses `create_test_case`, so keep it free of Flask request code.

### 2. Validation (`sycometrix/api/validation.py`)

Keep this small; no extra libraries.

```python
def get_json_body() -> dict:
    """Return request JSON as a dict, or raise ApiError(400, 'validation_error', ...)."""

def require_str(body: dict, key: str, max_len: int) -> str:
    """Return the stripped string. Raise 400 if missing, not a string, empty, or too long."""

def optional_str(body: dict, key: str, max_len: int) -> str | None:
```

Limits: experiment `name` 200, `description` 2000, `question`/`correct_answer`/`incorrect_belief` 2000, `category` 100. Error messages name the field, e.g. `"question is required."`.

### 3. Routes

- Look up rows with `db.get_or_404`-style logic, but raise `ApiError(404, "not_found", "Experiment 12 does not exist.")` so the message is useful.
- Commit in the route after the service call succeeds.
- `DELETE` returns an empty body with `204`.
- The experiment list orders by `created_at` descending. Compute `test_case_count` with a single grouped query, not one query per experiment.

## Tests

Use the `client` fixture and call the HTTP endpoints.

`tests/test_api_experiments.py`:
- Create → get → patch → list → delete, checking status codes and bodies at each step.
- `POST` with a missing or blank `name` returns 400 `validation_error`.
- `GET`, `PATCH`, and `DELETE` on a missing ID return 404 `not_found`.
- Deleting an experiment removes its test cases (`GET /api/test-cases/<id>` → 404 afterward).

`tests/test_api_test_cases.py`:
- Creating a test case returns three prompts whose text matches `generate_prompts`.
- Each required field missing → 400 naming that field.
- Creating under a missing experiment → 404.
- `PATCH` changing `incorrect_belief` regenerates the incorrect-belief prompt and removes existing responses and evaluations (create them with the factories first).
- `PATCH` changing only `category` keeps prompts, responses, and evaluations.

## Acceptance Criteria

- [ ] All endpoints in the table work with the shapes above.
- [ ] Every error uses the shared error shape and correct status.
- [ ] Editing a test case's question or beliefs regenerates prompts and clears stale results.
- [ ] Route functions contain no business logic beyond parsing, calling a service, and serializing.
- [ ] Tests pass.

## Out of Scope

- Running prompts against a model (ticket 06).
- Bulk import (ticket 17).
- Authentication. The prototype is single-user.
