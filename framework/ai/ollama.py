from __future__ import annotations

import json

import httpx

from framework.ai.base import ChatResponse, Message, ToolSchema, Usage
from framework.errors import ProviderError


class OllamaProvider:
    name = "ollama"
    supports_native_tools = False

    def __init__(self, model: str, base_url: str = "http://127.0.0.1:11434",
                 timeout: float = 60.0):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def chat(self, messages: list[Message], *, tools: list[ToolSchema] | None = None,
             temperature: float = 0.2) -> ChatResponse:
        if not self.model:
            raise ProviderError("OLLAMA_MODEL is not configured")
        payload = {
            "model": self.model,
            "messages": [{"role": m.role.value, "content": m.content} for m in messages],
            "options": {"temperature": temperature},
            "stream": False,
        }
        try:
            resp = httpx.post(f"{self.base_url}/api/chat", json=payload, timeout=self.timeout)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderError(f"Ollama request failed: {exc}") from exc
        data = resp.json()
        msg = data["message"]
        native_calls = msg.get("tool_calls") or []
        if native_calls:
            # Some Ollama models use native tool_calls instead of following
            # the ReAct prompt's text-JSON instruction, leaving content empty.
            # Synthesize the equivalent ReAct-JSON string so the agent's
            # existing parse_react_response() path still picks up the call.
            fn = native_calls[0]["function"]
            content = json.dumps({"tool": fn["name"], "args": fn.get("arguments") or {}})
        else:
            content = msg["content"]
        return ChatResponse(content=content, usage=Usage(), raw=data)
