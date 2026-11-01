"""Exercise request contracts, failures, and retries without network calls."""

import json
import traceback
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from unittest.mock import Mock, call

import pytest
import requests

from sycometrix.services import llm_client as client_module
from sycometrix.services.llm_client import (
    FakeLLMClient,
    LLMError,
    OpenRouterClient,
    get_llm_client,
)

KEY = "test-key-not-a-real-credential"
MODEL = "example/model"
MESSAGES = [{"role": "user", "content": "Hello"}]


@pytest.fixture(autouse=True)
def no_real_http(monkeypatch):
    def blocked(*args, **kwargs):
        pytest.fail("Tests must inject a mocked HTTP session.")

    monkeypatch.setattr(requests.Session, "request", blocked)


def response(status=200, data=None, headers=None):
    result = requests.Response()
    result.status_code = status
    result.headers.update(headers or {})
    result._content = json.dumps(data).encode()
    return result


def success(text="Hello back", model=MODEL):
    return response(data={"model": model, "choices": [{"message": {"content": text}}]})


def setup_client(*outcomes, max_retries=3):
    session = Mock(spec=requests.Session)
    session.post.side_effect = outcomes
    sleep = Mock()
    client = OpenRouterClient(
        KEY,
        "https://openrouter.ai/api/v1/",
        session=session,
        sleep=sleep,
        timeout=15,
        max_retries=max_retries,
    )
    return client, session, sleep


def test_success_headers_body_and_latency(monkeypatch):
    payload = success(text=" Answer kept verbatim. ", model="provider/answered-model")
    client, session, sleep = setup_client(payload)
    monkeypatch.setattr(client_module.time, "perf_counter", Mock(side_effect=[10.0, 10.25]))

    result = client.chat(MODEL, MESSAGES)

    assert result.text == " Answer kept verbatim. "
    assert result.model == "provider/answered-model"
    assert result.latency_ms == 250
    assert result.raw == payload.json()
    session.post.assert_called_once_with(
        "https://openrouter.ai/api/v1/chat/completions",
        json={"model": MODEL, "messages": MESSAGES},
        headers={
            "Authorization": f"Bearer {KEY}",
            "Content-Type": "application/json",
            "X-Title": "SycoMetrix",
        },
        timeout=15,
        allow_redirects=False,
    )
    sleep.assert_not_called()


def test_optional_parameters_keep_zero_and_no_reasoning():
    client, session, _ = setup_client(success(model=None))
    result = client.chat(MODEL, MESSAGES, temperature=0.0, seed=0, max_tokens=64)
    assert session.post.call_args.kwargs["json"] == {
        "model": MODEL,
        "messages": MESSAGES,
        "temperature": 0.0,
        "seed": 0,
        "max_tokens": 64,
    }
    assert result.model == MODEL


@pytest.mark.parametrize("header, delay", [(None, 1), ("7", 7), ("0", 0), ("bad", 1)])
def test_rate_limit_then_success_honors_retry_after(header, delay):
    headers = {} if header is None else {"Retry-After": header}
    client, session, sleep = setup_client(response(429, headers=headers), success())
    assert client.chat(MODEL, MESSAGES).text == "Hello back"
    assert session.post.call_count == 2
    sleep.assert_called_once_with(delay)


def test_retry_after_http_date():
    future = datetime.now(UTC) + timedelta(seconds=30)
    client, _, sleep = setup_client(
        response(503, headers={"Retry-After": format_datetime(future, usegmt=True)}), success()
    )
    client.chat(MODEL, MESSAGES)
    assert 28 <= sleep.call_args.args[0] <= 30


def test_server_errors_stop_after_initial_attempt_and_three_retries():
    client, session, sleep = setup_client(
        *(response(500, {"error": {"message": "Provider unavailable"}}) for _ in range(4))
    )
    with pytest.raises(LLMError, match="Provider unavailable"):
        client.chat(MODEL, MESSAGES)
    assert session.post.call_count == 4
    assert sleep.call_args_list == [call(1), call(2), call(4)]


@pytest.mark.parametrize("error", [requests.Timeout, requests.ConnectionError])
def test_network_failure_can_retry_and_recover(error):
    client, session, sleep = setup_client(error("Temporary failure"), success())
    assert client.chat(MODEL, MESSAGES).text == "Hello back"
    assert session.post.call_count == 2
    sleep.assert_called_once_with(1)


@pytest.mark.parametrize("status", [400, 401, 403, 404, 422])
def test_other_client_errors_are_not_retried_and_redact_key(status, caplog):
    client, session, sleep = setup_client(
        response(status, {"error": {"message": f"Request rejected: Bearer {KEY}"}})
    )
    with pytest.raises(LLMError) as raised:
        client.chat(MODEL, MESSAGES)
    assert "Request rejected" in str(raised.value)
    assert "[redacted]" in str(raised.value)
    assert KEY not in str(raised.value) + caplog.text
    session.post.assert_called_once()
    sleep.assert_not_called()


def test_network_exception_does_not_leak_key_in_traceback(caplog):
    client, session, sleep = setup_client(requests.Timeout(f"Bearer {KEY}"), max_retries=0)
    with pytest.raises(LLMError, match="network error or timeout") as raised:
        client.chat(MODEL, MESSAGES)
    formatted = "".join(traceback.format_exception(raised.value))
    assert KEY not in formatted + caplog.text
    session.post.assert_called_once()
    sleep.assert_not_called()


def test_http_200_error_body_is_failure():
    client, session, sleep = setup_client(
        response(200, {"error": {"message": f"Generation failed: {KEY}"}})
    )
    with pytest.raises(LLMError, match="Generation failed") as raised:
        client.chat(MODEL, MESSAGES)
    assert KEY not in str(raised.value)
    session.post.assert_called_once()
    sleep.assert_not_called()


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"choices": []},
        {"choices": [{"message": {}}]},
        {"choices": [{"message": {"content": None}}]},
        {"choices": [{"message": {"content": " \n\t"}}]},
    ],
)
def test_missing_or_blank_content_is_rejected(data):
    client, _, _ = setup_client(response(data=data))
    with pytest.raises(LLMError, match="^Model returned an empty response$"):
        client.chat(MODEL, MESSAGES)


@pytest.mark.parametrize("status", [200, 401, 502])
def test_non_json_response_has_safe_error(status):
    bad_response = response(status)
    bad_response._content = f"<html>{KEY}</html>".encode()
    client, _, _ = setup_client(bad_response, max_retries=0)
    with pytest.raises(LLMError) as raised:
        client.chat(MODEL, MESSAGES)
    assert KEY not in str(raised.value)
    assert (
        "invalid JSON" in str(raised.value)
        if status == 200
        else f"HTTP {status}" in str(raised.value)
    )


def test_fake_responder_and_call_history_are_independent_of_later_edits():
    responder = Mock(return_value="Scripted answer")
    client = FakeLLMClient(responder)
    messages = [{"role": "user", "content": "Original question"}]
    result = client.chat(MODEL, messages, temperature=0.5, seed=2, max_tokens=50)
    responder.assert_called_once_with(MODEL, messages)
    messages[0]["content"] = "Edited later"
    assert result.text == "Scripted answer"
    assert result.model == MODEL
    assert result.latency_ms == 0
    assert client.calls == [
        {
            "model": MODEL,
            "messages": [{"role": "user", "content": "Original question"}],
            "temperature": 0.5,
            "seed": 2,
            "max_tokens": 50,
        }
    ]


def test_fake_default_uses_last_user_message_and_eighty_characters():
    client = FakeLLMClient()
    messages = [
        {"role": "user", "content": "Earlier"},
        {"role": "user", "content": "x" * 100},
        {"role": "assistant", "content": "Do not echo this"},
    ]
    assert client.chat(MODEL, messages).text == f"[fake:{MODEL}] " + "x" * 80
    assert client.chat(MODEL, []).text == f"[fake:{MODEL}] "


def test_factory_uses_fake_under_testing_config(app):
    assert isinstance(get_llm_client(), FakeLLMClient)


def test_injected_client_takes_priority_over_configuration(app, fake_llm):
    app.config.update(LLM_PROVIDER="openrouter", OPENROUTER_API_KEY=None)
    assert get_llm_client() is fake_llm


@pytest.mark.parametrize("key", [None, "", "  "])
def test_factory_requires_openrouter_key(app, key):
    app.config.update(LLM_PROVIDER="openrouter", OPENROUTER_API_KEY=key)
    with pytest.raises(LLMError, match=r"OPENROUTER_API_KEY.*\.env"):
        get_llm_client()


def test_factory_passes_configuration_without_sending_requests(app, monkeypatch):
    constructor = Mock()
    monkeypatch.setattr(client_module, "OpenRouterClient", constructor)
    app.config.update(
        LLM_PROVIDER="openrouter",
        OPENROUTER_API_KEY=KEY,
        OPENROUTER_BASE_URL="https://openrouter.ai/api/v1",
        LLM_TIMEOUT_SECONDS=25,
        LLM_MAX_RETRIES=2,
    )
    assert get_llm_client() is constructor.return_value
    constructor.assert_called_once_with(
        api_key=KEY,
        base_url="https://openrouter.ai/api/v1",
        timeout=25,
        max_retries=2,
    )


def test_factory_rejects_unknown_provider(app):
    app.config["LLM_PROVIDER"] = "unsupported"
    with pytest.raises(LLMError, match="Unsupported LLM_PROVIDER"):
        get_llm_client()
