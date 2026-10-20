"""Die öffentliche OpenAPI-Spec (Paket 17, D5) — die Chat-API, wie die b-api sie einbindet.

Leitfaden „Übergabe an Team 6“: die Spec ist Voraussetzung für die Einbindung in die b-api;
sie trägt einen Anzeigenamen und einen Beschreibungstext für Endnutzende (Grundlage eines
künftigen Produktkatalogs) und zeigt keine Infrastruktur- oder Verwaltungs-Endpunkte.
Abgeleitet aus der vollen Spec der App, damit sie nie veraltet; exportiert als
``docs/api/openapi-public.json`` mit eigenem CI-Gate (``scripts/export_openapi.py``).
"""

from __future__ import annotations

import copy
import json
from typing import Any

from fastapi import FastAPI

from boerdi import __version__
from boerdi.settings import get_settings

#: Die Operationen der öffentlichen Spec: Chat (auch als Strom), Agent für Gastanwendungen,
#: Sprache, Verlauf einer Sitzung, Lotsen-Modus. Widget-Dateien sind keine API.
OEFFENTLICH: tuple[tuple[str, str], ...] = (
    ("/api/chat", "post"),
    ("/api/chat/stream", "post"),
    ("/api/agent", "post"),
    ("/api/agent/stream", "post"),
    ("/api/speech/status", "get"),
    ("/api/speech/transcribe", "post"),
    ("/api/speech/synthesize", "post"),
    ("/api/sessions/{session_id}/messages", "get"),
    ("/api/config/guide-mode", "get"),
)

TITEL = "BOERDi – Chatbot von WirLernenOnline"
#: Entwurf (Plan Paket 17, §8) — vom Nutzer abzunehmen.
BESCHREIBUNG = (
    "BOERDi hilft beim Finden und Nutzen offener Bildungsinhalte von WirLernenOnline: "
    "Fragen stellen, passende Materialien, Themenseiten und Sammlungen erhalten, Inhalte "
    "zusammenfassen lassen."
)

_REF = "#/components/schemas/"

#: Der vorgesehene Zugang zu ``/api/agent*``: der Zugangsblock der angemeldeten Person
#: (``api/turn_auth.require_agent_caller``). Die Kopfzeile liest der Endpunkt selbst, FastAPI
#: kennt sie deshalb nicht — die öffentliche Spec weist sie ausdrücklich aus und stellt sie VOR
#: den Studio-Schlüssel, der nur für Server-zu-Server gedacht ist (Review Phase D, C7).
_ZUGANGSBLOCK = {
    "type": "apiKey", "in": "header", "name": "WLO-Access-Block",
    "description": (
        "Zugangsblock der angemeldeten WLO-Person (vom MCP-Server ausgestellt). Der "
        "Studio-Schlüssel (StudioKey) ist der Verwaltungsschlüssel und gehört nie in eine "
        "Gastanwendung."
    ),
}
_AGENT_PFADE = ("/api/agent", "/api/agent/stream")


def _refs(knoten: Any) -> set[str]:
    text = json.dumps(knoten)
    return {teil.split('"', 1)[0] for teil in text.split(_REF)[1:]}


def oeffentliche_spec(app: FastAPI) -> dict[str, Any]:
    """Die volle Spec der App, beschnitten auf :data:`OEFFENTLICH` und die gebrauchten Schemas."""
    voll = app.openapi()
    spec = copy.deepcopy({k: v for k, v in voll.items() if k not in ("paths", "components")})
    pfade: dict[str, Any] = {}
    for pfad, methode in OEFFENTLICH:
        op = voll.get("paths", {}).get(pfad, {}).get(methode)
        if op is not None:
            pfade.setdefault(pfad, {})[methode] = copy.deepcopy(op)
    for pfad in _AGENT_PFADE:
        op = pfade.get(pfad, {}).get("post")
        if op is not None:
            op["security"] = [{"WloAccessBlock": []}, *op.get("security", [])]
    spec["paths"] = pfade

    alle = voll.get("components", {}).get("schemas", {})
    gebraucht: set[str] = set()
    offen = _refs(pfade)
    while offen:  # transitiv: Schemas, die gebrauchte Schemas referenzieren
        name = offen.pop()
        if name in gebraucht or name not in alle:
            continue
        gebraucht.add(name)
        offen |= _refs(alle[name])
    schemas = {n: copy.deepcopy(alle[n]) for n in sorted(gebraucht)}
    komponenten: dict[str, Any] = {"schemas": schemas}
    verfahren = {n for op in (o for ops in pfade.values() for o in ops.values())
                 for s in op.get("security", []) for n in s}
    schemes = voll.get("components", {}).get("securitySchemes", {})
    schemes = {**schemes, "WloAccessBlock": _ZUGANGSBLOCK}
    if verfahren:
        komponenten["securitySchemes"] = {n: copy.deepcopy(schemes[n])
                                          for n in sorted(verfahren) if n in schemes}
    spec["components"] = komponenten
    spec["info"] = {
        "title": TITEL,
        "description": BESCHREIBUNG,
        "version": get_settings().boerdi_version or __version__,
    }
    return spec
