"""Non-diagnostic signal types for AquaSignal detectors (no pollution/disease)."""

from __future__ import annotations

from enum import Enum


class SignalType(str, Enum):
    """Hypothesis kinds emitted by detectors — never diagnoses."""

    TEMPORAL_SHIFT = "temporal_shift"
    CONTRADICTION = "contradiction"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    # Catalogued for later phases; A1 has no detector math.
    FREQUENCY_BURST = "frequency_burst"
    CROSS_SOURCE_CONFLICT = "cross_source_conflict"
