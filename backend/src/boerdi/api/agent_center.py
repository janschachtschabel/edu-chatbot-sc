"""Die Agent-Steuerzentrale im Studio (ST-8): was der Agent bekommt, nur lesend.

Eigener Router mit Studio-Schlüssel und NICHT unter ``/api/agent`` — jener
lässt sich mit ``AGENT_OPEN`` ohne Anmeldung öffnen, und das Skill-Verzeichnis
löst einen MCP-Abruf aus. Derselbe Grund wie bei ``/api/master-skill``, der den
Master-Skill zeigt; hier stehen die übrigen Stücke daneben.
"""

from __future__ import annotations

import re
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Security

from boerdi.api.deps import Lang, require_studio_key
from boerdi.i18n.messages import msg
from boerdi.services.agent_prompt_preview import prompt_vorschau
from boerdi.services.agent_skill_directory import (
    VerzeichnisFehler,
    skill_suche,
    skill_verzeichnis,
)
from boerdi.services.agent_tool_overview import werkzeugliste

router = APIRouter(
    prefix="/api/agent-center", tags=["agent"],
    dependencies=[Security(require_studio_key)],
)

#: Eine edu-sharing-Kennung, wie sie der MCP annimmt (höchstens 64 Zeichen) —
#: nur Kennungs-Zeichen, damit nichts anderes in den Werkzeug-Aufruf gelangt.
_KENNUNG = r"^[A-Za-z0-9-]{1,64}$"

#: So viel vom MCP-Fehlertext geht ins Studio — so viel, wie das Protokoll
#: festhält (``services/agent_skill_directory``).
_GRUND_MAX = 200

#: Eine Adresse im MCP-Fehlertext. Bei einem HTTP-Fehler nennt httpx die
#: angefragte URL („… for url 'http://…/mcp'"), also die interne MCP-Adresse;
#: die gehört ins Protokoll, nicht ins Studio.
_ADRESSE = re.compile(r"[a-z][a-z0-9+.-]*://[^\s'\"<>)]+", re.IGNORECASE)


def _grund(detail: str) -> str:
    """Der MCP-Fehlertext fürs Studio: Adressen ersetzt, höchstens ``_GRUND_MAX`` Zeichen."""
    text = _ADRESSE.sub("[…]", detail)
    return text if len(text) <= _GRUND_MAX else text[: _GRUND_MAX - 1] + "…"


@router.get("/tools")
async def agent_werkzeuge() -> dict:
    """Die Werkzeuge eines Chat-Zugs im Agent-Modus, je mit Art, Beschreibung,
    ob ein gewöhnlicher Zug es bekommt, und den Sperren, die es nehmen können
    (ST-8b)."""
    return werkzeugliste()


@router.get("/skills")
async def agent_skills(
    lang: Lang,
    collection: str = Query(
        ..., pattern=_KENNUNG,
        description="nodeId of the collection whose approved skills are listed"),
) -> dict:
    """Das Skill-Verzeichnis einer Sammlung aus ``get_skill_registry``: das
    Registry-Dokument, die freigegebenen Skills und nicht aufgelöste Einträge
    (ST-8c). Antwortet der MCP nicht oder unlesbar: 502 mit dem Grund."""
    try:
        return await skill_verzeichnis(collection)
    except VerzeichnisFehler as exc:
        text = (msg(lang, "agentCenter.registryFailed", error=_grund(exc.detail))
                if exc.grund == "mcp" else msg(lang, "agentCenter.registryUnreadable"))
        raise HTTPException(502, text) from exc


@router.get("/skills/search")
async def agent_skill_suche(
    lang: Lang,
    q: str = Query(
        ..., max_length=200, pattern=r"\S",
        description="search term; the MCP server's search_skill takes at most 200 characters"),
) -> dict:
    """Skills per Suchbegriff im Skill-Bestand des MCP-Servers (``search_skill``,
    Paket F3): die konfigurierte Skills-Sammlung samt Skillsets, ohne sie das ganze
    Repositorium; höchstens 25 Treffer, ``truncated`` bei voller Seite. Bietet der
    MCP-Server das Werkzeug nicht an: ``available: false`` — das Studio verweist
    dann auf die Suche per Sammlungs-ID. Antwortet der MCP nicht oder unlesbar:
    502 mit dem Grund."""
    try:
        return await skill_suche(q.strip())
    except VerzeichnisFehler as exc:
        text = (msg(lang, "agentCenter.searchFailed", error=_grund(exc.detail))
                if exc.grund == "mcp" else msg(lang, "agentCenter.registryUnreadable"))
        raise HTTPException(502, text) from exc


@router.get("/prompt")
async def agent_prompt(
    locale: Literal["de", "en"] = Query(
        "de", description="widget language; the head names it as the fallback language"),
) -> dict:
    """Der stabile Anfang der Kette eines Chat-Zugs im Agent-Modus (ST-8d): der Kopf
    im Wortlaut (Rolle, Anrede, Grenzen, Sprache, Wissens-Regel), der Master-Skill
    mit Zustand, danach die Blöcke je Zug als Kennungen, dazu Zahl und Umfang der
    Werkzeug-Beschreibungen."""
    return await prompt_vorschau(locale)
