# PRANA Environment Setup

Create a local `.env` file from `.env.example`.

```powershell
Copy-Item .env.example .env
```

Never commit `.env`.

## Core Providers

Open-Meteo is the default weather and air-quality provider and does not need an API key.

Optional fallback/reference keys:

```text
OPENWEATHER_API_KEY=
OPENAQ_API_KEY=
```

## WhatsApp

These are placeholders for the Twilio WhatsApp sandbox. `WHATSAPP_FROM_NUMBER` includes
the `whatsapp:` prefix (Twilio's sandbox number); `WHATSAPP_BOT_NUMBER` is the same number
written as bare E.164, used only for the wa.me deep link shown to users (no prefix).

```text
WHATSAPP_ACCOUNT_SID=
WHATSAPP_AUTH_TOKEN=
WHATSAPP_FROM_NUMBER=whatsapp:+14155238886
WHATSAPP_BOT_NUMBER=
WHATSAPP_SANDBOX_JOIN_CODE=
WHATSAPP_WEBHOOK_BASE_URL=
```

## LLM

PRANA uses OpenRouter as the primary hosted LLM provider and Ollama as the local fallback.

```text
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=
```

The LLM is not responsible for final risk scoring. It should only:

- understand WhatsApp messages,
- extract structured sleep/recovery check-in fields,
- draft user-friendly replies,
- support translation/localization.

The Python backend remains responsible for deterministic scoring, alert thresholds, and escalation rules.

## Local Verification

Run deterministic formula tests:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Compile core backend modules:

```powershell
.\.venv\Scripts\python.exe -m py_compile data_fetcher.py ha_aqi_calculator.py rds_calculator.py ccri_calculator.py prana_system.py backend\main.py backend\llm.py
```
