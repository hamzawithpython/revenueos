"""Labeled test-set generator for evaluation.

Produces claims with gold labels baked in: the correct CPT/ICD pairing,
whether the claim should scrub clean, and the expected denial CARC (if any).
The harness scores the live pipeline's actual output against these labels.

SYNTHETIC DATA ONLY.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import random

import yaml
from faker import Faker

fake = Faker()
PATTERNS = Path(__file__).resolve().parents[1] / "synthetic" / "patterns"


def _load():
    with open(PATTERNS / "procedures.yaml", "r", encoding="utf-8") as f:
        proc = yaml.safe_load(f)
    return proc["procedures"], proc["diagnoses"]


PROCEDURES, DIAGNOSES = _load()


@dataclass
class LabeledClaim:
    # Inputs
    member_id: str
    patient_name: str
    dob: str
    gender: str
    payer_name: str
    dos: str
    pos: str
    provider_npi: str
    clinical_note: str
    cpt: str
    cpt_charge: float
    modifier: str | None
    icd10: str
    # Gold labels
    gold_defect: str            # missing_modifier / dx_cpt_mismatch / inactive_eligibility / none
    gold_should_be_clean: bool  # should the scrubber pass it?
    gold_valid_dx: list = field(default_factory=list)  # acceptable dx for this CPT


def _make(defect: str, force_payer: str | None = None) -> LabeledClaim:
    procedure = random.choice(PROCEDURES)
    valid_dx = procedure["valid_dx"]

    if defect == "dx_cpt_mismatch":
        bad = [d["icd10"] for d in DIAGNOSES if d["icd10"] not in valid_dx]
        icd10 = random.choice(bad) if bad else random.choice(valid_dx)
    else:
        icd10 = random.choice(valid_dx)

    if procedure["requires_modifier"]:
        modifier = None if defect == "missing_modifier" else random.choice(["LT", "RT"])
    else:
        # A non-modifier procedure can't carry the missing_modifier defect;
        # caller avoids that pairing.
        modifier = None

    gender = random.choice(["M", "F"])
    clean = defect in ("none", "inactive_eligibility")  # eligibility issues still scrub clean
    return LabeledClaim(
        member_id=fake.bothify("??########").upper(),
        patient_name=fake.name_male() if gender == "M" else fake.name_female(),
        dob=fake.date_of_birth(minimum_age=18, maximum_age=90).isoformat(),
        gender=gender,
        payer_name=force_payer or "Medicare",
        dos=fake.date_this_year().isoformat(),
        pos="11",
        provider_npi=fake.numerify("##########"),
        clinical_note=f"Patient presents for {procedure['description'].lower()}.",
        cpt=procedure["cpt"],
        cpt_charge=procedure["charge"],
        modifier=modifier,
        icd10=icd10,
        gold_defect=defect,
        gold_should_be_clean=clean,
        gold_valid_dx=valid_dx,
    )


def build_test_set(n: int = 40, seed: int = 42) -> list[LabeledClaim]:
    """Balanced labeled set: mix of clean, missing-modifier, and mismatch claims."""
    random.seed(seed)
    Faker.seed(seed)
    out: list[LabeledClaim] = []

    # Distribution: 50% clean, 25% missing modifier, 25% dx/cpt mismatch.
    plan = (["none"] * (n // 2)
            + ["missing_modifier"] * (n // 4)
            + ["dx_cpt_mismatch"] * (n - n // 2 - n // 4))
    random.shuffle(plan)

    for defect in plan:
        if defect == "missing_modifier":
            # Must use a modifier-requiring procedure; retry until we get one.
            while True:
                c = _make("missing_modifier")
                proc = next(p for p in PROCEDURES if p["cpt"] == c.cpt)
                if proc["requires_modifier"]:
                    break
        else:
            c = _make(defect)
        out.append(c)
    return out
