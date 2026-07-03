"""Twilio WhatsApp webhook: message -> agent -> reply."""
from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Request, Response
from twilio.request_validator import RequestValidator

from framework import agent as make_agent
from prana.bot.bootstrap import (
    build_messaging, build_provider_chain, build_registry, build_repo,
    build_commands, settings,
)

router = APIRouter()
logger = logging.getLogger(__name__)

# Module-level singletons (tests monkeypatch these)
registry = build_registry()
messaging = build_messaging()
user_repo = build_repo()
provider = build_provider_chain()
AUTH_TOKEN = settings.whatsapp_auth_token
WEBHOOK_URL = f"{settings.whatsapp_webhook_base_url}/webhook/whatsapp"
validator = RequestValidator(AUTH_TOKEN)
commands = build_commands()

_ONBOARD = "Welcome to PRANA. Please register in the app first."
_ACTIVATED = "You're all set! PRANA will alert you when conditions turn risky."


def _valid_signature(form: dict, header: str | None) -> bool:
    if not header:
        logger.warning("WhatsApp webhook rejected: missing X-Twilio-Signature header")
        return False
    if not validator.validate(WEBHOOK_URL, form, header):
        logger.warning(
            "WhatsApp webhook signature validation failed (check WHATSAPP_WEBHOOK_BASE_URL=%r "
            "matches the public URL Twilio is actually calling)", WEBHOOK_URL,
        )
        return False
    return True


def _parse(form: dict):
    phone = form.get("From")
    body = form.get("Body")
    if not phone or body is None:
        return None
    return phone.removeprefix("whatsapp:"), body


async def _run_agent_and_reply(phone: str, text: str) -> None:
    """Run the agent and send its reply. Scheduled as a background task so the
    webhook can ACK Twilio within its 15s timeout regardless of how long the
    agent (live data fetch + LLM calls) takes."""
    user = await user_repo.get_by_phone(phone)
    if user is None:  # deleted between ACK and task run; nothing to reply to
        return
    # 1. Try shortcut commands first (modular, fast, deterministic)
    command_reply = await commands.dispatch(text, user)
    if command_reply:
        await messaging.send(channel="whatsapp", recipient=phone, body=command_reply)
        return

    # 2. Fall back to LLM agent (flexible natural language)
    ag = make_agent(provider, registry, max_steps=settings.agent_max_steps,
                    temperature=settings.agent_temperature)
    try:
        result = await ag.run(text, user)
        body = result.answer or "Sorry, please try again."
    except Exception:  # noqa: BLE001 - never leave the user without a reply
        logger.exception("Agent run failed for %s", phone)
        body = "Sorry, something went wrong. Please try again shortly."
    await messaging.send(channel="whatsapp", recipient=phone, body=body)


@router.post("/webhook/whatsapp")
async def receive(request: Request, background: BackgroundTasks) -> Response:
    form = dict(await request.form())
    if not _valid_signature(form, request.headers.get("X-Twilio-Signature")):
        return Response(status_code=403)

    parsed = _parse(form)
    if not parsed:
        return Response(status_code=200)
    phone, text = parsed

    user = await user_repo.get_by_phone(phone)
    if user is None:
        await messaging.send(channel="whatsapp", recipient=phone, body=_ONBOARD)
        return Response(status_code=200)

    if not user.metadata.get("verified", True):
        user.metadata["verified"] = True
        await user_repo.upsert(user)
        await messaging.send(channel="whatsapp", recipient=phone, body=_ACTIVATED)
        return Response(status_code=200)

    # The agent run can take ~15s (live data + LLM). Run it after responding so
    # Twilio gets its ACK immediately and never times out the webhook.
    background.add_task(_run_agent_and_reply, phone, text)
    return Response(status_code=200)
