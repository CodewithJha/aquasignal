"""Liveness endpoint for container / PaaS health checks.

Reports only coarse status — never the DB path, AI keys, or model config.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.composition import check_database

router = APIRouter()


@router.get("/healthz")
def healthz() -> JSONResponse:
    db_ok = check_database()
    return JSONResponse(
        {"status": "ok" if db_ok else "degraded", "database": "ok" if db_ok else "unreachable"},
        status_code=200 if db_ok else 503,
    )
