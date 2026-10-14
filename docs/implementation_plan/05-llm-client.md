# 05 — LLM Client

**Phase:** LLM pipeline · **Depends on:** 02 · **Unblocks:** 06 · **Size:** M

## Goal

Build one small interface for sending a chat request to an LLM, with two implementations:

- `OpenRouterClient`, which calls OpenRouter over HTTP (see [LLM API usage](../API.md)).
- `FakeLLMClient`, which returns canned text, so tests and frontend work never spend API quota.

Also add API endpoints and a CLI command for managing rows in the `model` table.

## Background

- [LLM API usage](../API.md): OpenRouter endpoint, headers, and parameters.
- Config keys from ticket 01: `LLM_PROVIDER`, `OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL`, `DEFAULT_MODEL`, `LLM_TIMEOUT_SECONDS`, `LLM_MAX_RETRIES`, `MAX_RESPONSE_TOKENS`.

### Rate limits

Free OpenRouter models are rate limited per minute and per day, and the daily cap is low unless the account has bought credits. Check the current numbers on OpenRouter's docs before running a full experiment. A 50-question experiment needs about **300 requests**: 150 to the tested model (3 per question) plus 150 to the judge model (ticket 07). This is why `FakeLLMClient` matters: use it for all development and tests, and save real calls for actual experiments.

## Files

| File                              | Change |
|-----------------------------------|--------|
| `sycometrix/services/llm_client.py` | Create |
| `sycometrix/api/llm_models.py`    | Create: `/api/models` routes |
| `sycometrix/api/serializers.py`   | Add `serialize_llm_model` |
| `sycometrix/cli.py`               | Create: `seed-models` command; register in `create_app` |
| `tests/test_llm_client.py`        | Create |
| `tests/test_api_llm_models.py`    | Create |

## Implementation Steps

### 1. Interface

```python
@dataclass
class ChatResult:
    text: str          # the assistant message content
    model: str         # the model slug that answered
    latency_ms: int
    raw: dict          # full provider response, for debugging


class LLMError(Exception):
    """The provider failed, after retries where retrying made sense."""


class LLMClient(Protocol):
    def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
        seed: int | None = None,
        max_tokens: int | None = None,
    ) -> ChatResult: ...
```

`messages` uses the OpenAI format: `[{"role": "system" | "user" | "assistant", "content": "..."}]`.

### 2. `OpenRouterClient`

```python
class OpenRouterClient:
    def __init__(self, api_key: str, base_url: str, timeout: int = 120, max_retries: int = 3,
                 session: requests.Session | None = None): ...
```

- `POST {base_url}/chat/completions` with headers `Authorization: Bearer <key>`, `Content-Type: application/json`, `X-Title: SycoMetrix`.
- Body: `model`, `messages`, and `temperature`, `seed`, `max_tokens` **only when not `None`**.
- Do **not** enable `reasoning` (the example in API.md does). We only store the final answer, and reasoning tokens slow responses down and use up `max_tokens`.
- Return `choices[0].message.content`. If it's missing, `None`, or blank, raise `LLMError("Model returned an empty response")`. Reasoning models sometimes do this when `max_tokens` is too small.
- OpenRouter can return HTTP 200 with an `{"error": {...}}` body. Treat that as a failure.
- Retry on network errors, timeouts, HTTP 429, and HTTP 5xx, with exponential backoff (1s, 2s, 4s, ...). If the response has a `Retry-After` header, wait that long instead. Don't retry other 4xx errors (bad key, unknown model); raise `LLMError` right away with the provider's message.
- Never log or include the API key in error messages.
- Accept an injected `requests.Session` so tests can mock it. Inject the sleep function too (`sleep=time.sleep`) so retry tests don't actually wait.

### 3. `FakeLLMClient`

```python
class FakeLLMClient:
    def __init__(self, responder: Callable[[str, list[dict]], str] | None = None): ...
```

- If `responder` is given, call it with `(model, messages)` and return its string. Tests use this to script exact answers.
- Otherwise return a deterministic default: `f"[fake:{model}] {last_user_message[:80]}"`.
- Record every call in `self.calls: list[dict]` so tests can assert what was sent.
- Ticket 07 extends the default so judge prompts get valid JSON back. Leave a `# TODO(ticket 07)` comment where that goes.

### 4. Factory

```python
def get_llm_client() -> LLMClient:
    """Return the client for the current app.

    1. If current_app.extensions has "llm_client", return it (tests inject clients this way).
    2. If LLM_PROVIDER == "fake", return FakeLLMClient().
    3. If LLM_PROVIDER == "openrouter", require OPENROUTER_API_KEY (raise LLMError with a clear
       message pointing at .env if it's missing) and return an OpenRouterClient.
    """
```

Add a `fake_llm` pytest fixture in `tests/conftest.py`:

```python
@pytest.fixture
def fake_llm(app):
    client = FakeLLMClient()
    app.extensions["llm_client"] = client
    yield client
    app.extensions.pop("llm_client", None)
```

### 5. Model registry API

| Method | Path           | Body                                            | Returns |
|--------|----------------|-------------------------------------------------|---------|
| GET    | `/api/models`  | —                                               | `200` list, ordered by `display_name` |
| POST   | `/api/models`  | `{provider, model_name, display_name?}`         | `201` model; `409 conflict` if `(provider, model_name)` exists |

Shape: `{"id": 1, "provider": "openrouter", "model_name": "nvidia/nemotron-3-ultra-550b-a55b:free", "display_name": "Nemotron 3 Ultra (free)"}`. `display_name` defaults to `model_name`.

### 6. CLI

In `sycometrix/cli.py`, create a `click` group or plain commands and register them in `create_app` with `app.cli.add_command(...)`.

`flask seed-models`: insert a `model` row for `DEFAULT_MODEL` with provider `"openrouter"` if it isn't already there. Print what it did. Running it twice must not fail or create duplicates.

### 7. Manual smoke test

Add a `flask llm-ping` command that sends "Reply with the word pong." to `DEFAULT_MODEL` and prints the reply and latency. This is the quickest way for a teammate to confirm their API key works. Document both commands in the README.

## Tests

`tests/test_llm_client.py` (mock the `requests.Session`; never hit the network):

- A successful request returns `ChatResult` with the content, and the request body contains `model` and `messages`, and omits `temperature` when it's `None`.
- The `Authorization` header is set; the key doesn't appear in any raised error's message.
- 429 then 200 → succeeds after one retry, and the injected sleep was called.
- 500 four times with `max_retries=3` → raises `LLMError`.
- 401 → raises `LLMError` immediately with no retry.
- 200 with an `error` body → `LLMError`.
- 200 with empty content → `LLMError`.
- `FakeLLMClient` with a responder returns the responder's output and records calls.
- `get_llm_client()` returns a fake under `TestingConfig`, and raises a clear error for `openrouter` without a key.

`tests/test_api_llm_models.py`: create, list, duplicate → 409, missing `model_name` → 400.

## Acceptance Criteria

- [ ] `OpenRouterClient` works against the real API (verify once with `flask llm-ping`).
- [ ] Retries and errors behave as described, and tests cover them without network access.
- [ ] `FakeLLMClient` is used automatically in tests.
- [ ] `/api/models` endpoints and `flask seed-models` work.
- [ ] The API key never appears in logs, errors, or API responses.

## Out of Scope

- Calling the client for test cases (ticket 06).
- Other providers' SDKs (Anthropic, OpenAI, ...). If added later, they implement the same `LLMClient` protocol and get a new `LLM_PROVIDER` value; OpenRouter already gives access to many models through one API.
