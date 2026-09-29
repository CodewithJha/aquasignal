"""InvestigationBriefService — read-only presentation of persisted A4 analysis.

Consumes AnalysisRun / EnvironmentalSignal / EvidenceRelation / EvidenceItem
only. Never re-runs SignalEngine, never executes SQL, never invents scores.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.application.errors import ResourceNotFound
from app.application.ports import UnitOfWork
from app.domain.evidence.enums import EvidenceSourceClass, RelationType
from app.domain.evidence.item import EvidenceItem
from app.domain.evidence.relation import EvidenceRelation
from app.domain.investigation.analysis_run import AnalysisRun
from app.domain.investigation.case import InvestigationCase
from app.domain.investigation.decision import HumanDecision
from app.domain.investigation.enums import AnalysisRunStatus
from app.domain.signal.enums import SignalType
from app.domain.signal.environmental import EnvironmentalSignal
from app.domain.observer import UNKNOWN_OBSERVER_LABEL, observer_pseudonym
from app.domain.sites import get_site
from app.flags.schema import DEFAULT_SCHEMA
from app.signals.params import ContradictionParams
from app.signals.vocabulary import canonical_value


@dataclass(frozen=True, slots=True)
class AnalysisListItem:
    """One row on the site analysis history list — counts only, no scores."""

    run_id: str
    started_at: datetime
    finished_at: datetime | None
    status: str
    evidence_count: int
    signal_count: int
    detector_set_version: str
    error_summary: str | None = None
    evidence_origin: str = "NO EVIDENCE"


EVIDENCE_ORIGIN_LABELS: Mapping[str, str] = {
    "synthetic": "SYNTHETIC FIXTURE",
    "finalized": "FINALIZED OBSERVATIONS",
    "public": "PUBLIC SERIES",
}


def _evidence_kind(item: EvidenceItem) -> str:
    if item.source_class is EvidenceSourceClass.FIXTURE or item.is_synthetic:
        return "synthetic"
    if item.source_class is EvidenceSourceClass.CONFIRMGATE_PACKET:
        return "finalized"
    return "public"


def evidence_origin_label(items: Iterable[EvidenceItem]) -> str:
    """Run-level provenance badge: which kinds of evidence the snapshot froze."""
    kinds = {_evidence_kind(i) for i in items}
    if not kinds:
        return "NO EVIDENCE"
    if len(kinds) > 1:
        return "MIXED"
    return EVIDENCE_ORIGIN_LABELS[kinds.pop()]


@dataclass(frozen=True, slots=True)
class EvidenceView:
    """Evidence row for investigation UI — distinct ConfirmGate vs synthetic labels."""

    evidence_id: str
    source_class: str
    source_label: str
    is_synthetic: bool
    observed_at: datetime
    site_id: str
    site_label: str
    fields: Mapping[str, str]
    confirmgate_observation_url: str | None
    license_tag: str
    observer_pseudonym: str = UNKNOWN_OBSERVER_LABEL

    @property
    def short_label(self) -> str:
        if self.source_class == EvidenceSourceClass.CONFIRMGATE_PACKET.value:
            return f"Observation {self.evidence_id[:8]}"
        return self.evidence_id

    @property
    def observer_label(self) -> str:
        if self.is_synthetic:
            return "Synthetic fixture"
        if self.source_class == EvidenceSourceClass.CONFIRMGATE_PACKET.value:
            return self.observer_pseudonym
        return self.source_label


@dataclass(frozen=True, slots=True)
class ContradictionPairView:
    """Side-by-side protocol disagreement — no which-is-wrong, no causality."""

    relation_id: str
    left: EvidenceView
    right: EvidenceView
    message: str
    rationale_code: str
    differing_fields: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SignalView:
    """Persisted detector hypothesis for display (evidence language)."""

    signal_id: str
    signal_type: str
    summary: str
    explanation: Mapping[str, Any]
    detector_id: str
    detector_version: str
    window_start: datetime
    window_end: datetime
    evidence_ids: tuple[str, ...]
    evidence_count: int
    metrics: Mapping[str, Any]
    is_insufficient: bool
    temporal_points: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True, slots=True)
class StanceCounts:
    """Supporting / conflicting / insufficient — never a confidence %."""

    supporting: int
    conflicting: int
    insufficient: int
    duplicates: int


@dataclass(frozen=True, slots=True)
class FieldComparison:
    """One compared protocol field in an observation pair (original values)."""

    field_code: str
    left_value: str
    right_value: str


@dataclass(frozen=True, slots=True)
class ObservationPairView:
    """Observation-pair outcome aggregated from field-level relations.

    ``outcome``: ``disagree`` (≥1 conflicting field), ``duplicate`` (every
    relation is a duplicate), otherwise ``agree``.
    """

    left: EvidenceView
    right: EvidenceView
    outcome: str
    conflicting_fields: tuple[FieldComparison, ...]
    relation_count: int
    time_delta_seconds: float
    time_delta_label: str


@dataclass(frozen=True, slots=True)
class PairSummary:
    """Observation-pair counts shown in the brief summary — never a score."""

    observations_analysed: int
    pairs_compared: int
    disagreeing_pairs: int
    agreeing_pairs: int
    duplicate_pairs: int
    insufficient_conditions: int
    comparison_window_label: str | None = None


@dataclass(frozen=True, slots=True)
class DetectorVersionView:
    detector_id: str
    detector_version: str


@dataclass(frozen=True, slots=True)
class ReproducibilityView:
    """Copyable analysis identity — how the run was produced."""

    run_id: str
    snapshot_id: str | None
    snapshot_hash: str
    parameters_hash: str
    detector_set_version: str
    status: str
    evidence_count: int
    started_at: datetime
    finished_at: datetime | None
    error_summary: str | None = None
    vocabulary_version: str | None = None


@dataclass(frozen=True, slots=True)
class DecisionView:
    """Persisted HumanDecision as shown on the brief (authoritative, human)."""

    decision_id: str
    decision_code: str
    rationale: str
    actor_type: str
    actor_id: str
    decided_at: datetime


@dataclass(frozen=True, slots=True)
class CaseView:
    """Minimal InvestigationCase display (system analysis vs human review)."""

    case_id: str
    state: str
    analysis_run_id: str
    reproducibility_ref: str
    opened_at: datetime
    window_start: datetime
    window_end: datetime
    signal_count: int
    version: int = 0
    is_terminal: bool = False
    decisions: tuple[DecisionView, ...] = ()


@dataclass(frozen=True, slots=True)
class AnalysisBrief:
    """Primary investigation surface payload."""

    run_id: str
    site_id: str
    site_label: str
    city: str
    status: str
    window_start: datetime | None
    window_end: datetime | None
    evidence_count: int
    signal_count: int
    detector_set_version: str
    stance: StanceCounts
    evidence: tuple[EvidenceView, ...]
    signals: tuple[SignalView, ...]
    contradictions: tuple[ContradictionPairView, ...]
    insufficient_signals: tuple[SignalView, ...]
    supports_messages: tuple[str, ...]
    reproducibility: ReproducibilityView
    run_history: tuple[AnalysisListItem, ...]
    cases: tuple[CaseView, ...]
    no_signal_success: bool
    failed: bool
    failure_message: str | None
    system_analysis_note: str = (
        "SYSTEM ANALYSIS — deterministic detectors; not a human decision."
    )
    human_review_note: str = (
        "HUMAN DECISION — only a human reviewer can record decisions or close "
        "an InvestigationCase. AI advisory cannot."
    )
    pair_summary: PairSummary | None = None
    observation_pairs: tuple[ObservationPairView, ...] = ()
    findings: tuple[str, ...] = ()
    detector_versions: tuple[DetectorVersionView, ...] = ()

    @property
    def disagreeing_pairs(self) -> tuple[ObservationPairView, ...]:
        return tuple(p for p in self.observation_pairs if p.outcome == "disagree")

    @property
    def agreeing_pairs(self) -> tuple[ObservationPairView, ...]:
        return tuple(p for p in self.observation_pairs if p.outcome == "agree")

    @property
    def duplicate_pairs(self) -> tuple[ObservationPairView, ...]:
        return tuple(p for p in self.observation_pairs if p.outcome == "duplicate")

    @property
    def is_synthetic_run(self) -> bool:
        return any(e.is_synthetic for e in self.evidence)


class InvestigationBriefService:
    """Thin read model over A4 persistence ports."""

    def __init__(self, uow_factory: Callable[[], UnitOfWork]) -> None:
        self._uow_factory = uow_factory

    def list_analyses_for_site(self, site_id: str) -> list[AnalysisListItem]:
        site = get_site(site_id)
        with self._uow_factory() as uow:
            runs = uow.analysis_runs.list_for_site(site.site_id)
            items = [self._list_item(uow, run) for run in runs]
            uow.commit()
            return items

    def get_brief(self, run_id: str) -> AnalysisBrief:
        with self._uow_factory() as uow:
            run = uow.analysis_runs.get(run_id)
            if run is None:
                raise ResourceNotFound("analysis_run", run_id)
            brief = self._build_brief(uow, run)
            uow.commit()
            return brief

    def list_signals(self, run_id: str) -> list[SignalView]:
        return list(self.get_brief(run_id).signals)

    def list_evidence(self, run_id: str) -> list[EvidenceView]:
        return list(self.get_brief(run_id).evidence)

    def get_reproducibility(self, run_id: str) -> ReproducibilityView:
        return self.get_brief(run_id).reproducibility

    def _list_item(self, uow: UnitOfWork, run: AnalysisRun) -> AnalysisListItem:
        snap = uow.evidence_snapshots.find_for_hash(
            run.snapshot_hash, near=run.started_at
        )
        evidence_ids = snap.ordered_evidence_ids if snap else ()
        evidence_count = len(evidence_ids)
        origin = evidence_origin_label(uow.evidence_items.require(eid) for eid in evidence_ids)
        signal_count = len(run.signals_produced)
        error = None
        if run.status is AnalysisRunStatus.FAILED and run.error:
            error = _safe_error(run.error)
        return AnalysisListItem(
            run_id=run.run_id,
            started_at=run.started_at,
            finished_at=run.finished_at,
            status=run.status.value,
            evidence_count=evidence_count,
            signal_count=signal_count,
            detector_set_version=run.detector_set_version,
            error_summary=error,
            evidence_origin=origin,
        )

    def _build_brief(self, uow: UnitOfWork, run: AnalysisRun) -> AnalysisBrief:
        snap = uow.evidence_snapshots.find_for_hash(
            run.snapshot_hash, near=run.started_at
        )
        evidence_ids = snap.ordered_evidence_ids if snap else ()
        items = [uow.evidence_items.require(eid) for eid in evidence_ids]
        site_id = run.site_id if run.site_id and run.site_id != "unknown" else None
        if site_id is None:
            site_id = _site_id_from_items(items, snap)
        site = get_site(site_id)

        signals_raw = uow.environmental_signals.list_for_run(run.run_id)
        relations = uow.evidence_relations.list_for_run(run.run_id)
        evidence_views = tuple(
            self._evidence_view(uow, item) for item in items
        )
        evidence_by_id = {e.evidence_id: e for e in evidence_views}

        signal_views = tuple(
            self._signal_view(sig, evidence_by_id) for sig in signals_raw
        )
        insufficient = tuple(s for s in signal_views if s.is_insufficient)
        contradictions = tuple(
            self._contradiction_pair(rel, evidence_by_id)
            for rel in relations
            if rel.relation_type is RelationType.CONFLICTS
            and rel.left_ref in evidence_by_id
            and rel.right_ref in evidence_by_id
        )
        supports = tuple(
            rel.message
            for rel in relations
            if rel.relation_type is RelationType.SUPPORTS
        )
        stance = StanceCounts(
            supporting=sum(
                1 for r in relations if r.relation_type is RelationType.SUPPORTS
            ),
            conflicting=sum(
                1 for r in relations if r.relation_type is RelationType.CONFLICTS
            ),
            insufficient=len(insufficient),
            duplicates=sum(
                1 for r in relations if r.relation_type is RelationType.DUPLICATES
            ),
        )

        window_start, window_end = (
            run.time_window.start,
            run.time_window.end,
        )
        # Prefer run scope; if only a placeholder micro-window, derive from evidence.
        span = (window_end - window_start).total_seconds()
        if span < 0.001:
            derived = _window_from_signals(signals_raw, items)
            if derived[0] is not None:
                window_start, window_end = derived
        cases = tuple(
            self._case_view(
                rec.case,
                version=rec.version,
                decisions=uow.human_decisions.list_for_case(rec.case.case_id),
            )
            for rec in uow.investigation_cases.list_for_site(site.site_id)
            if rec.case.analysis_run_id == run.run_id
        )
        history = tuple(
            self._list_item(uow, r)
            for r in uow.analysis_runs.list_for_site(site.site_id)
        )

        observation_pairs = _observation_pairs(relations, evidence_by_id)
        pair_summary = _pair_summary(
            observation_pairs,
            observations_analysed=len(evidence_ids),
            insufficient_conditions=len(insufficient),
            signals=signal_views,
        )
        detector_versions = tuple(
            sorted(
                {
                    DetectorVersionView(s.detector_id, s.detector_version)
                    for s in signal_views
                },
                key=lambda d: (d.detector_id, d.detector_version),
            )
        )

        failed = run.status is AnalysisRunStatus.FAILED
        no_signal_success = (
            run.status is AnalysisRunStatus.SUCCEEDED
            and len(signals_raw) == 0
            and stance.conflicting == 0
            and len(insufficient) == 0
        )

        repro = ReproducibilityView(
            run_id=run.run_id,
            snapshot_id=snap.snapshot_id if snap else None,
            snapshot_hash=run.snapshot_hash,
            parameters_hash=run.parameters_hash,
            detector_set_version=run.detector_set_version,
            status=run.status.value,
            evidence_count=len(evidence_ids),
            started_at=run.started_at,
            finished_at=run.finished_at,
            error_summary=_safe_error(run.error) if failed else None,
            vocabulary_version=_vocabulary_version(snap),
        )

        return AnalysisBrief(
            run_id=run.run_id,
            site_id=site.site_id,
            site_label=site.display_name,
            city=site.city,
            status=run.status.value,
            window_start=window_start,
            window_end=window_end,
            evidence_count=len(evidence_ids),
            signal_count=len(signals_raw),
            detector_set_version=run.detector_set_version,
            stance=stance,
            evidence=evidence_views,
            signals=signal_views,
            contradictions=contradictions,
            insufficient_signals=insufficient,
            supports_messages=supports,
            reproducibility=repro,
            run_history=history,
            cases=cases,
            no_signal_success=no_signal_success,
            failed=failed,
            failure_message=_safe_error(run.error) if failed else None,
            pair_summary=pair_summary,
            observation_pairs=observation_pairs,
            findings=()
            if failed
            else _findings(observation_pairs, pair_summary, signal_views),
            detector_versions=detector_versions,
        )

    def _evidence_view(self, uow: UnitOfWork, item: EvidenceItem) -> EvidenceView:
        # Prefer normalized fields stored on EvidenceItem (A6); packet fallback for
        # ConfirmGate rows that predate fields_json population.
        fields: dict[str, str] = dict(item.fields)
        observation_url: str | None = None
        observer_label = UNKNOWN_OBSERVER_LABEL
        if item.source_class is EvidenceSourceClass.CONFIRMGATE_PACKET:
            record = uow.packets.get(item.evidence_id)
            if record is not None:
                observer_label = observer_pseudonym(record.packet.observer_ref)
                if not fields:
                    fields = {
                        code: str(fv.value)
                        for code, fv in record.packet.fields.items()
                    }
            observation_url = f"/observation/{item.evidence_id}"
            source_label = "ConfirmGate finalized observation"
        elif item.source_class is EvidenceSourceClass.FIXTURE or item.is_synthetic:
            source_label = "SYNTHETIC FIXTURE (not live OneAquaHealth data)"
        else:
            source_label = item.source_class.value.replace("_", " ")

        return EvidenceView(
            evidence_id=item.evidence_id,
            source_class=item.source_class.value,
            source_label=source_label,
            is_synthetic=item.is_synthetic,
            observed_at=item.observed_at,
            site_id=item.site.site_id,
            site_label=item.site.display_name,
            fields=fields,
            confirmgate_observation_url=observation_url,
            license_tag=item.license_tag,
            observer_pseudonym=observer_label,
        )

    def _signal_view(
        self,
        signal: EnvironmentalSignal,
        evidence_by_id: Mapping[str, EvidenceView],
    ) -> SignalView:
        is_insufficient = signal.signal_type is SignalType.INSUFFICIENT_EVIDENCE
        temporal_points: list[dict[str, Any]] = []
        if signal.signal_type is SignalType.TEMPORAL_SHIFT:
            temporal_points = _temporal_timeline(signal, evidence_by_id)
        return SignalView(
            signal_id=signal.signal_id,
            signal_type=signal.signal_type.value,
            summary=signal.summary,
            explanation=dict(signal.explanation),
            detector_id=signal.detector_id.value,
            detector_version=signal.detector_version.value,
            window_start=signal.time_window.start,
            window_end=signal.time_window.end,
            evidence_ids=signal.evidence_ids,
            evidence_count=len(signal.evidence_ids),
            metrics=dict(signal.metrics),
            is_insufficient=is_insufficient,
            temporal_points=tuple(temporal_points),
        )

    def _contradiction_pair(
        self,
        rel: EvidenceRelation,
        evidence_by_id: Mapping[str, EvidenceView],
    ) -> ContradictionPairView:
        left = evidence_by_id[rel.left_ref]
        right = evidence_by_id[rel.right_ref]
        differing = tuple(
            sorted(
                {
                    k
                    for k in set(left.fields) | set(right.fields)
                    if left.fields.get(k) != right.fields.get(k)
                }
            )
        )
        return ContradictionPairView(
            relation_id=rel.relation_id,
            left=left,
            right=right,
            message=rel.message,
            rationale_code=rel.rationale_code,
            differing_fields=differing,
        )

    def _case_view(
        self,
        case: InvestigationCase,
        *,
        version: int,
        decisions: Sequence[HumanDecision],
    ) -> CaseView:
        return CaseView(
            case_id=case.case_id,
            state=case.state.value,
            analysis_run_id=case.analysis_run_id,
            reproducibility_ref=case.reproducibility_ref,
            opened_at=case.opened_at,
            window_start=case.window.start,
            window_end=case.window.end,
            signal_count=len(case.signal_ids),
            version=version,
            is_terminal=case.is_terminal,
            decisions=tuple(
                DecisionView(
                    decision_id=d.decision_id,
                    decision_code=d.decision_code.value,
                    rationale=d.rationale,
                    actor_type=d.actor.actor_type.value,
                    actor_id=d.actor.actor_id,
                    decided_at=d.decided_at,
                )
                for d in decisions
            ),
        )


def _safe_error(message: str | None) -> str | None:
    if not message:
        return None
    # Never surface stack traces / SQL internals.
    first = message.strip().splitlines()[0]
    if "Traceback" in first or "sqlite" in first.lower():
        return "Analysis failed. Detectors could not complete for this run."
    return first[:280]


def _vocabulary_version(snap) -> str | None:
    if snap and isinstance(snap.source_manifest, dict):
        version = snap.source_manifest.get("vocabulary_version")
        return str(version) if version else None
    return None


def _site_id_from_items(
    items: Sequence[EvidenceItem],
    snap,
) -> str:
    if items:
        return items[0].site.site_id
    if snap and isinstance(snap.source_manifest, dict):
        sid = snap.source_manifest.get("site_id")
        if sid:
            return str(sid)
    raise ResourceNotFound("analysis_site", "unknown")


def _window_from_signals(
    signals: Sequence[EnvironmentalSignal],
    items: Sequence[EvidenceItem],
) -> tuple[datetime | None, datetime | None]:
    if signals:
        starts = [s.time_window.start for s in signals]
        ends = [s.time_window.end for s in signals]
        return min(starts), max(ends)
    if items:
        times = [i.observed_at for i in items]
        return min(times), max(times)
    return None, None


def _temporal_timeline(
    signal: EnvironmentalSignal,
    evidence_by_id: Mapping[str, EvidenceView],
) -> list[dict[str, Any]]:
    """Ordinal/categorical timeline points from cited evidence — not continuous concentration."""
    field_code = None
    metrics = signal.metrics
    if isinstance(metrics.get("field_code"), str):
        field_code = metrics["field_code"]
    expl = signal.explanation
    if field_code is None and isinstance(expl.get("field_code"), str):
        field_code = expl["field_code"]
    field_code = field_code or "foam"

    points: list[dict[str, Any]] = []
    for eid in signal.evidence_ids:
        ev = evidence_by_id.get(eid)
        if ev is None:
            continue
        raw = ev.fields.get(field_code)
        if raw is None:
            continue
        points.append(
            {
                "evidence_id": eid,
                "observed_at": ev.observed_at.isoformat(),
                "field_code": field_code,
                "value": raw,
                "is_synthetic": ev.is_synthetic,
            }
        )
    points.sort(key=lambda p: (p["observed_at"], p["evidence_id"]))
    return points


_CONTRADICTION_DETECTOR = "cross_observation_contradiction"
_TEMPORAL_DETECTOR = "temporal_baseline_shift"
_PAIR_RELATIONS = frozenset(
    {RelationType.CONFLICTS, RelationType.SUPPORTS, RelationType.DUPLICATES}
)
_OUTCOME_ORDER = {"disagree": 0, "agree": 1, "duplicate": 2}


def format_duration(seconds: float) -> str:
    total = int(abs(seconds))
    if total < 60:
        return "under 1 min"
    if total < 3600:
        return f"{total // 60} min"
    hours, rem = divmod(total, 3600)
    if hours < 48:
        minutes = rem // 60
        return f"{hours} h {minutes} min" if minutes else f"{hours} h"
    return f"{hours // 24} days"


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def _conflicting_fields(
    left: EvidenceView, right: EvidenceView
) -> tuple[FieldComparison, ...]:
    """Fields whose canonical values differ, in detector field order.

    Relations persist only type + message, so field names are re-derived from
    the frozen evidence using the same canonicalization the detectors saw.
    Only fields the detector compares (default field codes, both values in the
    controlled vocabulary) may be reported as disagreements.
    """
    out: list[FieldComparison] = []
    for code in ContradictionParams().field_codes:
        if code not in left.fields or code not in right.fields:
            continue
        if not (
            DEFAULT_SCHEMA.is_allowed_value(code, left.fields[code])
            and DEFAULT_SCHEMA.is_allowed_value(code, right.fields[code])
        ):
            continue
        if canonical_value(code, left.fields[code]) != canonical_value(
            code, right.fields[code]
        ):
            out.append(FieldComparison(code, left.fields[code], right.fields[code]))
    return tuple(out)


def _observation_pairs(
    relations: Sequence[EvidenceRelation],
    evidence_by_id: Mapping[str, EvidenceView],
) -> tuple[ObservationPairView, ...]:
    grouped: dict[tuple[str, str], list[EvidenceRelation]] = {}
    for rel in relations:
        if (
            rel.relation_type in _PAIR_RELATIONS
            and rel.left_ref in evidence_by_id
            and rel.right_ref in evidence_by_id
        ):
            grouped.setdefault((rel.left_ref, rel.right_ref), []).append(rel)

    pairs: list[ObservationPairView] = []
    for (left_id, right_id), rels in grouped.items():
        left = evidence_by_id[left_id]
        right = evidence_by_id[right_id]
        types = {r.relation_type for r in rels}
        if RelationType.CONFLICTS in types:
            outcome = "disagree"
        elif types == {RelationType.DUPLICATES}:
            outcome = "duplicate"
        else:
            outcome = "agree"
        delta = abs((left.observed_at - right.observed_at).total_seconds())
        pairs.append(
            ObservationPairView(
                left=left,
                right=right,
                outcome=outcome,
                conflicting_fields=(
                    _conflicting_fields(left, right) if outcome == "disagree" else ()
                ),
                relation_count=len(rels),
                time_delta_seconds=delta,
                time_delta_label=format_duration(delta),
            )
        )
    pairs.sort(
        key=lambda p: (
            _OUTCOME_ORDER[p.outcome],
            -len(p.conflicting_fields),
            p.time_delta_seconds,
            min(p.left.observed_at, p.right.observed_at),
            p.left.evidence_id,
            p.right.evidence_id,
        )
    )
    return tuple(pairs)


def _signals_from(
    signals: Sequence[SignalView], detector_id: str
) -> list[SignalView]:
    return [s for s in signals if s.detector_id == detector_id]


def _pair_summary(
    pairs: Sequence[ObservationPairView],
    *,
    observations_analysed: int,
    insufficient_conditions: int,
    signals: Sequence[SignalView],
) -> PairSummary:
    window_label = None
    for sig in _signals_from(signals, _CONTRADICTION_DETECTOR):
        seconds = sig.metrics.get("comparison_window_seconds")
        if isinstance(seconds, (int, float)):
            window_label = format_duration(float(seconds))
    return PairSummary(
        observations_analysed=observations_analysed,
        pairs_compared=len(pairs),
        disagreeing_pairs=sum(1 for p in pairs if p.outcome == "disagree"),
        agreeing_pairs=sum(1 for p in pairs if p.outcome == "agree"),
        duplicate_pairs=sum(1 for p in pairs if p.outcome == "duplicate"),
        insufficient_conditions=insufficient_conditions,
        comparison_window_label=window_label,
    )


def _findings(
    pairs: Sequence[ObservationPairView],
    summary: PairSummary,
    signals: Sequence[SignalView],
) -> tuple[str, ...]:
    """Plain-language bullets computed only from persisted signals/relations."""
    out: list[str] = []
    disagree = [p for p in pairs if p.outcome == "disagree"]
    field_order: list[str] = []
    for p in disagree:
        for c in p.conflicting_fields:
            if c.field_code not in field_order:
                field_order.append(c.field_code)
    for code in field_order:
        involved = [
            p
            for p in disagree
            if code in {c.field_code for c in p.conflicting_fields}
        ]
        n = len(involved)
        gap = format_duration(max(p.time_delta_seconds for p in involved))
        verb = "disagrees" if n == 1 else "disagree"
        spread = gap if n == 1 else f"up to {gap}"
        out.append(
            f"{_plural(n, 'observation pair')} {verb} about {code} "
            f"(recorded {spread} apart)."
        )
    unexplained = [p for p in disagree if not p.conflicting_fields]
    if unexplained:
        out.append(
            f"{_plural(len(unexplained), 'observation pair')} disagree on at least "
            "one compared field."
        )
    if summary.agreeing_pairs:
        verb = "agrees" if summary.agreeing_pairs == 1 else "agree"
        out.append(
            f"{_plural(summary.agreeing_pairs, 'observation pair')} {verb} on every "
            "compared field."
        )
    if summary.duplicate_pairs:
        dups = [p for p in pairs if p.outcome == "duplicate"]
        gap = format_duration(max(p.time_delta_seconds for p in dups))
        out.append(
            f"{_plural(summary.duplicate_pairs, 'observation pair')} "
            f"{'looks' if summary.duplicate_pairs == 1 else 'look'} like duplicate "
            f"submissions (identical values; largest time gap {gap})."
        )

    contradiction_insufficient = [
        s for s in _signals_from(signals, _CONTRADICTION_DETECTOR) if s.is_insufficient
    ]
    for sig in contradiction_insufficient:
        have = sig.metrics.get("comparable_observation_count")
        need = sig.metrics.get("minimum_comparable_observations")
        if have is not None and need is not None:
            out.append(
                f"Disagreement check: insufficient evidence ({have} of {need} "
                "comparable observations)."
            )
        else:
            out.append("Disagreement check: insufficient evidence.")
    if not pairs and not contradiction_insufficient and summary.observations_analysed >= 2:
        within = (
            f" (within {summary.comparison_window_label})"
            if summary.comparison_window_label
            else ""
        )
        out.append(
            "Disagreement check: no two observations were recorded close enough "
            f"in time to compare{within}."
        )

    temporal = _signals_from(signals, _TEMPORAL_DETECTOR)
    for sig in temporal:
        m = sig.metrics
        field = m.get("field_code") or sig.explanation.get("field_code") or "foam"
        base_n, recent_n = m.get("baseline_count"), m.get("recent_count")
        if sig.is_insufficient:
            base_req = m.get("minimum_baseline_samples", sig.explanation.get("baseline_required"))
            recent_req = m.get("minimum_recent_samples", sig.explanation.get("recent_required"))
            out.append(
                f"Temporal baseline ({field}): insufficient evidence "
                f"({base_n} of {base_req} baseline and {recent_n} of {recent_req} "
                "recent observations)."
            )
        else:
            out.append(
                f"Temporal baseline ({field}): recent observations differ from the "
                f"baseline ({recent_n} recent vs {base_n} baseline observations)."
            )
    if not temporal:
        out.append("Temporal baseline: no shift detected.")
    return tuple(out)


def list_item_to_api(item: AnalysisListItem) -> dict[str, Any]:
    return _list_api(item)


def signal_to_api(s: SignalView) -> dict[str, Any]:
    return _signal_api(s)


def evidence_to_api(e: EvidenceView) -> dict[str, Any]:
    return _evidence_api(e)


def reproducibility_to_api(r: ReproducibilityView) -> dict[str, Any]:
    return _repro_api(r)


def brief_to_api_dict(brief: AnalysisBrief) -> dict[str, Any]:
    """Typed JSON shape for API — no raw ORM/persistence rows."""
    return {
        "run_id": brief.run_id,
        "site": {
            "site_id": brief.site_id,
            "label": brief.site_label,
            "city": brief.city,
        },
        "status": brief.status,
        "window": {
            "start": brief.window_start.isoformat() if brief.window_start else None,
            "end": brief.window_end.isoformat() if brief.window_end else None,
        },
        "counts": {
            "evidence": brief.evidence_count,
            "signals": brief.signal_count,
            "supporting": brief.stance.supporting,
            "conflicting": brief.stance.conflicting,
            "insufficient": brief.stance.insufficient,
            "duplicates": brief.stance.duplicates,
        },
        "pair_counts": _pair_summary_api(brief.pair_summary),
        "observation_pairs": [_pair_api(p) for p in brief.observation_pairs],
        "findings": list(brief.findings),
        "detector_versions": [
            {"detector_id": d.detector_id, "detector_version": d.detector_version}
            for d in brief.detector_versions
        ],
        "detector_set_version": brief.detector_set_version,
        "no_signal_success": brief.no_signal_success,
        "failed": brief.failed,
        "failure_message": brief.failure_message,
        "system_analysis_note": brief.system_analysis_note,
        "human_review_note": brief.human_review_note,
        "evidence": [_evidence_api(e) for e in brief.evidence],
        "signals": [_signal_api(s) for s in brief.signals],
        "contradictions": [_contradiction_api(c) for c in brief.contradictions],
        "insufficient_signals": [_signal_api(s) for s in brief.insufficient_signals],
        "supports_messages": list(brief.supports_messages),
        "reproducibility": _repro_api(brief.reproducibility),
        "run_history": [_list_api(r) for r in brief.run_history],
        "cases": [
            {
                "case_id": c.case_id,
                "state": c.state,
                "analysis_run_id": c.analysis_run_id,
                "reproducibility_ref": c.reproducibility_ref,
                "opened_at": c.opened_at.isoformat(),
                "window": {
                    "start": c.window_start.isoformat(),
                    "end": c.window_end.isoformat(),
                },
                "signal_count": c.signal_count,
                "version": c.version,
                "decisions": [
                    {
                        "decision_id": d.decision_id,
                        "decision_code": d.decision_code,
                        "rationale": d.rationale,
                        "actor": {"type": d.actor_type, "id": d.actor_id},
                        "decided_at": d.decided_at.isoformat(),
                    }
                    for d in c.decisions
                ],
            }
            for c in brief.cases
        ],
    }


def _list_api(item: AnalysisListItem) -> dict[str, Any]:
    return {
        "run_id": item.run_id,
        "started_at": item.started_at.isoformat(),
        "finished_at": item.finished_at.isoformat() if item.finished_at else None,
        "status": item.status,
        "evidence_count": item.evidence_count,
        "signal_count": item.signal_count,
        "detector_set_version": item.detector_set_version,
        "error_summary": item.error_summary,
        "evidence_origin": item.evidence_origin,
    }


def _evidence_api(e: EvidenceView) -> dict[str, Any]:
    return {
        "evidence_id": e.evidence_id,
        "source_class": e.source_class,
        "source_label": e.source_label,
        "is_synthetic": e.is_synthetic,
        "observed_at": e.observed_at.isoformat(),
        "site_id": e.site_id,
        "site_label": e.site_label,
        "fields": dict(e.fields),
        "confirmgate_observation_url": e.confirmgate_observation_url,
        "license_tag": e.license_tag,
        "observer": e.observer_label,
    }


def _signal_api(s: SignalView) -> dict[str, Any]:
    return {
        "signal_id": s.signal_id,
        "signal_type": s.signal_type,
        "summary": s.summary,
        "explanation": dict(s.explanation),
        "detector_id": s.detector_id,
        "detector_version": s.detector_version,
        "window": {
            "start": s.window_start.isoformat(),
            "end": s.window_end.isoformat(),
        },
        "evidence_ids": list(s.evidence_ids),
        "evidence_count": s.evidence_count,
        "metrics": dict(s.metrics),
        "is_insufficient": s.is_insufficient,
        "temporal_points": list(s.temporal_points),
    }


def _contradiction_api(c: ContradictionPairView) -> dict[str, Any]:
    return {
        "relation_id": c.relation_id,
        "message": c.message,
        "rationale_code": c.rationale_code,
        "differing_fields": list(c.differing_fields),
        "left": _evidence_api(c.left),
        "right": _evidence_api(c.right),
    }


def _pair_summary_api(s: PairSummary | None) -> dict[str, Any] | None:
    if s is None:
        return None
    return {
        "observations_analysed": s.observations_analysed,
        "pairs_compared": s.pairs_compared,
        "disagreeing_pairs": s.disagreeing_pairs,
        "agreeing_pairs": s.agreeing_pairs,
        "duplicate_pairs": s.duplicate_pairs,
        "insufficient_conditions": s.insufficient_conditions,
        "comparison_window": s.comparison_window_label,
    }


def _pair_api(p: ObservationPairView) -> dict[str, Any]:
    return {
        "left_evidence_id": p.left.evidence_id,
        "right_evidence_id": p.right.evidence_id,
        "outcome": p.outcome,
        "time_delta_seconds": p.time_delta_seconds,
        "relation_count": p.relation_count,
        "conflicting_fields": [
            {
                "field_code": c.field_code,
                "left_value": c.left_value,
                "right_value": c.right_value,
            }
            for c in p.conflicting_fields
        ],
    }


def _repro_api(r: ReproducibilityView) -> dict[str, Any]:
    return {
        "run_id": r.run_id,
        "snapshot_id": r.snapshot_id,
        "snapshot_hash": r.snapshot_hash,
        "parameters_hash": r.parameters_hash,
        "detector_set_version": r.detector_set_version,
        "status": r.status,
        "evidence_count": r.evidence_count,
        "started_at": r.started_at.isoformat(),
        "finished_at": r.finished_at.isoformat() if r.finished_at else None,
        "error_summary": r.error_summary,
        "vocabulary_version": r.vocabulary_version,
    }
