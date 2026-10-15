# SycoMetrix

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

## Documentation

- [Project overview](docs/overview.md)
- [Tech stack](docs/tech_stack.md)
- [Implementation plan](docs/implementation_plan/README.md)
- [UML design docs](docs/uml/README.md)

## License

The SycoMetrix Project uses the MIT license.
