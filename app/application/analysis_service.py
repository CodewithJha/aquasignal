"""AnalysisService — AquaSignal orchestration (no detector math, no SQL, no UI).

Pipeline:
  FINALIZED packets + labelled fixtures
    → EvidenceObservation / EvidenceItem
    → canonical vocabulary (detector input only; items keep original values)
    → EvidenceSnapshot
    → SignalEngine (pure)
    → SignalResult → EnvironmentalSignal + EvidenceRelation
    → AnalysisRun (append-only SUCCEEDED | FAILED)
    → optional InvestigationCase (via InvestigationService)
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from typing import Any, Mapping
from uuid import uuid4

from app.application.errors import AnalysisOrchestrationError, PacketNotFound
from app.application.analysis_policy import default_scope_for
from app.application.evidence_gate import (
    observed_at_for_packet,
    require_labelled_fixture,
)
from app.application.evidence_mapping import (
    fixture_to_evidence_item,
    packet_to_evidence_item,
    packet_to_observation,
)
from app.application.params_hash import hash_analysis_parameters
from app.application.ports import UnitOfWork
from app.application.result_mapping import map_signal_results
from app.domain.enums import ActorType
from app.domain.evidence.item import EvidenceItem
from app.domain.evidence.relation import EvidenceRelation
from app.domain.evidence.snapshot import EvidenceSnapshot
from app.domain.investigation.analysis_run import AnalysisRun
from app.domain.provenance_port import ProvenanceIntent
from app.domain.signal.environmental import EnvironmentalSignal
from app.domain.signal.value_objects import TimeWindow
from app.domain.value_objects import Actor, SiteRef
from app.signals.engine import SignalEngine
from app.signals.models import AnalysisContext, EvidenceObservation, sort_observations
from app.signals.vocabulary import (
    VOCABULARY_CANONICALIZATION_VERSION,
    canonicalize_fields,
)

logger = logging.getLogger("aquasignal.analysis")


@dataclass(frozen=True, slots=True)
class AnalysisOutcome:
    """Durable results of one analysis transaction (append-only history)."""

    snapshot: EvidenceSnapshot
    run: AnalysisRun
    signals: tuple[EnvironmentalSignal, ...]
    relations: tuple[EvidenceRelation, ...]
    observations: tuple[EvidenceObservation, ...]
    parameters_hash: str
    detector_set_version: str


class AnalysisService:
    """Coordinates eligibility → snapshot → engine → persist in one UoW."""

    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        *,
        signal_engine: SignalEngine | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._engine = signal_engine or SignalEngine()

    @property
    def signal_engine(self) -> SignalEngine:
        return self._engine

    @property
    def detector_set_version(self) -> str:
        return self._engine.detector_set_version

    def analyze(
        self,
        *,
        site: SiteRef,
        time_window: TimeWindow,
        packet_ids: Sequence[str] = (),
        fixture_observations: Sequence[EvidenceObservation] = (),
        params: Mapping[str, Any] | None = None,
        actor: Actor | None = None,
    ) -> AnalysisOutcome:
        """Run the full A4/A6 pipeline and commit atomically.

        Raises EvidenceNotEligible for draft packets / unlabelled fixtures.
        Never overwrites an existing SUCCEEDED AnalysisRun (new run_id each call).
        Detector/mapping failures after STARTED persist as FAILED (no orphan STARTED).
        """
        system = actor or Actor(ActorType.SYSTEM, "analysis-service")
        params_map = dict(params or {})
        parameters_hash = hash_analysis_parameters(params_map)
        detector_set_version = self._engine.detector_set_version

        with self._uow_factory() as uow:
            observations, items, confirmgate_packet_ids = self._collect_evidence(
                uow,
                packet_ids=packet_ids,
                fixture_observations=fixture_observations,
                site=site,
            )
            if not observations:
                raise AnalysisOrchestrationError(
                    "analysis requires at least one FINALIZED packet or labelled fixture"
                )

            ordered = sort_observations(observations)
            ordered_ids = tuple(o.evidence_id for o in ordered)
            manifest = {
                "site_id": site.site_id,
                "packet_ids": sorted(confirmgate_packet_ids),
                "fixture_ids": sorted(
                    o.evidence_id
                    for o in ordered
                    if o.evidence_id not in confirmgate_packet_ids
                ),
                "n_evidence": len(ordered_ids),
                "vocabulary_version": VOCABULARY_CANONICALIZATION_VERSION,
            }
            snapshot = EvidenceSnapshot.create(
                ordered_evidence_ids=ordered_ids,
                source_manifest=manifest,
                snapshot_id=f"snap_{uuid4().hex[:12]}",
            )

            run = AnalysisRun.start(
                snapshot_hash=snapshot.snapshot_hash,
                detector_set_version=detector_set_version,
                parameters_hash=parameters_hash,
                site_id=site.site_id,
                time_window=time_window,
                run_id=f"run_{uuid4().hex[:12]}",
            )

            # FK save order: items → snapshot → run (STARTED) before engine.
            for item in items:
                uow.evidence_items.save(item)
            uow.evidence_snapshots.save(snapshot)
            uow.analysis_runs.save(run)

            context = AnalysisContext(
                site=site,
                time_window=time_window,
                params=params_map,
            )
            try:
                raw_results = self._engine.analyze(ordered, context)
                signals, relations = map_signal_results(
                    raw_results,
                    analysis_run_id=run.run_id,
                )
            except Exception as exc:
                # Persist FAILED in the same transaction — never leave STARTED.
                err = _safe_run_error(exc)
                logger.warning(
                    "analysis.run_failed",
                    extra={
                        "run_id": run.run_id,
                        "site_id": site.site_id,
                        "error_type": type(exc).__name__,
                    },
                )
                run.fail(error=err)
                uow.analysis_runs.save(run)
                uow.commit()
                return AnalysisOutcome(
                    snapshot=snapshot,
                    run=run,
                    signals=(),
                    relations=(),
                    observations=tuple(ordered),
                    parameters_hash=parameters_hash,
                    detector_set_version=detector_set_version,
                )

            for signal in signals:
                uow.environmental_signals.save(signal)

            run.succeed(signals_produced=tuple(s.signal_id for s in signals))
            uow.analysis_runs.save(run)

            for relation in relations:
                uow.evidence_relations.save(relation)

            intents = self._provenance_intents(
                packet_ids=confirmgate_packet_ids,
                actor=system,
                snapshot=snapshot,
                run=run,
                signal_ids=tuple(s.signal_id for s in signals),
                relation_count=len(relations),
                detector_set_version=detector_set_version,
            )
            if intents:
                uow.provenance.append_many(intents)

            uow.commit()

            return AnalysisOutcome(
                snapshot=snapshot,
                run=run,
                signals=signals,
                relations=relations,
                observations=tuple(ordered),
                parameters_hash=parameters_hash,
                detector_set_version=detector_set_version,
            )

    def analyze_finalized_for_site(
        self,
        *,
        site: SiteRef,
        actor: Actor | None = None,
    ) -> AnalysisOutcome:
        """Analyze every FINALIZED ConfirmGate observation for one site.

        Scope comes from ``analysis_policy.default_scope_for`` (evidence-derived,
        deterministic). Raises AnalysisOrchestrationError when the site has no
        FINALIZED observations. FINALIZED is terminal, so the id list cannot go
        stale before ``analyze`` re-applies the eligibility gate.
        """
        with self._uow_factory() as uow:
            packet_ids = uow.packets.list_finalized_ids_for_site(site.site_id)
            observed = []
            for pid in packet_ids:
                record = uow.packets.get(pid)
                if record is None:
                    raise PacketNotFound(pid)
                observed.append(observed_at_for_packet(record.packet))
        if not packet_ids:
            raise AnalysisOrchestrationError(
                f"no FINALIZED observations for site {site.site_id}; "
                "finalize an observation in ConfirmGate first"
            )
        scope = default_scope_for(observed)
        return self.analyze(
            site=site,
            time_window=scope.time_window,
            packet_ids=packet_ids,
            params=scope.params,
            actor=actor,
        )

    def get_run(self, run_id: str) -> AnalysisRun:
        with self._uow_factory() as uow:
            return uow.analysis_runs.require(run_id)

    def list_signals_for_run(self, run_id: str) -> list[EnvironmentalSignal]:
        with self._uow_factory() as uow:
            return uow.environmental_signals.list_for_run(run_id)

    def list_relations_for_run(self, run_id: str) -> list[EvidenceRelation]:
        with self._uow_factory() as uow:
            return uow.evidence_relations.list_for_run(run_id)

    def get_snapshot(self, snapshot_id: str) -> EvidenceSnapshot:
        with self._uow_factory() as uow:
            return uow.evidence_snapshots.require(snapshot_id)

    def _collect_evidence(
        self,
        uow: UnitOfWork,
        *,
        packet_ids: Sequence[str],
        fixture_observations: Sequence[EvidenceObservation],
        site: SiteRef,
    ) -> tuple[list[EvidenceObservation], list[EvidenceItem], list[str]]:
        observations: list[EvidenceObservation] = []
        items: list[EvidenceItem] = []
        confirmgate_ids: list[str] = []

        for packet_id in packet_ids:
            record = uow.packets.get(packet_id)
            if record is None:
                raise PacketNotFound(packet_id)
            packet = record.packet
            if packet.site.site_id != site.site_id:
                raise AnalysisOrchestrationError(
                    f"packet {packet_id} site {packet.site.site_id} "
                    f"does not match analysis site {site.site_id}"
                )
            obs = packet_to_observation(packet)
            item = packet_to_evidence_item(packet)
            observations.append(_canonical(obs))
            items.append(item)
            confirmgate_ids.append(packet.packet_id)

        for fixture in fixture_observations:
            require_labelled_fixture(fixture)
            if fixture.site.site_id != site.site_id:
                raise AnalysisOrchestrationError(
                    f"fixture {fixture.evidence_id} site {fixture.site.site_id} "
                    f"does not match analysis site {site.site_id}"
                )
            observations.append(_canonical(fixture))
            items.append(fixture_to_evidence_item(fixture))

        return observations, items, confirmgate_ids

    def _provenance_intents(
        self,
        *,
        packet_ids: Sequence[str],
        actor: Actor,
        snapshot: EvidenceSnapshot,
        run: AnalysisRun,
        signal_ids: tuple[str, ...],
        relation_count: int,
        detector_set_version: str,
    ) -> list[ProvenanceIntent]:
        """Append analysis events onto ConfirmGate packets only (FK-safe)."""
        if not packet_ids:
            return []
        after = {
            "snapshot_id": snapshot.snapshot_id,
            "snapshot_hash": snapshot.snapshot_hash,
            "run_id": run.run_id,
            "parameters_hash": run.parameters_hash,
            "detector_set_version": detector_set_version,
            "signal_ids": list(signal_ids),
            "relation_count": relation_count,
            "status": run.status.value,
            "site_id": run.site_id,
        }
        intents: list[ProvenanceIntent] = []
        for pid in packet_ids:
            intents.append(
                ProvenanceIntent(
                    packet_id=pid,
                    action="analysis.snapshot_built",
                    actor=actor,
                    after={
                        "snapshot_id": snapshot.snapshot_id,
                        "snapshot_hash": snapshot.snapshot_hash,
                        "evidence_ids": list(snapshot.ordered_evidence_ids),
                    },
                    rule_engine_version=detector_set_version,
                )
            )
            intents.append(
                ProvenanceIntent(
                    packet_id=pid,
                    action="analysis.run_succeeded",
                    actor=actor,
                    after=after,
                    rule_engine_version=detector_set_version,
                )
            )
        return intents


def _canonical(obs: EvidenceObservation) -> EvidenceObservation:
    """Detector input only; EvidenceItem keeps the original values."""
    return replace(obs, fields=canonicalize_fields(obs.fields))


def _safe_run_error(exc: BaseException) -> str:
    name = type(exc).__name__
    msg = str(exc).strip().splitlines()[0] if str(exc).strip() else name
    if "Traceback" in msg or "sqlite" in msg.lower():
        return f"Analysis failed ({name}). Detectors could not complete for this run."
    return f"{name}: {msg}"[:280]
