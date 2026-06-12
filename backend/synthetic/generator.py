"""Synthetic claim generator. Samples from YAML pattern files to produce
realistic ? and realistically flawed ? claims.

SYNTHETIC DATA ONLY. Names/addresses via Faker; clinical/billing content
sampled from pattern distributions. No real PHI.
"""
from __future__ import annotations
import random
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from faker import Faker

fake = Faker()
PATTERNS_DIR = Path(__file__).parent / "patterns"


def _load(name: str) -> dict:
    with open(PATTERNS_DIR / name, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


PAYERS = _load("payers.yaml")["payers"]
PROC = _load("procedures.yaml")
PROCEDURES = PROC["procedures"]
DIAGNOSES = PROC["diagnoses"]
DENIALS = _load("denials.yaml")["denials"]

# Defects we deliberately inject so downstream agents have work to do.
DEFECTS = ["missing_modifier", "dx_cpt_mismatch", "inactive_eligibility", "none"]
DEFECT_WEIGHTS = [0.18, 0.18, 0.10, 0.54]  # ~46% of claims carry a defect


@dataclass
class GeneratedClaim:
    patient_name: str
    dob: str
    gender: str
    member_id: str
    synthetic_mrn: str
    payer: dict
    dos: str
    pos: str
    provider_npi: str
    clinical_note: str
    cpt: str
    cpt_charge: float
    modifier: str | None
    icd10: str
    defect: str
    dx_hints: list = field(default_factory=list)


def _weighted_choice(items, weight_key="weight"):
    weights = [i[weight_key] for i in items]
    return random.choices(items, weights=weights, k=1)[0]


def generate_claim() -> GeneratedClaim:
    payer = _weighted_choice(PAYERS)
    procedure = random.choice(PROCEDURES)
    defect = random.choices(DEFECTS, weights=DEFECT_WEIGHTS, k=1)[0]

    # Choose diagnosis: valid pairing unless we're injecting a mismatch.
    if defect == "dx_cpt_mismatch":
        bad_dx = [d["icd10"] for d in DIAGNOSES if d["icd10"] not in procedure["valid_dx"]]
        icd10 = random.choice(bad_dx) if bad_dx else random.choice(procedure["valid_dx"])
    else:
        icd10 = random.choice(procedure["valid_dx"])

    # Modifier logic: if required and we're injecting missing_modifier, omit it.
    if procedure["requires_modifier"]:
        modifier = None if defect == "missing_modifier" else random.choice(["LT", "RT"])
    else:
        modifier = None

    gender = random.choice(["M", "F"])
    return GeneratedClaim(
        patient_name=fake.name_male() if gender == "M" else fake.name_female(),
        dob=fake.date_of_birth(minimum_age=18, maximum_age=90).isoformat(),
        gender=gender,
        member_id=fake.bothify("??########").upper(),
        synthetic_mrn=fake.bothify("MRN-######"),
        payer=payer,
        dos=fake.date_this_year().isoformat(),
        pos="11",  # office
        provider_npi=fake.numerify("##########"),
        clinical_note=f"Patient presents for {procedure['description'].lower()}.",
        cpt=procedure["cpt"],
        cpt_charge=procedure["charge"],
        modifier=modifier,
        icd10=icd10,
        defect=defect,
        dx_hints=[icd10],
    )


def generate_batch(n: int) -> list[GeneratedClaim]:
    return [generate_claim() for _ in range(n)]
