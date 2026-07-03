import asyncio

import pytest
from framework.ai.base import ChatResponse, Message, Role
from framework.ai.mock import MockProvider
from framework.ai.fallback import FallbackProvider
from framework.errors import ProviderError


def test_uses_first_working_provider():
    good = MockProvider(responses=[ChatResponse(content="ok")])
    chain = FallbackProvider([good])
    assert asyncio.run(chain.chat([Message(Role.USER, "x")])).content == "ok"


def test_falls_through_to_next_on_error():
    bad = MockProvider(error=ProviderError("down"))
    good = MockProvider(responses=[ChatResponse(content="recovered")])
    chain = FallbackProvider([bad, good])
    assert asyncio.run(chain.chat([Message(Role.USER, "x")])).content == "recovered"


def test_all_fail_raises_provider_error():
    chain = FallbackProvider([MockProvider(error=ProviderError("a")),
                              MockProvider(error=ProviderError("b"))])
    with pytest.raises(ProviderError):
        asyncio.run(chain.chat([Message(Role.USER, "x")]))


def test_supports_native_tools_true_only_when_all_support():
    # Informational property: true only if every provider uses native tools.
    only_react = FallbackProvider([MockProvider(responses=[], supports_native_tools=False)])
    assert only_react.supports_native_tools is False
    mixed = FallbackProvider([
        MockProvider(responses=[], supports_native_tools=True),
        MockProvider(responses=[], supports_native_tools=False),
    ])
    assert mixed.supports_native_tools is False
    all_native = FallbackProvider([
        MockProvider(responses=[], supports_native_tools=True),
        MockProvider(responses=[], supports_native_tools=True),
    ])
    assert all_native.supports_native_tools is True


def test_passes_tools_to_every_provider():
    # tools must reach a downstream provider even if it sits behind a
    # failing native provider — each provider handles tools on its own now.
    bad = MockProvider(error=ProviderError("down"), supports_native_tools=True)
    good = MockProvider(responses=[ChatResponse(content="ok")], supports_native_tools=False)
    chain = FallbackProvider([bad, good])
    schemas = [{"type": "function", "function": {"name": "t", "parameters": {}}}]
    asyncio.run(chain.chat([Message(Role.USER, "x")], tools=schemas))
    assert good.calls[0]["tools"] == schemas
