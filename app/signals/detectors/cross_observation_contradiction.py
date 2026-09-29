"""cross_observation_contradiction v2 — protocol-level stance, not spatial truth.

Comparison strategy (explicit):
1. Same ``site_id`` as AnalysisContext.site.
2. ``observed_at`` inside AnalysisContext.time_window.
3. Observation pairs with |Δt| <= ContradictionParams.comparison_window only.
   Pairs further apart describe different visits: no relation of any kind.
4. Per pair, the shared fields: in ContradictionParams.field_codes, present on
   both items, and allowed by ConfirmGate ``FieldSchema`` vocabulary.
5. Pair-level duplicate rule: |Δt| <= duplicate_max_delta AND every shared field
   equal → every shared field is ``duplicates`` (never also ``supports``).
6. Otherwise per shared field: equal → ``supports``; unequal → ``conflicts``.
7. Canonical pair order: min(evidence_id), max(evidence_id). Never emit A↔B twice.

v1 compared every pair in the whole analysis window (up to 120 days) and only
treated Δt == 0 as duplicate, so separate visits months apart were reported as
contradictions.

Insufficient comparable observations → ``insufficient_evidence`` (not contradiction).
"""

from __future__ import annotations

from datetime import timedelta
from itertools import combinations
from typing import Sequence

from app.domain.evidence.enums import RelationType
from app.domain.signal.enums import SignalType
from app.domain.signal.value_objects import DetectorId, DetectorVersion
from app.flags.schema import DEFAULT_SCHEMA, FieldSchema
from app.signals.models import (
    AnalysisContext,
    DetectionStatus,
    EvidenceObservation,
    RelationResult,
    SignalResult,
    canonical_pair,
    sort_observations,
)
from app.signals.params import ContradictionParams

DETECTOR_ID = "cross_observation_contradiction"
DETECTOR_VERSION = "v2"
COMPARISON_RULE = "schema_vocab_normalize_v1"


def format_delta(delta: timedelta) -> str:
    """Human-readable time span used in relation messages and summaries."""
    seconds = int(abs(delta).total_seconds())
    if seconds < 60:
        return "under 1 min"
    if seconds < 3600:
        return f"{seconds // 60} min"
    hours, rem = divmod(seconds, 3600)
    if hours < 48:
        minutes = rem // 60
        return f"{hours} h {minutes} min" if minutes else f"{hours} h"
    return f"{hours // 24} days"


class CrossObservationContradictionDetector:
    """Pairwise protocol comparison of near-simultaneous observations at one site."""

    def __init__(self, schema: FieldSchema | None = None) -> None:
        self._schema = schema or DEFAULT_SCHEMA

    @property
    def detector_id(self) -> DetectorId:
        return DetectorId(DETECTOR_ID)

    @property
    def detector_version(self) -> DetectorVersion:
        return DetectorVersion(DETECTOR_VERSION)

    def analyze(
        self,
        evidence: Sequence[EvidenceObservation],
        context: AnalysisContext,
    ) -> Sequence[SignalResult]:
        params = self._resolve_params(context)
        site_id = context.site.site_id
        window_label = format_delta(params.comparison_window)

        scoped = [
            obs
            for obs in sort_observations(evidence)
            if obs.site.site_id == site_id
            and context.time_window.contains(obs.observed_at)
        ]

        comparable: dict[str, tuple[str, ...]] = {}
        for obs in scoped:
            codes = tuple(
                code
                for code in params.field_codes
                if code in obs.fields
                and self._schema.is_allowed_value(code, obs.fields[code])
            )
            if codes:
                comparable[obs.evidence_id] = codes

        relations: list[RelationResult] = []
        pairs_compared = 0
        pairs_outside_window = 0
        conflicting_pairs = 0
        agreeing_pairs = 0
        duplicate_pairs = 0

        holders = [obs for obs in scoped if obs.evidence_id in comparable]
        # Deterministic pairwise: combinations over already-sorted holders.
        for a, b in combinations(holders, 2):
            left, right = canonical_pair(a, b)
            shared = tuple(
                code
                for code in params.field_codes
                if code in comparable[left.evidence_id]
                and code in comparable[right.evidence_id]
            )
            if not shared:
                continue
            delta = abs(left.observed_at - right.observed_at)
            if delta > params.comparison_window:
                pairs_outside_window += 1
                continue
            pairs_compared += 1
            pair_relations = self._compare_pair(left, right, shared, delta, params)
            types = {r.relation_type for r in pair_relations}
            if RelationType.CONFLICTS in types:
                conflicting_pairs += 1
            elif RelationType.DUPLICATES in types:
                duplicate_pairs += 1
            else:
                agreeing_pairs += 1
            relations.extend(pair_relations)

        # Stable relation order: field → left_ref → right_ref → type.
        relations.sort(
            key=lambda r: (
                r.field_code,
                r.left_ref,
                r.right_ref,
                r.relation_type.value,
            )
        )

        cited = tuple(obs.evidence_id for obs in holders)

        if len(comparable) < params.minimum_comparable_observations:
            summary = (
                "Insufficient comparable observations for cross-observation "
                f"contradiction analysis at site {site_id}: "
                f"{len(comparable)}/{params.minimum_comparable_observations} "
                "with controlled-vocabulary fields in scope."
            )
            return (
                SignalResult(
                    status=DetectionStatus.INSUFFICIENT_EVIDENCE,
                    detector_id=self.detector_id,
                    detector_version=self.detector_version,
                    signal_type=SignalType.INSUFFICIENT_EVIDENCE,
                    site=context.site,
                    time_window=context.time_window,
                    summary=summary,
                    metrics={
                        "comparable_observation_count": len(comparable),
                        "comparison_window_seconds": (
                            params.comparison_window.total_seconds()
                        ),
                        "conflict_count": 0,
                        "duplicate_count": 0,
                        "minimum_comparable_observations": (
                            params.minimum_comparable_observations
                        ),
                        "relation_count": 0,
                        "support_count": 0,
                    },
                    evidence_ids=cited,
                    explanation={
                        "reason": "insufficient_comparable_observations",
                        "site_id": site_id,
                    },
                    relations=(),
                ),
            )

        conflict_count = sum(
            1 for r in relations if r.relation_type is RelationType.CONFLICTS
        )
        support_count = sum(
            1 for r in relations if r.relation_type is RelationType.SUPPORTS
        )
        duplicate_count = sum(
            1 for r in relations if r.relation_type is RelationType.DUPLICATES
        )

        metrics = {
            "agreeing_pair_count": agreeing_pairs,
            "comparable_observation_count": len(comparable),
            "comparison_window_seconds": params.comparison_window.total_seconds(),
            "conflict_count": conflict_count,
            "conflicting_pair_count": conflicting_pairs,
            "duplicate_count": duplicate_count,
            "duplicate_max_delta_seconds": params.duplicate_max_delta.total_seconds(),
            "duplicate_pair_count": duplicate_pairs,
            "field_codes": list(params.field_codes),
            "minimum_comparable_observations": params.minimum_comparable_observations,
            "pairs_compared": pairs_compared,
            "pairs_outside_comparison_window": pairs_outside_window,
            "relation_count": len(relations),
            "support_count": support_count,
        }

        if conflict_count > 0:
            conflict_fields = sorted(
                {
                    r.field_code
                    for r in relations
                    if r.relation_type is RelationType.CONFLICTS
                }
            )
            summary = (
                "Protocol-level disagreements were found between observations "
                f"at site {site_id} recorded within {window_label} of each other "
                f"for field(s): {', '.join(conflict_fields)}. "
                f"Pairs compared={pairs_compared}, disagreeing={conflicting_pairs}, "
                f"agreeing={agreeing_pairs}, duplicates={duplicate_pairs}."
            )
            return (
                SignalResult(
                    status=DetectionStatus.SIGNAL,
                    detector_id=self.detector_id,
                    detector_version=self.detector_version,
                    signal_type=SignalType.CONTRADICTION,
                    site=context.site,
                    time_window=context.time_window,
                    summary=summary,
                    metrics=metrics,
                    evidence_ids=cited,
                    explanation={
                        "comparison_rule": COMPARISON_RULE,
                        "comparison_window_seconds": (
                            params.comparison_window.total_seconds()
                        ),
                        "conflict_fields": conflict_fields,
                        "site_id": site_id,
                    },
                    relations=tuple(relations),
                ),
            )

        if pairs_compared == 0:
            summary = (
                f"No two observations at site {site_id} were recorded within "
                f"{window_label} of each other; no same-visit comparison was possible."
            )
        else:
            summary = (
                f"No protocol contradictions at site {site_id} between observations "
                f"recorded within {window_label} of each other. "
                f"Pairs compared={pairs_compared}, agreeing={agreeing_pairs}, "
                f"duplicates={duplicate_pairs}."
            )
        return (
            SignalResult(
                status=DetectionStatus.NO_SIGNAL,
                detector_id=self.detector_id,
                detector_version=self.detector_version,
                signal_type=None,
                site=context.site,
                time_window=context.time_window,
                summary=summary,
                metrics=metrics,
                evidence_ids=cited,
                explanation={
                    "comparison_rule": COMPARISON_RULE,
                    "comparison_window_seconds": params.comparison_window.total_seconds(),
                    "site_id": site_id,
                },
                relations=tuple(relations),
            ),
        )

    def _compare_pair(
        self,
        left: EvidenceObservation,
        right: EvidenceObservation,
        shared: tuple[str, ...],
        delta: timedelta,
        params: ContradictionParams,
    ) -> list[RelationResult]:
        normalized = {
            code: (
                self._schema.normalize_value(left.fields[code]),
                self._schema.normalize_value(right.fields[code]),
            )
            for code in shared
        }
        is_duplicate = delta <= params.duplicate_max_delta and all(
            nl == nr for nl, nr in normalized.values()
        )
        gap = format_delta(delta)
        site_id = left.site.site_id

        out: list[RelationResult] = []
        for code in shared:
            norm_l, norm_r = normalized[code]
            if is_duplicate:
                relation = RelationType.DUPLICATES
                rationale = "same_vocab_values_within_duplicate_delta"
                message = (
                    f"Two observations at site {site_id} recorded {gap} apart "
                    f"report identical values on every compared field "
                    f"({code}: {norm_l}); treated as one duplicate submission, "
                    f"not independent corroboration."
                )
            elif norm_l == norm_r:
                relation = RelationType.SUPPORTS
                rationale = "same_vocab_value_corroboration"
                message = (
                    f"Two observations at site {site_id} recorded {gap} apart "
                    f"report the same {code} value ({norm_l}); treated as "
                    f"supporting evidence."
                )
            else:
                relation = RelationType.CONFLICTS
                rationale = "vocab_value_mismatch"
                message = (
                    f"Two observations at the same site recorded {gap} apart "
                    f"report different values for {code}: one reports {norm_l} "
                    f"and one reports {norm_r}."
                )
            out.append(
                RelationResult(
                    relation_type=relation,
                    left_ref=left.evidence_id,
                    right_ref=right.evidence_id,
                    rationale_code=rationale,
                    message=message,
                    field_code=code,
                    value_left=norm_l,
                    value_right=norm_r,
                    observed_at_left=left.observed_at,
                    observed_at_right=right.observed_at,
                    comparison_rule=COMPARISON_RULE,
                )
            )
        return out

    def _resolve_params(self, context: AnalysisContext) -> ContradictionParams:
        raw = context.param("cross_observation_contradiction")
        if raw is None:
            return ContradictionParams()
        if isinstance(raw, ContradictionParams):
            return raw
        return ContradictionParams.from_mapping(raw)
