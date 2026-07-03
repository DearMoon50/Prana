from __future__ import annotations

import uuid

import httpx

from framework.agent.react import build_react_messages, parse_react_response
from framework.ai.base import ChatResponse, Message, ToolCall, ToolSchema, Usage
from framework.errors import ProviderError


class OllamaProvider:
    name = "ollama"
    supports_native_tools = False

    def __init__(self, model: str, base_url: str = "http://127.0.0.1:11434",
                 timeout: float = 60.0):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def chat(self, messages: list[Message], *, tools: list[ToolSchema] | None = None,
                   temperature: float = 0.2) -> ChatResponse:
        if not self.model:
            raise ProviderError("OLLAMA_MODEL is not configured")
        # Ollama has no native function-calling contract we rely on, so when
        # tools are offered we drive tool use with a ReAct text prompt and
        # parse the model's reply ourselves. Re-applied each call so multi-step
        # follow-ups carrying prior tool results get re-framed.
        send = build_react_messages(messages, tools) if tools else messages
        payload = {
            "model": self.model,
            "messages": [{"role": m.role.value, "content": m.content} for m in send],
            "options": {"temperature": temperature},
            "stream": False,
        }
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(f"{self.base_url}/api/chat", json=payload, timeout=self.timeout)
                resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderError(f"Ollama request failed: {exc}") from exc
        data = resp.json()
        msg = data["message"]
        if not tools:
            return ChatResponse(content=msg.get("content"), usage=Usage(), raw=data)

        # Some models (e.g. gpt-oss) emit Ollama's native tool_calls field
        # instead of following the ReAct text instruction; honor both.
        native_calls = msg.get("tool_calls") or []
        if native_calls:
            calls = [
                ToolCall(id=tc.get("id") or str(uuid.uuid4()),
                         name=tc["function"]["name"],
                         arguments=tc["function"].get("arguments") or {})
                for tc in native_calls
            ]
            return ChatResponse(content=None, tool_calls=calls, usage=Usage(), raw=data)

        tool_calls, answer = parse_react_response(msg.get("content") or "")
        return ChatResponse(content=answer, tool_calls=tool_calls, usage=Usage(), raw=data)
