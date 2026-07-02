"""LLM adapter for PRANA WhatsApp conversations.

OpenRouter is the primary hosted provider. Ollama is the local fallback.
The scoring engine should remain deterministic; this adapter is for language
understanding, response drafting, and structured extraction only.

Superseded by framework.ai; retained until all callers migrated.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests

from prana.config import (
    LLM_PROVIDER,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    OPENROUTER_MODEL,
)
from backend.logger import get_logger

from framework.ai.factory import build_provider
from framework.config.settings import FrameworkSettings
from framework.ai.base import Message, Role

_log = get_logger("llm")


@dataclass
class LLMMessage:
    role: str
    content: str


class LLMClient:
    def __init__(
        self,
        provider: str = LLM_PROVIDER,
        openrouter_api_key: str = OPENROUTER_API_KEY,
        openrouter_base_url: str = OPENROUTER_BASE_URL,
        openrouter_model: str = OPENROUTER_MODEL,
        ollama_base_url: str = OLLAMA_BASE_URL,
        ollama_model: str = OLLAMA_MODEL,
    ):
        self.provider = provider
        self.openrouter_api_key = openrouter_api_key
        self.openrouter_base_url = openrouter_base_url.rstrip("/")
        self.openrouter_model = openrouter_model
        self.ollama_base_url = ollama_base_url.rstrip("/")
        self.ollama_model = ollama_model

    def chat(self, messages: List[LLMMessage], temperature: float = 0.2) -> str:
        """Return a model response, preferring OpenRouter with Ollama fallback."""
        if self.provider == "ollama":
            return self._chat_ollama(messages, temperature)

        try:
            return self._chat_openrouter(messages, temperature)
        except Exception as error:
            if self.ollama_model:
                _log.warning("OpenRouter failed, falling back to Ollama: %s", error)
                return self._chat_ollama(messages, temperature)
            raise

    def extract_sleep_checkin(self, user_message: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Extract sleep check-in fields and apply dynamic profile updates if detected."""
        normalized = user_message.strip().lower()
        
        result = {}
        # ... logic for simple numbered replies ...
        if normalized in {"1", "comfortable", "slept comfortably", "cool enough"}:
            result = {
                "sleep_environment": "comfortable", "sleep_quality": "good",
                "cooling_issue": False, "power_issue": False, "confidence": "high",
            }
        elif normalized in {"2", "warm", "warm but manageable", "manageable"}:
            result = {
                "sleep_environment": "warm_manageable", "sleep_quality": "moderate",
                "cooling_issue": False, "power_issue": False, "confidence": "high",
            }
        elif normalized in {"3", "too hot", "too hot to sleep", "too hot to sleep well"}:
            result = {
                "sleep_environment": "too_hot", "sleep_quality": "poor",
                "cooling_issue": True, "power_issue": False, "confidence": "high",
            }
        elif normalized in {"4", "power cut", "no fan", "fan issue", "ac issue", "fan/ac or power issue"}:
            result = {
                "sleep_environment": "cooling_unavailable", "sleep_quality": "poor",
                "cooling_issue": True, "power_issue": True, "confidence": "high",
            }
        else:
            provider = build_provider(FrameworkSettings())
            resp = provider.chat([
                Message(Role.SYSTEM, (
                    "Extract PRANA sleep recovery check-in data. Return ONLY compact JSON "
                    "with the following fields:\n"
                    "- sleep_environment: 'comfortable', 'warm_manageable', 'too_hot', 'cooling_unavailable'\n"
                    "- sleep_quality: 'good', 'moderate', 'poor'\n"
                    "- cooling_issue: boolean\n"
                    "- power_issue: boolean\n"
                    "- profile_updates: Optional dict with keys like 'floor_level' ('top' or 'other'), 'fan' (boolean), "
                    "'windows_open' (boolean), 'ac' (boolean) if the user implies a change in their house/setup.\n"
                    "- confidence: 'high' or 'low'.")),
                Message(Role.USER, user_message),
            ], temperature=0)
            
            import json
            content = resp.content.strip()
            if content.startswith("```json"):
                content = content.replace("```json", "", 1).replace("```", "", 1).strip()
            elif content.startswith("```"):
                content = content.replace("```", "", 2).strip()

            try:
                result = json.loads(content)
            except Exception:
                result = {"raw_llm_response": resp.content, "confidence": "low"}

        # --- DYNAMIC PROFILE OVERRIDE ---
        if user_id and result.get("profile_updates"):
            from prana.database import SessionLocal
            from prana.models import UserProfile
            db = SessionLocal()
            try:
                prof = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
                if prof:
                    updates = result["profile_updates"]
                    if 'floor_level' in updates: prof.floor_level = updates['floor_level']
                    if 'fan' in updates: prof.has_fan = updates['fan']
                    if 'windows_open' in updates: prof.windows_open = updates['windows_open']
                    if 'ac' in updates: prof.has_ac = updates['ac']
                    db.commit()
                    _log.info("Applied dynamic profile update for user %s: %s", user_id, updates)
            finally:
                db.close()
                
        return result

    def _chat_openrouter(self, messages: List[LLMMessage], temperature: float) -> str:
        if not self.openrouter_api_key:
            raise RuntimeError("OPENROUTER_API_KEY is not configured")
        if not self.openrouter_model:
            raise RuntimeError("OPENROUTER_MODEL is not configured")

        payload = {
            "model": self.openrouter_model,
            "messages": [message.__dict__ for message in messages],
            "temperature": temperature,
        }
        headers = {
            "Authorization": f"Bearer {self.openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://prana.local",
            "X-Title": "PRANA",
        }
        response = requests.post(
            f"{self.openrouter_base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    def _chat_ollama(self, messages: List[LLMMessage], temperature: float) -> str:
        if not self.ollama_model:
            raise RuntimeError("OLLAMA_MODEL is not configured")

        payload = {
            "model": self.ollama_model,
            "messages": [message.__dict__ for message in messages],
            "options": {"temperature": temperature},
            "stream": False,
        }
        response = requests.post(
            f"{self.ollama_base_url}/api/chat",
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        return data["message"]["content"]


def get_llm_client() -> LLMClient:
    return LLMClient()
