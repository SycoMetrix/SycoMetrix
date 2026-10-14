# 01 — Project Setup

**Phase:** Foundation · **Depends on:** — · **Unblocks:** 02, 03 · **Size:** M

## Goal

Create the Flask project skeleton so everyone can clone the repo, start PostgreSQL, run the app, and run tests with one set of instructions. No features yet, just a working "hello world" with the structure every later ticket builds on.

## Background

- [Tech stack](../tech_stack.md): Python, Flask, PostgreSQL, pytest.
- [Shared conventions](README.md#shared-conventions): repository layout and code style.

## Files to Create

| File                              | Purpose                                                    |
|-----------------------------------|------------------------------------------------------------|
| `requirements.txt`                | Runtime dependencies                                       |
| `requirements-dev.txt`            | Test and lint dependencies (includes `-r requirements.txt`) |
| `.env.example`                    | Every environment variable the app reads, with safe defaults |
| `docker-compose.yml`              | Local PostgreSQL 16                                        |
| `sycometrix/__init__.py`          | `create_app()` factory                                     |
| `sycometrix/config.py`            | `Config`, `DevelopmentConfig`, `TestingConfig`             |
| `sycometrix/extensions.py`        | `db` and `migrate` instances                               |
| `sycometrix/api/__init__.py`      | `api_bp` blueprint, `api_error()` helper, JSON error handlers |
| `tests/conftest.py`               | `app`, `client`, and `db_session` fixtures                 |
| `tests/test_health.py`            | Smoke test                                                 |
| `pyproject.toml`                  | ruff and pytest settings only (not packaging)             |
| `.github/workflows/tests.yml`     | Run ruff and pytest on every PR                            |
| `AGENTS.md`                       | Short pointer file for AI agents (see step 9)              |
| `docs/uml/01-project-setup.md`    | UML design doc (see [Design docs](README.md#design-docs))  |

Update `README.md` with setup instructions.

## Implementation Steps

### 1. Dependencies

`requirements.txt`:

```
Flask
Flask-SQLAlchemy
Flask-Migrate
psycopg[binary]
python-dotenv
requests
pandas
numpy
```

`requirements-dev.txt`:

```
-r requirements.txt
pytest
pytest-cov
ruff
```

Install into a fresh virtual environment, confirm everything works, then pin exact versions (`pip freeze`, copy only the top-level packages with `==` versions) so the whole team installs the same thing.

### 2. Configuration (`sycometrix/config.py`)

Load `.env` with `python-dotenv` at import time. Read every setting from the environment with a default:

| Config key                  | Env var                 | Default                                                           |
|-----------------------------|-------------------------|-------------------------------------------------------------------|
| `SECRET_KEY`                | `SECRET_KEY`            | `"dev-only-change-me"`                                            |
| `SQLALCHEMY_DATABASE_URI`   | `DATABASE_URL`          | `"postgresql+psycopg://sycometrix:sycometrix@localhost:5432/sycometrix"` |
| `LLM_PROVIDER`              | `LLM_PROVIDER`          | `"openrouter"` (`"fake"` is the other option)                     |
| `OPENROUTER_API_KEY`        | `OPENROUTER_API_KEY`    | `None`                                                            |
| `OPENROUTER_BASE_URL`       | `OPENROUTER_BASE_URL`   | `"https://openrouter.ai/api/v1"`                                  |
| `DEFAULT_MODEL`             | `DEFAULT_MODEL`         | `"nvidia/nemotron-3-ultra-550b-a55b:free"`                        |
| `JUDGE_MODEL`               | `JUDGE_MODEL`           | same as `DEFAULT_MODEL`                                           |
| `DEFAULT_TEMPERATURE`       | `DEFAULT_TEMPERATURE`   | `0.0` (float)                                                     |
| `MAX_RESPONSE_TOKENS`       | `MAX_RESPONSE_TOKENS`   | `1024` (int)                                                      |
| `LLM_TIMEOUT_SECONDS`       | `LLM_TIMEOUT_SECONDS`   | `120` (int)                                                       |
| `LLM_MAX_RETRIES`           | `LLM_MAX_RETRIES`       | `3` (int)                                                         |

Classes:

- `Config`: the table above.
- `DevelopmentConfig(Config)`: `DEBUG = True`.
- `TestingConfig(Config)`: `TESTING = True`, `SQLALCHEMY_DATABASE_URI = os.getenv("TEST_DATABASE_URL", "sqlite://")`, `LLM_PROVIDER = "fake"`.

Later tickets read these keys from `current_app.config`. Add new keys here, not as scattered `os.getenv` calls.

### 3. Extensions (`sycometrix/extensions.py`)

```python
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)
migrate = Migrate()
```

SQLite ignores foreign keys unless told otherwise, which would break `ON DELETE CASCADE` in tests. Register a listener that turns them on for SQLite connections only:

```python
from sqlalchemy import event
from sqlalchemy.engine import Engine


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
    if dbapi_connection.__class__.__module__.startswith("sqlite3"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
```

### 4. App factory (`sycometrix/__init__.py`)

```python
def create_app(config_class: type[Config] = DevelopmentConfig) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class)
    db.init_app(app)
    migrate.init_app(app, db)

    from sycometrix import models  # noqa: F401  (registers models with SQLAlchemy; created in ticket 02)
    from sycometrix.api import api_bp
    app.register_blueprint(api_bp, url_prefix="/api")
    return app
```

Until ticket 02 exists, guard the `models` import or create an empty `sycometrix/models.py`.

Flask finds the factory through `FLASK_APP=sycometrix` (put this in `.env.example`), so `flask run` and `flask db ...` both work.

### 5. API blueprint and error handling (`sycometrix/api/__init__.py`)

- Create `api_bp = Blueprint("api", __name__)`.
- Add `api_error(status: int, code: str, message: str)`, which returns `(jsonify({"error": {"code": code, "message": message}}), status)`.
- Register handlers so every API error is JSON in the shape from [Shared conventions](README.md#json-api). Use `api_bp.app_errorhandler` (app-wide) and only return JSON when the path starts with `/api`: routing 404s and 405s happen before Flask knows the request belongs to the blueprint, so blueprint-only handlers never see them.
  - `404` → `not_found`
  - `400` → `validation_error`
  - `405` → `method_not_allowed`
  - `500` → `internal_error` (log the exception; don't leak the traceback)
- Add `GET /api/health` returning `{"status": "ok"}`.

Also add a custom exception that services can raise and the blueprint turns into a response:

```python
class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str): ...
```

Register `@api_bp.errorhandler(ApiError)` to return `api_error(e.status, e.code, e.message)`. Later tickets raise `ApiError(404, "not_found", "...")` instead of building responses by hand.

### 6. Local PostgreSQL (`docker-compose.yml`)

```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: sycometrix
      POSTGRES_PASSWORD: sycometrix
      POSTGRES_DB: sycometrix
    ports:
      - "${POSTGRES_PORT:-5432}:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
volumes:
  pgdata:
```

Teammates without Docker can install PostgreSQL locally and set `DATABASE_URL`. If a local PostgreSQL already uses port 5432, set `POSTGRES_PORT` (and the port in `DATABASE_URL`) to a free port.

### 7. Test fixtures (`tests/conftest.py`)

```python
@pytest.fixture
def app():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()
```

`tests/test_health.py` checks that `GET /api/health` returns 200 and `{"status": "ok"}`, and that `GET /api/does-not-exist` returns 404 with `error.code == "not_found"`.

### 8. Tooling

`pyproject.toml`:

```toml
[tool.ruff]
line-length = 100
target-version = "py312"
# Code blocks in docs are illustrative; don't let `ruff format` rewrite them.
extend-exclude = ["*.md"]

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

`.github/workflows/tests.yml`: on `pull_request` and `push` to `main`, set up Python 3.12, `pip install -r requirements-dev.txt`, then run `ruff check .` and `pytest`. Tests use SQLite, so CI doesn't need a database service.

### 9. `AGENTS.md`

A short file at the repo root that tells AI agents where to look:

```markdown
# Notes for AI agents

- Read docs/implementation_plan/README.md for conventions before changing code.
- Work on one ticket from docs/implementation_plan/ at a time.
- Add or update the ticket's UML design doc in docs/uml/ (see docs/uml/README.md).
- Run `ruff check .` and `pytest` before finishing.
- Never call a real LLM in tests; use FakeLLMClient.
- Never commit .env or API keys.
```

### 10. README

Add a **Getting Started** section to `README.md`:

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

## Acceptance Criteria

- [ ] A fresh clone can follow the README to install, start the database, and run `flask run`.
- [ ] `GET /api/health` returns `200 {"status": "ok"}`.
- [ ] Unknown `/api/...` routes return JSON 404 errors in the shared error shape.
- [ ] `pytest` passes without PostgreSQL running.
- [ ] `ruff check .` passes.
- [ ] CI runs ruff and pytest on pull requests.
- [ ] `.env.example` lists every config variable; `.env` stays gitignored (it already is).

## Out of Scope

- Database tables (ticket 02).
- Any HTML pages (ticket 10).
