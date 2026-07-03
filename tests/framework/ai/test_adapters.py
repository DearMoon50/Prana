import asyncio
import json

import httpx
import pytest
import respx
from framework.ai.base import Message, Role
from framework.ai.openrouter import OpenRouterProvider
from framework.ai.ollama import OllamaProvider
from framework.ai.gemini import GeminiProvider
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
    r = asyncio.run(p.chat([Message(Role.USER, "hi")]))
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
    r = asyncio.run(OpenRouterProvider(api_key="k", model="m").chat([Message(Role.USER, "hi")]))
    assert r.tool_calls[0].name == "get_risk" and r.tool_calls[0].arguments == {"x": 1}


@respx.mock
def test_openrouter_http_error_raises_provider_error():
    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=httpx.Response(500, json={"error": "boom"})
    )
    with pytest.raises(ProviderError):
        asyncio.run(OpenRouterProvider(api_key="k", model="m").chat([Message(Role.USER, "hi")]))


def test_openrouter_missing_key_raises():
    with pytest.raises(ProviderError):
        asyncio.run(OpenRouterProvider(api_key="", model="m").chat([Message(Role.USER, "hi")]))


_GET_RISK_SCHEMA = {
    "type": "function",
    "function": {"name": "get_risk", "description": "Get risk",
                 "parameters": {"type": "object", "properties": {}}},
}


@respx.mock
def test_ollama_parses_content():
    respx.post("http://127.0.0.1:11434/api/chat").mock(
        return_value=httpx.Response(200, json={"message": {"content": "local reply"}})
    )
    r = asyncio.run(OllamaProvider(model="llama3").chat([Message(Role.USER, "hi")]))
    assert r.content == "local reply" and r.tool_calls == []


@respx.mock
def test_ollama_react_text_tool_call_populates_tool_calls():
    # With tools passed, OllamaProvider builds the ReAct prompt internally
    # and parses a text-JSON tool call into ChatResponse.tool_calls.
    respx.post("http://127.0.0.1:11434/api/chat").mock(
        return_value=httpx.Response(200, json={"message": {
            "content": '```json\n{"tool": "get_risk", "args": {}}\n```'
        }})
    )
    r = asyncio.run(OllamaProvider(model="phi4-mini").chat(
        [Message(Role.USER, "what is my risk")], tools=[_GET_RISK_SCHEMA]))
    assert r.content is None
    assert r.tool_calls[0].name == "get_risk" and r.tool_calls[0].arguments == {}


@respx.mock
def test_ollama_native_tool_call_populates_tool_calls():
    # Some models (e.g. gpt-oss) use Ollama's native tool_calls field
    # instead of the ReAct text instruction. OllamaProvider must surface
    # these as ChatResponse.tool_calls too.
    respx.post("http://127.0.0.1:11434/api/chat").mock(
        return_value=httpx.Response(200, json={"message": {
            "content": "",
            "tool_calls": [
                {"id": "call_1", "function": {"name": "get_risk", "arguments": {}}}
            ],
        }})
    )
    r = asyncio.run(OllamaProvider(model="gpt-oss:20b-cloud").chat(
        [Message(Role.USER, "hi")], tools=[_GET_RISK_SCHEMA]))
    assert r.tool_calls[0].name == "get_risk" and r.tool_calls[0].arguments == {}


@respx.mock
def test_ollama_react_plain_answer_sets_content():
    respx.post("http://127.0.0.1:11434/api/chat").mock(
        return_value=httpx.Response(200, json={"message": {
            "content": '{"answer": "you are safe"}'
        }})
    )
    r = asyncio.run(OllamaProvider(model="phi4-mini").chat(
        [Message(Role.USER, "am i safe")], tools=[_GET_RISK_SCHEMA]))
    assert r.content == "you are safe" and r.tool_calls == []


@respx.mock
def test_gemini_parses_text_and_function_call():
    respx.post(
        url__startswith="https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    ).mock(
        return_value=httpx.Response(200, json={
            "candidates": [{"content": {"parts": [
                {"text": "hello"},
                {"functionCall": {"name": "get_risk", "args": {"x": 1}}},
            ]}}],
        })
    )
    r = asyncio.run(GeminiProvider(api_key="k", model="gemini-2.0-flash").chat([Message(Role.USER, "hi")]))
    assert r.content == "hello"
    assert r.tool_calls[0].name == "get_risk" and r.tool_calls[0].arguments == {"x": 1}


@respx.mock
def test_gemini_http_error_raises_provider_error():
    respx.post(
        url__startswith="https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    ).mock(return_value=httpx.Response(500, json={"error": "boom"}))
    with pytest.raises(ProviderError):
        asyncio.run(GeminiProvider(api_key="k", model="gemini-2.0-flash").chat([Message(Role.USER, "hi")]))


def test_gemini_missing_key_raises():
    with pytest.raises(ProviderError):
        asyncio.run(GeminiProvider(api_key="", model="gemini-2.0-flash").chat([Message(Role.USER, "hi")]))


@respx.mock
def test_gemini_function_call_only_content_is_none():
    respx.post(
        url__startswith="https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    ).mock(
        return_value=httpx.Response(200, json={
            "candidates": [{"content": {"parts": [
                {"functionCall": {"name": "get_risk", "args": {"x": 1}}},
            ]}}],
        })
    )
    r = asyncio.run(GeminiProvider(api_key="k", model="gemini-2.0-flash").chat([Message(Role.USER, "hi")]))
    assert r.content is None
    assert r.tool_calls[0].name == "get_risk" and r.tool_calls[0].arguments == {"x": 1}
