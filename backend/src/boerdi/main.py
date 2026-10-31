"""App factory. Kept ≤150 lines per spec §4 — routers/middlewares mount here.

P0-4: all §5.1 routers mounted (contract stubs, replaced in-place P1–P7).
P1-3: CORS (credentials only with explicit origins, ALT main.py:188-195),
security response headers (ALT Audit N-8), startup config warnings.
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from boerdi import __version__
from boerdi.api import (
    agent,
    agent_center,
    chat,
    config,
    config_areas,
    config_choices,
    config_documents,
    config_effects,
    config_elements,
    config_fassungen,
    config_snapshots,
    health,
    loadtest,
    master_skill,
    nutzung,
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
from boerdi.api.openapi_public import oeffentliche_spec
from boerdi.api.sse import nachlaeufer_abwarten
from boerdi.obs.drittlogger import drittlogger_einstellen
from boerdi.obs.log_format import StdoutHandler, formatter_fuer
from boerdi.obs.tasks import ABBRUCH_FRIST_S, cancel_and_drain
from boerdi.obs.trace_id import TraceIdFilter, TraceIdMiddleware
from boerdi.services import aufbewahrung
from boerdi.services import master_skill as master_skill_dienst
from boerdi.services.master_skill import starte as starte_master_skill_takt
from boerdi.services.safety import moderation
from boerdi.services.warmup import spawn_startup_warmups
from boerdi.settings import (
    STUDIO_GEHEIMNIS_MINDESTLAENGE,
    UMBENANNTE_VARIABLEN,
    Settings,
    get_settings,
)

log = logging.getLogger("startup")


def _configure_logging(settings: Settings) -> None:
    # Paket 17 (D4): JSON oder Klartext (``LOG_FORMAT``), Trace-ID in jeder Zeile, nur
    # stdout. Uvicorns eigene Logger laufen seit ``boerdi.serve`` (``log_config=None``)
    # über dieselbe Wurzel und damit im selben Format.
    handler = StdoutHandler()
    handler.setFormatter(formatter_fuer(settings.log_format))
    handler.addFilter(TraceIdFilter())
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO), handlers=[handler],
    )
    # Paket 18C/D: Fremd-Logger ohne Inhalte, IPs und Adressen (``httpx`` meldete jede
    # Anfrage mit voller Adresse samt Abfrage, Review Paket 6); LiteLLM ohne eigenen Handler.
    drittlogger_einstellen(settings.log_content)


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
    # Paket 19 (H-3, P19-E2): zu kurze Geheimnisse halten Studio bzw. Verwaltung zu. ERROR, nie
    # der Wert — die Länge allein sagt, was zu tun ist.
    if (key and not key.upper().startswith("CHANGE_ME")
            and len(key) < STUDIO_GEHEIMNIS_MINDESTLAENGE):
        log.error("STUDIO_API_KEY ist kürzer als %d Zeichen — die Verwaltungsrouten bleiben "
                  "GESPERRT (503). Einen langen Zufallswert setzen.",
                  STUDIO_GEHEIMNIS_MINDESTLAENGE)
    passwort = settings.studio_password.get_secret_value().strip()
    if (passwort and not passwort.upper().startswith("CHANGE_ME")
            and len(passwort) < STUDIO_GEHEIMNIS_MINDESTLAENGE):
        log.error("STUDIO_PASSWORD ist kürzer als %d Zeichen — das Studio bleibt GESPERRT (503). "
                  "Ein längeres Passwort setzen.", STUDIO_GEHEIMNIS_MINDESTLAENGE)
    if key and not key.isascii():
        # Review 2026-10-30: Kopfzeilen kommen als latin-1 an — ein solcher Schlüssel passt nie.
        log.warning("⚠ STUDIO_API_KEY enthält Zeichen außerhalb von ASCII — keine Anfrage kann "
                    "ihn vorlegen. Einen Zufallswert aus Buchstaben und Ziffern setzen.")
    if settings.b_api_route.strip() and settings.llm_provider != "b-api-openai":
        # Paket 17: still übergangen hielte der Betreiber die Route für aktiv.
        log.warning(
            "⚠ B_API_ROUTE=%r ist gesetzt, wirkt aber nur mit LLM_PROVIDER=b-api-openai "
            "(aktiv: %s) — die Route wird NICHT genutzt.",
            settings.b_api_route.strip(), settings.llm_provider,
        )
    roh_modus = os.environ.get("B_API_KEY_MODE", "").strip()
    if roh_modus and roh_modus.lower() != settings.b_api_key_mode:
        # Review-Runde 3 (Befund 4): ein Tippfehler fiel still auf auto zurück.
        log.warning(
            "⚠ B_API_KEY_MODE=%r ist unbekannt — es gilt %r (erlaubt: auto, static, forward).",
            roh_modus, settings.b_api_key_mode,
        )
    for alt, neu in UMBENANNTE_VARIABLEN.items():
        if os.environ.get(alt, "").strip():
            log.warning("⚠ %s ist veraltet und heißt jetzt %s — der alte Name wirkt "
                        "übergangsweise weiter.", alt, neu)
    if settings.log_content:
        log.warning(
            "⚠ LOG_CONTENT ist an — Inhalte (Nachrichten, Prompts, Werkzeugargumente und "
            "-ergebnisse) stehen auf DEBUG im Log. Nur für eine akute Analyse; danach ausschalten."
        )
    roh_ausfall = os.environ.get("MODERATION_FAILURE_MODE", "").strip()
    if roh_ausfall and roh_ausfall.lower() != settings.moderation_failure_mode:
        # Review 18: ein Schalter, der schließen soll, öffnete bei einem Tippfehler still.
        log.warning(
            "⚠ MODERATION_FAILURE_MODE=%r ist unbekannt — es gilt %r (erlaubt: open, "
            "closed).", roh_ausfall, settings.moderation_failure_mode,
        )
    if settings.moderation_failure_mode == "closed" and moderation._moderation_target() is None:
        log.warning(
            "⚠ MODERATION_FAILURE_MODE=closed, aber für diesen Anbieter ist keine "
            "Moderation eingerichtet — JEDER Zug wird abgewiesen."
        )
    if settings.b_api_key_mode == "forward" and not settings.llm_provider.startswith("b-api"):
        # Gesamt-Review Paket 17 (AB2): ohne b-api gibt es keinen Schlüssel durchzureichen.
        log.warning(
            "⚠ B_API_KEY_MODE=forward wirkt nur mit LLM_PROVIDER=b-api-* (aktiv: %s) — "
            "Züge ohne Authorization werden NICHT abgewiesen.", settings.llm_provider,
        )
    if settings.b_api_route.strip() and settings.llm_chat_model == settings.b_api_route.strip():
        # Review Paket 17 (A-2): die naheliegende Verwechslung. Das Chat-Modell bestimmt die
        # Parameter — ein Routenname hat keine Regeln, es gingen ``temperature``/``max_tokens``
        # hinaus, und eine gpt-6-Route antwortet mit 400 (gemessen 2026-10-20).
        log.warning(
            "⚠ LLM_CHAT_MODEL ist der Routenname %r. Es muss das Modell der Route nennen "
            "(z. B. gpt-6-luna), das die Parameter bestimmt; der Routenname gehört nur in "
            "B_API_ROUTE.",
            settings.b_api_route.strip(),
        )
    if (os.environ.get("KUBERNETES_SERVICE_HOST")
            and settings.rate_limit_storage_uri.strip().startswith("memory://")):
        # Paket 17 (C4): Kubernetes setzt die Variable in jeden Pod. Im Speicher zählt jede
        # Replik für sich — das Limit gilt N-fach.
        log.warning(
            "⚠ RATE_LIMIT_STORAGE_URI=memory:// in Kubernetes: jede Replik zählt für sich, "
            "das Limit gilt so oft, wie Repliken laufen. Auf Valkey stellen "
            "(redis://…, siehe docs/cluster-checkliste.md)."
        )
    if settings.cors_allow_extensions and "*" not in settings.cors_effective_origins:
        # Nur bei enger Liste melden — und zwar an der WIRKSAMEN, nicht an der
        # geschriebenen: im offenen Zustand ist die Regel folgenlos, und eine
        # Zeile, die dort eine Wirkung behauptet, stumpft die Warnung darunter ab.
        log.info(
            "CORS: Browser-Erweiterungen sind zusätzlich zur Liste erlaubt "
            "(safari-web-extension://, chrome-extension://). Safari vergibt die "
            "UUID je Installation, deshalb eine Regel statt Listeneinträgen. "
            "Abschalten mit CORS_ALLOW_EXTENSIONS=false."
        )
    if settings.cors_allow_all:
        if settings.cors_origin_list and settings.cors_origin_list != ["*"]:
            # Der teure Fall: jemand hat eine Liste gepflegt und sie gilt nicht.
            # Eine still uebergangene Konfiguration ist schlimmer als eine
            # offene — der Betreiber glaubt dann, er habe zugemacht.
            log.warning(
                "⚠ CORS ist OFFEN für alle Ursprünge (Vorgabe). CORS_ORIGINS=%r "
                "ist gesetzt, wird aber ÜBERSTEUERT. Zum Schließen "
                "CORS_ALLOW_ALL=false setzen.",
                ",".join(settings.cors_origin_list),
            )
        else:
            log.warning(
                "⚠ CORS ist OFFEN für alle Ursprünge (Vorgabe). Für Produktion "
                "CORS_ALLOW_ALL=false setzen und die einbettenden Domains in "
                "CORS_ORIGINS auflisten."
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
    from boerdi.services.sitzungssperre import sperr_engine

    settings = get_settings()
    engine = make_engine(settings)
    store = ConfigStore(engine, listen_dsn=asyncpg_dsn(settings.database_url))
    await store.start()
    # warm ALL areas so the sync loader facade never misses (P2-3)
    await store.preload([meta["area"] for meta in await store.list_areas()])
    config_loader.bind_store(store)
    app.state.engine = engine
    # Paket 19 (Audit 2026-10-31, H-5): die Sitzungssperre der Chat-Züge über eine eigene
    # kleine Engine — unter Last wartet sie nicht hinter den Zügen auf eine Verbindung.
    app.state.sperr_engine = sperr_engine(settings)
    app.state.session_factory = make_session_factory(engine)  # api.deps.get_session
    app.state.config_store = store
    # V9 housekeeping: a crashed loadtest can leave a ``running`` row that would
    # permanently 409-block new runs — sweep rows without a heartbeat (Paket 17, C1:
    # never the live run of another replica) to ``failed`` on boot (best-effort; a sweep
    # failure must never block startup).
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
    # Paket 8 (A): die Aufbewahrungsfristen der Protokolle, alle 6 Stunden.
    takt = aufbewahrung.starte(engine, app.state.session_factory)
    # 2026-10-18: der Master-Skill im 5-Minuten-Takt, damit kein Zug auf ihn wartet.
    # Paket 17 (C3): Stand geteilt über die Datenbank, Signal über die NOTIFY-Bahn.
    master_skill_dienst.binde(engine)
    store.subscribe(master_skill_dienst.bei_signal)
    skill_takt = starte_master_skill_takt()
    try:
        yield
    finally:
        # Paket 9: zuerst die Züge, deren Client aufgelegt hat — sie schreiben noch.
        await nachlaeufer_abwarten()
        master_skill_dienst.binde(None)  # ab hier startet ein Signal keine Übernahme mehr
        # Takte und Listener teilen sich EINE Abbruchfrist (Review 2026-10-30): nacheinander
        # waren es zweimal 5 s, und mit dem Rest lag die Summe über ``stop_grace_period``.
        uhr = asyncio.get_running_loop()
        ende = uhr.time() + ABBRUCH_FRIST_S
        await cancel_and_drain([takt, skill_takt, *master_skill_dienst.laufende_uebernahmen()],
                               bezeichnung="Herunterfahren")
        config_loader.bind_store(None)
        # Paket 19 (N-25): mindestens 0,5 s — mit 0 warnte jedes Herunterfahren nach langem
        # Abbruch der Takte „abgebrochene Aufgabe … nicht beendet“ (der Puffer der Gnadenfrist
        # deckt die halbe Sekunde, ``test_das_herunterfahren_passt_in_die_gnadenfrist``).
        await store.stop(frist_s=max(0.5, ende - uhr.time()))
        await engine.dispose()
        await app.state.sperr_engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    _configure_logging(settings)
    _warn_insecure_config(settings)

    app = FastAPI(
        title="boerdi-chat backend",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        # Paket 17 (D5): ``/openapi.json`` liefert nur die öffentliche Chat-API (unten); die
        # volle Spec samt Studio und Verwaltung steht am internen Port (``api/intern``).
        openapi_url=None,
        lifespan=_lifespan,
    )

    oeffentlich: dict[str, dict] = {}

    @app.get("/openapi.json", include_in_schema=False)
    def openapi_oeffentlich() -> dict:
        # Einmal je App gebaut — der Pfad ist anonym erreichbar (Review Phase D, C13).
        if "spec" not in oeffentlich:
            oeffentlich["spec"] = oeffentliche_spec(app)
        return oeffentlich["spec"]

    # HTTP-layer rate limit (P1-4/V7); the limiter lives in api/ratelimit.py
    from boerdi.api.ratelimit import limiter

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    # A config value Postgres refuses (Paket 4b, A4): 400 naming the area.
    from boerdi.api.config_antworten import nicht_speicherbar_antwort
    from boerdi.services.config_conflict import BereichNichtSpeicherbar

    app.add_exception_handler(BereichNichtSpeicherbar, nicht_speicherbar_antwort)
    # Paket 19 (N-5): eine 422 nennt Ort, Art und Satz — nie die Eingabe (``input``/``ctx``).
    from fastapi.exceptions import RequestValidationError

    from boerdi.api.pruef_fehler import pruef_fehler_antwort

    app.add_exception_handler(RequestValidationError, pruef_fehler_antwort)

    # studio-bff (P9-1): /studio/api/* → /api/* with key injection, cookie-gated.
    # Registered BEFORE CORS on purpose: ``add_middleware`` inserts at the front,
    # so the LAST one added is outermost — CORS must wrap this gate, or a
    # cross-origin preflight (which by definition carries no cookie) would be
    # answered with 401 instead of the CORS headers.
    #
    # Die Rumpf-Grenze (Audit 2026-09-29) steht VOR dem Proxy, also innerhalb
    # von ihm und von CORS: sie sieht den umgeschriebenen /api-Pfad, und ihre
    # 413 trägt die CORS-Kopfzeilen. Begründung in api/body_limit.py.
    from boerdi.api.body_limit import BodySizeLimitMiddleware
    from boerdi.api.studio_proxy import StudioProxyMiddleware

    app.add_middleware(BodySizeLimitMiddleware)
    app.add_middleware(StudioProxyMiddleware)

    cors_origins = settings.cors_effective_origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        # Ursprünge von Browser-Erweiterungen kommen als REGEL dazu, nicht als
        # Listeneintrag: Safari vergibt die UUID je Installation, eine statische
        # Liste kann den Fall nicht abdecken (Begründung an
        # ``Settings.cors_origin_regex``). Starlette prüft Liste ODER Regel.
        allow_origin_regex=settings.cors_origin_regex,
        allow_credentials=("*" not in cors_origins),  # credentials only with specific origins
        allow_methods=["*"],
        allow_headers=["*"],
        # Paket 9: das Widget liest nach einem 429 die Wartezeit (Verlaufsnachfrage).
        expose_headers=["Retry-After"],
    )

    # Paket 8 (P1): HSTS für den ganzen Host. Über HTTP ignorieren Browser den
    # Header (RFC 6797, 8.1) — lokal ohne TLS schadet er nicht.
    hsts = f"max-age={settings.hsts_max_age}" if settings.hsts_max_age else ""

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
        if hsts:
            response.headers.setdefault("Strict-Transport-Security", hsts)
        return response

    # Paket 17 (D3): zuletzt hinzugefügt = äußerste Schicht — zählt jede Antwort, auch
    # 413/401/CORS. Ausgeliefert werden die Zahlen nur am internen Port (``api/intern``).
    from boerdi.obs.metrics import MetrikMiddleware

    app.add_middleware(MetrikMiddleware)
    # Paket 17 (D4): die Trace-ID gilt ab der äußersten Schicht — auch Zählung, CORS und
    # Fehlerantworten loggen schon unter ihr.
    app.add_middleware(TraceIdMiddleware)

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
    app.include_router(config_documents.router)
    app.include_router(config_effects.router)
    app.include_router(config_elements.router)
    app.include_router(config_snapshots.router)
    app.include_router(config_fassungen.router)
    app.include_router(rag.router)
    app.include_router(quality.router)
    app.include_router(usage.router)
    app.include_router(nutzung.router)
    app.include_router(safety.router)
    app.include_router(eval_api.router)
    app.include_router(loadtest.router)
    app.include_router(master_skill.router)
    app.include_router(agent_center.router)
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
