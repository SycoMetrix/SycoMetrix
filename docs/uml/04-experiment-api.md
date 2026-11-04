# 04 — Experiment and Test Case API

## Package structure

```mermaid
flowchart LR
    Routes[api/experiments.py and api/test_cases.py] --> Validation[api/validation.py]
    Routes --> Serializers[api/serializers.py]
    Routes --> Services[services/test_cases.py]
    Services --> Prompts[services/prompts.py]
    Routes --> Models[models.py]
    Services --> Models
```

Sources: [experiment routes](../../sycometrix/api/experiments.py),
[test case routes](../../sycometrix/api/test_cases.py), and
[test case service](../../sycometrix/services/test_cases.py).

## Test case creation

```mermaid
sequenceDiagram
    participant Client
    participant Route as create_experiment_test_case
    participant Service as create_test_case
    participant Generator as generate_prompts
    participant DB
    Client->>Route: POST question and beliefs
    Route->>Service: validated fields
    Service->>Generator: question, correct answer, incorrect belief
    Generator-->>Service: three ordered PromptVariation values
    Service->>DB: add TestCase and Prompt rows
    Route->>DB: commit
    Route-->>Client: 201 test case detail
```

## Editing stale data

```mermaid
flowchart TD
    Edit[Update test case] --> Source{Question or belief changed?}
    Source -- No --> Fields[Update supplied fields]
    Source -- Yes --> Delete[Delete evaluations and prompts]
    Delete --> Generate[Generate three replacement prompts]
    Generate --> Fields
    Fields --> Commit[Route commits]
```

## Design notes

- Routes only validate input, call the service layer, commit, and serialize results.
- Experiment listing uses one grouped query to count test cases and orders newest experiments first.
- Prompt serialization explicitly follows `Condition` order rather than database IDs.
- Test case detail reserves `results` for later response-collection work; evaluation summaries are included in experiment detail.
