# 06 — Response Collection

Ticket: [06 — Response collection](../implementation_plan/06-response-collection.md)

This ticket adds the single-case pipeline that sends one model three independent
prompts, stores each answer, and returns the updated test case detail. The
service layer keeps the HTTP route thin; the CLI reuses the same service for a
whole experiment so the backend can stop after each case without losing progress.

## Package flow

```mermaid
flowchart LR
    API[sycometrix/api/test_cases.py] --> Service[sycometrix/services/pipeline.py]
    Service --> Collect[sycometrix/services/collection.py]
    Collect --> Client[LLMClient.chat]
    Collect --> DB[(SQLite/PostgreSQL)]
    CLI[sycometrix/cli.py] --> Service
```

`run_test_case()` is the single entry point for one test case and one model. It
commits after the collection step and leaves stance/scoring work for later
tickets. The route validates the model and temperature before calling the same
service so the API and CLI behave consistently.

Source: [collection.py](../../sycometrix/services/collection.py),
[pipeline.py](../../sycometrix/services/pipeline.py),
[test_cases.py](../../sycometrix/api/test_cases.py),
[cli.py](../../sycometrix/cli.py)

## Request and save sequence

```mermaid
sequenceDiagram
    participant HTTP as POST /api/test-cases/:id/run
    participant Route as test_cases.py
    participant Pipe as run_test_case
    participant Collect as collect_responses
    participant Client as LLMClient
    participant DB as database

    HTTP->>Route: model_id, temperature, seed
    Route->>Route: validate model + sampling args
    Route->>Pipe: run_test_case(test_case, model, ...)
    Pipe->>Collect: collect_responses(...)
    loop each condition in neutral, correct_belief, incorrect_belief
        Collect->>Client: chat(model_name, [{role:user, content: prompt_text}])
        Client-->>Collect: ChatResult with text
    end
    Collect->>DB: delete stale responses + evaluation for this model
    Collect->>DB: insert 3 Response rows
    Collect-->>Pipe: new responses
    Pipe->>DB: commit
    Pipe-->>Route: None
    Route-->>HTTP: test case detail with results
```

The collection service gathers all three model replies before making any write,
so a failed response leaves the earlier database state intact. It deletes stale
rows for the same model/test case before inserting the new three replies, which
keeps the result set consistent with the current prompts and model.

## State of one run

```mermaid
stateDiagram-v2
    [*] --> Ready
    Ready --> Collecting: run_test_case()
    Collecting --> Failed: LLMError / validation problem
    Collecting --> Saved: all prompts responded
    Saved --> Committed: db.session.commit()
    Committed --> [*]
    Failed --> RolledBack: rollback and re-raise
    RolledBack --> [*]
```

Design notes:

- The actual run remains one test case and one model. The frontend or CLI loops
  over test cases and can show partial progress without a background worker.
- `results` in the test case detail is assembled with the model registry and each
  prompt's latest response for that model, ordered by `display_name`.
- Later tickets will add stance classification and evaluation to this same
  pipeline, without changing the outer request/commit pattern.
