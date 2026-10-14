# 02 — Database Models and Migrations

**Phase:** Foundation · **Depends on:** 01 · **Unblocks:** 04, 05 · **Size:** M

## Goal

Implement the proposed schema from [Database design](../database_er_diagrams.md) as SQLAlchemy models, create the first migration, and add test helpers for building data.

## Background

- [Database design → Proposed Schema](../database_er_diagrams.md#proposed-schema): the source of truth for tables and columns.
- [Shared conventions → Code style](README.md#code-style): SQLAlchemy 2.0 style only.

## Changes to the Documented Schema

This ticket makes two small additions. Update `docs/database_er_diagrams.md` in the same PR so the doc stays accurate.

| Change                                         | Why                                                                                                    |
|------------------------------------------------|--------------------------------------------------------------------------------------------------------|
| Add `response.stance_rationale` (text, nullable) | Ticket 07 stores the judge's one-sentence reason for each stance. It shows up in the comparison view.  |
| Add `UNIQUE (prompt_id, model_id)` on `response` | Without a `run` table, each model has one current response per prompt. Re-running replaces it.         |

Also define `response.stance` as **the response's conclusion relative to `test_case.correct_answer`**: `agrees` means the response affirms the correct answer, `disagrees` means it contradicts it, `unclear` means it doesn't commit. `stance` is nullable; it is `NULL` until ticket 07 classifies the response. Add this definition to the doc too.

## Files

| File                          | Change                                       |
|-------------------------------|----------------------------------------------|
| `sycometrix/models.py`        | Create: enums and models                     |
| `migrations/`                 | Create with `flask db init`, then first migration |
| `tests/factories.py`          | Create: helper functions to build test data  |
| `tests/test_models.py`        | Create                                       |
| `docs/database_er_diagrams.md`| Update as described above                    |

## Implementation Steps

### 1. Enums

Use Python `enum.Enum` subclasses with string values, stored with `sqlalchemy.Enum(..., values_callable=lambda e: [m.value for m in e])` so the database stores the lowercase values, not the member names.

```python
class Condition(str, enum.Enum):
    NEUTRAL = "neutral"
    CORRECT_BELIEF = "correct_belief"
    INCORRECT_BELIEF = "incorrect_belief"


class Stance(str, enum.Enum):
    AGREES = "agrees"
    DISAGREES = "disagrees"
    UNCLEAR = "unclear"


class RiskLevel(str, enum.Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
```

Write the enum so adding a fourth condition later (e.g. `new_evidence`, see the open questions in the database doc) only means adding a member and a migration.

### 2. Models

Class names below are fixed because later tickets import them. Note `LLMModel`: calling it `Model` would be confusing next to `db.Model`. Its table name is still `model`.

| Class        | `__tablename__` | Columns                                                                                                                            |
|--------------|-----------------|------------------------------------------------------------------------------------------------------------------------------------|
| `Experiment` | `experiment`    | `id`, `name` (String(200), not null), `description` (Text, nullable), `created_at` (DateTime(timezone=True), default now UTC)       |
| `TestCase`   | `test_case`     | `id`, `experiment_id` (FK, not null, `ondelete="CASCADE"`), `question` (Text), `correct_answer` (Text), `incorrect_belief` (Text), `category` (String(100), nullable) |
| `Prompt`     | `prompt`        | `id`, `test_case_id` (FK, cascade), `condition` (Enum `Condition`), `prompt_text` (Text)                                           |
| `LLMModel`   | `model`         | `id`, `provider` (String(50)), `model_name` (String(200)), `display_name` (String(200))                                            |
| `Response`   | `response`      | `id`, `prompt_id` (FK, cascade), `model_id` (FK, cascade), `response_text` (Text), `stance` (Enum `Stance`, nullable), `stance_rationale` (Text, nullable), `temperature` (Float, nullable), `seed` (Integer, nullable), `created_at` |
| `Evaluation` | `evaluation`    | `id`, `test_case_id` (FK, cascade), `model_id` (FK, cascade), `score` (Float), `risk_level` (Enum `RiskLevel`), `flagged` (Boolean), `explanation` (Text), `created_at` |

Unique constraints (use `__table_args__ = (UniqueConstraint(...),)`):

- `prompt (test_case_id, condition)`
- `model (provider, model_name)`
- `response (prompt_id, model_id)`
- `evaluation (test_case_id, model_id)`

Relationships (set `cascade="all, delete-orphan"` on the parent side so ORM deletes cascade too, in addition to the database `ON DELETE CASCADE`):

- `Experiment.test_cases` ↔ `TestCase.experiment` (order by `TestCase.id`)
- `TestCase.prompts` ↔ `Prompt.test_case`
- `TestCase.evaluations` ↔ `Evaluation.test_case`
- `Prompt.responses` ↔ `Response.prompt`
- `LLMModel.responses` ↔ `Response.model`
- `LLMModel.evaluations` ↔ `Evaluation.model`

Helper methods that later tickets use:

```python
class TestCase:
    def prompt_for(self, condition: Condition) -> Prompt | None: ...
    def responses_for(self, model_id: int) -> dict[Condition, Response | None]:
        """Map each condition to this model's response, or None if it hasn't run."""
    def evaluation_for(self, model_id: int) -> Evaluation | None: ...
```

Use a `utcnow()` helper (`datetime.now(timezone.utc)`) for `created_at` defaults.

Note for pytest: a class named `TestCase` in a module that pytest collects can trigger a collection warning. Since it lives in `sycometrix/models.py` (not under `tests/`) it is fine, but if you import it into a test module, add `__test__ = False` to the class.

### 3. Migration

```bash
flask db init
flask db migrate -m "initial schema"
```

Open the generated file and check it by hand:

- Enum types are created (PostgreSQL native enums) and dropped in `downgrade()`.
- Every foreign key has `ondelete="CASCADE"`.
- All four unique constraints are present.

Then run `flask db upgrade` against the Docker PostgreSQL and confirm the tables exist (`docker compose exec db psql -U sycometrix -c '\dt'`).

### 4. Test factories (`tests/factories.py`)

Plain functions (no extra library) that add to `db.session`, flush, and return the object. Later tickets lean on these heavily.

```python
def make_experiment(name="Test experiment", **kw) -> Experiment
def make_test_case(experiment=None, question="Is the Earth approximately spherical?",
                   correct_answer="The Earth is approximately spherical.",
                   incorrect_belief="The Earth is flat.", category="science",
                   with_prompts=True) -> TestCase
def make_llm_model(model_name="fake/model", provider="fake", display_name="Fake Model") -> LLMModel
def make_response(prompt, model, text="...", stance=None) -> Response
```

Until ticket 03 exists, `with_prompts=True` can create three prompts with placeholder text. Ticket 04 switches it to the real generator.

## Tests (`tests/test_models.py`)

- Creating an experiment with a test case, three prompts, a model, three responses, and an evaluation works, and the relationships navigate both ways.
- A second prompt with the same `(test_case_id, condition)` raises `IntegrityError`.
- A second response for the same `(prompt_id, model_id)` raises `IntegrityError`.
- Deleting an experiment deletes its test cases, prompts, responses, and evaluations, but not the `LLMModel`.
- `TestCase.responses_for(model_id)` returns all three conditions as keys, with `None` for missing ones.
- Enum columns round-trip as enum members and are stored as lowercase strings.

## Acceptance Criteria

- [ ] All six models exist with the columns, constraints, and relationships above.
- [ ] `flask db upgrade` works on a fresh PostgreSQL database, and `flask db downgrade` reverses it.
- [ ] Tests pass on SQLite. (Optional: also run them once with `TEST_DATABASE_URL` pointing at PostgreSQL.)
- [ ] `docs/database_er_diagrams.md` reflects the two additions and the `stance` definition.

## Out of Scope

- API endpoints (ticket 04).
- The `run` table and question bank from the database doc's open questions.
