"""AquaSignal Phase A5 — thin investigation HTTP adapters.

Read-only over InvestigationBriefService. No SQL, no detector math,
no SignalEngine re-run on render.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from app.application.errors import ResourceNotFound
from app.application.investigation_advisory import advisory_to_api, safe_advise
from app.application.investigation_service import parse_decision_code
from app.application.investigation_brief import (
    brief_to_api_dict,
    evidence_to_api,
    list_item_to_api,
    reproducibility_to_api,
    signal_to_api,
)
from app.composition import get_services
from app.domain.errors import DomainValidationError
from app.domain.investigation.enums import DecisionCode
from app.domain.sites import get_site, list_sites
from app.domain.value_objects import Actor, SiteRef
from app.web.errors import UserError, map_exception
from app.web.routes import page

logger = logging.getLogger("aquasignal.web")

router = APIRouter()

INVESTIGATION_AUTHORITY = (
    ("integrity", "ConfirmGate human finalize gates citizen evidence"),
    ("system", "SYSTEM ANALYSIS — versioned detectors on a frozen snapshot"),
    ("stance", "Signals show supports / conflicts / insufficient — not diagnoses"),
    ("advisory", "AI ADVISORY — optional restatement only; never authority"),
    ("human", "HUMAN DECISION — case conclusions require a human (not AI)"),
    ("fhir", "FHIR remains finalize-only on observations — never from signals"),
)

DECISION_CHOICES = (
    (DecisionCode.NOTE.value, "Add review note (case stays open for review)"),
    (DecisionCode.REQUEST_MORE_EVIDENCE.value, "Request more evidence"),
    (DecisionCode.CONCLUDE_INSUFFICIENT.value, "Close: evidence insufficient"),
    (DecisionCode.CONCLUDE_CHANGE_SUSPECTED.value, "Close: change suspected, follow up"),
    (DecisionCode.DISMISS.value, "Dismiss case"),
)


def _brief():
    return get_services().brief


def _copilot():
    return get_services().investigation_copilot


def _investigation_page(request: Request, name: str, **ctx: Any) -> HTMLResponse:
    ctx.setdefault("authority_steps", INVESTIGATION_AUTHORITY)
    ctx.setdefault("investigation_page", True)
    ctx.setdefault(
        "product_line",
        "AquaSignal · Site Investigation Brief",
    )
    return page(request, name, **ctx)


@router.get("/investigate", response_class=HTMLResponse)
def investigate_index(request: Request) -> HTMLResponse:
    """Site picker — defaults narrative to Coimbra for demo."""
    return _investigation_page(
        request,
        "investigate_index.html",
        title="Investigate — AquaSignal",
        sites=_sites(),
        default_site_id="coimbra",
    )


@router.get("/investigate/sites/{site_id}", response_class=HTMLResponse)
def investigate_site_list(request: Request, site_id: str) -> HTMLResponse:
    try:
        site = get_site(site_id)
    except DomainValidationError as exc:
        err = map_exception(exc)
        return _investigation_page(
            request,
            "investigate_empty.html",
            title="Site not found",
            errors=[err],
            status_code=err.http_status,
            heading="Site not found",
            message=str(exc),
        )
    return _site_list_page(request, site)


def _site_list_page(
    request: Request,
    site: SiteRef,
    *,
    errors: list[UserError] | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    rows = _brief().list_analyses_for_site(site.site_id)
    return _investigation_page(
        request,
        "investigate_list.html",
        title=f"Analyses — {site.display_name}",
        site=site,
        analyses=rows,
        empty=not rows,
        errors=errors or [],
        status_code=status_code,
    )


@router.post("/investigate/sites/{site_id}/analyze")
def investigate_site_analyze(request: Request, site_id: str) -> Response:
    """Explicit human-triggered analysis of the site's FINALIZED observations."""
    try:
        site = get_site(site_id)
    except DomainValidationError as exc:
        err = map_exception(exc)
        return _investigation_page(
            request,
            "investigate_empty.html",
            title="Site not found",
            errors=[err],
            status_code=err.http_status,
            heading="Site not found",
            message=str(exc),
        )
    try:
        outcome = get_services().analysis.analyze_finalized_for_site(
            site=site, actor=_reviewer_actor()
        )
    except Exception as exc:
        err = map_exception(exc)
        logger.warning("investigate.analyze_failed", extra={"code": err.code})
        return _site_list_page(request, site, errors=[err], status_code=err.http_status)
    return RedirectResponse(
        url=f"/investigate/analyses/{outcome.run.run_id}", status_code=303
    )


@router.post("/investigate/analyses/{run_id}/cases")
def investigate_open_case(request: Request, run_id: str) -> Response:
    try:
        get_services().investigation.open_case_for_run(
            analysis_run_id=run_id, opened_by=_reviewer_actor()
        )
    except Exception as exc:
        return _detail_error(request, run_id, exc)
    return RedirectResponse(url=f"/investigate/analyses/{run_id}", status_code=303)


@router.post("/investigate/cases/{case_id}/decisions")
def investigate_record_decision(
    request: Request,
    case_id: str,
    decision_code: str = Form(""),
    rationale: str = Form(""),
    expected_version: str = Form(""),
) -> Response:
    """Translate the reviewer form into InvestigationService.record_decision."""
    services = get_services()
    try:
        record = services.investigation.get_case(case_id)
    except ResourceNotFound:
        return _investigation_page(
            request,
            "investigate_empty.html",
            title="Case not found",
            errors=[UserError("not_found", "Investigation case not found.", 404)],
            status_code=404,
            heading="No case",
            message="This investigation case was not found.",
        )
    run_id = record.case.analysis_run_id
    try:
        version = _parse_version(expected_version)
        services.investigation.record_decision(
            case_id=case_id,
            actor=_reviewer_actor(),
            decision_code=parse_decision_code(decision_code),
            rationale=rationale,
            expected_version=version,
        )
    except Exception as exc:
        return _detail_error(request, run_id, exc)
    return RedirectResponse(url=f"/investigate/analyses/{run_id}", status_code=303)


@router.get("/investigate/analyses/{run_id}", response_class=HTMLResponse)
def investigate_detail(request: Request, run_id: str) -> HTMLResponse:
    return _detail_page(request, run_id)


def _detail_page(
    request: Request,
    run_id: str,
    *,
    errors: list[UserError] | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    try:
        brief = _brief().get_brief(run_id)
    except ResourceNotFound:
        return _investigation_page(
            request,
            "investigate_empty.html",
            title="Analysis not found",
            errors=[UserError("not_found", "Analysis run not found.", 404)],
            status_code=404,
            heading="No analysis",
            message="This analysis run was not found. Seed a Coimbra fixture run for the demo.",
        )
    # Render SYSTEM ANALYSIS first; advisory is optional and never blocks the page.
    advisory = safe_advise(_copilot(), brief)
    return _investigation_page(
        request,
        "investigate_detail.html",
        title=f"Analysis {brief.run_id} — {brief.site_label}",
        brief=brief,
        advisory=advisory,
        decision_choices=DECISION_CHOICES,
        errors=errors or [],
        status_code=status_code,
    )


def _detail_error(request: Request, run_id: str, exc: Exception) -> HTMLResponse:
    err = map_exception(exc)
    logger.warning("investigate.action_failed", extra={"code": err.code, "run_id": run_id})
    return _detail_page(request, run_id, errors=[err], status_code=err.http_status)


def _parse_version(raw: str) -> int:
    try:
        version = int(raw)
    except (TypeError, ValueError):
        raise DomainValidationError("expected_version is required") from None
    if version < 1:
        raise DomainValidationError("expected_version must be >= 1")
    return version


def _reviewer_actor() -> Actor:
    return get_services().reviewer.reviewer


# --- Typed JSON API (no raw persistence) ---------------------------------


@router.get("/api/sites/{site_id}/analyses")
def api_list_analyses(site_id: str) -> JSONResponse:
    try:
        get_site(site_id)
    except DomainValidationError as exc:
        err = map_exception(exc)
        return JSONResponse(
            {"error": {"code": err.code, "message": err.message}},
            status_code=err.http_status,
        )
    rows = _brief().list_analyses_for_site(site_id)
    return JSONResponse(
        {"site_id": site_id, "analyses": [list_item_to_api(r) for r in rows]}
    )


@router.get("/api/analyses/{run_id}")
def api_analysis_detail(run_id: str) -> JSONResponse:
    try:
        brief = _brief().get_brief(run_id)
    except ResourceNotFound:
        return JSONResponse(
            {"error": {"code": "not_found", "message": "Analysis run not found."}},
            status_code=404,
        )
    payload = brief_to_api_dict(brief)
    advisory = safe_advise(_copilot(), brief)
    payload["ai_advisory"] = advisory_to_api(advisory)
    return JSONResponse(payload)


@router.get("/api/analyses/{run_id}/signals")
def api_analysis_signals(run_id: str) -> JSONResponse:
    try:
        signals = _brief().list_signals(run_id)
    except ResourceNotFound:
        return JSONResponse(
            {"error": {"code": "not_found", "message": "Analysis run not found."}},
            status_code=404,
        )
    return JSONResponse(
        {"run_id": run_id, "signals": [signal_to_api(s) for s in signals]}
    )


@router.get("/api/analyses/{run_id}/evidence")
def api_analysis_evidence(run_id: str) -> JSONResponse:
    try:
        evidence = _brief().list_evidence(run_id)
    except ResourceNotFound:
        return JSONResponse(
            {"error": {"code": "not_found", "message": "Analysis run not found."}},
            status_code=404,
        )
    return JSONResponse(
        {"run_id": run_id, "evidence": [evidence_to_api(e) for e in evidence]}
    )


@router.get("/api/analyses/{run_id}/reproducibility")
def api_analysis_reproducibility(run_id: str) -> JSONResponse:
    try:
        repro = _brief().get_reproducibility(run_id)
    except ResourceNotFound:
        return JSONResponse(
            {"error": {"code": "not_found", "message": "Analysis run not found."}},
            status_code=404,
        )
    return JSONResponse(
        {"run_id": run_id, "reproducibility": reproducibility_to_api(repro)}
    )


def _sites() -> list[dict[str, str]]:
    return [
        {"id": s.site_id, "label": s.display_name, "city": s.city}
        for s in list_sites()
    ]
