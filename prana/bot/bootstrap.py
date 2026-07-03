"""Wires framework components for PRANA's bot at startup."""
from __future__ import annotations

from framework.ai.factory import build_provider
from framework.config.settings import FrameworkSettings
from framework.messaging.registry import MessagingRegistry
from framework.messaging.whatsapp import TwilioWhatsAppChannel
from framework.persistence.sqlite import (
    SQLiteUserRepository, SQLiteCheckinRepository,
    SQLiteRDSStateRepository, SQLiteRiskEvalRepository,
)
from framework.tools.base import ToolRegistry
from prana.ai_tools.risk import risk_tool
from prana.ai_tools.checkin import record_checkin_tool
from prana.config import DATABASE_URL
from prana.bot.commands import CommandRegistry, handle_help, handle_risk, handle_profile

settings = FrameworkSettings()


def build_registry() -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(risk_tool)
    reg.register(record_checkin_tool)
    return reg


def build_provider_chain():
    return build_provider(settings)


def build_messaging() -> MessagingRegistry:
    reg = MessagingRegistry()
    reg.add(TwilioWhatsAppChannel(
        settings.whatsapp_account_sid, settings.whatsapp_auth_token, settings.whatsapp_from_number,
    ))
    return reg


def build_repo() -> SQLiteUserRepository:
    return SQLiteUserRepository(DATABASE_URL)


def build_checkin_repo() -> SQLiteCheckinRepository:
    return SQLiteCheckinRepository(DATABASE_URL)


def build_rds_repo() -> SQLiteRDSStateRepository:
    from prana.config import RDS_MAX_DAYS
    return SQLiteRDSStateRepository(DATABASE_URL, max_days=RDS_MAX_DAYS)


def build_risk_eval_repo() -> SQLiteRiskEvalRepository:
    return SQLiteRiskEvalRepository(DATABASE_URL)


def build_commands() -> CommandRegistry:
    cmd_reg = CommandRegistry(prefix="/")
    cmd_reg.register("help", "List all available commands.", lambda ctx: handle_help_dispatch(cmd_reg, ctx))
    cmd_reg.register("risk", "Quickly check your current climate risk scores.", handle_risk)
    cmd_reg.register("profile", "View your registered home profile.", handle_profile)
    return cmd_reg


async def handle_help_dispatch(reg: CommandRegistry, ctx: UserContext) -> str:
    return reg.get_help_text()
