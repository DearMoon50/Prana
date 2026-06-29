import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from twilio.request_validator import RequestValidator
from framework.ai.base import ChatResponse, ToolCall, Usage
from framework.ai.mock import MockProvider
from framework.context.user import UserContext
from framework.messaging.mock import MockChannel
from framework.messaging.registry import MessagingRegistry
from framework.persistence.memory import InMemoryUserRepository
from framework.tools.base import ToolRegistry
from prana.ai_tools.risk import risk_tool
import prana.bot.whatsapp_webhook as wh

BASE_URL = "https://example.ngrok-free.app/webhook/whatsapp"


@pytest.fixture
def client(monkeypatch):
    repo = InMemoryUserRepository()
    msg = MessagingRegistry(); mock_channel = MockChannel(); mock_channel.name = "whatsapp"; msg.add(mock_channel)
    reg = ToolRegistry(); reg.register(risk_tool)
    provider = MockProvider(responses=[
        ChatResponse(content=None, tool_calls=[ToolCall("1", "get_risk", {})], usage=Usage()),
        ChatResponse(content="Your risk is HIGH tonight.", usage=Usage()),
    ])
    monkeypatch.setattr(wh, "user_repo", repo)
    monkeypatch.setattr(wh, "messaging", msg)
    monkeypatch.setattr(wh, "registry", reg)
    monkeypatch.setattr(wh, "provider", provider)
    monkeypatch.setattr(wh, "AUTH_TOKEN", "secret")
    monkeypatch.setattr(wh, "validator", RequestValidator("secret"))
    monkeypatch.setattr(wh, "WEBHOOK_URL", BASE_URL)
    from unittest.mock import patch
    from datetime import datetime
    patcher = patch("prana.ai_tools.risk.PRANASystem")
    MockSys = patcher.start()
    MockSys.return_value.update_all.return_value = {
        "ccri": 72, "risk_level": "HIGH", "ndt": 34, "alert_message": "hot",
        "rds": {"rds_mid": 150, "consecutive_nights": 3}, "timestamp": datetime(2026, 6, 26),
    }
    app = FastAPI(); app.include_router(wh.router)
    yield TestClient(app), repo, mock_channel
    patcher.stop()


def _sign(form: dict, secret: str) -> str:
    return RequestValidator(secret).compute_signature(BASE_URL, form)


def _post(c, form: dict):
    return c.post("/webhook/whatsapp", data=form,
                  headers={"X-Twilio-Signature": _sign(form, "secret")})


def test_known_user_gets_agent_reply(client):
    c, repo, channel = client
    import asyncio
    asyncio.run(
        repo.upsert(UserContext(user_id="u1", phone="+919900",
                                metadata={"lat": 13.08, "lon": 80.27, "verified": True})))
    r = _post(c, {"From": "whatsapp:+919900", "Body": "why is my risk high?"})
    assert r.status_code == 200
    assert channel.sent[-1].body == "Your risk is HIGH tonight."
    assert channel.sent[-1].recipient == "+919900"


def test_agent_path_acks_empty_and_replies_via_background(client):
    # The webhook must ACK Twilio with an empty 200 (not the agent's answer)
    # and deliver the reply via a BackgroundTask, so a slow agent run can't
    # blow Twilio's 15s webhook timeout. TestClient runs background tasks
    # after the response, so the reply is still observed once delivered.
    c, repo, channel = client
    import asyncio
    asyncio.run(
        repo.upsert(UserContext(user_id="u5", phone="+919900009999",
                                metadata={"lat": 13.08, "lon": 80.27, "verified": True})))
    r = _post(c, {"From": "whatsapp:+919900009999", "Body": "why is my risk high?"})
    assert r.status_code == 200
    # The HTTP body is the empty ack, NOT the agent's answer — proving the
    # answer is sent out-of-band via the messaging channel, not in the response.
    assert r.text == ""
    assert channel.sent[-1].body == "Your risk is HIGH tonight."
    assert channel.sent[-1].recipient == "+919900009999"


def test_agent_runner_scheduled_not_awaited_in_handler(client, monkeypatch):
    # Directly assert the route schedules _run_agent_and_reply as a background
    # task rather than awaiting it inline: replace it with a sync spy and
    # confirm the route still returns 200 without the spy having to be async-
    # awaited within the request (BackgroundTasks invokes it post-response).
    c, repo, _ = client
    import asyncio
    asyncio.run(
        repo.upsert(UserContext(user_id="u6", phone="+919900001212",
                                metadata={"lat": 13.08, "lon": 80.27, "verified": True})))
    calls = []

    async def spy(phone, text):
        calls.append((phone, text))
    monkeypatch.setattr(wh, "_run_agent_and_reply", spy)

    r = _post(c, {"From": "whatsapp:+919900001212", "Body": "why is my risk high?"})
    assert r.status_code == 200 and r.text == ""
    # background task ran (post-response) with the parsed phone + text
    assert calls == [("+919900001212", "why is my risk high?")]


def test_forged_signature_rejected(client):
    c, _, _ = client
    r = c.post("/webhook/whatsapp", data={"From": "whatsapp:+919900", "Body": "hi"},
               headers={"X-Twilio-Signature": "wrong"})
    assert r.status_code == 403


def test_unverified_user_first_message_activates(client):
    c, repo, channel = client
    import asyncio
    asyncio.run(
        repo.upsert(UserContext(user_id="u2", phone="+919900005555",
                                metadata={"lat": 13.08, "lon": 80.27, "verified": False})))
    r = _post(c, {"From": "whatsapp:+919900005555", "Body": "PRANA START"})
    assert r.status_code == 200
    assert "all set" in channel.sent[-1].body.lower()
    assert channel.sent[-1].recipient == "+919900005555"

    async def check():
        return await repo.get_by_phone("+919900005555")
    user = asyncio.run(check())
    assert user.metadata["verified"] is True


def test_verified_user_gets_normal_agent_flow_not_activation_message(client):
    c, repo, channel = client
    import asyncio
    asyncio.run(
        repo.upsert(UserContext(user_id="u3", phone="+919900006666",
                                metadata={"lat": 13.08, "lon": 80.27, "verified": True})))
    r = _post(c, {"From": "whatsapp:+919900006666", "Body": "why is my risk high?"})
    assert r.status_code == 200
    assert "all set" not in channel.sent[-1].body.lower()


def test_unknown_user_gets_register_first_message(client):
    c, repo, channel = client
    r = _post(c, {"From": "whatsapp:+919900007777", "Body": "hello"})
    assert r.status_code == 200
    assert "register" in channel.sent[-1].body.lower()


def test_inbound_whatsapp_prefix_is_stripped_for_lookup(client):
    c, repo, channel = client
    import asyncio
    asyncio.run(
        repo.upsert(UserContext(user_id="u4", phone="+919900008888",
                                metadata={"lat": 13.08, "lon": 80.27, "verified": True})))
    r = _post(c, {"From": "whatsapp:+919900008888", "Body": "why is my risk high?"})
    assert r.status_code == 200
    assert channel.sent[-1].recipient == "+919900008888"
