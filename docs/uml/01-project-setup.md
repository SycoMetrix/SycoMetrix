# 01 — Project Setup: Design

Ticket: [01 — Project setup](../implementation_plan/01-project-setup.md)

This ticket builds the Flask skeleton: the app factory, configuration, database extensions, and the JSON API blueprint with its shared error handling. There are no features yet; every later ticket plugs into the pieces shown here.

## Package Diagram

Which modules exist and how they depend on each other. Dashed boxes are placeholders that later tickets fill in.

```mermaid
flowchart TB
    subgraph sycometrix["sycometrix (package)"]
        init["__init__.py<br/>create_app()"]
        config["config.py<br/>Config classes"]
        ext["extensions.py<br/>db, migrate, Base"]
        models["models.py<br/>(see 02-database-models)"]
        subgraph api["api/"]
            apiinit["__init__.py<br/>api_bp, ApiError, api_error()"]
        end
        services["services/<br/>(tickets 03+)"]
    end

    tests["tests/<br/>conftest.py, test_health.py"]
    dotenv[(".env")]

    init --> config
    init --> ext
    init --> models
    init --> apiinit
    models -.-> ext
    services -.->|raise ApiError| apiinit
    config -->|load_dotenv| dotenv
    tests --> init
    tests --> config
    tests --> ext

    classDef future stroke-dasharray: 5 5
    class services future
```

Source: [`sycometrix/`](../../sycometrix/)

## Class Diagram

```mermaid
classDiagram
    direction LR

    class Config {
        +SECRET_KEY: str
        +SQLALCHEMY_DATABASE_URI: str
        +LLM_PROVIDER: str
        +OPENROUTER_API_KEY: str | None
        +OPENROUTER_BASE_URL: str
        +DEFAULT_MODEL: str
        +JUDGE_MODEL: str
        +DEFAULT_TEMPERATURE: float
        +MAX_RESPONSE_TOKENS: int
        +LLM_TIMEOUT_SECONDS: int
        +LLM_MAX_RETRIES: int
    }
    class DevelopmentConfig {
        +DEBUG = True
    }
    class TestingConfig {
        +TESTING = True
        +SQLALCHEMY_DATABASE_URI = TEST_DATABASE_URL or "sqlite://"
        +LLM_PROVIDER = "fake"
    }
    Config <|-- DevelopmentConfig
    Config <|-- TestingConfig

    class DeclarativeBase {
        <<SQLAlchemy>>
    }
    class Base
    DeclarativeBase <|-- Base

    class SQLAlchemy {
        <<Flask-SQLAlchemy>>
        +session
        +init_app(app)
        +create_all()
        +drop_all()
    }
    class Migrate {
        <<Flask-Migrate>>
        +init_app(app, db)
    }
    SQLAlchemy ..> Base : model_class

    class Exception {
        <<builtin>>
    }
    class ApiError {
        +status: int
        +code: str
        +message: str
    }
    Exception <|-- ApiError

    class Blueprint {
        <<Flask>>
    }
    class api_bp {
        <<instance>>
        +health() GET /health
    }
    Blueprint <|.. api_bp : instance of
    api_bp ..> ApiError : handles

    class sycometrix {
        <<module>>
        +create_app(config_class: type~Config~) Flask
    }
    sycometrix ..> Config : reads
    sycometrix ..> SQLAlchemy : db.init_app
    sycometrix ..> Migrate : migrate.init_app
    sycometrix ..> api_bp : registers at /api
```

Source: [`config.py`](../../sycometrix/config.py), [`extensions.py`](../../sycometrix/extensions.py), [`api/__init__.py`](../../sycometrix/api/__init__.py), [`__init__.py`](../../sycometrix/__init__.py)

## Sequence Diagrams

### App startup

`flask run` finds the factory through `FLASK_APP=sycometrix`. Tests call `create_app(TestingConfig)` directly.

```mermaid
sequenceDiagram
    participant CLI as flask CLI / pytest
    participant Factory as create_app()
    participant Cfg as config.py
    participant Ext as db, migrate
    participant API as api_bp

    CLI->>Cfg: import (runs load_dotenv, reads env vars)
    CLI->>Factory: create_app(config_class)
    Factory->>Factory: app = Flask(__name__)
    Factory->>Cfg: app.config.from_object(config_class)
    Factory->>Ext: db.init_app(app)
    Factory->>Ext: migrate.init_app(app, db)
    Factory->>Factory: import sycometrix.models
    Factory->>API: app.register_blueprint(api_bp, url_prefix="/api")
    Note over API,Factory: Registers /api/health and the<br/>app-wide ApiError and HTTPException handlers
    Factory-->>CLI: app
```

### `GET /api/health`

```mermaid
sequenceDiagram
    actor Client
    participant Flask
    participant Health as api_bp.health()

    Client->>Flask: GET /api/health
    Flask->>Health: route match
    Health-->>Flask: jsonify({"status": "ok"})
    Flask-->>Client: 200 {"status": "ok"}
```

### Error handling

How the three kinds of failure become the shared JSON error shape `{"error": {"code", "message"}}`.

```mermaid
sequenceDiagram
    actor Client
    participant Flask
    participant View as API view / service
    participant H1 as _handle_api_error
    participant H2 as _handle_http_exception

    alt Unknown route or wrong method
        Client->>Flask: GET /api/does-not-exist
        Flask->>Flask: routing raises NotFound (404) or MethodNotAllowed (405)
        Flask->>H2: handle(e)
        H2->>H2: _is_api_request()? yes
        H2-->>Client: 404 {"error": {"code": "not_found", ...}}
    else Service raises ApiError
        Client->>Flask: request
        Flask->>View: call
        View-->>Flask: raise ApiError(409, "conflict", "...")
        Flask->>H1: handle(e)
        H1-->>Client: 409 {"error": {"code": "conflict", ...}}
    else Unhandled exception
        Client->>Flask: request
        Flask->>View: call
        View-->>Flask: raise RuntimeError
        Flask->>Flask: log traceback, wrap in InternalServerError
        Flask->>H2: handle(e)
        H2-->>Client: 500 {"error": {"code": "internal_error", "message": "An unexpected error occurred."}}
    end
```

Status codes map to error codes like this: 400 `validation_error`, 404 `not_found`, 405 `method_not_allowed`, 409 `conflict`, 500 `internal_error`, 502 `llm_error`. Any other HTTP error uses its name in snake case (e.g. 415 `unsupported_media_type`).

## Deployment Diagram

What runs where during local development and in CI.

```mermaid
flowchart LR
    subgraph dev["Developer machine"]
        browser["Browser / curl"]
        flask["flask run<br/>(DevelopmentConfig)"]
        subgraph docker["Docker"]
            pg[("PostgreSQL 16<br/>host port POSTGRES_PORT → 5432")]
        end
        pytest["pytest<br/>(TestingConfig)"]
        sqlite[("SQLite<br/>in-memory")]
    end

    subgraph ci["GitHub Actions"]
        ruff["ruff check ."]
        cipytest["pytest"]
        cisqlite[("SQLite<br/>in-memory")]
    end

    openrouter(["OpenRouter API<br/>(ticket 05)"])

    browser -->|HTTP :5000| flask
    flask -->|DATABASE_URL| pg
    pytest --> sqlite
    cipytest --> cisqlite
    flask -.-> openrouter
```

## Design Notes

- **Error handlers are app-wide, not blueprint-only.** Flask raises 404 and 405 during routing, before it knows a request belongs to `api_bp`, so a blueprint-scoped handler never sees them. The handlers are registered with `app_errorhandler` and check `_is_api_request()` (path starts with `/api`). Non-API paths fall through to Flask's normal HTML error pages, which the frontend pages (ticket 10) can rely on.
- **500 responses never include exception details.** Flask logs the traceback before calling the handler; the response body only says "An unexpected error occurred."
- **Empty env vars count as unset.** `.env.example` lists every variable, some with empty values (e.g. `JUDGE_MODEL=`). `config.py` treats an empty value as missing, so `JUDGE_MODEL` falls back to `DEFAULT_MODEL` instead of becoming `""`.
- **SQLite foreign keys.** A SQLAlchemy `connect` listener runs `PRAGMA foreign_keys=ON` for SQLite only, so `ON DELETE CASCADE` (ticket 02) behaves the same in tests as in PostgreSQL.
- **Configurable PostgreSQL port.** `docker-compose.yml` maps `${POSTGRES_PORT:-5432}`, because a local PostgreSQL already on 5432 silently intercepts connections meant for the container.
- **No packaging.** `pyproject.toml` only configures ruff and pytest. pytest finds the package via `pythonpath = ["."]`, and ruff skips Markdown so it doesn't reformat example code in the docs.
