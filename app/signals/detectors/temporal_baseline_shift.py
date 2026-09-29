"""temporal_baseline_shift v1 — evidence change via median + MAD (not diagnosis).

Zero-MAD rule (documented + tested):
    When baseline MAD == 0 (constant ordinal baseline), the comparison threshold
    is exactly **1.0 ordinal unit** (one vocabulary step). ``threshold_multiplier``
    is not applied to a zero scale. This avoids division-by-zero / silent epsilon
    substitution while remaining deterministic.
"""

from __future__ import annotations

from typing import Sequence

from app.domain.signal.enums import SignalType
from app.domain.signal.value_objects import DetectorId, DetectorVersion
from app.signals.models import (
    AnalysisContext,
    DetectionStatus,
    EvidenceObservation,
    SignalResult,
    sort_observations,
)
from app.signals.ordinals import to_ordinal
from app.signals.params import TemporalBaselineParams
from app.signals.stats import (
    finite_float,
    interquartile_range,
    median_absolute_deviation,
    safe_median,
)

DETECTOR_ID = "temporal_baseline_shift"
DETECTOR_VERSION = "v1"

# Explicit zero-MAD threshold (ordinal steps). Do not change without bumping version.
ZERO_MAD_ABSOLUTE_THRESHOLD = 1.0


class TemporalBaselineShiftDetector:
    """Compare recent ordinal median to baseline median using robust scale."""

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

        series: list[tuple[EvidenceObservation, float]] = []
        skipped_invalid = 0
        skipped_other_site = 0
        skipped_missing = 0

        for obs in sort_observations(evidence):
            if obs.site.site_id != site_id:
                skipped_other_site += 1
                continue
            if params.field_code not in obs.fields:
                skipped_missing += 1
                continue
            ordinal = to_ordinal(params.field_code, obs.fields[params.field_code])
            if ordinal is None:
                skipped_invalid += 1
                continue
            series.append((obs, float(ordinal)))

        baseline_pts = [
            (obs, val)
            for obs, val in series
            if params.baseline_window.contains(obs.observed_at)
        ]
        recent_pts = [
            (obs, val)
            for obs, val in series
            if params.recent_window.contains(obs.observed_at)
        ]

        baseline_vals = [v for _, v in baseline_pts]
        recent_vals = [v for _, v in recent_pts]
        # Unique evidence ids from combined windows, ordered by (time, id).
        seen: set[str] = set()
        ordered_ids: list[str] = []
        for obs in sort_observations([p[0] for p in baseline_pts + recent_pts]):
            if obs.evidence_id not in seen:
                seen.add(obs.evidence_id)
                ordered_ids.append(obs.evidence_id)
        cited_ids = tuple(ordered_ids)

        common_metrics = {
            "baseline_count": len(baseline_vals),
            "recent_count": len(recent_vals),
            "field_code": params.field_code,
            "minimum_baseline_samples": params.minimum_baseline_samples,
            "minimum_recent_samples": params.minimum_recent_samples,
            "scale": params.scale,
            "skipped_invalid_vocab": skipped_invalid,
            "skipped_missing_field": skipped_missing,
            "skipped_other_site": skipped_other_site,
            "threshold_multiplier": finite_float(params.threshold_multiplier),
            "zero_mad_absolute_threshold": ZERO_MAD_ABSOLUTE_THRESHOLD,
        }

        if (
            len(baseline_vals) < params.minimum_baseline_samples
            or len(recent_vals) < params.minimum_recent_samples
        ):
            summary = (
                f"Insufficient evidence for temporal comparison of "
                f"{params.field_code}: baseline {len(baseline_vals)}/"
                f"{params.minimum_baseline_samples}, recent {len(recent_vals)}/"
                f"{params.minimum_recent_samples}."
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
                    metrics=common_metrics,
                    evidence_ids=cited_ids,
                    explanation={
                        "baseline_count": len(baseline_vals),
                        "baseline_required": params.minimum_baseline_samples,
                        "field_code": params.field_code,
                        "reason": "insufficient_samples",
                        "recent_count": len(recent_vals),
                        "recent_required": params.minimum_recent_samples,
                    },
                ),
            )

        baseline_median = finite_float(safe_median(baseline_vals))
        recent_median = finite_float(safe_median(recent_vals))
        mad = finite_float(median_absolute_deviation(baseline_vals, baseline_median))
        iqr = (
            finite_float(interquartile_range(baseline_vals))
            if len(baseline_vals) >= 2
            else 0.0
        )

        if params.scale == "mad":
            # Zero-MAD rule: see module docstring.
            if mad == 0.0:
                threshold = ZERO_MAD_ABSOLUTE_THRESHOLD
                threshold_rule = "zero_mad_absolute_ordinal_step"
            else:
                threshold = finite_float(params.threshold_multiplier * mad)
                threshold_rule = "k_times_mad"
            scale_value = mad
        else:
            if iqr == 0.0:
                threshold = ZERO_MAD_ABSOLUTE_THRESHOLD
                threshold_rule = "zero_iqr_absolute_ordinal_step"
            else:
                threshold = finite_float(params.threshold_multiplier * iqr)
                threshold_rule = "k_times_iqr"
            scale_value = iqr

        delta = finite_float(recent_median - baseline_median)
        abs_delta = finite_float(abs(delta))
        # Inclusive: meeting the threshold counts as a shift (needed for
        # zero-MAD absolute ordinal-step rule where |delta|==1.0).
        is_shift = abs_delta >= threshold

        metrics = {
            **common_metrics,
            "baseline_mad": mad,
            "baseline_median": baseline_median,
            "baseline_iqr": iqr,
            "delta": delta,
            "recent_median": recent_median,
            "scale_value": scale_value,
            "threshold": threshold,
            "threshold_rule": threshold_rule,
        }

        explanation = {
            "baseline_window": {
                "end": params.baseline_window.end.isoformat(),
                "start": params.baseline_window.start.isoformat(),
            },
            "delta": delta,
            "field_code": params.field_code,
            "is_shift": is_shift,
            "recent_window": {
                "end": params.recent_window.end.isoformat(),
                "start": params.recent_window.start.isoformat(),
            },
            "threshold": threshold,
            "threshold_rule": threshold_rule,
        }

        if is_shift:
            summary = (
                f"The recent {params.field_code} observations differ from the "
                f"historical baseline by the configured robust threshold. "
                f"Baseline median={baseline_median}, recent median={recent_median}, "
                f"|delta|={abs_delta}, threshold={threshold} "
                f"(rule={threshold_rule}). Baseline n={len(baseline_vals)}, "
                f"recent n={len(recent_vals)}."
            )
            return (
                SignalResult(
                    status=DetectionStatus.SIGNAL,
                    detector_id=self.detector_id,
                    detector_version=self.detector_version,
                    signal_type=SignalType.TEMPORAL_SHIFT,
                    site=context.site,
                    time_window=context.time_window,
                    summary=summary,
                    metrics=metrics,
                    evidence_ids=cited_ids,
                    explanation=explanation,
                ),
            )

        summary = (
            f"No meaningful temporal shift for {params.field_code}: "
            f"baseline median={baseline_median}, recent median={recent_median}, "
            f"|delta|={abs_delta} does not exceed threshold={threshold} "
            f"(rule={threshold_rule}). Baseline n={len(baseline_vals)}, "
            f"recent n={len(recent_vals)}."
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
                evidence_ids=cited_ids,
                explanation=explanation,
            ),
        )

    def _resolve_params(self, context: AnalysisContext) -> TemporalBaselineParams:
        raw = context.param("temporal_baseline_shift")
        if raw is None:
            raise ValueError(
                "AnalysisContext.params['temporal_baseline_shift'] is required"
            )
        if isinstance(raw, TemporalBaselineParams):
            return raw
        return TemporalBaselineParams.from_mapping(raw)
