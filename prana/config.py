"""Configuration for PRANA Climate Risk System"""
import os
from dotenv import load_dotenv

load_dotenv()

# API Keys
OPENWEATHER_API_KEY = os.getenv('OPENWEATHER_API_KEY', '')
OPENAQ_API_KEY = os.getenv('OPENAQ_API_KEY', '')  # Get free key from https://openaq.org

# Twilio WhatsApp sandbox (deep link only; Twilio Account SID/Auth Token live in framework.config.settings.FrameworkSettings)
WHATSAPP_BOT_NUMBER = os.getenv('WHATSAPP_BOT_NUMBER', '')  # E.164 number for wa.me deep links, e.g. 919900000000

# LLM provider for WhatsApp bot
LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'openrouter')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY', '')
OPENROUTER_BASE_URL = os.getenv('OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1')
OPENROUTER_MODEL = os.getenv('OPENROUTER_MODEL', '')
OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL', 'http://127.0.0.1:11434')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', '')

# Runtime
APP_ENV = os.getenv('APP_ENV', 'development')
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./prana.db')

# API Endpoints
OPENMETEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
OPENMETEO_AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
OPENMETEO_SATELLITE_RADIATION_URL = "https://satellite-api.open-meteo.com/v1/archive"
OPENWEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"
OPENWEATHER_FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"
OPENAQ_URL = "https://api.openaq.org/v3/locations"  # v3 locations endpoint
NASA_POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"

# WBGT Coefficients (ISO 7243 / Liljegren)
WBGT_TW_COEFF = 0.7  # Wet bulb temperature
WBGT_TG_COEFF = 0.2  # Globe temperature
WBGT_TD_COEFF = 0.1  # Dry bulb temperature

# Ozone Amplification Factor (Shen et al. 2020)
OAF_BASE_TEMP = 25.0  # Celsius
OAF_COEFFICIENT = 0.04
OAF_BLEND_WEIGHT = 0.5  # Weight for heat-driven ozone increment blended into base AQI
OZONE_HEAT_COUPLING_THRESHOLD_AQI = 50  # Only apply heat factor when O3 AQI >= this (NOx-limited below)

# Recovery Debt Score
# RDS_NIGHTTIME_THRESHOLD is retained only as a reference point for the naive
# tonight-only forecast baseline in research/rds_demo/demo.py -- the ledger
# itself has no hard threshold (see SLEEP_LOSS_ANCHORS below, a continuous
# curve). RDS_DECAY_FACTOR, RDS_MAX_DAYS, and RDS_ONBOARDING_AC_OFFSET from the
# old model were retired by the sleep-debt-ledger rebuild (see
# RECOVERY_WINDOW_NIGHTS, RECOVERY_PER_COOL_NIGHT_MIN, and
# RDS_ASHRAE_AC_BASELINE/RDS_ASHRAE_AC_INTERACTION further below) and removed.
RDS_NIGHTTIME_THRESHOLD = 32.0  # Celsius - no recovery above this (dry-bulb scale)
# TODO(vulnerability-tracks): per-tag threshold differentiation is deferred until there's
# check-in data to calibrate it. Household-member tags are collected for that future
# purpose but not yet wired into any scoring.

# --- Indoor temperature offset model (effective sleeping temp vs outdoor) ---
# Cooling devices (negative = cooler indoors)
RDS_ONBOARDING_FAN_OFFSET = -2.0  # degC: equivalent cooling effect of a fan at sleep (~1 m/s airflow, ASHRAE 55 elevated air speed)
RDS_ONBOARDING_WINDOW_OFFSET = -1.5  # degC: night ventilation / cross-breeze when windows kept open (PROTOTYPE_ASSUMPTION)
# Building envelope (positive = hotter indoors)
# Climate-Zone-Aware building envelope offsets (Nature Sci Data 10.1038/s41597-022-01314-5).
# Segregated to avoid Simpson's Paradox: Dry climates (Delhi) show top-floor cooling, 
# while Humid climates (Dhaka) show top-floor heat entrapment.
RDS_CLIMATE_ZONE_COEFFS = {
    "hot_dry": {  # Derived from Delhi/Faisalabad (Hot, Dry/Semi-Arid)
        "roof": {
            "tin":      {"baseline": -3.17, "interaction":  0.136},
            "concrete": {"baseline":  2.50, "interaction": -0.087},
            "stone":    {"baseline": -0.35, "interaction":  0.058},
            "brick":    {"baseline":  0.0,  "interaction":  0.0},
        },
        "floor": {
            "top": -1.02, # degC (Significant radiative sky cooling in dry air)
            "other": 0.0
        }
    },
    "hot_humid": {  # Derived from Dhaka/Coastal (Hot, Humid/Tropical)
        "roof": {
            "tin":      {"baseline": -3.82, "interaction":  0.125},
            "concrete": {"baseline":  0.0,  "interaction":  0.0},  # Reference in sample
            "brick":    {"baseline":  0.0,  "interaction":  0.0},
        },
        "floor": {
            "top": 0.92, # degC (Heat trap: lack of radiative sky cooling under moisture)
            "other": 0.0
        }
    },
    "default": {  # Conservative fallback based on global MixedLM pooled result (n=26,501)
        "roof": {
            "tin":      {"baseline":  1.89, "interaction": -0.047},
            "concrete": {"baseline":  1.37, "interaction": -0.016},
            "stone":    {"baseline":  0.57, "interaction":  0.043},
            "brick":    {"baseline":  0.0,  "interaction":  0.0},
        },
        "floor": {
            "top": 0.0, # Defensive floor (do not assume sky cooling if zone unknown)
            "other": 0.0
        }
    }
}
# Occupancy (positive = hotter indoors from metabolic heat load)
RDS_ONBOARDING_PER_EXTRA_OCCUPANT_OFFSET = 0.5  # degC per person beyond the first sharing the sleeping room

RDS_INDOOR_OFFSET_BAND_WIDTH = 2.0  # degC, ± band around onboarding offset estimate
RDS_AC_EXTRA_BAND_WIDTH = 1.5  # degC, additional ± uncertainty when AC present (usage / power-reliability variance)

# Use wet-bulb nighttime temperature (humidity-aware) instead of dry-bulb air
# temp for the RFU threshold check. The body cannot cool by evaporation when
# humidity is high, so 32C at 80% RH is far more dangerous than 32C at 40% RH.
RDS_USE_WET_BULB = True
# When wet bulb is used the recovery threshold is re-expressed on the wet-bulb
# scale. Physiological heat-strain literature places uncompensable nighttime
# heat stress around a wet-bulb of ~28C.
RDS_NIGHTTIME_WETBULB_THRESHOLD = 28.0  # Celsius - no recovery above this (wet-bulb scale)

# ---------------------------------------------------------------------------
# Sleep-debt ledger (RDS rebuild) -- debt is measured in MINUTES of sleep
# lost to heat, replacing the unitless 0-100 score. See docs/RDS_MODEL.md.
# ---------------------------------------------------------------------------

# Per-night dose-response anchors: (effective_indoor_temp_C, minutes_lost).
# Anchored to Minor et al. 2022 (One Earth, ~47k users / 7M nights): a night
# minimum near 30C costs ~14 min of sleep vs a cool baseline; loss accelerates
# with heat. Linearly interpolated between anchors, flat outside the range.
SLEEP_LOSS_ANCHORS = [
    (20.0, 0.0),
    (25.0, 4.0),
    (28.0, 9.0),
    (30.0, 14.0),
    (33.0, 22.0),
    (35.0, 30.0),
    (40.0, 55.0),
    (45.0, 60.0),
]

# Debt ledger dynamics (minutes).
RECOVERY_DEBT_CAP_MIN = 240          # ~4h max carried debt; replaces the old 100 cap
RECOVERY_PER_COOL_NIGHT_MIN = 45     # minutes of debt cleared by one recovering night (see RECOVERY_NIGHT_LOSS_THRESHOLD_MIN)
RECOVERY_NIGHT_LOSS_THRESHOLD_MIN = 5  # a night losing < this counts as a recovering night
RECOVERY_WINDOW_NIGHTS = 7           # nights of history the ledger walks
HOT_CLIMATE_SLEEP_MULTIPLIER = 1.0   # knob for Minor's 2.5-3x low-income finding (default off)

# Debt-to-tier thresholds (minutes).
RECOVERY_TIER_MODERATE_MIN = 30.0
RECOVERY_TIER_HIGH_MIN = 90.0
RECOVERY_TIER_SEVERE_MIN = 180.0

# Temp-dependent AC offset (ASHRAE Global Thermal Comfort DB II finding):
# homes WITHOUT AC run ~+3.5C hotter than AC homes at ~30C outdoor, gap widening
# with heat. Expressed as effective indoor cooling = baseline + interaction * T,
# giving ~-3.5C at 30C (base -1.5 + -0.0667*30). Replaces flat RDS_ONBOARDING_AC_OFFSET.
RDS_ASHRAE_AC_BASELINE = -1.5
RDS_ASHRAE_AC_INTERACTION = -0.0667

# CCRI Thresholds
CCRI_SAFE = 20
CCRI_ELEVATED = 40
CCRI_HIGH = 60
CCRI_CRITICAL = 80
# Above 80 = COMPOUND EMERGENCY

# Update frequency (hours)
UPDATE_INTERVAL = 3

# --- Proactive alert cadence ---
ALERT_MIN_HOURS_BETWEEN = 24          # at most one proactive alert per user per day
ALERT_QUIET_HOURS_START = 22          # local hour [0-23]; no alerts at/after this
ALERT_QUIET_HOURS_END = 7             # local hour [0-23]; no alerts before this
