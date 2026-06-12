"""HTTP clients for the mock EDI services.

URLs come from settings so the same code runs locally (localhost) or in
the compose network (service names). Phase 3 runs locally.
"""
from __future__ import annotations
import httpx

from app.core.config import settings


def check_eligibility(payload: dict) -> dict:
    url = f"{settings.mock_eligibility_url}/eligibility"
    with httpx.Client(timeout=15) as client:
        r = client.post(url, json=payload)
        r.raise_for_status()
        return r.json()
