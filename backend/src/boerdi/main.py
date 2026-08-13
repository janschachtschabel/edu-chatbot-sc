"""App factory. Kept ≤150 lines per spec §4 — routers/middlewares mount here.

P0-4: all §5.1 routers mounted (contract stubs, replaced in-place P1–P7).
P1-3: CORS (credentials only with explicit origins, ALT main.py:188-195),
security response headers (ALT Audit N-8), startup config warnings.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from boerdi import __version__
from boerdi.api import (
    agent,
    chat,
    config,
    config_areas,
    config_choices,
    config_elements,
    config_snapshots,
    health,
    loadtest,
    quality,
    rag,
    safety,
    sessions,
    speech,
    studio_bff,
    usage,
    widget,
)
from boerdi.api import (
    eval as eval_api,
)
from boerdi.services.warmup import spawn_startup_warmups
from boerdi.settings import Settings, get_settings

log = logging.getLogger("startup")


def _configure_logging(settings: Settings) -> None:
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _warn_insecure_config(settings: Settings) -> None:
    """Startup warnings (port of ALT lifespan checks)."""
    key = settings.studio_api_key.get_secret_value().strip()
    if not key or key.upper().startswith("CHANGE_ME"):
        log.warning(
            "⚠ STUDIO_API_KEY ist nicht gesetzt (oder noch der Platzhalter) — "
            "Studio-/Admin-/Eval-Endpunkte sind GESPERRT (fail-closed). Für "
            "Staging/Produktion einen langen Zufallswert setzen; lokal öffnet "
            "BOERDI_ALLOW_OPEN_ADMIN=1."
        )
    if "*" in settings.cors_origins:
        log.warning(
            "⚠ CORS_ORIGINS='*' (offen für alle Ursprünge). Für Produktion eine "
            "Allow-Liste der einbettenden Domains in CORS_ORIGINS setzen."
        )


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Engine + ConfigStore (NOTIFY listener) live for the app's lifetime
    (P2-2). Fails fast when Postgres is unreachable — DB is core infra."""
    from boerdi.db.notify import asyncpg_dsn
    from boerdi.db.session import make_engine, make_session_factory
    from boerdi.services import config_loader
    from boerdi.services.config_store import ConfigStore
    from boerdi.services.loadtest import sweep_orphaned_loadtests

    settings = get_settings()
    engine = make_engine(settings)
    store = ConfigStore(engine, listen_dsn=asyncpg_dsn(settings.database_url))
    await store.start()
    # warm ALL areas so the sync loader facade never misses (P2-3)
    await store.preload([meta["area"] for meta in await store.list_areas()])
    config_loader.bind_store(store)
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)  # api.deps.get_session
    app.state.config_store = store
    # V9 housekeeping: a crashed loadtest can leave a ``running`` row that would
    # permanently 409-block new runs — sweep stale rows to ``failed`` on boot
    # (best-effort; a sweep failure must never block startup).
    try:
        async with app.state.session_factory() as _lt_sess:
            _swept = await sweep_orphaned_loadtests(_lt_sess)
        if _swept:
            log.info("swept %d orphaned loadtest run(s) to failed at startup", _swept)
    except Exception:
        log.warning("loadtest orphan-sweep skipped at startup", exc_info=True)
    # W1: Vokabular- + LLM-Vorwärmung im Hintergrund (ALT ``main.py:173-178``), damit
    # der erste Zug einer frischen Replica nicht die kalten Kosten zahlt. Startet und
    # kehrt sofort zurück — die Bereitschaft der Instanz hängt nicht daran.
    spawn_startup_warmups()
    try:
        yield
    finally:
        config_loader.bind_store(None)
        await store.stop()
        await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    _configure_logging(settings)
    _warn_insecure_config(settings)

    app = FastAPI(
        title="boerdi-chat backend",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        lifespan=_lifespan,
    )

    # HTTP-layer rate limit (P1-4/V7); the limiter lives in api/ratelimit.py
    from boerdi.api.ratelimit import limiter

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # studio-bff (P9-1): /studio/api/* → /api/* with key injection, cookie-gated.
    # Registered BEFORE CORS on purpose: ``add_middleware`` inserts at the front,
    # so the LAST one added is outermost — CORS must wrap this gate, or a
    # cross-origin preflight (which by definition carries no cookie) would be
    # answered with 401 instead of the CORS headers.
    from boerdi.api.studio_proxy import StudioProxyMiddleware

    app.add_middleware(StudioProxyMiddleware)

    cors_origins = settings.cors_origin_list
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=("*" not in cors_origins),  # credentials only with specific origins
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def _security_headers(request, call_next):
        """Basale Security-Response-Header (ALT Audit N-8). ``setdefault``
        überschreibt keine endpoint-eigenen Header. X-Frame-Options=SAMEORIGIN
        ist unkritisch fürs Embedding — das Widget lädt per <script src>,
        nicht via iframe; die Demo-Seiten sollen nicht drittseitig geframt werden."""
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        return response

    app.include_router(health.public_router)
    app.include_router(agent.router)
    app.include_router(chat.public_router)
    app.include_router(chat.router)
    app.include_router(sessions.router)
    app.include_router(sessions.public_router)
    app.include_router(config.router)
    app.include_router(config.public_router)
    app.include_router(config_areas.router)
    app.include_router(config_choices.router)
    app.include_router(config_elements.router)
    app.include_router(config_snapshots.router)
    app.include_router(rag.router)
    app.include_router(quality.router)
    app.include_router(usage.router)
    app.include_router(safety.router)
    app.include_router(eval_api.router)
    app.include_router(loadtest.router)
    app.include_router(speech.public_router)
    app.include_router(widget.public_router)
    app.include_router(studio_bff.router)
    # Mount last: SpaFiles owns /studio, the BFF routes above must win.
    from boerdi.api.studio_static import mount_studio_spa

    mount_studio_spa(app)

    # OTel (P1-5): no-op unless OTEL_EXPORTER_OTLP_ENDPOINT is configured
    from boerdi.obs.otel import setup_otel

    setup_otel(app)

    return app


app = create_app()
