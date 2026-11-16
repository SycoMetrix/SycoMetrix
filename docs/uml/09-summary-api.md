# 09 — Experiment Summary API

Ticket: [09 — Experiment summary API](../implementation_plan/09-summary-api.md)

## Package flow

```mermaid
flowchart LR
    Route[sycometrix/api/experiments.py] --> Summary[build_summary]
    Summary --> Pandas[pandas.DataFrame]
    Summary --> DB[(Evaluation, TestCase, LLMModel)]
    Summary --> JSON[Dashboard JSON]
```

Source: [experiments.py](../../sycometrix/api/experiments.py),
[summary.py](../../sycometrix/services/summary.py)

## Summary sequence

```mermaid
sequenceDiagram
    participant HTTP as GET /api/experiments/:id/summary
    participant Route as experiments.py
    participant Service as build_summary
    participant DB as database
    participant Pandas as pandas

    HTTP->>Route: optional model_id
    Route->>DB: verify experiment and model
    Route->>Service: build_summary(experiment_id, model_id)
    Service->>DB: count test cases
    Service->>DB: query evaluations, cases, and models
    Service->>Pandas: aggregate filtered and all-model rows
    Pandas-->>Service: dashboard statistics
    Service-->>Route: JSON compatible dictionary
    Route-->>HTTP: summary response
```

## Design notes

- The optional model filter applies to headline totals, category statistics, and cases.
- Model comparison always aggregates all evaluations, allowing the dashboard to compare models even when a headline is filtered.
- `totals.evaluated` counts evaluation rows. `totals.not_evaluated` counts distinct test cases with no evaluation in the selected scope. For an unfiltered test case `evaluated` can exceed `test_cases`.
- Empty evaluation sets retain the experiment's test-case count and return null rates and means.
