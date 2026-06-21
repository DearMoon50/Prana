# PRANA Roadmap

This roadmap updates the original PRANA plan with the current Flutter + Python backend direction.

## Product Goal

PRANA is a compound climate-risk platform for people exposed to heat, pollution, and poor nighttime recovery. The mobile app captures user location and shows dashboards. WhatsApp handles warnings, check-ins, language support, and escalation.

## Current Foundation

- Flutter mobile app scaffolded with GPS/manual location input.
- FastAPI backend exposes `GET /health` and `POST /risk/current`.
- Open-Meteo is the primary free weather provider.
- Open-Meteo Air Quality is the primary free modeled air-quality provider.
- OpenWeatherMap and OpenAQ are optional fallback/reference providers.
- Current backend returns structured `summary`, `components`, `sources`, and `confidence`.
- Backend alert text is ASCII-safe for WhatsApp and mobile rendering.

## Updated Provider Strategy

### Primary Free Providers

- Weather and forecast: Open-Meteo Forecast API.
- Air-quality model forecast: Open-Meteo Air Quality API.
- Historical/nighttime climate support: NASA POWER or ERA5-derived data in a later phase.

### Optional Reference Providers

- OpenAQ for nearby station measurements when available.
- OpenWeatherMap only as a weather fallback if configured.

## Formula Roadmap

### Phase 1: Formula Documentation

- Create `FORMULA_VALIDATION.md`.
- Mark each formula as one of:
  - Official/standard
  - Published approximation
  - PRANA custom index
  - Prototype assumption
- Document sources, limits, confidence, and what should not be claimed.

### Phase 2: Heat / NDT

- Keep NDT as PRANA terminology, but expose it as `estimated_wbgt_plus_urban_offset`.
- Use Open-Meteo wet-bulb temperature when available.
- Use solar radiation for globe temperature approximation.
- Later add OpenStreetMap/Landsat/ECOSTRESS-based urban heat offset.
- Add heat confidence based on wet bulb, radiation, and urban offset quality.

### Phase 3: Air Quality / Heat-Pollution Risk

- Rename HA-AQI to avoid implying it is an official AQI.
- Stop multiplying full AQI by heat.
- Separate:
  - `base_aqi`
  - `dominant_pollutant`
  - `pm25_aqi`
  - `pm10_aqi`
  - `o3_aqi`
  - `ozone_heat_adjusted_risk`
  - `pollution_confidence`
- Add proper AQI averaging/NowCast behavior where data supports it.

### Phase 4: Recovery / RDS

- Reframe RDS as a recovery-risk estimate, not measured indoor recovery.
- Use nighttime outdoor temperature, wet bulb, humidity, and hot-night streaks.
- Add WhatsApp check-ins only when recovery uncertainty or possible impact is high.
- Store user feedback to personalize future RDS.
- Keep final RDS deterministic in Python; use the LLM only to understand conversation and extract structured data.

### Phase 5: CCRI

- Mark CCRI as a custom PRANA compound risk score.
- Return component scores and multipliers:
  - heat score
  - pollution score
  - recovery score
  - compound multiplier
- Add confidence and limitations to every score.
- Later calibrate against real heat-event, hospital, or mortality datasets.

## Backend Roadmap

### Phase 1: Persistence

- Add SQLite locally with SQLAlchemy.
- Later migrate to PostgreSQL.
- Store users, locations, risk results, WhatsApp messages, and sleep check-ins.

### Phase 2: User and Location APIs

- `POST /users`
- `POST /users/{user_id}/locations`
- `GET /users/{user_id}/results`
- `POST /users/{user_id}/risk/current`

### Phase 3: WhatsApp Bot

- Integrate WhatsApp Business Cloud API or provider adapter.
- Add webhook verification and inbound message handling.
- Add STOP/delete flow.
- Add recovery check-ins only when needed.
- Add health-worker escalation path.

### Phase 4: LLM Conversation Layer

- Primary LLM provider: OpenRouter.
- Local fallback: Ollama.
- LLM responsibilities:
  - classify user intent
  - extract structured sleep/recovery feedback
  - localize and soften message wording
  - summarize risk explanations
- Backend responsibilities:
  - deterministic scoring
  - safety rules
  - persistence
  - alert scheduling
  - escalation logic

### Phase 5: Scheduler

- Calculate risk every 3 hours for active locations.
- Send alerts only when thresholds or trend changes justify it.
- Respect opt-in, quiet hours, and message frequency caps.

## WhatsApp RDS Check-In Policy

Do not ask every day. Ask only when:

- nighttime heat or wet bulb is elevated,
- multiple hot nights occur in a row,
- RDS uncertainty is high,
- the user has opted in,
- the user has not been asked recently.

Recommended message:

```text
PRANA check-in: Nighttime heat near you may affect recovery.

How was your sleep environment last night?
1. Comfortable
2. Warm but manageable
3. Too hot to sleep well
4. Fan/AC or power issue
```

Frequency cap:

- maximum once per day,
- maximum 2-3 times per week,
- only during elevated heat periods.

## Environment Variables

Use `.env` locally. Never commit it.

Required later:

- `WHATSAPP_ACCESS_TOKEN`
- `WHATSAPP_PHONE_NUMBER_ID`
- `WHATSAPP_VERIFY_TOKEN`
- `WHATSAPP_APP_SECRET`
- `OPENROUTER_API_KEY`

Optional:

- `OPENAQ_API_KEY`
- `OPENWEATHER_API_KEY`
- `OLLAMA_BASE_URL`
- `OLLAMA_MODEL`

## Immediate Next Steps

1. Create `FORMULA_VALIDATION.md`.
2. Refactor HA-AQI into heat-pollution risk with ozone-specific adjustment.
3. Add database persistence.
4. Add WhatsApp webhook skeleton.
5. Add OpenRouter/Ollama LLM adapter.

## Completed Since This Roadmap

- Added secret-safe `.gitignore` coverage for env files, logs, databases, virtualenvs, and Flutter build outputs.
- Added OpenRouter/Ollama environment variables to `.env.example`.
- Added `backend.llm.LLMClient` with OpenRouter primary and Ollama fallback.
- Added deterministic parsing for simple RDS sleep check-in replies before using the LLM.
- Added `FORMULA_VALIDATION.md` to distinguish official methods, approximations, PRANA custom formulas, and prototype assumptions.
- Refactored heat-pollution scoring so heat adjusts ozone-specific risk instead of multiplying the full AQI.
- Added formula regression tests for AQI components, heat-pollution risk, RDS, and CCRI.
