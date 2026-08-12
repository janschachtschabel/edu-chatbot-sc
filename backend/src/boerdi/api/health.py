"""Health/root endpoints (P1-6, port of ALT main.py health section).

/health is the liveness probe for Docker HEALTHCHECK / load balancers —
intentionally simple, no DB/LLM gating (a warming instance can already
serve). /api/health adds provider/model display WITHOUT secrets.

GET and HEAD are declared separately: a single api_route(methods=[...]) makes
FastAPI derive the operationId from an unordered method set — non-deterministic
output would break the frozen-contract diff gate (P0-4).
"""

from fastapi import APIRouter
from fastapi.responses import RedirectResponse

from boerdi.services import llm_models
from boerdi.services.mcp.auth import auth_mode
from boerdi.services.rag.rerank import reranker_status

public_router = APIRouter(tags=["health"])

_OK = {"status": "ok"}


def _health_detail() -> dict:
    model = llm_models.get_chat_model()
    info: dict = {
        "status": "ok",
        "provider": llm_models.get_provider(),
        "chat_model": model,
        "embed_model": llm_models.get_embed_model(),
        "gpt5_params_active": llm_models.supports_gpt5_params(model),
        # C3: Betriebsart gegenüber dem MCP-Server — ``service`` (Zugangsblock
        # hinterlegt) oder ``anonymous``. Nur das Wort, nie der Block: sonst
        # könnte ein Betreiber nicht prüfen, ob sein Token überhaupt greift.
        "mcp_auth": auth_mode(),
        # Wie `mcp_auth` nur das WORT, aber hier mit einem eigenen Zweck: der
        # Reranker kann eingeschaltet und trotzdem untätig sein, wenn das
        # Modell fehlt. Ohne dieses Feld merkt man das nur an unauffällig
        # schlechteren Antworten — die teuerste Art, einen Fehler zu finden.
        "reranker": reranker_status(),
    }
    if info["gpt5_params_active"]:
        info["verbosity"] = llm_models.get_verbosity()
        info["reasoning_effort"] = llm_models.get_reasoning_effort()
    return info


@public_router.get("/health")
def health() -> dict[str, str]:
    return _OK


@public_router.head("/health")
def health_head() -> dict[str, str]:
    return _OK


@public_router.get("/api/health")
def api_health() -> dict:
    return _health_detail()


@public_router.head("/api/health")
def api_health_head() -> dict:
    return _health_detail()


@public_router.get("/")
def root() -> RedirectResponse:
    return RedirectResponse(url="/api/health")


@public_router.head("/")
def root_head() -> RedirectResponse:
    return RedirectResponse(url="/api/health")
