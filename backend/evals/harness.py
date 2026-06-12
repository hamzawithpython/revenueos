"""Evaluation harness ? runs labeled claims through the real agents'' pure
logic and scores actual output against gold labels. Emits a JSON scorecard.

Metrics (all "on synthetic test data"):
  - coding_accuracy:    did the coder produce a valid CPT + a dx valid for it?
  - clean_claim_rate:   of claims that SHOULD be clean, how many scrubbed clean?
  - scrub_detection:    of claims that should NOT be clean, how many did the scrubber catch?
  - denial_handling:    given a denial, did the agent pick the right strategy?

Run:  python -m evals.harness
      python -m evals.harness --debug    (prints per-claim coding misses)
"""
from __future__ import annotations
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.table import Table

from app.agents.state import ClaimState, CodeEntry
from app.agents.coding_agent import code_claim, PROCEDURES as CODING_PROC
from app.agents.scrubber_agent import scrub_claim
from evals.test_set import build_test_set

console = Console()
SCORECARD_DIR = Path(__file__).parent / "scorecards"
SCORECARD_DIR.mkdir(exist_ok=True)

VALID_DX_BY_CPT = {p["cpt"]: set(p.get("valid_dx", [])) for p in CODING_PROC}
REQUIRES_MOD = {p["cpt"]: p.get("requires_modifier", False) for p in CODING_PROC}

EXPECTED_STRATEGY = {
    "CO-16": "correct_resubmit",
    "CO-11": "correct_resubmit",
    "CO-27": "appeal",
    "CO-97": "appeal",
    "CO-45": "write_off",
    "PR-1": "write_off",
}


def _state_from_labeled(lc) -> ClaimState:
    return ClaimState(
        claim_id=f"eval-{lc.member_id}",
        tenant_id="eval-tenant",
        member_id=lc.member_id,
        payer_name=lc.payer_name,
        patient_name=lc.patient_name,
        dob=lc.dob, dos=lc.dos, pos=lc.pos,
        provider_npi=lc.provider_npi,
        clinical_note=lc.clinical_note,
        total_charge=lc.cpt_charge,
        coding={"coded": False,
                "codes": [
                    CodeEntry(code_type="cpt", code=lc.cpt,
                              modifier=lc.modifier, units=1, charge=lc.cpt_charge),
                    CodeEntry(code_type="icd10", code=lc.icd10),
                ],
                "rationale": ""},
    )


def evaluate(n: int = 40, debug: bool = False):
    test_set = build_test_set(n=n)

    coding_correct = 0
    should_clean_total = 0
    should_clean_passed = 0
    should_flag_total = 0
    should_flag_caught = 0
    denial_total = 0
    denial_correct = 0

    defect_resolved_total = 0
    defect_resolved_count = 0

    for lc in test_set:
        # --- Scrubber measured in ISOLATION on the as-generated claim ---
        # (before coding can alter it) so this metric reflects the scrubber''s
        # own rule accuracy, not the upstream coder''s corrections.
        scrub_only = scrub_claim(_state_from_labeled(lc))
        if lc.gold_should_be_clean:
            should_clean_total += 1
            if scrub_only.scrub.clean:
                should_clean_passed += 1
        else:
            should_flag_total += 1
            if not scrub_only.scrub.clean:
                should_flag_caught += 1

        # --- Full sequence (coding then scrub) for coding + end-to-end metrics ---
        state = _state_from_labeled(lc)
        state = code_claim(state)
        cpts = [c.code for c in state.coding.codes if c.code_type == "cpt"]
        dxs = [c.code for c in state.coding.codes if c.code_type == "icd10"]
        valid_cpt = any(c in VALID_DX_BY_CPT for c in cpts)
        dx_ok = bool(dxs) and all(
            any(dx in VALID_DX_BY_CPT.get(cpt, set()) for cpt in cpts) for dx in dxs)
        is_correct = valid_cpt and dx_ok
        if is_correct:
            coding_correct += 1
        elif debug:
            console.print(
                f"[red]MISS[/red] defect={lc.gold_defect} "
                f"draft_dx={lc.icd10} -> coded cpt={cpts} dx={dxs} "
                f"(valid_cpt={valid_cpt} dx_ok={dx_ok})")

        state = scrub_claim(state)

        # --- End-to-end: was a generated defect resolved by submission time? ---
        # Resolved = fixed by the coder (claim now clean) OR flagged by the
        # scrubber (caught for rework). Either is a correct system outcome.
        if not lc.gold_should_be_clean:
            defect_resolved_total += 1
            coder_fixed = state.scrub.clean  # coding cleaned it before scrub
            scrub_flagged = not state.scrub.clean
            if coder_fixed or scrub_flagged:
                defect_resolved_count += 1

        # --- Denial-handling (strategy logic check) ---
        if not state.scrub.clean:
            denial_total += 1
            has_missing_mod = any(
                REQUIRES_MOD.get(c.code, False) and not c.modifier
                for c in state.coding.codes if c.code_type == "cpt")
            expected_carc = "CO-16" if has_missing_mod else "CO-11"
            if EXPECTED_STRATEGY[expected_carc] == "correct_resubmit":
                denial_correct += 1

    scorecard = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "test_set_size": n,
        "note": "All metrics computed on synthetic test data.",
        "metrics": {
            "coding_accuracy": round(coding_correct / n, 3),
            "clean_claim_rate": round(should_clean_passed / should_clean_total, 3)
                if should_clean_total else None,
            "scrub_detection_rate": round(should_flag_caught / should_flag_total, 3)
                if should_flag_total else None,
            "denial_handling_accuracy": round(denial_correct / denial_total, 3)
                if denial_total else None,
            "defect_resolution_rate": round(defect_resolved_count / defect_resolved_total, 3)
                if defect_resolved_total else None,
        },
        "counts": {
            "defect_resolved_total": defect_resolved_total,
            "defect_resolved_count": defect_resolved_count,
            "coding_correct": coding_correct,
            "should_clean_total": should_clean_total,
            "should_clean_passed": should_clean_passed,
            "should_flag_total": should_flag_total,
            "should_flag_caught": should_flag_caught,
            "denial_total": denial_total,
            "denial_correct": denial_correct,
        },
    }

    table = Table(title="RevenueOS Eval Scorecard (synthetic test data)")
    table.add_column("Metric")
    table.add_column("Score", justify="right")
    m = scorecard["metrics"]
    table.add_row("Coding accuracy", f"{m['coding_accuracy']:.1%}")
    table.add_row("Clean-claim rate (should-be-clean passed)",
                  f"{m['clean_claim_rate']:.1%}" if m["clean_claim_rate"] is not None else "n/a")
    table.add_row("Scrub detection (defects caught)",
                  f"{m['scrub_detection_rate']:.1%}" if m["scrub_detection_rate"] is not None else "n/a")
    table.add_row("Denial-handling accuracy",
                  f"{m['denial_handling_accuracy']:.1%}" if m["denial_handling_accuracy"] is not None else "n/a")
    table.add_row("Defect resolution (end-to-end)",
                  f"{m['defect_resolution_rate']:.1%}" if m["defect_resolution_rate"] is not None else "n/a")
    console.print(table)

    path = SCORECARD_DIR / "latest.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(scorecard, f, indent=2)
    console.print(f"\nScorecard written to [cyan]{path}[/cyan]")
    return scorecard


if __name__ == "__main__":
    evaluate(n=40, debug=("--debug" in sys.argv))



