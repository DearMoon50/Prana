"""FastAPI backend for the PRANA mobile app."""

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import sys
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import OPENAQ_API_KEY, OPENWEATHER_API_KEY, UPDATE_INTERVAL  # noqa: E402
from prana_system import PRANASystem  # noqa: E402


app = FastAPI(
    title="PRANA API",
    description="Backend API for PRANA climate risk results and mobile dashboard data.",
    version="0.1.0",
)


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


class RiskResponse(BaseModel):
    result: Dict[str, Any]
    calculation_log: str


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
    """Calculate current PRANA climate risk metrics for a user-selected location."""
    result, logs = await run_in_threadpool(_run_prana_pipeline, payload)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not calculate risk. Check API keys, coordinates, and upstream services.",
        )

    return RiskResponse(result=result, calculation_log=logs)


def _run_prana_pipeline(payload: RiskRequest) -> tuple[Optional[Dict[str, Any]], str]:
    prana = PRANASystem(
        api_key=OPENWEATHER_API_KEY,
        location_name=payload.location_name,
        urban_heat_offset=payload.urban_heat_offset,
        openaq_api_key=OPENAQ_API_KEY,
    )

    stdout = StringIO()
    with redirect_stdout(stdout):
        result = prana.update_all(payload.lat, payload.lon)

    return result, stdout.getvalue()
