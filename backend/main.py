"""FastAPI backend for the PRANA mobile app."""

import os
import time
from collections import defaultdict
from contextlib import asynccontextmanager, redirect_stdout
from datetime import datetime, timezone
from io import StringIO
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.logger import get_logger

logger = get_logger("api")

from prana.config import OPENAQ_API_KEY, OPENWEATHER_API_KEY, UPDATE_INTERVAL  # noqa: E402
from prana.config import RDS_NIGHTTIME_THRESHOLD  # noqa: E402
from prana.prana_system import PRANASystem  # noqa: E402
from prana.bot.bootstrap import (  # noqa: E402
    build_repo, build_checkin_repo, build_rds_repo, build_risk_eval_repo,
    build_household_repo, settings,
)
from prana.personalization import personalize_offset, get_onboarding_prior  # noqa: E402
from framework.context.user import UserContext  # noqa: E402
from prana.config import WHATSAPP_BOT_NUMBER  # noqa: E402
from enum import Enum

user_repo = build_repo()
checkin_repo = build_checkin_repo()
rds_repo = build_rds_repo()
risk_eval_repo = build_risk_eval_repo()
household_repo = build_household_repo()


from prana.scheduler import AlertScheduler  # noqa: E402

_scheduler = AlertScheduler()


@asynccontextmanager
async def lifespan(app):
    """Manage scheduler lifecycle."""
    if os.getenv("DISABLE_ALERT_SCHEDULER") != "1":
        _scheduler.start()
    yield
    await _scheduler.stop()


app = FastAPI(
    title="PRANA API",
    description="Backend API for PRANA climate risk results and mobile dashboard data.",
    version="0.1.0",
    lifespan=lifespan,
)

_cors_origins = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

from prana.bot.whatsapp_webhook import router as whatsapp_router  # noqa: E402
app.include_router(whatsapp_router)
# ---------------------------------------------------------------------------
# Simple in-memory rate limiter with stale record eviction
# ---------------------------------------------------------------------------

_RATE_LIMIT = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
_window_store: dict = defaultdict(list)


def _evict_stale_windows(now: float) -> None:
    """Drop client IPs whose entire request window has expired."""
    cutoff = now - 60
    stale = [ip for ip, times in _window_store.items() if not times or times[-1] <= cutoff]
    for ip in stale:
        del _window_store[ip]


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    _evict_stale_windows(now)
    window = _window_store[client_ip]
    cutoff = now - 60
    window[:] = [t for t in window if t > cutoff]

    # Stale record eviction: if an IP has no active window, clean it up to prevent
    # memory leaking over time in long-running processes.
    if not window and client_ip in _window_store:
        del _window_store[client_ip]
        window = []

    if len(window) >= _RATE_LIMIT:
        logger.warning("Rate limit hit for %s", client_ip)
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Please try again in a minute."},
        )

    if client_ip not in _window_store:
        _window_store[client_ip] = window
    window.append(now)
    return await call_next(request)


class RiskRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90, description="User latitude.")
    lon: float = Field(..., ge=-180, le=180, description="User longitude.")
    location_name: str = Field("Current location", min_length=1, max_length=120)
    urban_heat_offset: float = Field(
        3.0,
        ge=0,
        le=8,
        description="Ward-level urban heat island offset in Celsius.",
    )
    sleep_checkin: Optional[dict] = Field(
        None, description="Structured sleep check-in from WhatsApp."
    )
    onboarding_data: Optional[dict] = Field(
        None, description="Home profile: {ac: bool, roof_material: str, floor_level: str}"
    )
    user_id: Optional[str] = Field(
        None,
        description="If provided, the user's stored sleep check-ins personalise "
                    "the RDS indoor-offset estimate. Omit for population-only scoring.",
    )


class RiskResponse(BaseModel):
    result: Dict[str, Any]
    calculation_log: str

    model_config = {"json_encoders": {datetime: lambda v: v.isoformat()}}


class HomeProfile(BaseModel):
    ac: bool
    roof_material: str
    floor_level: str
    fan: bool = False
    windows_open: bool = False
    occupants: int = Field(1, ge=1, le=10, description="People sharing the sleeping room.")


class CheckinRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=64)
    sleep_quality: str = Field(
        ..., description="good | moderate | poor (or comfortable/warm/too_hot)."
    )
    outdoor_temp: Optional[float] = Field(
        None, ge=-30, le=60, description="Outdoor nighttime temp for the reported night (C)."
    )
    humidity: Optional[float] = Field(None, ge=0, le=100)
    checkin_date: Optional[str] = Field(
        None, description="ISO date (YYYY-MM-DD). Defaults to today (UTC)."
    )


class CheckinResponse(BaseModel):
    ok: bool
    user_id: str
    checkin_date: str
    n_checkins: int


class RegisterRequest(BaseModel):
    phone: str = Field(..., min_length=8, max_length=20)
    location_name: str = Field(..., min_length=1, max_length=120)
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    urban_heat_offset: Optional[float] = Field(None, ge=0, le=8)
    onboarding: HomeProfile


class RegisterResponse(BaseModel):
    ok: bool
    user_id: str
    verified: bool
    whatsapp_link: str
    sandbox_join_code: str


class TagEnum(str, Enum):
    CHILD = "child"
    TEEN = "teen"
    ADULT = "adult"
    WOMAN = "woman"
    ELDERLY = "elderly"


class HouseholdMemberAdd(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=60)
    tag: TagEnum
    outdoor_worker: bool = False


class HouseholdMember(BaseModel):
    id: int
    user_id: str
    name: str
    tag: TagEnum
    outdoor_worker: bool
    created_at: str


@app.get("/health")
def health() -> Dict[str, Any]:
    """Return backend status for app and deployment checks."""
    return {
        "status": "ok",
        "service": "prana-api",
        "update_interval_hours": UPDATE_INTERVAL,
        "weather_provider": "open-meteo",
        "air_quality_provider": "open-meteo-cams",
        "openweather_fallback_configured": bool(OPENWEATHER_API_KEY),
        "openaq_configured": bool(OPENAQ_API_KEY),
    }


@app.post("/risk/current", response_model=RiskResponse)
async def calculate_current_risk(payload: RiskRequest) -> RiskResponse:
    """Calculate current PRANA climate risk. When user_id is supplied, seed the
    RDS ledger + check-in personalization for that user and persist the result."""
    personalization = None
    onb_data = payload.onboarding_data or {}
    loc_name = payload.location_name
    historical_temps = []

    if payload.user_id:
        user = await user_repo.get_by_phone(payload.user_id)
        if user and user.metadata.get("onboarding"):
            onb_data = user.metadata["onboarding"]
            loc_name = user.metadata.get("location_name") or loc_name

        checkins = await checkin_repo.list_for_user(payload.user_id, limit=30)
        if checkins:
            prior_mean, prior_sd = get_onboarding_prior(onb_data, loc_name)
            post = personalize_offset(prior_mean, prior_sd, checkins, RDS_NIGHTTIME_THRESHOLD)
            personalization = {"offset": post.mean, "band": post.sd, "n_checkins": post.n_checkins}

        historical_temps = await rds_repo.load(payload.user_id)

    result, logs = await run_in_threadpool(
        _run_prana_pipeline, payload, personalization, historical_temps
    )
    if not result:
        raise HTTPException(status_code=502, detail="Risk calculation failed.")

    if payload.user_id:
        await risk_eval_repo.add(
            payload.user_id,
            outdoor_temp=result.get("raw_temp"),
            outdoor_humidity=result.get("raw_humidity"),
            base_aqi=(result.get("aqi") or {}).get("base_aqi"),
            ndt=result.get("ndt"),
            rds_mid=(result.get("rds") or {}).get("rds_mid"),
            ccri=result.get("ccri"),
        )
        await rds_repo.save(payload.user_id, result.get("rds_historical_temps", []))

    return RiskResponse(result=_serialize_result(result), calculation_log=logs)


@app.post("/checkin", response_model=CheckinResponse)
async def record_checkin(payload: CheckinRequest) -> CheckinResponse:
    """Record a nightly sleep check-in. These accumulate as the evidence that
    personalises a user's RDS indoor-offset over time."""
    checkin_date = payload.checkin_date or datetime.now(timezone.utc).date().isoformat()
    await checkin_repo.add(
        user_id=payload.user_id,
        checkin_date=checkin_date,
        sleep_quality=payload.sleep_quality,
        outdoor_temp=payload.outdoor_temp,
        humidity=payload.humidity,
    )
    stored = await checkin_repo.list_for_user(payload.user_id, limit=1000)
    return CheckinResponse(
        ok=True, user_id=payload.user_id, checkin_date=checkin_date,
        n_checkins=len(stored),
    )


@app.post("/register", response_model=RegisterResponse)
async def register(payload: RegisterRequest) -> RegisterResponse:
    """Register a phone + location + home profile through the single shared user
    repository, so the webhook and scheduler see the same record. Verification is
    completed later by the user's own inbound WhatsApp message; re-registering an
    already-verified phone must NOT reset it to unverified."""
    existing = await user_repo.get_by_phone(payload.phone)
    verified = bool(existing.metadata.get("verified")) if existing else False

    user = UserContext(
        user_id=payload.phone,
        phone=payload.phone,
        metadata={
            "lat": payload.lat,
            "lon": payload.lon,
            "location_name": payload.location_name,
            "urban_heat_offset": payload.urban_heat_offset,
            "onboarding": payload.onboarding.model_dump(),
            "verified": verified,
            "last_alert_level": existing.metadata.get("last_alert_level") if existing else None,
        },
    )
    await user_repo.upsert(user)

    return RegisterResponse(
        ok=True,
        user_id=payload.phone,
        verified=verified,
        whatsapp_link=f"https://wa.me/{WHATSAPP_BOT_NUMBER}?text=PRANA%20START",
        sandbox_join_code=settings.whatsapp_sandbox_join_code,
    )


def _run_prana_pipeline(payload: RiskRequest, personalization=None, historical_temps=None):
    prana = PRANASystem(
        api_key=OPENWEATHER_API_KEY,
        location_name=payload.location_name,
        urban_heat_offset=payload.urban_heat_offset,
        openaq_api_key=OPENAQ_API_KEY,
        onboarding_data=payload.onboarding_data,
    )

    # Seed RDS calculator with persisted history from DB
    if historical_temps:
        prana.rds_calculator.nighttime_temps = historical_temps

    stdout = StringIO()
    with redirect_stdout(stdout):
        result = prana.update_all(
            payload.lat, payload.lon,
            sleep_checkin=payload.sleep_checkin,
            personalization=personalization,
        )

    if result:
        # Pass historical temps back so they can be saved to DB
        result['rds_historical_temps'] = prana.rds_calculator.nighttime_temps

    return result, stdout.getvalue()


def _serialize_result(result: dict) -> dict:
    """Recursively convert datetime objects to ISO strings for JSON serialization."""
    if isinstance(result, dict):
        return {k: _serialize_result(v) for k, v in result.items()}
    if isinstance(result, list):
        return [_serialize_result(v) for v in result]
    if isinstance(result, datetime):
        return result.isoformat()
    return result


@app.post("/household/members", response_model=HouseholdMember)
async def add_household_member(payload: HouseholdMemberAdd) -> Any:
    """Add a new member to the user's household for vulnerability-track tagging."""
    member_id = await household_repo.add(
        payload.user_id, payload.name, payload.tag.value, payload.outdoor_worker
    )
    members = await household_repo.list_for_user(payload.user_id)
    # The member is the one we just added (or we could fetch by ID)
    for m in members:
        if m["id"] == member_id:
            return m
    raise HTTPException(status_code=500, detail="Failed to retrieve newly added member.")


@app.get("/household/members", response_model=list[HouseholdMember])
async def list_household_members(user_id: str) -> list[dict]:
    """Retrieve all tagged members in a user's household."""
    return await household_repo.list_for_user(user_id)


@app.delete("/household/members/{id}")
async def delete_household_member(id: int) -> dict:
    """Remove a household member tag."""
    ok = await household_repo.delete(id)
    if not ok:
        raise HTTPException(status_code=404, detail="Member not found.")
    return {"ok": True}
