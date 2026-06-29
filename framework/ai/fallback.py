from __future__ import annotations

from framework.ai.base import ChatResponse, LLMProvider, Message, ToolSchema
from framework.errors import ProviderError


class FallbackProvider:
    name = "fallback"

    def __init__(self, providers: list[LLMProvider]):
        if not providers:
            raise ProviderError("FallbackProvider requires at least one provider")
        self.providers = providers

    @property
    def supports_native_tools(self) -> bool:
        # Informational only — the Agent no longer steers on this. True only
        # when every provider in the chain uses native tools.
        return all(p.supports_native_tools for p in self.providers)

    def chat(self, messages: list[Message], *, tools: list[ToolSchema] | None = None,
             temperature: float = 0.2) -> ChatResponse:
        errors = []
        for provider in self.providers:
            try:
                # Each provider adapts `tools` to its own tool-calling style.
                return provider.chat(messages, tools=tools, temperature=temperature)
            except Exception as exc:  # noqa: BLE001 - try next provider
                errors.append(f"{provider.name}: {exc}")
        raise ProviderError("All providers failed: " + "; ".join(errors))
