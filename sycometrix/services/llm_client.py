"""Real and simulated chat clients with a shared result format."""

import math
import time
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Protocol, cast

import requests
from flask import current_app


@dataclass
class ChatResult:
    text: str
    model: str
    latency_ms: int
    raw: dict


class LLMError(Exception):
    """A chat request failed after any appropriate retries."""


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


def _retry_delay(header: str | None, attempt: int) -> float:
    """Accept Retry-After seconds or an HTTP date; otherwise use backoff."""
    if header:
        try:
            seconds = float(header)
            if math.isfinite(seconds) and seconds >= 0:
                return seconds
        except ValueError:
            try:
                retry_at = parsedate_to_datetime(header)
                if retry_at.tzinfo is None:
                    retry_at = retry_at.replace(tzinfo=UTC)
                return max(0.0, (retry_at - datetime.now(UTC)).total_seconds())
            except (TypeError, ValueError, OverflowError):
                pass
    return float(2**attempt)


class OpenRouterClient:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        timeout: int = 120,
        max_retries: int = 3,
        session: requests.Session | None = None,
        *,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not api_key or not api_key.strip():
            raise LLMError("OPENROUTER_API_KEY is missing. Set it in your local .env file.")
        if timeout <= 0 or max_retries < 0:
            raise ValueError("timeout must be positive and max_retries must be nonnegative.")
        self._api_key = api_key.strip()
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._timeout = timeout
        self._max_retries = max_retries
        self._session = session if session is not None else requests.Session()
        self._sleep = sleep

    def _error_message(self, data: object, status: int) -> str:
        message = f"OpenRouter request failed (HTTP {status})."
        if isinstance(data, dict):
            error = data.get("error")
            if isinstance(error, dict):
                error = error.get("message")
            if isinstance(error, str) and error.strip():
                message = error.strip()
        return message.replace(self._api_key, "[redacted]")

    def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
        seed: int | None = None,
        max_tokens: int | None = None,
    ) -> ChatResult:
        body = {"model": model, "messages": messages}
        for name, value in (
            ("temperature", temperature),
            ("seed", seed),
            ("max_tokens", max_tokens),
        ):
            if value is not None:
                body[name] = value
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "X-Title": "SycoMetrix",
        }
        started = time.perf_counter()

        for attempt in range(self._max_retries + 1):
            try:
                response = self._session.post(
                    self._url,
                    json=body,
                    headers=headers,
                    timeout=self._timeout,
                    allow_redirects=False,
                )
            except requests.RequestException:
                # Request exceptions can contain headers or URLs; do not expose them.
                if attempt == self._max_retries:
                    raise LLMError(
                        "OpenRouter request failed due to a network error or timeout."
                    ) from None
                self._sleep(float(2**attempt))
                continue

            status = response.status_code
            if (status == 429 or 500 <= status < 600) and attempt < self._max_retries:
                self._sleep(_retry_delay(response.headers.get("Retry-After"), attempt))
                continue

            try:
                data = response.json()
            except ValueError:
                if 200 <= status < 300:
                    raise LLMError("OpenRouter returned invalid JSON.") from None
                data = None

            if not 200 <= status < 300 or (isinstance(data, dict) and "error" in data):
                raise LLMError(self._error_message(data, status))
            if not isinstance(data, dict):
                raise LLMError("OpenRouter returned an invalid response format.")
            try:
                content = data["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError):
                content = None
            if not isinstance(content, str) or not content.strip():
                raise LLMError("Model returned an empty response")

            answered_model = data.get("model")
            if not isinstance(answered_model, str) or not answered_model.strip():
                answered_model = model
            return ChatResult(
                text=content,
                model=answered_model,
                latency_ms=int((time.perf_counter() - started) * 1000),
                raw=data,
            )

        raise LLMError("OpenRouter request failed.")


class FakeLLMClient:
    def __init__(self, responder: Callable[[str, list[dict[str, str]]], str] | None = None) -> None:
        self._responder = responder
        self.calls: list[dict] = []

    def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
        seed: int | None = None,
        max_tokens: int | None = None,
    ) -> ChatResult:
        self.calls.append(
            {
                "model": model,
                "messages": deepcopy(messages),
                "temperature": temperature,
                "seed": seed,
                "max_tokens": max_tokens,
            }
        )
        if self._responder is not None:
            text = self._responder(model, messages)
        else:
            from sycometrix.services.stance import JUDGE_SYSTEM_PROMPT

            if (
                messages
                and messages[0].get("role") == "system"
                and messages[0].get("content") == JUDGE_SYSTEM_PROMPT
            ):
                text = '{"stance": "agrees", "rationale": "Fake judge."}'
            else:
                last_user_message = next(
                    (
                        message["content"]
                        for message in reversed(messages)
                        if message["role"] == "user"
                    ),
                    "",
                )
                text = f"[fake:{model}] {last_user_message[:80]}"
        return ChatResult(text=text, model=model, latency_ms=0, raw={"fake": True})


def get_llm_client() -> LLMClient:
    """Use an injected client first, otherwise select the configured provider."""
    if "llm_client" in current_app.extensions:
        return cast(LLMClient, current_app.extensions["llm_client"])
    provider = current_app.config["LLM_PROVIDER"]
    if provider == "fake":
        return FakeLLMClient()
    if provider == "openrouter":
        return OpenRouterClient(
            api_key=current_app.config.get("OPENROUTER_API_KEY") or "",
            base_url=current_app.config["OPENROUTER_BASE_URL"],
            timeout=current_app.config["LLM_TIMEOUT_SECONDS"],
            max_retries=current_app.config["LLM_MAX_RETRIES"],
        )
    raise LLMError("Unsupported LLM_PROVIDER. Choose 'fake' or 'openrouter'.")
