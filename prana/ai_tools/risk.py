"""PRANA's get_risk tool — wraps the deterministic scoring engine for the agent."""
from __future__ import annotations

import asyncio
from framework.context.user import UserContext
from framework.tools.base import Tool
from prana.config import OPENAQ_API_KEY, OPENWEATHER_API_KEY, RDS_NIGHTTIME_THRESHOLD
from prana.prana_system import PRANASystem
from prana.personalization import personalize_offset, get_onboarding_prior


async def get_risk(*, ctx: UserContext, historical_temps=None, personalization=None) -> dict:
    meta = ctx.metadata
    
    # Self-loading: if called as a tool (without explicit history/personalization),
    # fetch the data from the shared DB using the user context.
    if ctx.user_id:
        from prana.bot.bootstrap import build_rds_repo, build_checkin_repo
        if historical_temps is None:
            historical_temps = await build_rds_repo().load(ctx.user_id)
        if personalization is None:
            checkins = await build_checkin_repo().list_for_user(ctx.user_id, limit=30)
            if checkins:
                onb = meta.get("onboarding") or {}
                prior_mean, prior_sd = get_onboarding_prior(onb, meta.get("location_name"))
                post = personalize_offset(prior_mean, prior_sd, checkins, RDS_NIGHTTIME_THRESHOLD)
                personalization = {"offset": post.mean, "band": post.sd, "n_checkins": post.n_checkins}

    system = PRANASystem(
        api_key=OPENWEATHER_API_KEY,
        location_name=meta.get("location_name", "Current location"),
        urban_heat_offset=meta.get("urban_heat_offset"),
        openaq_api_key=OPENAQ_API_KEY,
        onboarding_data=meta.get("onboarding"),
    )
    if historical_temps:
        system.rds_calculator.nighttime_temps = historical_temps

    # update_all does blocking network calls; run it off the event loop.
    result = await asyncio.to_thread(
        system.update_all, meta["lat"], meta["lon"], personalization=personalization
    )
    if not result:
        return {"error": "Risk data is temporarily unavailable."}
    rds = result["rds"]
    ts = result["timestamp"]
    return {
        "ccri": result["ccri"],
        "risk_level": result["risk_level"],
        "ndt": result["ndt"],
        "rds_mid": rds["rds_mid"],
        "consecutive_nights": rds["consecutive_nights"],
        "alert_message": result["alert_message"],
        "as_of": ts.isoformat() if hasattr(ts, "isoformat") else ts,
        "weather": result.get("weather"),
        "base_aqi": result.get("base_aqi"),
        "rds_historical_temps": system.rds_calculator.nighttime_temps,
    }


risk_tool = Tool(
    name="get_risk",
    description=(
        "Get the user's current compound climate risk (heat + pollution + sleep "
        "recovery). Call this whenever the user asks about their risk, heat, air "
        "quality, sleep, or why an alert was sent."
    ),
    parameters={"type": "object", "properties": {}, "required": []},
    fn=get_risk,
    required_permission=None,
)
