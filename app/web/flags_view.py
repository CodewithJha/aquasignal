"""Flag presentation helpers — human-readable groups, no trust scores."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.domain.enums import Severity
from app.domain.value_objects import QualityFlag
from app.web.forms import label_for


@dataclass(frozen=True, slots=True)
class FlagView:
    flag_id: str
    severity: str
    title: str
    guidance: str
    rule_id: str
    blocks_confirm: bool
    blocks_finalize: bool


@dataclass(frozen=True, slots=True)
class FlagGroups:
    needs_correction: tuple[FlagView, ...]
    warnings: tuple[FlagView, ...]

    @property
    def has_blocking(self) -> bool:
        return bool(self.needs_correction)

    @property
    def can_confirm(self) -> bool:
        """UX gate: clear hard + soft before confirm (soft cannot be fixed after)."""
        return not self.needs_correction

    @property
    def can_finalize(self) -> bool:
        return not any(f.blocks_finalize for f in self.needs_correction)


@dataclass(frozen=True, slots=True)
class FindingView:
    """Reviewer finding row — human message + machine identifiers."""

    flag_id: str
    rule_id: str
    code: str
    severity: str
    message: str
    field: str | None
    ruleset: str | None
    overridden: bool
    overridable: bool


def present_findings(
    flags: Iterable[QualityFlag],
    *,
    ruleset_version: str | None = None,
) -> tuple[FindingView, ...]:
    """Structured findings for reviewer detail (not dismissable)."""
    out: list[FindingView] = []
    for flag in flags:
        field = None
        for ref in flag.evidence_refs:
            if ref.startswith("fields."):
                field = ref.split(".", 1)[1]
                break
        out.append(
            FindingView(
                flag_id=flag.flag_id,
                rule_id=flag.rule_id,
                code=flag.code,
                severity=flag.severity.value,
                message=flag.message,
                field=field,
                ruleset=flag.rule_version or ruleset_version,
                overridden=flag.is_overridden,
                overridable=flag.overridable,
            )
        )
    return tuple(out)


def present_flags(flags: Iterable[QualityFlag]) -> FlagGroups:
    needs: list[FlagView] = []
    warns: list[FlagView] = []
    for flag in flags:
        if flag.is_overridden:
            continue
        view = _to_view(flag)
        if flag.severity in {Severity.HARD_REJECT, Severity.SOFT_BLOCK_FINALIZE}:
            needs.append(view)
        else:
            warns.append(view)
    return FlagGroups(needs_correction=tuple(needs), warnings=tuple(warns))


def _to_view(flag: QualityFlag) -> FlagView:
    title = _title_for(flag)
    guidance = _guidance_for(flag)
    return FlagView(
        flag_id=flag.flag_id,
        severity=flag.severity.value,
        title=title,
        guidance=guidance,
        rule_id=flag.rule_id,
        blocks_confirm=flag.severity == Severity.HARD_REJECT,
        blocks_finalize=flag.severity
        in {Severity.HARD_REJECT, Severity.SOFT_BLOCK_FINALIZE},
    )


def _title_for(flag: QualityFlag) -> str:
    code = flag.code
    mapping = {
        "COMPLETENESS_EMPTY": "No stream observations yet",
        "COMPLETENESS_REQUIRED": "Missing a required sensory check",
        "VOCAB_INVALID_VALUE": "Unsupported value",
        "VOCAB_UNKNOWN_CODE": "Unsupported field",
        "NONCLAIM": "Disallowed claim",
        "FHIR_MISSING_EFFECTIVE": "Observation time missing",
        "FHIR_MISSING_LOCATION_ID": "Site identifier missing",
        "MEDIA_REQUIRED": "Photo evidence recommended",
        "DUPLICATE_CANDIDATE": "Possible duplicate submission",
        "GEO_UNSUPPORTED_CITY": "Site not in the OAH demo set",
    }
    if code in mapping:
        return mapping[code]
    # Pull field name from evidence when possible.
    for ref in flag.evidence_refs:
        if ref.startswith("fields."):
            field = ref.split(".", 1)[1]
            return f"Check {label_for(field)}"
    return flag.message.split(".")[0][:80] or code


def _guidance_for(flag: QualityFlag) -> str:
    """Plain-language next step — never a confidence percentage."""
    if flag.code == "COMPLETENESS_EMPTY":
        return (
            "Add foam, water colour, and smell (at minimum) before you confirm. "
            "These are field checks, not lab results."
        )
    if flag.code == "COMPLETENESS_REQUIRED":
        return (
            "Fill every item marked as needed before finalize. "
            "You can still review warnings afterward."
        )
    if flag.code == "VOCAB_INVALID_VALUE":
        return "Choose a listed option. Free-text lab codes are not accepted here."
    if flag.severity == Severity.HARD_REJECT:
        return flag.message
    if flag.severity == Severity.SOFT_BLOCK_FINALIZE:
        return (
            f"{flag.message} Fix this before finalize — confirm freezes the snapshot."
        )
    return flag.message
