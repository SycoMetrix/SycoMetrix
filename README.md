# SycoMetrix

![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/SycoMetrix/SycoMetrix/tests.yml) ![GitHub code size in bytes](https://img.shields.io/github/languages/code-size/SycoMetrix/SycoMetrix)

An AI Sycophancy Detection Tool.

## Getting Started

Requires Python 3.12 and Docker (or a local PostgreSQL 16).

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env          # then add your OPENROUTER_API_KEY
docker compose up -d db
flask db upgrade              # after ticket 02
flask run
pytest
```

The app runs at <http://127.0.0.1:5000>. Check it with `curl http://127.0.0.1:5000/api/health`.

Tests use an in-memory SQLite database, so `pytest` works without PostgreSQL running.

Before opening a pull request, run:

```bash
ruff check .
ruff format .
pytest
```

### Troubleshooting

- **`role "sycometrix" does not exist`**: another PostgreSQL is already using port 5432, so the app is talking to it instead of the Docker container. In `.env`, set `POSTGRES_PORT=5433` and change the port in `DATABASE_URL` to `5433`, then run `docker compose up -d db` again.
- **No Docker**: install PostgreSQL locally, create a `sycometrix` user and database, and point `DATABASE_URL` at it.

> [!TIP]
> Ensure that you are using an OpenRouter API Key with a valid model. Models are subject to be removed from OpenRouter or change prices.

## LLM client and model registry

Set `LLM_PROVIDER=fake` in your local `.env` while developing. The fake client
returns deterministic text and makes no network requests. `TestingConfig` also
selects it automatically; tests can inject a scripted client with the `fake_llm`
fixture.

The model registry uses the database configured by `DATABASE_URL`. After starting
the database and running its existing migrations, register the default model:

```bash
python -m flask --app sycometrix db upgrade
python -m flask --app sycometrix seed-models
python -m flask --app sycometrix seed-models
```

The second run reports that the row already exists. The command always registers
`DEFAULT_MODEL` with provider `openrouter`, even when development uses the fake
client. It does not contact OpenRouter or check whether that model is available.

`GET /api/models` returns model records ordered by `display_name`.
`POST /api/models` accepts `provider`, `model_name`, and an optional `display_name`
(defaults to `model_name`). Successful creation returns `201`; an existing
provider/model pair returns `409`. Invalid input returns `400` using the shared
JSON error shape. Registry responses contain only `id`, `provider`, `model_name`,
and `display_name`.

For a single connectivity check, run:

```bash
python -m flask --app sycometrix llm-ping
```

With `LLM_PROVIDER=fake`, the reply starts with `[fake:...]`; this checks command
wiring only. To verify the real API, set `LLM_PROVIDER=openrouter`, add your own
`OPENROUTER_API_KEY` to `.env`, and set `DEFAULT_MODEL` to a currently available
OpenRouter model ID. Run `llm-ping` again; it prints the answer and latency. This
command sends one logical chat request, which can require retries and consume
API quota. It does not need a model registry row or a database connection.

Keep `.env` out of commits. The client sends the key only in the authorization
header, omits optional sampling parameters when they are `None`, and does not
enable reasoning. It retries network failures, `429`, and `5xx`, using
`Retry-After` when supplied or delays of 1, 2, 4, ... seconds. `LLM_MAX_RETRIES=3`
allows four total attempts. Other `4xx` errors fail immediately. An error object
in an HTTP `200` response and a missing or blank answer also raise `LLMError`.

Tests mock HTTP and sleep; never use a real API key to run them:

```bash
python -m pytest tests/test_llm_client.py tests/test_api_llm_models.py -q
python -m ruff check .
python -m pytest -q
```

See [Ticket 05 design](docs/uml/05-llm-client.md) for the interface and retry flow.
Check [OpenRouter limits](https://openrouter.ai/docs/api_reference/limits) before
running real experiments.

## Documentation

- [Project overview](docs/overview.md)
- [Tech stack](docs/tech_stack.md)
- [Implementation plan](docs/implementation_plan/README.md)
- [UML design docs](docs/uml/README.md)
- [OpenRouter API](docs/API.md)

## License

The SycoMetrix Project uses the MIT license.
