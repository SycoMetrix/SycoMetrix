# Notes for AI agents

- Read docs/implementation_plan/README.md for conventions before changing code.
- Work on one ticket from docs/implementation_plan/ at a time.
- Add or update the ticket's UML design doc in docs/uml/ (see docs/uml/README.md).
- Run `ruff check .` and `pytest` before finishing.
- Never call a real LLM in tests; use FakeLLMClient.
- Never commit .env or API keys.
