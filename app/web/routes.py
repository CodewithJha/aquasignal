"""ConfirmGate web routes — thin HTTP adapters over flow services.

Phase 6: citizen submit → DeterministicFlagEngine → correct → confirm → finalize → FHIR.
Phase 7: reviewer worklist → accept / edit / reject (CONFIRMED ≠ FINALIZED).
No FlagEngine / SQL / FHIR mapping logic in this module.

Handlers are sync ``def`` on purpose: services do blocking SQLite and optional
HTTP AI calls, so FastAPI must run them in its threadpool, not the event loop.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.ai.validate import field_suggestion_rows, unpack_flag_explanations
from app.application.citizen_flow import CitizenFlowError, CitizenFlowService
from app.application.errors import PacketNotFound
from app.application.reviewer_flow import ReviewerFlowService
from app.composition import get_services
from app.demo.config import DemoSettings
from app.domain.enums import REJECTION_REASON_LABELS, WorkflowState
from app.domain.errors import DomainValidationError
from app.domain.observer import observer_pseudonym
from app.domain.sites import get_site, list_sites
from app.fhir.errors import (
    FhirExportRefused,
    MissingRequiredOahData,
    StructuralGuardFailure,
    UnsupportedOahMapping,
)
from app.fhir.versions import (
    OAH_FHIR_MAPPER_VERSION,
    OAH_IG_VERSION,
    PROFILE_LOCATION_OAH,
    PROFILE_OBSERVATION_INDICATORS_OAH,
)
from app.flags.schema import FLAG_RULES_VERSION
from app.web.errors import UserError, map_exception, map_form_errors
from app.web.flags_view import present_findings, present_flags
from app.web.observer_cookie import current_observer_ref
from app.web.forms import (
    fields_from_packet,
    form_catalog,
    label_for,
    parse_submission,
)

logger = logging.getLogger("confirmgate.web")

router = APIRouter()
templates: Jinja2Templates | None = None

DEFAULT_ONE_HEALTH = (
    "Degraded urban streams are associated with One Health pressures described in "
    "the OneAquaHealth Policy Brief (study-level association language). "
    "This observation does not diagnose disease or confirm an outbreak."
)

AUTHORITY_STEPS = (
    ("evaluate", "Pre-confirm quality flags (rules engine)"),
    ("ai", "AI optional — never authority (NullAiAssist OK)"),
    ("confirm", "Human confirm freezes the field snapshot"),
    ("finalize", "Explicit finalize unlocks export"),
    ("fhir", "FHIR Bundle from finalized snapshot only"),
)


def _ai_panel(packet) -> dict[str, Any]:
    """Advisory AI panel context — distinct from deterministic flags."""
    stored = dict(packet.suggestions)
    rows = field_suggestion_rows(stored)
    for row in rows:
        row["label"] = label_for(row["field"])
        current = packet.fields.get(row["field"])
        row["current_value"] = str(current.value) if current else None
    explains = unpack_flag_explanations(stored)
    return {
        "suggestion_rows": rows,
        "flag_explanations": explains,
        "has_advisory": bool(rows or explains),
        "ai_unavailable": False,
    }


def configure_templates(directory: str | Path) -> None:
    global templates
    templates = Jinja2Templates(directory=str(directory))
    templates.env.filters["observer_pseudonym"] = observer_pseudonym
    templates.env.globals["demo_mode"] = DemoSettings.from_env().demo_mode


def _flow() -> CitizenFlowService:
    return get_services().flow


def _reviewer() -> ReviewerFlowService:
    return get_services().reviewer


def page(request: Request, name: str, **ctx: Any) -> HTMLResponse:
    if templates is None:
        raise RuntimeError("Templates not configured")
    status_code = int(ctx.pop("status_code", 200))
    base = {
        "authority_steps": AUTHORITY_STEPS,
        "ai_model": get_services().ai.model_id,
        "flag_engine_name": type(get_services().flag_engine).__name__,
        "flag_engine_version": get_services().flag_engine.version,
        "auth_note": (
            "No multi-user authentication yet — demo reviewer is a composition-root "
            "Actor only; do not treat /review as an access-control boundary."
        ),
        "reviewer_actor_id": _reviewer().reviewer.actor_id,
    }
    base.update(ctx)
    return templates.TemplateResponse(
        request, name, base, status_code=status_code
    )


def _sites_for_template() -> list[dict[str, str]]:
    return [
        {
            "id": s.site_id,
            "label": s.display_name,
            "city": s.city,
        }
        for s in list_sites()
    ]


def _parse_revision(raw: str | None) -> int | None:
    if raw is None or str(raw).strip() == "":
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _photo_name_from_provenance(packet_id: str) -> str | None:
    for event in _flow().list_provenance(packet_id):
        if event.action == "media.noted" and event.after:
            name = event.after.get("photo_name")
            if name:
                return str(name)
    return None


def _observation_context(packet_id: str, *, errors: list[UserError] | None = None) -> dict[str, Any]:
    record = _flow().get(packet_id)
    packet = record.packet
    groups = present_flags(packet.flags)
    state = packet.workflow_state
    ai_panel = _ai_panel(packet)
    # Provenance-based unavailable flag (list once).
    events = _flow().list_provenance(packet_id)
    ai_panel["ai_unavailable"] = any(e.action == "ai.unavailable" for e in events)
    return {
        "packet": packet,
        "packet_id": packet.packet_id,
        "site_label": packet.site.display_name,
        "state": state.value,
        "flag_groups": groups,
        "field_values": fields_from_packet(packet.fields),
        "field_catalog": form_catalog(),
        "notes": packet.notes or "",
        "one_health_sentence": packet.one_health_sentence or DEFAULT_ONE_HEALTH,
        "suggestions": dict(packet.suggestions),
        "ai_panel": ai_panel,
        "can_edit": state == WorkflowState.FLAGGED,
        "can_use_suggestions": state == WorkflowState.FLAGGED,
        "can_confirm": state == WorkflowState.FLAGGED and groups.can_confirm,
        "can_request_review": state == WorkflowState.FLAGGED,
        "can_finalize": state == WorkflowState.CONFIRMED and groups.can_finalize,
        "is_finalized": state == WorkflowState.FINALIZED,
        "is_confirmed": state
        in {WorkflowState.CONFIRMED, WorkflowState.FINALIZED},
        "errors": errors or [],
        "events": events,
        "confirmation_hash": (
            packet.confirmation.content_hash if packet.confirmation else None
        ),
        "revision": record.revision,
    }


def _review_detail_context(
    packet_id: str, *, errors: list[UserError] | None = None
) -> dict[str, Any]:
    record = _reviewer().get(packet_id)
    packet = record.packet
    state = packet.workflow_state
    findings = present_findings(
        packet.flags, ruleset_version=packet.rule_engine_version
    )
    ai_panel = _ai_panel(packet)
    events = _reviewer().list_provenance(packet_id)
    ai_panel["ai_unavailable"] = any(e.action == "ai.unavailable" for e in events)
    return {
        "packet": packet,
        "packet_id": packet.packet_id,
        "site_label": packet.site.display_name,
        "state": state.value,
        "revision": record.revision,
        "findings": findings,
        "field_values": fields_from_packet(packet.fields),
        "field_catalog": form_catalog(),
        "notes": packet.notes or "",
        "photo_name": _photo_name_from_provenance(packet_id),
        "ai_panel": ai_panel,
        "can_act": state == WorkflowState.NEEDS_REVIEW,
        "can_accept": state == WorkflowState.NEEDS_REVIEW
        and not packet.standing_hard_rejects(),
        "rejection_reasons": list(REJECTION_REASON_LABELS.items()),
        "errors": errors or [],
        "events": events,
        "confirmation_hash": (
            packet.confirmation.content_hash if packet.confirmation else None
        ),
    }


@router.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    return upload_form(request)


@router.get("/upload", response_class=HTMLResponse)
def upload_form(request: Request) -> HTMLResponse:
    return page(
        request,
        "upload.html",
        title="ConfirmGate — Submit observation",
        sites=_sites_for_template(),
        field_catalog=form_catalog(),
        errors=[],
        field_values={},
        notes="",
    )


@router.post("/upload")
def upload_post(
    request: Request,
    site: str = Form(...),
    notes: str = Form(""),
    photo: UploadFile | None = File(default=None),
    macrophytes: str = Form(""),
    macrophytes_non_native: str = Form(""),
    riparian_vegetation: str = Form(""),
    riparian_non_native: str = Form(""),
    hydromorphology: str = Form(""),
    foam: str = Form(""),
    colour: str = Form(""),
    smell: str = Form(""),
) -> HTMLResponse:
    form = {
        "site": site,
        "notes": notes,
        "macrophytes": macrophytes,
        "macrophytes_non_native": macrophytes_non_native,
        "riparian_vegetation": riparian_vegetation,
        "riparian_non_native": riparian_non_native,
        "hydromorphology": hydromorphology,
        "foam": foam,
        "colour": colour,
        "smell": smell,
    }
    photo_name = photo.filename if photo and photo.filename else None
    parsed = parse_submission(form, photo_filename=photo_name)
    if not parsed.ok:
        return page(
            request,
            "upload.html",
            title="ConfirmGate — Submit observation",
            sites=_sites_for_template(),
            field_catalog=form_catalog(),
            errors=map_form_errors(parsed.errors),
            field_values={k: str(v.value) for k, v in parsed.fields.items()},
            notes=parsed.notes or "",
            status_code=400,
        )

    try:
        site_ref = get_site(parsed.site_id)
    except DomainValidationError as exc:
        err = map_exception(exc)
        return page(
            request,
            "upload.html",
            title="ConfirmGate — Submit observation",
            sites=_sites_for_template(),
            field_catalog=form_catalog(),
            errors=[err],
            field_values={k: str(v.value) for k, v in parsed.fields.items()},
            notes=parsed.notes or "",
            status_code=err.http_status,
        )

    try:
        record = _flow().submit(
            site=site_ref,
            fields=parsed.fields,
            notes=parsed.notes,
            photo_name=parsed.photo_name,
            observer_ref=current_observer_ref(request),
        )
    except Exception as exc:
        err = map_exception(exc)
        logger.warning("upload.failed", extra={"code": err.code})
        return page(
            request,
            "upload.html",
            title="ConfirmGate — Submit observation",
            sites=_sites_for_template(),
            field_catalog=form_catalog(),
            errors=[err],
            field_values={k: str(v.value) for k, v in parsed.fields.items()},
            notes=parsed.notes or "",
            status_code=err.http_status,
        )

    return RedirectResponse(
        url=f"/observation/{record.packet.packet_id}",
        status_code=303,
    )


@router.get("/observation/{packet_id}", response_class=HTMLResponse)
def observation_get(request: Request, packet_id: str) -> HTMLResponse:
    try:
        ctx = _observation_context(packet_id)
    except PacketNotFound:
        return page(
            request,
            "observation.html",
            title="ConfirmGate — Not found",
            packet=None,
            errors=[UserError("not_found", "Observation not found.", 404)],
            status_code=404,
        )
    return page(
        request,
        "observation.html",
        title="ConfirmGate — Review & confirm",
        **ctx,
    )


@router.post("/observation/{packet_id}/suggestion/accept")
def observation_accept_suggestion(
    request: Request,
    packet_id: str,
    field: str = Form(...),
) -> HTMLResponse:
    try:
        _flow().accept_suggestion(packet_id, field=field)
    except Exception as exc:
        err = map_exception(exc)
        try:
            ctx = _observation_context(packet_id, errors=[err])
        except PacketNotFound:
            return RedirectResponse("/upload", status_code=303)
        return page(
            request,
            "observation.html",
            title="ConfirmGate — Review & confirm",
            status_code=err.http_status,
            **ctx,
        )
    return RedirectResponse(url=f"/observation/{packet_id}", status_code=303)


@router.post("/observation/{packet_id}/suggestion/decline")
def observation_decline_suggestion(
    request: Request,
    packet_id: str,
    field: str = Form(...),
) -> HTMLResponse:
    try:
        _flow().decline_suggestion(packet_id, field=field)
    except Exception as exc:
        err = map_exception(exc)
        try:
            ctx = _observation_context(packet_id, errors=[err])
        except PacketNotFound:
            return RedirectResponse("/upload", status_code=303)
        return page(
            request,
            "observation.html",
            title="ConfirmGate — Review & confirm",
            status_code=err.http_status,
            **ctx,
        )
    return RedirectResponse(url=f"/observation/{packet_id}", status_code=303)


@router.post("/observation/{packet_id}/correct")
def observation_correct(
    request: Request,
    packet_id: str,
    notes: str = Form(""),
    macrophytes: str = Form(""),
    macrophytes_non_native: str = Form(""),
    riparian_vegetation: str = Form(""),
    riparian_non_native: str = Form(""),
    hydromorphology: str = Form(""),
    foam: str = Form(""),
    colour: str = Form(""),
    smell: str = Form(""),
) -> HTMLResponse:
    form = {
        "notes": notes,
        "macrophytes": macrophytes,
        "macrophytes_non_native": macrophytes_non_native,
        "riparian_vegetation": riparian_vegetation,
        "riparian_non_native": riparian_non_native,
        "hydromorphology": hydromorphology,
        "foam": foam,
        "colour": colour,
        "smell": smell,
    }
    parsed = parse_submission(form, require_site=False)
    if not parsed.ok:
        try:
            ctx = _observation_context(
                packet_id, errors=map_form_errors(parsed.errors)
            )
        except PacketNotFound:
            return RedirectResponse("/upload", status_code=303)
        return page(
            request,
            "observation.html",
            title="ConfirmGate — Review & confirm",
            status_code=400,
            **ctx,
        )

    try:
        _flow().correct(packet_id, fields=parsed.fields, notes=parsed.notes)
    except Exception as exc:
        err = map_exception(exc)
        try:
            ctx = _observation_context(packet_id, errors=[err])
        except PacketNotFound:
            return RedirectResponse("/upload", status_code=303)
        return page(
            request,
            "observation.html",
            title="ConfirmGate — Review & confirm",
            status_code=err.http_status,
            **ctx,
        )
    return RedirectResponse(url=f"/observation/{packet_id}", status_code=303)


@router.post("/observation/{packet_id}/confirm")
def observation_confirm(request: Request, packet_id: str) -> HTMLResponse:
    try:
        _flow().confirm(packet_id)
    except Exception as exc:
        err = map_exception(exc)
        try:
            ctx = _observation_context(packet_id, errors=[err])
        except PacketNotFound:
            return RedirectResponse("/upload", status_code=303)
        return page(
            request,
            "observation.html",
            title="ConfirmGate — Review & confirm",
            status_code=err.http_status,
            **ctx,
        )
    return RedirectResponse(url=f"/observation/{packet_id}", status_code=303)


@router.post("/observation/{packet_id}/request-review")
def observation_request_review(
    request: Request, packet_id: str
) -> HTMLResponse:
    """Citizen hand-off to NEEDS_REVIEW — does not confirm or finalize."""
    try:
        _flow().request_review(packet_id)
    except Exception as exc:
        err = map_exception(exc)
        try:
            ctx = _observation_context(packet_id, errors=[err])
        except PacketNotFound:
            return RedirectResponse("/upload", status_code=303)
        return page(
            request,
            "observation.html",
            title="ConfirmGate — Review & confirm",
            status_code=err.http_status,
            **ctx,
        )
    return RedirectResponse(url=f"/review/{packet_id}", status_code=303)


@router.post("/observation/{packet_id}/finalize")
def observation_finalize(
    request: Request,
    packet_id: str,
    one_health_sentence: str = Form(""),
) -> HTMLResponse:
    try:
        _flow().finalize(
            packet_id,
            one_health_sentence=one_health_sentence or DEFAULT_ONE_HEALTH,
        )
    except Exception as exc:
        err = map_exception(exc)
        if isinstance(
            exc,
            (
                StructuralGuardFailure,
                MissingRequiredOahData,
                UnsupportedOahMapping,
                CitizenFlowError,
            ),
        ):
            err = map_exception(exc)
        try:
            ctx = _observation_context(packet_id, errors=[err])
        except PacketNotFound:
            return RedirectResponse("/upload", status_code=303)
        return page(
            request,
            "observation.html",
            title="ConfirmGate — Review & confirm",
            status_code=err.http_status,
            **ctx,
        )
    return RedirectResponse(url=f"/fhir?packet_id={packet_id}", status_code=303)


@router.get("/review", response_class=HTMLResponse)
def review_queue(request: Request) -> HTMLResponse:
    """Phase 7 reviewer worklist — NEEDS_REVIEW only, oldest first."""
    items = _reviewer().list_queue()
    return page(
        request,
        "review.html",
        title="ConfirmGate — Reviewer worklist",
        items=items,
    )


@router.get("/review/{packet_id}", response_class=HTMLResponse)
def review_detail(request: Request, packet_id: str) -> HTMLResponse:
    try:
        ctx = _review_detail_context(packet_id)
    except PacketNotFound:
        return page(
            request,
            "review_detail.html",
            title="ConfirmGate — Not found",
            packet=None,
            errors=[UserError("not_found", "Observation not found.", 404)],
            status_code=404,
        )
    return page(
        request,
        "review_detail.html",
        title="ConfirmGate — Reviewer detail",
        **ctx,
    )


@router.post("/review/{packet_id}/accept")
def review_accept(
    request: Request,
    packet_id: str,
    revision: str = Form(""),
) -> HTMLResponse:
    expected = _parse_revision(revision)
    try:
        _reviewer().accept(packet_id, expected_revision=expected)
    except Exception as exc:
        err = map_exception(exc)
        try:
            ctx = _review_detail_context(packet_id, errors=[err])
        except PacketNotFound:
            return RedirectResponse("/review", status_code=303)
        return page(
            request,
            "review_detail.html",
            title="ConfirmGate — Reviewer detail",
            status_code=err.http_status,
            **ctx,
        )
    return RedirectResponse(url=f"/review/{packet_id}", status_code=303)


@router.post("/review/{packet_id}/reject")
def review_reject(
    request: Request,
    packet_id: str,
    reason_code: str = Form(""),
    explanation: str = Form(""),
    revision: str = Form(""),
) -> HTMLResponse:
    expected = _parse_revision(revision)
    try:
        _reviewer().reject(
            packet_id,
            reason_code=reason_code,
            explanation=explanation or None,
            expected_revision=expected,
        )
    except Exception as exc:
        err = map_exception(exc)
        try:
            ctx = _review_detail_context(packet_id, errors=[err])
        except PacketNotFound:
            return RedirectResponse("/review", status_code=303)
        return page(
            request,
            "review_detail.html",
            title="ConfirmGate — Reviewer detail",
            status_code=err.http_status,
            **ctx,
        )
    return RedirectResponse(url=f"/review/{packet_id}", status_code=303)


@router.post("/review/{packet_id}/edit")
def review_edit(
    request: Request,
    packet_id: str,
    notes: str = Form(""),
    revision: str = Form(""),
    macrophytes: str = Form(""),
    macrophytes_non_native: str = Form(""),
    riparian_vegetation: str = Form(""),
    riparian_non_native: str = Form(""),
    hydromorphology: str = Form(""),
    foam: str = Form(""),
    colour: str = Form(""),
    smell: str = Form(""),
) -> HTMLResponse:
    form = {
        "notes": notes,
        "macrophytes": macrophytes,
        "macrophytes_non_native": macrophytes_non_native,
        "riparian_vegetation": riparian_vegetation,
        "riparian_non_native": riparian_non_native,
        "hydromorphology": hydromorphology,
        "foam": foam,
        "colour": colour,
        "smell": smell,
    }
    parsed = parse_submission(form, require_site=False)
    expected = _parse_revision(revision)
    if not parsed.ok:
        try:
            ctx = _review_detail_context(
                packet_id, errors=map_form_errors(parsed.errors)
            )
        except PacketNotFound:
            return RedirectResponse("/review", status_code=303)
        return page(
            request,
            "review_detail.html",
            title="ConfirmGate — Reviewer detail",
            status_code=400,
            **ctx,
        )
    try:
        _reviewer().edit(
            packet_id,
            fields=parsed.fields,
            notes=parsed.notes,
            expected_revision=expected,
        )
    except Exception as exc:
        err = map_exception(exc)
        try:
            ctx = _review_detail_context(packet_id, errors=[err])
        except PacketNotFound:
            return RedirectResponse("/review", status_code=303)
        return page(
            request,
            "review_detail.html",
            title="ConfirmGate — Reviewer detail",
            status_code=err.http_status,
            **ctx,
        )
    return RedirectResponse(url=f"/review/{packet_id}", status_code=303)


@router.get("/fhir", response_class=HTMLResponse)
def fhir_page(request: Request, packet_id: str | None = None) -> HTMLResponse:
    if not packet_id:
        return page(
            request,
            "fhir.html",
            title="ConfirmGate — FHIR export",
            packet=None,
            export=None,
            meta=None,
            errors=[],
            hint=(
                "Pass ?packet_id=… after human confirm and finalize. "
                "Unconfirmed or CONFIRMED-only packets are refused. "
                "No preliminary Observation path."
            ),
        )
    try:
        record = _flow().get(packet_id)
    except PacketNotFound:
        return page(
            request,
            "fhir.html",
            title="ConfirmGate — FHIR export",
            packet=None,
            export=None,
            meta=None,
            errors=[UserError("not_found", "Observation not found.", 404)],
            status_code=404,
        )

    packet = record.packet
    if packet.workflow_state != WorkflowState.FINALIZED:
        return page(
            request,
            "fhir.html",
            title="ConfirmGate — FHIR export",
            packet=packet,
            export=None,
            meta=None,
            errors=[
                UserError(
                    "export_not_finalized",
                    f"State is {packet.workflow_state.value}. "
                    "Confirm ≠ finalize. Export only after FINALIZED.",
                    409,
                )
            ],
            events=_flow().list_provenance(packet_id),
            status_code=409,
        )

    try:
        _record, result = _flow().export_fhir(packet_id)
        meta = _flow().export_meta(result)
    except (
        FhirExportRefused,
        StructuralGuardFailure,
        MissingRequiredOahData,
        UnsupportedOahMapping,
        CitizenFlowError,
    ) as exc:
        err = map_exception(exc)
        return page(
            request,
            "fhir.html",
            title="ConfirmGate — FHIR export",
            packet=packet,
            export=None,
            meta=None,
            errors=[err],
            events=_flow().list_provenance(packet_id),
            status_code=err.http_status,
        )

    return page(
        request,
        "fhir.html",
        title="ConfirmGate — FHIR export",
        packet=packet,
        export=result,
        meta=meta,
        errors=[],
        events=_flow().list_provenance(packet_id),
        profiles={
            "location": PROFILE_LOCATION_OAH,
            "observation_indicators": PROFILE_OBSERVATION_INDICATORS_OAH,
            "ig_version": OAH_IG_VERSION,
            "mapper_version": OAH_FHIR_MAPPER_VERSION,
            "ruleset_version": FLAG_RULES_VERSION,
        },
        one_health_sentence=packet.one_health_sentence,
    )


@router.get("/fhir/bundle")
def fhir_bundle_json(packet_id: str) -> JSONResponse:
    """Raw Bundle JSON — FINALIZED only."""
    try:
        _record, result = _flow().export_fhir(packet_id)
    except PacketNotFound:
        return JSONResponse({"error": "not_found"}, status_code=404)
    except Exception as exc:
        err = map_exception(exc)
        return JSONResponse(
            {"error": err.code, "detail": err.message},
            status_code=err.http_status,
        )
    return JSONResponse(result.bundle)


@router.post("/fhir")
def fhir_post(packet_id: str = Form(...)) -> JSONResponse:
    return fhir_bundle_json(packet_id)
