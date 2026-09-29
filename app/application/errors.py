"""Application / persistence errors — no raw sqlite messages for callers."""

from __future__ import annotations


class PersistenceError(Exception):
    """Base for durable-store failures visible above infrastructure."""


class PacketNotFound(PersistenceError):
    def __init__(self, packet_id: str) -> None:
        self.packet_id = packet_id
        super().__init__(f"packet not found: {packet_id}")


class DuplicatePacket(PersistenceError):
    def __init__(self, packet_id: str) -> None:
        self.packet_id = packet_id
        super().__init__(f"packet already exists: {packet_id}")


class ConcurrencyConflict(PersistenceError):
    """Optimistic concurrency failure (packet revision or case version)."""

    def __init__(self, entity_id: str, expected_revision: int) -> None:
        self.entity_id = entity_id
        # ConfirmGate callers historically use packet_id.
        self.packet_id = entity_id
        self.expected_revision = expected_revision
        super().__init__(
            f"concurrency conflict for {entity_id} "
            f"(expected revision {expected_revision})"
        )


class PersistenceFailure(PersistenceError):
    """Generic durable-store failure (connection, IO, constraint)."""


class MigrationFailure(PersistenceError):
    """Schema migration could not be applied or verified."""


class ProvenanceAppendFailure(PersistenceError):
    """Append-only provenance write failed (transaction should roll back)."""


class ResourceNotFound(PersistenceError):
    def __init__(self, resource: str, resource_id: str) -> None:
        self.resource = resource
        self.resource_id = resource_id
        super().__init__(f"{resource} not found: {resource_id}")


class DuplicateResource(PersistenceError):
    def __init__(self, resource: str, resource_id: str) -> None:
        self.resource = resource
        self.resource_id = resource_id
        super().__init__(f"{resource} already exists: {resource_id}")


class ForeignKeyViolation(PersistenceError):
    """Referenced parent row missing or child constraint failed."""

    def __init__(self, message: str = "foreign key constraint failed") -> None:
        super().__init__(message)


class ImmutableAnalysisRun(PersistenceError):
    """Terminal AnalysisRun rows (SUCCEEDED/FAILED) must not be overwritten."""

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        super().__init__(f"analysis run is immutable after terminal status: {run_id}")


class SerializationFailure(PersistenceError):
    """JSON / row ↔ domain mapping failed (corrupt or invariant mismatch)."""


class EvidenceNotEligible(Exception):
    """ConfirmGate draft / non-FINALIZED packet (or unlabelled fixture) refused as evidence."""

    def __init__(self, message: str, *, packet_id: str | None = None) -> None:
        self.packet_id = packet_id
        super().__init__(message)


class AnalysisOrchestrationError(Exception):
    """Analysis pipeline failed before durable commit (no math leak into repos)."""
