"""M17 — Volltext eines Materials anzeigen (Direkt-Aktion ``show_content_text``).

Nutzer-Vorgabe 2026-07-30: der Nutzer soll den **Inhalt** bekommen (ein
Arbeitsblatt als Markdown), nicht nur die Metadaten — anzeigen und bei Bedarf
weiterverarbeiten. Der Weg dorthin ist bewusst **deterministisch**, aus zwei
belegbaren Gründen:

* **Wortlaut.** Ginge der Text durch das Antwort-LLM, wäre das Ergebnis eine
  Nacherzählung. Ein Arbeitsblatt, mit dem jemand arbeiten will, muss
  unverändert ankommen — die Wahrheitspflicht des Bots gilt hier wörtlich.
* **Länge.** ``get_wlo_content_text`` liefert bis zu ``CONTENT_TEXT_MAX_CHARS``
  (50000, live gegen den Server geprüft) — das sind ~15000 Token und passt in
  keine Antwort-Länge, die wir dem Modell geben. Ein LLM-vermittelter Pfad
  könnte die Anforderung also gar nicht erfüllen, nicht nur schlechter.

Deshalb ein eigener Handler statt eines Antwort-Musters mit Tool-Aufruf: die
Aktion überspringt Pattern-Engine und ``generate_response`` komplett und baut
die :class:`ChatResponse` selbst — dieselbe Bauart wie die drei Aktionen in
``direct_actions`` (der preflight-Knoten setzt das Ergebnis als
``TurnContext.early_response``).

**Eigene Datei, nicht ``direct_actions``:** jenes Modul steht bei 519 Zeilen
über dem ~300-Zeilen-Schwellwert und nennt in seinem eigenen Kopf den
Upgrade-Pfad („Split in ein ``direct_actions/``-Paket"). Ein vierter Handler
dort würde es weiter aufblähen; ein Geschwister-Modul ist der kleinere Schritt.

**Kein ``_build_inline_document``:** jener Helfer trennt Lead und Body (der Text
vor der ersten Überschrift wandert in die Bubble) — bei einem fremden Dokument
risse das den ersten Absatz heraus. Die Box wird hier direkt gebaut; deshalb
gibt es für M17 auch **keinen** ``display_rules.inline_documents.per_pattern``-
Schalter: ein Knopf ohne Wirkung wäre schlimmer als keiner.

Tests patchen die MCP- und Persistenz-Grenze auf DIESEM Modul (ALT-Konvention).
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from boerdi.api.schemas import ChatRequest, ChatResponse, DebugInfo, InlineDocument
from boerdi.i18n import Locale, bot_text, resolve_locale
from boerdi.services.db_sessions import save_message
from boerdi.services.mcp.client import call_mcp_tool
from boerdi.services.mcp.parsers import parse_content_text

logger = logging.getLogger(__name__)

_PATTERN_ID = "M17"

# Was der Server als Grund für einen fehlenden Volltext nennt (Envelope-Feld
# ``reason``) → was der Nutzer davon wissen muss. Der Unterschied ist
# handlungsleitend: ``access_denied`` ist eine Rechtefrage, an der kein zweiter
# Versuch etwas ändert; ``extraction_failed`` ist ein technischer Fehlschlag.
_GRUND_SCHLUESSEL: dict[str, str] = {
    "access_denied": "content.reason.accessDenied",
    "no_text_no_url": "content.reason.noTextNoUrl",
    "extraction_failed": "content.reason.extractionFailed",
    "node_not_found": "content.reason.nodeNotFound",
    "no_envelope": "content.reason.noEnvelope",
}

_QR_OHNE_TEXT = ("content.qr.createOwn", "content.qr.freeAlternatives")

# Nach erfolgreichem Volltext. Bewusst **konkrete Bearbeiten-Verben** statt
# eines vagen „Daran weiterarbeiten": M11 wird über genau solche Formulierungen
# ausgewählt (seine Trigger-Phrasen sind „mach das kürzer", „formuliere
# einfacher"). Ein vager Chip landete beim Klassifikator im Nirgendwo — der
# Knopf wäre Dekoration.
_QR_MIT_TEXT = ("content.qr.shorter", "content.qr.simpler", "content.qr.similar")


def _qr(schluessel: tuple[str, ...], lang: Locale) -> list[str]:
    return [bot_text(lang, k) for k in schluessel]


def _quelle_satz(parsed: dict[str, Any], lang: Locale) -> str:
    """Ein Satz darüber, woher der Text stammt — Grundlage der Nachnutzung."""
    url = (parsed.get("source_url") or "").strip()
    return "\n\n" + bot_text(lang, "content.source", url=url) if url else ""


async def _handle_show_content_text(
    session: AsyncSession | None,
    req: ChatRequest,
    session_state: dict,
) -> ChatResponse:
    """Volltext eines Materials holen und als Inline-Dokument zurückgeben.

    ``action_params``: ``node_id`` (Pflicht), ``title`` (optional, nur für die
    Ansprache im Fehlerfall — der Titel der Box kommt vom Server).

    Jeder Pfad liefert eine vollständige :class:`ChatResponse`; ein leerer
    Volltext wird **benannt** (mit dem Grund des Servers) statt still auf die
    Metadaten zurückzufallen.
    """
    lang = resolve_locale(req.environment.locale)
    node_id = str(req.action_params.get("node_id") or "").strip()
    titel_hinweis = str(req.action_params.get("title") or "").strip()

    debug = DebugInfo(pattern=_PATTERN_ID, tools_called=[], entities={})

    if not node_id:
        # Kein Ziel — das ist ein Aufruf-Fehler des Widgets, kein Nutzer-Fehler.
        logger.warning("show_content_text ohne node_id (session=%s)", req.session_id)
        return ChatResponse(
            session_id=req.session_id,
            content=bot_text(lang, "content.missingNode"),
            debug=debug,
        )

    debug.tools_called = ["get_wlo_content_text"]
    debug.entities = {"node_id": node_id}

    try:
        raw = await call_mcp_tool("get_wlo_content_text", {"nodeId": node_id})
    except Exception as err:
        logger.error("show_content_text: MCP-Aufruf fehlgeschlagen: %s", err)
        debug.entities["reason"] = "mcp_error"
        return ChatResponse(
            session_id=req.session_id,
            content=bot_text(lang, "content.mcpUnreachable"),
            quick_replies=_qr(_QR_OHNE_TEXT, lang),
            debug=debug,
        )

    parsed = parse_content_text(raw)
    text = (parsed.get("text") or "").strip()
    grund = (parsed.get("reason") or "").strip()
    debug.entities["reason"] = grund

    if not text:
        anrede = (
            bot_text(lang, "content.aboutMaterialNamed", title=titel_hinweis)
            if titel_hinweis
            else bot_text(lang, "content.aboutMaterial")
        )
        antwort = (
            anrede
            + bot_text(lang, _GRUND_SCHLUESSEL.get(grund, "content.reason.unknown"))
            + _quelle_satz(parsed, lang)
        )
        response = ChatResponse(
            session_id=req.session_id,
            content=antwort,
            quick_replies=_qr(_QR_OHNE_TEXT, lang),
            debug=debug,
        )
        # Kein Text = kein Vor-Inhalt. Den Zug hier als M17 zu markieren würde
        # einen Bearbeiten-Zug auf ein leeres Dokument schicken.
        persistiert = antwort
    else:
        titel = (
            parsed.get("title") or titel_hinweis or bot_text(lang, "content.fallbackTitle")
        ).strip()
        gekuerzt = bool(parsed.get("truncated"))
        doc = InlineDocument(
            kind="volltext",
            title=titel,
            content=text,
            meta={
                "pattern": _PATTERN_ID,
                "node_id": parsed.get("node_id") or node_id,
                "source": parsed.get("source") or "",
                "source_url": parsed.get("source_url") or "",
                "char_count": parsed.get("char_count") or len(text),
                "truncated": gekuerzt,
            },
        )
        lead = bot_text(lang, "content.lead", title=titel)
        if gekuerzt:
            # Wer mit dem Dokument arbeiten will, muss wissen, dass er nur
            # einen Teil davon hat.
            lead += bot_text(lang, "content.truncated")
        response = ChatResponse(
            session_id=req.session_id,
            content=lead + _quelle_satz(parsed, lang),
            quick_replies=_qr(_QR_MIT_TEXT, lang),
            inline_documents=[doc],
            debug=debug,
        )
        # **Der Volltext, nicht die Begleitzeile.** Der Antwort-Prompt eines
        # Folge-Zugs bekommt die letzten 10 Nachrichten aus der Historie, nicht
        # den Inhalt der Box. Stünde hier nur der Lead, hätte M11 („mach das
        # kürzer") nichts, was es überarbeiten könnte. ``turn_persist`` macht es
        # für M09/M10 aus demselben Grund genauso.
        persistiert = f"{lead}\n\n{text}"
        # Markierung für den Folge-Zug — dasselbe tut die Lernpfad-Direkt-
        # Aktion mit ``last_pattern = "M09"``.
        session_state["last_pattern"] = _PATTERN_ID

    try:
        await save_message(
            session, req.session_id, "assistant", persistiert,
            debug=debug.model_dump(),
        )
    except Exception:
        logger.debug("Persistieren der Volltext-Antwort fehlgeschlagen", exc_info=True)
    return response
