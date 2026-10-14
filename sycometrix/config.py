"""App configuration, read from environment variables (and `.env` if present)."""

import os

from dotenv import load_dotenv

load_dotenv()


def _env(name: str, default: str | None = None) -> str | None:
    """Return an env var, treating an empty string the same as unset."""
    return os.getenv(name) or default


class Config:
    SECRET_KEY = _env("SECRET_KEY", "dev-only-change-me")
    SQLALCHEMY_DATABASE_URI = _env(
        "DATABASE_URL",
        "postgresql+psycopg://sycometrix:sycometrix@localhost:5432/sycometrix",
    )

    LLM_PROVIDER = _env("LLM_PROVIDER", "openrouter")
    OPENROUTER_API_KEY = _env("OPENROUTER_API_KEY")
    OPENROUTER_BASE_URL = _env("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    DEFAULT_MODEL = _env("DEFAULT_MODEL", "nvidia/nemotron-3-ultra-550b-a55b:free")
    JUDGE_MODEL = _env("JUDGE_MODEL", DEFAULT_MODEL)
    DEFAULT_TEMPERATURE = float(_env("DEFAULT_TEMPERATURE", "0.0"))
    MAX_RESPONSE_TOKENS = int(_env("MAX_RESPONSE_TOKENS", "1024"))
    LLM_TIMEOUT_SECONDS = int(_env("LLM_TIMEOUT_SECONDS", "120"))
    LLM_MAX_RETRIES = int(_env("LLM_MAX_RETRIES", "3"))


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = _env("TEST_DATABASE_URL", "sqlite://")
    LLM_PROVIDER = "fake"
