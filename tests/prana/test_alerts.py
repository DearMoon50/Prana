import asyncio

from framework.context.user import UserContext
from framework.messaging.mock import MockChannel
from framework.messaging.registry import MessagingRegistry
from framework.persistence.memory import InMemoryUserRepository
from prana.alerts import check_and_alert_user, RISKY_LEVELS


def _setup():
    repo = InMemoryUserRepository()
    msg = MessagingRegistry()
    ch = MockChannel()
    ch.name = "whatsapp"
    msg.add(ch)
    return repo, msg, ch


def _user(level_in_meta=None):
    meta = {"lat": 13.08, "lon": 80.27, "location_name": "Test", "verified": True}
    if level_in_meta is not None:
        meta["last_alert_level"] = level_in_meta
    return UserContext(user_id="+919900", phone="+919900", metadata=meta)


def _risk(level, ccri=70):
    async def _fn(user):
        return {"risk_level": level, "ccri": ccri, "alert_message": f"{level} alert text"}
    return _fn


def test_alerts_when_risky_and_no_prior_alert():
    repo, msg, ch = _setup()
    user = _user()
    asyncio.run(repo.upsert(user))
    from datetime import datetime
    sent = asyncio.run(check_and_alert_user(user, _risk("HIGH"), repo, msg,
                                            now=datetime(2026, 7, 3, 12, 0)))
    assert sent is True
    assert ch.sent and "HIGH alert text" in ch.sent[-1].body
    assert ch.sent[-1].recipient == "+919900"
    # state recorded so we don't re-alert next cycle
    stored = asyncio.run(repo.get_by_phone("+919900"))
    assert stored.metadata["last_alert_level"] == "HIGH"


def test_no_alert_when_level_unchanged_risky():
    repo, msg, ch = _setup()
    user = _user(level_in_meta="HIGH")
    asyncio.run(repo.upsert(user))
    from datetime import datetime
    sent = asyncio.run(check_and_alert_user(user, _risk("HIGH"), repo, msg,
                                            now=datetime(2026, 7, 3, 12, 0)))
    assert sent is False
    assert ch.sent == []


def test_no_alert_when_safe():
    repo, msg, ch = _setup()
    user = _user()
    asyncio.run(repo.upsert(user))
    from datetime import datetime
    sent = asyncio.run(check_and_alert_user(user, _risk("ELEVATED"), repo, msg,
                                            now=datetime(2026, 7, 3, 12, 0)))
    assert sent is False
    assert ch.sent == []


def test_re_alerts_after_dropping_to_safe_then_rising():
    repo, msg, ch = _setup()
    user = _user(level_in_meta="HIGH")
    asyncio.run(repo.upsert(user))
    from datetime import datetime
    now = datetime(2026, 7, 3, 12, 0)
    # drops to safe -> clears the stored alert level, no message
    asyncio.run(check_and_alert_user(user, _risk("SAFE"), repo, msg, now=now))
    stored = asyncio.run(repo.get_by_phone("+919900"))
    assert stored.metadata.get("last_alert_level") in (None, "SAFE")
    assert ch.sent == []
    # rises back to HIGH -> alerts again
    sent = asyncio.run(check_and_alert_user(stored, _risk("HIGH"), repo, msg, now=now))
    assert sent is True
    assert "HIGH alert text" in ch.sent[-1].body


def test_escalation_to_higher_risky_level_re_alerts():
    repo, msg, ch = _setup()
    user = _user(level_in_meta="HIGH")
    asyncio.run(repo.upsert(user))
    from datetime import datetime
    sent = asyncio.run(check_and_alert_user(user, _risk("CRITICAL"), repo, msg,
                                            now=datetime(2026, 7, 3, 12, 0)))
    assert sent is True
    assert "CRITICAL alert text" in ch.sent[-1].body


def test_risky_levels_contains_expected():
    assert "HIGH" in RISKY_LEVELS
    assert "CRITICAL" in RISKY_LEVELS
    assert "COMPOUND EMERGENCY" in RISKY_LEVELS
    assert "SAFE" not in RISKY_LEVELS and "ELEVATED" not in RISKY_LEVELS
