import asyncio
from datetime import datetime

from framework.context.user import UserContext
from prana.alerts import check_and_alert_user


class FakeMessaging:
    def __init__(self):
        self.sent = []

    async def send(self, *, channel, recipient, body):
        self.sent.append((recipient, body))


class FakeRepo:
    async def upsert(self, user):
        pass


def _run(coro):
    return asyncio.run(coro)


async def _risk_high(user):
    return {"risk_level": "HIGH", "alert_message": "hot"}


def _user(**meta):
    merged = {"verified": True}
    merged.update(meta)
    return UserContext(user_id="+911", phone="+911", metadata=merged)


def test_fires_when_risky_changed_daytime_and_no_recent_alert():
    msg = FakeMessaging()
    user = _user()
    sent = _run(
        check_and_alert_user(user, _risk_high, FakeRepo(), msg, now=datetime(2026, 7, 3, 12, 0))
    )
    assert sent is True
    assert len(msg.sent) == 1
    assert user.metadata["last_alert_level"] == "HIGH"
    assert user.metadata["last_alert_at"] is not None


def test_suppressed_during_quiet_hours():
    msg = FakeMessaging()
    user = _user()
    sent = _run(
        check_and_alert_user(user, _risk_high, FakeRepo(), msg, now=datetime(2026, 7, 3, 23, 0))
    )
    assert sent is False
    assert msg.sent == []


def test_suppressed_when_alerted_within_24h():
    msg = FakeMessaging()
    user = _user(last_alert_level="SAFE", last_alert_at=datetime(2026, 7, 3, 6, 0).isoformat())
    sent = _run(
        check_and_alert_user(user, _risk_high, FakeRepo(), msg, now=datetime(2026, 7, 3, 12, 0))
    )
    assert sent is False
    assert msg.sent == []


def test_suppressed_when_level_unchanged():
    msg = FakeMessaging()
    user = _user(last_alert_level="HIGH", last_alert_at=datetime(2026, 7, 1, 12, 0).isoformat())
    sent = _run(
        check_and_alert_user(user, _risk_high, FakeRepo(), msg, now=datetime(2026, 7, 3, 12, 0))
    )
    assert sent is False
    assert msg.sent == []