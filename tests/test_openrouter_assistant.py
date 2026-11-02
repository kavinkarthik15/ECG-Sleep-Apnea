import asyncio

import httpx
import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.services.assistant import (
    AssistantProviderError,
    OllamaAssistant,
    OpenRouterAssistant,
    get_assistant_provider,
)


def _settings() -> Settings:
    return Settings(
        app_env="test",
        session_cookie_secure=False,
        openrouter_api_key=SecretStr("test-key"),
        openrouter_model="google/gemma-4-31b-it:free",
    )


def _ollama_settings() -> Settings:
    return Settings(
        app_env="test",
        session_cookie_secure=False,
        ollama_base_url="http://ollama.test",
        ollama_model="qwen2.5:3b",
    )


def test_ollama_success_uses_configured_endpoint_model_and_history(monkeypatch):
    captured = {}

    async def fake_post(_client, url, **kwargs):
        captured.update(url=url, kwargs=kwargs)
        return httpx.Response(200, json={"message": {"content": "Local answer"}})

    monkeypatch.setattr("httpx.AsyncClient.post", fake_post)
    reply = asyncio.run(
        OllamaAssistant(_ollama_settings()).answer(
            "Explain this.",
            {"summary": {"valid_windows": 1}},
            [{"role": "user", "content": "Earlier question"}],
        )
    )

    assert reply == "Local answer"
    assert captured["url"] == "http://ollama.test/api/chat"
    assert captured["kwargs"]["json"]["model"] == "qwen2.5:3b"
    assert captured["kwargs"]["json"]["stream"] is False
    assert captured["kwargs"]["json"]["messages"][1]["content"] == "Earlier question"


@pytest.mark.parametrize(
    ("exception", "code"),
    [
        (httpx.ConnectError("offline"), "OLLAMA_UNAVAILABLE"),
        (httpx.ConnectTimeout("connect timeout"), "OLLAMA_TIMEOUT"),
        (httpx.ReadTimeout("read timeout"), "OLLAMA_TIMEOUT"),
    ],
)
def test_ollama_connection_and_timeout_errors_are_safe(monkeypatch, exception, code):
    async def fake_post(*_args, **_kwargs):
        raise exception

    monkeypatch.setattr("httpx.AsyncClient.post", fake_post)
    with pytest.raises(AssistantProviderError) as error:
        asyncio.run(
            OllamaAssistant(_ollama_settings()).answer("Hello")
        )
    assert error.value.code == code


def test_ollama_missing_model_invalid_and_empty_responses(monkeypatch):
    async def missing_model(*_args, **_kwargs):
        return httpx.Response(404)

    monkeypatch.setattr("httpx.AsyncClient.post", missing_model)
    with pytest.raises(AssistantProviderError) as missing:
        asyncio.run(
            OllamaAssistant(_ollama_settings()).answer("Hello")
        )
    assert missing.value.code == "OLLAMA_MODEL_NOT_FOUND"

    async def invalid(*_args, **_kwargs):
        return httpx.Response(200, content=b"not-json")

    monkeypatch.setattr("httpx.AsyncClient.post", invalid)
    with pytest.raises(AssistantProviderError) as invalid_error:
        asyncio.run(
            OllamaAssistant(_ollama_settings()).answer("Hello")
        )
    assert invalid_error.value.code == "OLLAMA_INVALID_RESPONSE"

    async def empty(*_args, **_kwargs):
        return httpx.Response(200, json={"message": {"content": "  "}})

    monkeypatch.setattr("httpx.AsyncClient.post", empty)
    with pytest.raises(AssistantProviderError) as empty_error:
        asyncio.run(
            OllamaAssistant(_ollama_settings()).answer("Hello")
        )
    assert empty_error.value.code == "OLLAMA_EMPTY_RESPONSE"


def test_ollama_requires_no_openrouter_key(monkeypatch):
    async def fake_post(*_args, **_kwargs):
        return httpx.Response(200, json={"message": {"content": "Local answer"}})

    monkeypatch.setattr("httpx.AsyncClient.post", fake_post)
    settings = _ollama_settings().model_copy(update={"openrouter_api_key": None})
    assert settings.openrouter_api_key is None
    assert asyncio.run(
        OllamaAssistant(settings).answer("Hello")
    ) == "Local answer"


def test_provider_selection_defaults_to_ollama_and_openrouter_is_explicit():
    ollama_settings = _ollama_settings().model_copy(update={"openrouter_api_key": None})
    assert isinstance(get_assistant_provider(ollama_settings), OllamaAssistant)

    openrouter_settings = _settings().model_copy(update={"assistant_provider": "openrouter"})
    assert isinstance(get_assistant_provider(openrouter_settings), OpenRouterAssistant)


def test_openrouter_success_bounds_history_and_context(monkeypatch):
    captured = {}

    def fake_post(url, **kwargs):
        captured.update(kwargs)
        return httpx.Response(200, json={"choices": [{"message": {"content": "Safe answer"}}]})

    async def async_fake_post(_client, url, **kwargs):
        return fake_post(url, **kwargs)

    monkeypatch.setattr("httpx.AsyncClient.post", async_fake_post)
    reply = asyncio.run(OpenRouterAssistant(_settings()).answer(
        "Explain the selected value.",
        {"summary": {"valid_windows": 1}, "selected_window": {"features": {"mean_hr": 70}}},
        [{"role": "user", "content": "old"}] * 30,
    ))

    assert reply == "Safe answer"
    assert len(captured["json"]["messages"]) <= 14
    assert captured["json"]["messages"][1]["content"] == "old"
    assert "mean_hr" in captured["json"]["messages"][-1]["content"]
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert "test-key" not in captured["json"]["messages"][-1]["content"]


@pytest.mark.parametrize("status_code", [402, 429])
def test_openrouter_free_quota_errors_fail_closed(monkeypatch, status_code):
    async def fake_post(*_args, **_kwargs):
        return httpx.Response(status_code)

    monkeypatch.setattr("httpx.AsyncClient.post", fake_post)
    with pytest.raises(AssistantProviderError) as error:
        asyncio.run(OpenRouterAssistant(_settings()).answer("Hello"))
    assert error.value.code == "ASSISTANT_FREE_QUOTA_UNAVAILABLE"
    assert error.value.status_code == 503


def test_openrouter_invalid_response_is_rejected(monkeypatch):
    async def fake_post(*_args, **_kwargs):
        return httpx.Response(200, json={"choices": []})

    monkeypatch.setattr("httpx.AsyncClient.post", fake_post)
    with pytest.raises(AssistantProviderError) as error:
        asyncio.run(OpenRouterAssistant(_settings()).answer("Hello"))
    assert error.value.code == "ASSISTANT_INVALID_RESPONSE"


def test_medical_safety_preflight_does_not_call_provider(monkeypatch):
    called = False

    def fake_post(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("medical safety requests must not reach the provider")

    monkeypatch.setattr("httpx.AsyncClient.post", fake_post)
    reply = asyncio.run(OpenRouterAssistant(_settings()).answer("Do I have sleep apnea and what treatment should I take?"))
    assert "cannot diagnose" in reply
    assert "qualified healthcare professional" in reply
    assert not called


@pytest.mark.parametrize(
    ("exception", "code"),
    [
        (httpx.ReadTimeout("timeout"), "ASSISTANT_TIMEOUT"),
        (httpx.ConnectError("network"), "ASSISTANT_NETWORK_ERROR"),
    ],
)
def test_openrouter_provider_failures_are_sanitized(monkeypatch, exception, code):
    def fake_post(*_args, **_kwargs):
        raise exception

    async def async_fake_post(*_args, **_kwargs):
        raise exception

    monkeypatch.setattr("httpx.AsyncClient.post", async_fake_post)
    with pytest.raises(AssistantProviderError, match="temporarily unavailable|too long"):
        try:
            asyncio.run(OpenRouterAssistant(_settings()).answer("Hello"))
        except AssistantProviderError as error:
            assert error.code == code
            raise


def test_openrouter_rejects_missing_key_and_paid_model(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    missing_key = Settings(app_env="test", session_cookie_secure=False)
    with pytest.raises(AssistantProviderError) as missing:
        asyncio.run(OpenRouterAssistant(missing_key).answer("Hello"))
    assert missing.value.code == "ASSISTANT_NOT_CONFIGURED"

    with pytest.raises(ValueError):
        Settings(
            app_env="test",
            session_cookie_secure=False,
            openrouter_model="paid/model",
        )
