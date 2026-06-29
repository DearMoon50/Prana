import asyncio
from framework.agent.base import Agent
from framework.agent.result import AgentResult
from framework.ai.base import ChatResponse, ToolCall, Usage, Role, Message
from framework.ai.mock import MockProvider
from framework.errors import ProviderError
from framework.tools.base import Tool, ToolRegistry
from framework.context.user import UserContext


def _registry():
    r = ToolRegistry()
    r.register(Tool("get_risk", "risk", {"type": "object", "properties": {}},
                    fn=lambda *, ctx: {"ccri": 72, "risk_level": "HIGH"}))
    return r


def _run(agent, msg):
    return asyncio.run(agent.run(msg, UserContext(user_id="u1")))


def test_native_tool_call_then_answer():
    provider = MockProvider(responses=[
        ChatResponse(content=None, tool_calls=[ToolCall("1", "get_risk", {})], usage=Usage(5, 5, 0.01)),
        ChatResponse(content="Your risk is HIGH (72).", usage=Usage(8, 4, 0.01)),
    ], supports_native_tools=True)
    res = _run(Agent(provider, _registry()), "why is my risk high?")
    assert res.answer == "Your risk is HIGH (72)."
    assert res.trace[0].tool == "get_risk" and res.trace[0].ok
    assert res.usage.prompt_tokens == 13 and abs(res.usage.cost_usd - 0.02) < 1e-9


def test_direct_answer_no_tool():
    provider = MockProvider(responses=[ChatResponse(content="Hello!", usage=Usage())])
    res = _run(Agent(provider, _registry()), "hi")
    assert res.answer == "Hello!" and res.trace == []


def test_agent_always_passes_tools_to_provider():
    # The Agent no longer branches on supports_native_tools; it always
    # passes the tool schemas and reads ChatResponse.tool_calls uniformly.
    provider = MockProvider(responses=[
        ChatResponse(content=None, tool_calls=[ToolCall("1", "get_risk", {})], usage=Usage()),
        ChatResponse(content="Risk HIGH", usage=Usage()),
    ], supports_native_tools=False)
    res = _run(Agent(provider, _registry()), "risk?")
    assert res.answer == "Risk HIGH"
    assert res.trace[0].tool == "get_risk"
    # tools are always passed now, regardless of supports_native_tools
    assert provider.calls[0]["tools"] is not None


def test_agent_over_mixed_fallback_chain_reaches_react_provider():
    # Regression test for the supports_native_tools bug: a FallbackProvider
    # whose FIRST provider is native-but-failing must still let the Agent
    # drive a downstream ReAct provider correctly. The Agent passes tools to
    # the chain; the chain forwards them to whichever provider answers; the
    # OllamaProvider-style mock returns tool_calls then a grounded answer.
    from framework.ai.fallback import FallbackProvider
    native_down = MockProvider(error=ProviderError("no api key"),
                               supports_native_tools=True)
    react_provider = MockProvider(responses=[
        ChatResponse(content=None, tool_calls=[ToolCall("1", "get_risk", {})], usage=Usage()),
        ChatResponse(content="Your risk is HIGH (72).", usage=Usage()),
    ], supports_native_tools=False)
    chain = FallbackProvider([native_down, react_provider])
    res = _run(Agent(chain, _registry()), "what is my risk now")
    assert res.answer == "Your risk is HIGH (72)."
    assert res.trace[0].tool == "get_risk" and res.trace[0].ok


def test_max_steps_guard():
    # provider always asks for a tool, never answers
    loop = [ChatResponse(content=None, tool_calls=[ToolCall("1", "get_risk", {})], usage=Usage())
            for _ in range(10)]
    provider = MockProvider(responses=loop)
    res = _run(Agent(provider, _registry(), max_steps=3), "loop")
    assert res.steps == 3
    assert res.answer is not None  # graceful fallback string


def test_permission_error_feeds_back_not_crash():
    r = ToolRegistry()
    r.register(Tool("admin_tool", "x", {}, fn=lambda *, ctx: 1, required_permission="admin"))
    provider = MockProvider(responses=[
        ChatResponse(content=None, tool_calls=[ToolCall("1", "admin_tool", {})], usage=Usage()),
        ChatResponse(content="You are not authorized.", usage=Usage()),
    ])
    res = _run(Agent(provider, r), "do admin thing")
    assert res.answer == "You are not authorized."
    assert not res.trace[0].ok
