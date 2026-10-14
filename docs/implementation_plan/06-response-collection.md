# 06 — Response Collection

**Phase:** LLM pipeline · **Depends on:** 04, 05 · **Unblocks:** 07, 11 · **Size:** M

## Goal

Send a test case's three prompts to a model and save the three responses. This is workflow step 3 (collect responses). Add an API endpoint to run one test case and a CLI command to run a whole experiment.

This ticket also creates `services/pipeline.py`, the single entry point for "run this test case". Tickets 07 and 08 add steps to it.

## Background

- `TestCase.prompts`, `Response`, and the `UNIQUE (prompt_id, model_id)` constraint from ticket 02.
- `get_llm_client()` and `FakeLLMClient` from ticket 05.

### Why one test case per request

A full experiment can take many minutes (hundreds of slow LLM calls). Rather than adding a background job queue, the prototype runs **one test case per HTTP request**: three LLM calls, typically well under a minute. The frontend (ticket 11) loops over test cases and shows progress. The CLI command does the same loop for batch runs. This keeps the backend simple and makes partial progress safe.

## Files

| File                                 | Change |
|--------------------------------------|--------|
| `sycometrix/services/collection.py`  | Create |
| `sycometrix/services/pipeline.py`    | Create |
| `sycometrix/api/test_cases.py`       | Add the run endpoint |
| `sycometrix/api/serializers.py`      | Fill in `results` in the test case detail |
| `sycometrix/cli.py`                  | Add `run-experiment` |
| `tests/test_collection.py`           | Create |
| `tests/test_api_run.py`              | Create |

## Implementation Steps

### 1. Collection service (`services/collection.py`)

```python
def collect_responses(
    test_case: TestCase,
    model: LLMModel,
    client: LLMClient,
    *,
    temperature: float | None,
    seed: int | None,
    max_tokens: int | None,
) -> list[Response]:
```

Behavior:

1. For each prompt in condition order (neutral, correct belief, incorrect belief), call `client.chat(model.model_name, [{"role": "user", "content": prompt.prompt_text}], ...)`.
   - **Each prompt is a fresh, single-message conversation.** Never include earlier responses as history; otherwise the conditions would contaminate each other.
   - No system prompt. We want the model's default behavior.
2. Make **all three calls before writing anything**. If any call raises `LLMError`, let it propagate and leave the database unchanged. A test case should never end up with only some of its responses replaced.
3. After all three succeed, delete this model's existing responses for these prompts and this model's existing evaluation for the test case (both are now stale), then insert the three new `Response` rows with `temperature` and `seed` recorded. `stance` stays `NULL`.
4. Flush, don't commit. The caller commits.

### 2. Pipeline (`services/pipeline.py`)

```python
def run_test_case(
    test_case: TestCase,
    model: LLMModel,
    *,
    client: LLMClient | None = None,
    temperature: float | None = None,
    seed: int | None = None,
) -> None:
    """Run the full workflow for one test case and one model, then commit.

    Steps:
      1. Collect responses (this ticket).
      2. Classify stances (ticket 07).
      3. Score and save the evaluation (ticket 08).
    """
```

- `client` defaults to `get_llm_client()`.
- `temperature` defaults to `current_app.config["DEFAULT_TEMPERATURE"]`; `max_tokens` comes from `MAX_RESPONSE_TOKENS`.
- Commit at the end. On any exception, `db.session.rollback()` and re-raise.

### 3. Run endpoint

`POST /api/test-cases/<id>/run`

Body: `{"model_id": 1, "temperature": 0.0, "seed": 42}`. Only `model_id` is required.

| Situation                         | Response |
|-----------------------------------|----------|
| Success                           | `200` test case detail (with `results` filled in) |
| Test case not found               | `404 not_found` |
| `model_id` missing                | `400 validation_error` |
| `model_id` doesn't exist          | `400 validation_error` ("Model 9 does not exist.") |
| `temperature` not a number in [0, 2] | `400 validation_error` |
| `LLMError`                        | `502 llm_error` with the error message |

### 4. Fill in `results` in the test case detail

Replace the empty `results` list with one entry per model that has at least one response for this test case, ordered by model `display_name`:

```json
"results": [
  {
    "model": { "id": 1, "provider": "openrouter", "model_name": "...", "display_name": "..." },
    "responses": {
      "neutral":          { "id": 31, "response_text": "...", "stance": null, "stance_rationale": null,
                            "temperature": 0.0, "seed": null, "created_at": "..." },
      "correct_belief":   { ... },
      "incorrect_belief": { ... }
    },
    "evaluation": null
  }
]
```

- `responses` always has all three keys; a missing response is `null`.
- `evaluation` stays `null` until ticket 08.
- Use `TestCase.responses_for(model_id)` from ticket 02.

### 5. CLI: `flask run-experiment`

```
flask run-experiment EXPERIMENT_ID --model-id 1 [--only-pending] [--temperature 0.0] [--seed 42]
```

- Loops over the experiment's test cases and calls `run_test_case` for each.
- `--only-pending` skips test cases that already have all three responses for this model.
- Prints one line per case: `[12/50] #57 ok (8.4s)` or `[13/50] #58 FAILED: <message>`.
- Keeps going after a failure, then prints a final count: `48 succeeded, 2 failed.` and exits non-zero if anything failed.
- Ctrl-C stops cleanly between cases; finished cases stay saved because each is committed on its own.

## Tests

Use `FakeLLMClient` with a `responder` so you control exact output.

`tests/test_collection.py`:
- Running a test case makes exactly three calls, each with a single user message whose content is the prompt text.
- Three `Response` rows are saved with the right `prompt_id`, `model_id`, `temperature`, and `seed`.
- Running again replaces the responses (still three rows, new text) and deletes an existing evaluation.
- If the third call raises `LLMError`, the earlier responses from a previous run are still there, unchanged.

`tests/test_api_run.py`:
- Success returns 200 and `results[0].responses` has all three conditions with the fake text.
- Unknown test case → 404; missing or unknown `model_id` → 400; `LLMError` → 502 `llm_error`.

Test the CLI with `app.test_cli_runner()`: two test cases, one of which fails, gives exit code 1 and both summary lines.

## Acceptance Criteria

- [ ] `POST /api/test-cases/<id>/run` collects and saves three responses.
- [ ] Prompts are sent independently, with no shared history.
- [ ] Failed runs leave existing data unchanged.
- [ ] `flask run-experiment` runs a whole experiment with progress output and survives individual failures.
- [ ] Test case detail includes `results` in the shape above.
- [ ] Tests pass with no network access.

## Out of Scope

- Stances and scores (tickets 07, 08).
- Running several models at once (ticket 16).
- Background jobs or concurrency.
