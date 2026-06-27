import httpx
import pytest
import respx
from framework.ai.base import Message, Role
from framework.ai.openrouter import OpenRouterProvider
from framework.ai.ollama import OllamaProvider
from framework.errors import ProviderError


@respx.mock
def test_openrouter_parses_content_and_usage():
    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={
            "choices": [{"message": {"content": "hello", "tool_calls": None}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 3},
        })
    )
    p = OpenRouterProvider(api_key="k", model="m")
    r = p.chat([Message(Role.USER, "hi")])
    assert r.content == "hello"
    assert r.usage.prompt_tokens == 10 and r.usage.completion_tokens == 3


@respx.mock
def test_openrouter_parses_tool_calls():
    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={
            "choices": [{"message": {"content": None, "tool_calls": [
                {"id": "c1", "function": {"name": "get_risk", "arguments": "{\"x\": 1}"}}
            ]}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        })
    )
    r = OpenRouterProvider(api_key="k", model="m").chat([Message(Role.USER, "hi")])
    assert r.tool_calls[0].name == "get_risk" and r.tool_calls[0].arguments == {"x": 1}


@respx.mock
def test_openrouter_http_error_raises_provider_error():
    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=httpx.Response(500, json={"error": "boom"})
    )
    with pytest.raises(ProviderError):
        OpenRouterProvider(api_key="k", model="m").chat([Message(Role.USER, "hi")])


def test_openrouter_missing_key_raises():
    with pytest.raises(ProviderError):
        OpenRouterProvider(api_key="", model="m").chat([Message(Role.USER, "hi")])


@respx.mock
def test_ollama_parses_content():
    respx.post("http://127.0.0.1:11434/api/chat").mock(
        return_value=httpx.Response(200, json={"message": {"content": "local reply"}})
    )
    r = OllamaProvider(model="llama3").chat([Message(Role.USER, "hi")])
    assert r.content == "local reply" and r.tool_calls == []
