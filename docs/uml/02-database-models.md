# 02 — Database Models and Migrations: Design

Ticket: [02 — Database models and migrations](../implementation_plan/02-database-models.md)

This ticket turns the proposed schema into SQLAlchemy 2.0 models, adds the first Alembic migration, and adds factory helpers for tests. The table-level view (columns, keys, cardinality) lives in [Database design](../database_er_diagrams.md); this doc covers the Python side.

## Package Diagram

```mermaid
flowchart TB
    subgraph sycometrix["sycometrix (package)"]
        init["__init__.py<br/>create_app()"]
        ext["extensions.py<br/>db, migrate"]
        models["models.py<br/>enums, models, utcnow()"]
    end

    subgraph migrations["migrations/"]
        env["env.py"]
        rev["versions/c897b1ec3d6a<br/>create initial database models"]
    end

    subgraph tests["tests/"]
        factories["factories.py<br/>make_* helpers"]
        test_models["test_models.py"]
    end

    init --> models
    models --> ext
    env -->|target_metadata| ext
    env --> rev
    factories --> models
    factories --> ext
    test_models --> factories
    test_models --> models
```

Source: [`models.py`](../../sycometrix/models.py), [`migrations/`](../../migrations/), [`factories.py`](../../tests/factories.py)

## Class Diagram

```mermaid
classDiagram
    direction LR

    class Condition {
        <<StrEnum>>
        NEUTRAL = "neutral"
        CORRECT_BELIEF = "correct_belief"
        INCORRECT_BELIEF = "incorrect_belief"
    }
    class Stance {
        <<StrEnum>>
        AGREES = "agrees"
        DISAGREES = "disagrees"
        UNCLEAR = "unclear"
    }
    class RiskLevel {
        <<StrEnum>>
        NONE = "none"
        LOW = "low"
        MEDIUM = "medium"
        HIGH = "high"
    }

    class Experiment {
        +id: int
        +name: str
        +description: str | None
        +created_at: datetime
        +test_cases: list~TestCase~
    }
    class TestCase {
        +id: int
        +experiment_id: int
        +question: str
        +correct_answer: str
        +incorrect_belief: str
        +category: str | None
        +experiment: Experiment
        +prompts: list~Prompt~
        +evaluations: list~Evaluation~
        +prompt_for(condition) Prompt | None
        +responses_for(model_id) dict~Condition, Response | None~
        +evaluation_for(model_id) Evaluation | None
    }
    class Prompt {
        +id: int
        +test_case_id: int
        +condition: Condition
        +prompt_text: str
        +test_case: TestCase
        +responses: list~Response~
    }
    class LLMModel {
        +id: int
        +provider: str
        +model_name: str
        +display_name: str
        +responses: list~Response~
        +evaluations: list~Evaluation~
    }
    class Response {
        +id: int
        +prompt_id: int
        +model_id: int
        +response_text: str
        +stance: Stance | None
        +stance_rationale: str | None
        +temperature: float | None
        +seed: int | None
        +created_at: datetime
        +prompt: Prompt
        +model: LLMModel
    }
    class Evaluation {
        +id: int
        +test_case_id: int
        +model_id: int
        +score: float
        +risk_level: RiskLevel
        +flagged: bool
        +explanation: str
        +created_at: datetime
        +test_case: TestCase
        +model: LLMModel
    }

    Experiment "1" *-- "*" TestCase : test_cases
    TestCase "1" *-- "*" Prompt : prompts
    TestCase "1" *-- "*" Evaluation : evaluations
    Prompt "1" *-- "*" Response : responses
    LLMModel "1" *-- "*" Response : responses
    LLMModel "1" *-- "*" Evaluation : evaluations

    Prompt ..> Condition
    Response ..> Stance
    Evaluation ..> RiskLevel
```

All six models subclass `db.Model`. Composition arrows mark the parent side of each relationship, which uses `cascade="all, delete-orphan"`.

Source: [`models.py`](../../sycometrix/models.py)

## Sequence Diagram: `TestCase.responses_for(model_id)`

Later tickets (scoring, comparison view) use this to get one model's three responses for a test case. It works from the loaded relationships and never runs its own query.

```mermaid
sequenceDiagram
    participant Caller as scoring / API (later tickets)
    participant TC as TestCase
    participant P as Prompt
    participant R as Response

    Caller->>TC: responses_for(model_id)
    loop each condition in Condition
        TC->>P: find prompt where prompt.condition == condition
        alt prompt exists
            P->>R: find response where response.model_id == model_id
            R-->>TC: Response or None
        else no prompt
            TC->>TC: None
        end
    end
    TC-->>Caller: {NEUTRAL: ..., CORRECT_BELIEF: ..., INCORRECT_BELIEF: ...}
```

## Design Notes

- **Enums store values, not names.** Every enum column uses `values_callable=enum_values`, so the database holds `"incorrect_belief"` and not `"INCORRECT_BELIEF"`. That matches the JSON API's lowercase enum values. To add a condition later, add a member to `Condition` and write a migration that alters the PostgreSQL `condition` type.
- **`StrEnum` instead of `(str, Enum)`.** The ticket shows `class Condition(str, enum.Enum)`. The code uses `enum.StrEnum` (Python 3.11+), which behaves the same and is what ruff's `UP042` rule asks for.
- **Cascades in both places.** Foreign keys have `ondelete="CASCADE"` for the database. Parent relationships have `cascade="all, delete-orphan"` and `passive_deletes=True` for the ORM. With `passive_deletes`, the ORM leaves child deletes to the database and doesn't load children first. SQLite enforces the cascade too, because ticket 01 turns on `PRAGMA foreign_keys`.
- **`LLMModel` survives experiment deletes.** `LLMModel` is not a child of `Experiment`. Deleting an experiment removes its responses and evaluations through `Prompt` and `TestCase`, and the model row stays. Deleting an `LLMModel` removes that model's responses and evaluations.
- **One current response per prompt and model.** `UNIQUE (prompt_id, model_id)` means re-running a model replaces its response; it doesn't add another row.
- **Downgrade drops enum types.** Alembic's `drop_table` doesn't remove PostgreSQL native enum types. `downgrade()` drops `stance`, `condition`, and `risk_level` explicitly, so `upgrade` can run again. On SQLite, `checkfirst=True` makes this a no-op.
- **`TestCase.__test__ = False`** keeps pytest from trying to collect the model as a test class when a test module imports it.
- **Test factories** (`make_experiment`, `make_test_case`, `make_llm_model`, `make_response`, `make_evaluation`) add to `db.session`, flush, and return the object. `make_test_case(with_prompts=True)` creates placeholder prompt text for now; ticket 04 switches it to the real generator from ticket 03.
