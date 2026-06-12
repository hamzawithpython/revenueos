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


def submit_claim(payload: dict) -> dict:
    url = f"{settings.mock_clearinghouse_url}/submit"
    with httpx.Client(timeout=15) as client:
        r = client.post(url, json=payload)
        r.raise_for_status()
        return r.json()


def adjudicate_claim(payload: dict, eligibility_active: bool,
                     patient_responsibility: float) -> dict:
    url = f"{settings.mock_payer_url}/adjudicate"
    params = {
        "eligibility_active": str(eligibility_active).lower(),
        "patient_responsibility": patient_responsibility,
    }
    with httpx.Client(timeout=15) as client:
        r = client.post(url, json=payload, params=params)
        r.raise_for_status()
        return r.json()
