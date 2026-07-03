import pytest
import asyncio
from unittest.mock import MagicMock, patch
from framework.context.user import UserContext
from prana.bot.commands import CommandRegistry, handle_help, handle_risk

def test_command_registry_dispatch():
    registry = CommandRegistry(prefix="/")
    
    async def mock_handler(ctx):
        return "Command result"
        
    registry.register("test", "test description", mock_handler)
    
    ctx = UserContext(user_id="u1")
    
    # Prefix match
    res = asyncio.run(registry.dispatch("/test", ctx))
    assert res == "Command result"
    
    # Case insensitive
    res = asyncio.run(registry.dispatch("/TEST", ctx))
    assert res == "Command result"
    
    # Exact match without prefix
    res = asyncio.run(registry.dispatch("test", ctx))
    assert res == "Command result"
    
    # No match
    res = asyncio.run(registry.dispatch("/unknown", ctx))
    assert res is None


def test_help_command():
    from prana.bot.bootstrap import build_commands
    registry = build_commands()
    
    ctx = UserContext(user_id="u1")
    res = asyncio.run(registry.dispatch("/help", ctx))
    
    assert "/help" in res
    assert "/risk" in res
    assert "/profile" in res
    assert "List all available commands" in res


def test_risk_shortcut_calls_get_risk():
    from prana.bot.bootstrap import build_commands
    registry = build_commands()
    ctx = UserContext(user_id="u1", metadata={"lat": 10, "lon": 70})
    
    with patch("prana.ai_tools.risk.get_risk") as mock_get_risk:
        async def _mock_risk(*args, **kwargs):
            return {
                "risk_level": "MODERATE",
                "ccri": 45.0,
                "ndt": 28.5,
                "alert_message": "Warm night ahead."
            }
        mock_get_risk.side_effect = _mock_risk
        res = asyncio.run(registry.dispatch("/risk", ctx))
        
    assert "MODERATE" in res
    assert "45.0" in res
    assert "Warm night" in res
    mock_get_risk.assert_called_once()
