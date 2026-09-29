"""Forbidden-claim text screen for AI output — the one module used everywhere.

This is a secondary guard. The primary boundary is structural (schema, known
signal ids, closed vocabularies, id references checked against the brief).
The screen is deliberately conservative: on any hit the caller discards the
AI output and shows the deterministic result instead. That includes negated
disclaimers ("not a claim that water is safe"), which fail closed.

Text is normalized before matching: Unicode NFKC, lowercase, common leetspeak
digits/symbols mapped to letters, punctuation collapsed to single spaces.
"""

from __future__ import annotations

import re
import unicodedata

_LEET_I = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s"})
_LEET_L = str.maketrans({"0": "o", "1": "l", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s"})
_NON_WORD = re.compile(r"[^a-z0-9%]+")

_SOURCES = r"(sewage|sewer|wastewater|effluent|discharge|overflow|spill|runoff|leak|dumping)"

# Category → regexes matched against normalized text (word-bounded).
FORBIDDEN_CLAIM_PATTERNS: dict[str, tuple[str, ...]] = {
    "causality": (
        r"\bcaused by\b",
        r"\battributable to\b",
        r"\b(sewage|sewer|storm ?water|combined sewer) (overflow|discharge|spill|leak)s?\b",
        rf"\b(suggests?|indicates?|points? to|evidence of|consistent with|likely|probably|because of|due to|source is|sign of)( an?| the)? (illegal )?{_SOURCES}\b",
    ),
    "health": (
        r"\bhealth (risk|hazard|threat|concern|impact)s?\b",
        r"\bpublic health\b",
        r"\b(un ?safe|not safe|dangerous|hazardous|harmful)\b",
        r"\b(is|are|remains?|looks?) safe\b",
        r"\bsafe (to|for) (swim|drink|bath|bathe|fish|wade|play|use)",
        r"\b(illness|sickness|infections?|diseases?|outbreaks?|epidemic)\b",
    ),
    "pathogen": (
        r"\bpathogen(s|ic)?\b",
        r"\be ?coli\b",
        r"\b(fa?ecal )?coliforms?\b",
        r"\b(bacteria|bacterial|enterococc\w*|salmonella|legionella|viral|virus(es)?|norovirus)\b",
        r"\bcyanobacteri\w*\b",
    ),
    "toxicity": (
        r"\btox(ic|ins?|icity)\b",
        r"\bpoison(ous|ed|ing)?\b",
        r"\bmicrocystins?\b",
    ),
    "contamination": (
        r"\bcontaminat\w*\b",
        r"\bpollut\w*\b",
    ),
    "diagnosis": (
        # "diagnostic" stays allowed: "non-diagnostic" is the requested disclaimer.
        r"\bdiagnos(e|es|ed|is|ing)\b",
        r"\bconfirm(s|ed)? (the )?(presence|source|cause)\b",
    ),
    "scores": (
        r"\b(trust|confidence|risk|health|quality|safety) (score|index|rating)s?\b",
        r"\bwater quality index\b",
        r"\bwqi\b",
        r"\b\d+(\.\d+)? ?% ?(confidence|confident|certain|certainty|likely|likelihood|probability|chance)\b",
        r"\b(confidence|certainty|probability|likelihood)( level)?( of| is| at)? \d+(\.\d+)? ?%",
    ),
    "lab_indicators": (
        r"\b(bmwp|amr|args?|antimicrobial|antibiotic resistance|diatoms?|pharmaceuticals?)\b",
    ),
    "alerts": (
        r"\b(issue|raise|send|trigger)( an?| the)? (public )?(alert|warning|advisory)\b",
        r"\balerts? (should|must|will) be (issued|raised|sent)\b",
        r"\balert (the|authorities|residents|public)\b",
        r"\bclose the (river|beach|stream|site)\b",
        r"\bevacuat\w*\b",
    ),
}

_COMPILED: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (category, re.compile(pattern))
    for category, patterns in FORBIDDEN_CLAIM_PATTERNS.items()
    for pattern in patterns
)


def normalize_claim_text(text: str) -> tuple[str, ...]:
    """Normalized variants: digits kept, and leetspeak with ``1`` as ``i`` / ``l``."""
    base = unicodedata.normalize("NFKC", text).lower()
    variants = {base, base.translate(_LEET_I), base.translate(_LEET_L)}
    return tuple(
        sorted(" ".join(_NON_WORD.sub(" ", v).split()) for v in variants)
    )


def forbidden_claim_categories(text: str | None) -> frozenset[str]:
    if not text:
        return frozenset()
    hits: set[str] = set()
    for variant in normalize_claim_text(text):
        padded = f" {variant} "
        for category, pattern in _COMPILED:
            if pattern.search(padded):
                hits.add(category)
    return frozenset(hits)


def contains_forbidden_claim(text: str | None) -> bool:
    return bool(forbidden_claim_categories(text))


# Opaque ids minted by this system (see domain factories) and fixture ids.
_ID_REFERENCE = re.compile(
    r"\b(?:(?:sig|run|snap|case|dec|ev|rel|fix|fx)_[A-Za-z0-9_]+|[0-9a-f]{32})\b"
)


def unknown_id_references(text: str | None, known_ids: frozenset[str]) -> frozenset[str]:
    """Id-shaped tokens in free text that do not exist on the brief."""
    if not text:
        return frozenset()
    return frozenset(m for m in _ID_REFERENCE.findall(text) if m not in known_ids)
