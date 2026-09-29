"""ConfirmGate — thin FastAPI entrypoint.

Composition root: app.composition (DeterministicFlagEngine + SQLite + Null AI).
Routes: app.web.routes
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.web.health_routes import router as health_router
from app.web.investigation_routes import router as investigation_router
from app.web.observer_cookie import ObserverCookieMiddleware
from app.web.request_limits import MaxBodySizeMiddleware
from app.web.routes import configure_templates, router

ROOT = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(_app: FastAPI):
    from app.composition import get_services
    from app.demo.config import DemoSettings

    services = get_services()
    demo = DemoSettings.from_env()
    if demo.should_reset_on_start:
        from app.demo.reset import reset_demo_database

        reset_demo_database(settings=services.settings, demo=demo)
    yield


app = FastAPI(title="ConfirmGate", version="0.9.0-a6", lifespan=lifespan)
app.add_middleware(MaxBodySizeMiddleware)
app.add_middleware(ObserverCookieMiddleware)
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
configure_templates(ROOT / "templates")
app.include_router(router)
app.include_router(investigation_router)
app.include_router(health_router)
