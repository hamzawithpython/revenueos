"""Thin Groq chat client shared by all agents.

Centralizes model selection, JSON-mode requests, and basic error
handling so agents stay focused on their domain logic.
"""
from __future__ import annotations
import json
from groq import Groq

from app.core.config import settings

_client = Groq(api_key=settings.groq_api_key)


def chat_json(system: str, user: str, model: str | None = None) -> dict:
    """Call Groq expecting a JSON object back. Returns parsed dict.

    Uses JSON mode so the model returns strict JSON. Raises on transport
    errors; callers handle domain-level fallbacks.
    """
    resp = _client.chat.completions.create(
        model=model or settings.llm_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.1,
        response_format={"type": "json_object"},
    )
    content = resp.choices[0].message.content
    return json.loads(content)


def chat_text(system: str, user: str, model: str | None = None) -> str:
    """Call Groq expecting free text back (for appeal letters, etc.)."""
    resp = _client.chat.completions.create(
        model=model or settings.llm_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.2,
    )
    return resp.choices[0].message.content
