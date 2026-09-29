"""P1.4 — one forbidden-claim screen, adversarial cases."""

from __future__ import annotations

import pytest

from app.ai import claim_safety
from app.ai.claim_safety import (
    contains_forbidden_claim,
    forbidden_claim_categories,
    unknown_id_references,
)


@pytest.mark.parametrize(
    "text, category",
    [
        # Previously leaked through the keyword lists.
        ("suggests sewage overflow", "causality"),
        ("E. coli levels may be elevated", "pathogen"),
        ("likely unsafe for swimming", "health"),
        ("appears toxic", "toxicity"),
        ("p0llution detected", "contamination"),
        # Obfuscation / normalization.
        ("POLLUTION DETECTED!!!", "contamination"),
        ("po11uted stream", "contamination"),
        ("c0ntam1nated", "contamination"),
        ("e.coli", "pathogen"),
        ("E-Coli present", "pathogen"),
        ("P A T H O G E N".replace(" ", ""), "pathogen"),
        ("t0xic bloom", "toxicity"),
        # Categories.
        ("Foam was caused by a factory upstream.", "causality"),
        ("Consistent with a discharge event.", "causality"),
        ("points to illegal dumping", "causality"),
        ("combined sewer overflow likely", "causality"),
        ("The water is safe.", "health"),
        ("safe to swim", "health"),
        ("poses a health risk", "health"),
        ("possible disease outbreak", "health"),
        ("coliform bacteria", "pathogen"),
        ("cyanobacteria bloom", "pathogen"),
        ("poisoning risk", "toxicity"),
        ("diagnosed as degraded", "diagnosis"),
        ("trust score 0.8", "scores"),
        ("90% confidence in the shift", "scores"),
        ("confidence level of 85%", "scores"),
        ("water quality index is poor", "scores"),
        ("BMWP indicates", "lab_indicators"),
        ("AMR genes", "lab_indicators"),
        ("Issue an alert to residents", "alerts"),
        ("An alert should be issued", "alerts"),
    ],
)
def test_forbidden_claims_detected(text: str, category: str) -> None:
    assert category in forbidden_claim_categories(text), text
    assert contains_forbidden_claim(text)


@pytest.mark.parametrize(
    "text",
    [
        "Confidence is low",
        "Confidence is low with two observations.",
        "No alert needed.",
        "Two citizens reported a sewage smell on different days.",
        "Foam moved from absent to abundant between windows.",
        "Restates SYSTEM ANALYSIS only; not a diagnostic conclusion.",
        "Non-diagnostic restatement of the brief.",
        "Evidence is insufficient; request a repeat protocol observation.",
        "Riparian cover 0-25 vs 25-50 differs between reports.",
        "Results from the detectors show one conflict.",
        "",
        None,
    ],
)
def test_safe_restatements_pass(text) -> None:
    assert not contains_forbidden_claim(text), text


def test_unknown_id_references() -> None:
    known = frozenset({"sig_1", "fix_a_01", "run_x", "a" * 32})
    assert unknown_id_references("sig_1 and fix_a_01 on run_x", known) == frozenset()
    assert unknown_id_references(f"packet {'a' * 32}", known) == frozenset()
    assert unknown_id_references("see sig_2", known) == {"sig_2"}
    assert unknown_id_references(f"packet {'b' * 32}", known) == {"b" * 32}
    # Hashes (64 hex) are not packet-id shaped.
    assert unknown_id_references("hash " + "c" * 64, known) == frozenset()


def test_single_module_used_everywhere() -> None:
    import app.ai.investigation_validate as inv
    import app.ai.validate as val
    import app.web.investigation_routes as routes

    assert inv.contains_forbidden_claim is claim_safety.contains_forbidden_claim
    assert val.contains_forbidden_claim is claim_safety.contains_forbidden_claim
    assert not hasattr(routes, "PROHIBITED_CLAIM_SNIPPETS")
    assert not hasattr(inv, "_FORBIDDEN_PHRASES")
    assert not hasattr(val, "_PROHIBITED_TOKENS")
