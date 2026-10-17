"""Welche Werkzeuge fremder MCP-Server das Modell bekommt (Paket 11, E).

Der WLO-Server hat einen festen, handgepflegten Katalog (``services/mcp/tool_defs*``) und eine
Mechanik, die an seinen Werkzeugnamen hängt: Schreib-Abnahme, Karten, Vokabular, vorbereitete
Anfragen. Ein fremder Server bekommt nichts davon und wird deshalb streng gehalten:

- **Übernommen statt live gefragt:** „Server prüfen“ im Studio speichert Name, Beschreibung,
  Eingabeschema und ``readOnlyHint`` im Registry-Eintrag (``tool_schemas``). Im Zug fragt
  niemand den Server; angeboten wird, was die Redaktion übernommen hat.
- **Nur lesend:** ohne ``read_only`` kein Angebot. Schreibende Werkzeuge fremder Server
  bräuchten eine eigene Abnahme, die es nicht gibt.
- **Eigener Namensraum:** das Modell sieht ``<server-id>__<werkzeug>``. Kein Katalogname enthält
  den Trenner (ein Test hält das fest), also kann ein fremdes Werkzeug kein WLO-Werkzeug
  überdecken.
- **Abschaltbar** je Werkzeug über ``werkzeuge_aus`` des Servers — derselbe Schalter wie beim
  WLO-Server.

Rein: keine I/O, die Registry reicht der Aufrufer herein.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from boerdi.domain.werkzeug_freigabe import wirksam_aus

TRENNER = "__"
#: Grenze der Anbieter für Funktionsnamen: 30 für den Server, 2 Trenner, 32 für das Werkzeug —
#: so überlebt der Trenner jede Kürzung (Review Paket 11, #4).
_SERVER_TEIL, _WERKZEUG_TEIL = 30, 32
#: Größter Eingabeschema-Text, der angeboten wird (Review #6): jedes Schema reist in jedem Zug mit.
SCHEMA_HOECHSTENS = 8000
_UNGUELTIG = re.compile(r"[^A-Za-z0-9_-]")


@dataclass(frozen=True)
class FremdWerkzeug:
    modellname: str
    server_id: str
    url: str
    #: Der Name beim fremden Server — so wird er gerufen.
    name: str
    #: Die Definition für das Modell (OpenAI-Funktionsform, wie ``TOOL_DEFINITIONS``).
    definition: dict[str, Any]


def modellname(server_id: str, name: str) -> str:
    """``<server-id>__<werkzeug>``, nur aus erlaubten Zeichen, höchstens 64 lang."""
    server = _UNGUELTIG.sub("_", server_id)[:_SERVER_TEIL]
    return f"{server}{TRENNER}{_UNGUELTIG.sub('_', name)[:_WERKZEUG_TEIL]}"


def ist_fremd(name: str) -> bool:
    """Gehört ``name`` einem fremden Server? (Konvention: der Trenner.)"""
    return TRENNER in (name or "")


def _definition(
    name: str, eintrag: Mapping[str, Any], server_name: str,
) -> dict[str, Any] | None:
    schema = eintrag.get("input_schema")
    if isinstance(schema, dict) and "type" not in schema:
        schema = {"type": "object", **schema}
    if not isinstance(schema, dict) or schema.get("type") != "object":
        schema = {"type": "object", "properties": {}}
    if len(json.dumps(schema, ensure_ascii=False, default=str)) > SCHEMA_HOECHSTENS:
        return None
    beschreibung = str(eintrag.get("description") or "").strip()
    return {"type": "function", "function": {
        "name": name,
        "description": f"[Externer Dienst: {server_name}] {beschreibung}".strip()[:1024],
        "parameters": schema,
    }}


def _adresse(url: str) -> str:
    return url.strip().rstrip("/").lower()


def angebotene(servers: Iterable[Mapping[str, Any]], *, primaer_id: str,
               primaer_url: str = "") -> list[FremdWerkzeug]:
    """Die Werkzeuge fremder Server, die das Modell bekommen darf.

    Ein Eintrag mit der Adresse des WLO-Servers fällt heraus (Review Paket 11, #3): der Transport
    gäbe ihm den Zugangsblock der Person (``transport._client_fabrik`` vergleicht Adressen).
    """
    aus_der_liste: list[FremdWerkzeug] = []
    vergeben: set[str] = set()
    for server in servers:
        sid = str(server.get("id") or "")
        url = str(server.get("url") or "")
        if not sid or sid == primaer_id or not url or not server.get("enabled", True):
            continue
        if primaer_url and _adresse(url) == _adresse(primaer_url):
            continue
        aus = set(wirksam_aus(server, primaer=False, vorgabe=frozenset()))
        server_name = str(server.get("name") or sid)
        for eintrag in server.get("tool_schemas") or []:
            if not isinstance(eintrag, Mapping) or eintrag.get("read_only") is not True:
                continue
            name = str(eintrag.get("name") or "").strip()
            if not name or name in aus:
                continue
            mname = modellname(sid, name)
            definition = _definition(mname, eintrag, server_name)
            if mname in vergeben or definition is None or not ist_fremd(mname):
                continue
            vergeben.add(mname)
            aus_der_liste.append(FremdWerkzeug(
                modellname=mname, server_id=sid, url=url, name=name, definition=definition))
    return aus_der_liste
