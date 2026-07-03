"""Modular command registry for PRANA's WhatsApp bot shortcuts."""
from __future__ import annotations

import logging
from typing import Callable, Awaitable, Dict, List
from framework.context.user import UserContext

logger = logging.getLogger(__name__)

class Command:
    def __init__(self, name: str, description: str, handler: Callable[[UserContext], Awaitable[str]]):
        self.name = name
        self.description = description
        self.handler = handler

    async def execute(self, ctx: UserContext) -> str:
        try:
            return await self.handler(ctx)
        except Exception as e:
            logger.exception("Error executing command %s", self.name)
            return f"Sorry, there was an error running your command: {e}"

class CommandRegistry:
    def __init__(self, prefix: str = "/"):
        self.prefix = prefix
        self.commands: Dict[str, Command] = {}

    def register(self, name: str, description: str, handler: Callable[[UserContext], Awaitable[str]]):
        cmd = Command(name, description, handler)
        self.commands[name.lower()] = cmd

    async def dispatch(self, text: str, ctx: UserContext) -> str | None:
        raw = text.strip().lower()
        if not raw.startswith(self.prefix):
            # Check for exact matches without prefix too (e.g. "help")
            cmd_name = raw
        else:
            cmd_name = raw[len(self.prefix):]

        if cmd_name in self.commands:
            return await self.commands[cmd_name].execute(ctx)
        return None

    def get_help_text(self) -> str:
        lines = ["*Available Commands:*"]
        for name in sorted(self.commands.keys()):
            cmd = self.commands[name]
            lines.append(f"• *{self.prefix}{cmd.name}*: {cmd.description}")
        return "\n".join(lines)

# --- Built-in Command Handlers ---

async def handle_help(ctx: UserContext) -> str:
    # This is a bit circular, the registry will provide the help text.
    # We'll inject it later in the factory.
    return "Help command initialized."

async def handle_risk(ctx: UserContext) -> str:
    from prana.ai_tools.risk import get_risk
    res = await get_risk(ctx=ctx)
    if "error" in res:
        return res["error"]
    return (
        f"*Current Risk:* {res['risk_level']}\n"
        f"CCRI: {res['ccri']}\n"
        f"Sleep Recovery (NDT): {res['ndt']:.1f}°C\n\n"
        f"{res['alert_message']}"
    )

async def handle_profile(ctx: UserContext) -> str:
    onb = ctx.metadata.get("onboarding", {})
    loc = ctx.metadata.get("location_name", "Unknown")
    ac = "Yes" if onb.get("ac") else "No"
    roof = onb.get("roof_material", "Unknown")
    floor = onb.get("floor_level", "Unknown")
    return (
        f"*Your Profile:*\n"
        f"• Location: {loc}\n"
        f"• AC: {ac}\n"
        f"• Roof: {roof}\n"
        f"• Floor: {floor}"
    )
