"""Was welches Publikum von einer Antwort bekommt (Paket 18C/D).

Jeder bekommt ``ui`` (``api/schemas_ui``) — an der Antwort, am Strom-``result`` und an jeder
Nachricht im Verlauf: eine Ableitung, drei Ausgänge. Den Debug-Block (und im Verlauf die Trace-ID
je Nachricht) bekommt nur die Anlage selbst (``turn_auth.darf_diagnose``: Studio-Proxy,
Studio-Schlüssel, reiner Entwicklungsmodus) — Persona, Signale, Spur und Zugakte sind Diagnose
(Phase 4, der Schnitt).
"""

from __future__ import annotations

from typing import Any

from boerdi.api.schemas import ChatResponse, DebugInfo
from boerdi.api.schemas_ui import UiInfo
from boerdi.domain.prepared_write import VERLAUF_SCHLUESSEL
from boerdi.services.agent_zugblock import DOKUMENTE_DEBUG_KEY

_LIVE = {"pattern", "intent", "state", "tools_called", "phase3_modulations"}
#: Aus ``phase3_modulations`` nur, was das Gastgeber-Ereignis liest (``host-events.ts``) — der
#: Rest ist Diagnose: die vom Modell geschriebene Begründung der Kartenauswahl, die Kernregel
#: des Musters, der Zustandsübergang samt Grund (Review Phase 3). Eine Erlaubnisliste, damit ein
#: neuer Schlüssel nicht von selbst öffentlich wird.
MODULATIONEN = ("tone", "length", "formality", "card_text_mode", "rag_areas", "sources",
                "_tone_modifier_override")


def _text(wert: Any) -> str:
    return wert if isinstance(wert, str) else ""


def _texte(wert: Any) -> list[str]:
    return [w for w in wert if isinstance(w, str)] if isinstance(wert, list) else []


def _objekte(wert: Any) -> list[dict[str, Any]]:
    return [w for w in wert if isinstance(w, dict)] if isinstance(wert, list) else []


def _objekt(wert: Any) -> dict[str, Any] | None:
    return wert if isinstance(wert, dict) else None


def ui_aus_gespeichert(debug: Any) -> UiInfo:
    """``ui`` aus dem gespeicherten Debug-Block einer Nachricht. Alte Nachrichten und Felder in
    unerwarteter Form ergeben leere Felder, nie einen Fehler — der Verlauf muss laden."""
    d = debug if isinstance(debug, dict) else {}
    return UiInfo(
        pattern=_text(d.get("pattern")),
        intent=_text(d.get("intent")),
        state=_text(d.get("state")),
        tools_called=_texte(d.get("tools_called")),
        modulations={k: v for k, v in (_objekt(d.get("phase3_modulations")) or {}).items()
                     if k in MODULATIONEN},
        query_metas=_objekte(d.get("_query_metas")),
        web_links=_objekte(d.get("_web_links")),
        type_focus=_text(d.get("_type_focus")),
        dokumente=_objekte(d.get(DOKUMENTE_DEBUG_KEY)),
        topic_page_view=_objekt(d.get("_topic_page_view")),
        prepared_write=_objekt(d.get(VERLAUF_SCHLUESSEL)),
    )


def ui_aus_debug(debug: DebugInfo) -> UiInfo:
    """``ui`` einer Antwort, live aus ihrem Debug-Block."""
    return ui_aus_gespeichert(debug.model_dump(include=_LIVE))


def antwort_fuer(resp: ChatResponse, intern: bool) -> ChatResponse:
    """Die Antwort für ``POST /api/chat`` und das Strom-``result``: mit ``ui``, ohne Freigabe
    ohne Debug-Block. Den Typ-Fokus setzt ``turn_persist`` vorher an ``ui`` — er steht in keinem
    Feld des Debug-Blocks und bleibt."""
    ui = ui_aus_debug(resp.debug) if resp.debug is not None else UiInfo()
    resp.ui = ui.model_copy(update={"type_focus": resp.ui.type_focus})
    if not intern:
        resp.debug = None
    return resp


#: Nur für die Anlage: der Debug-Block und die Trace-ID, aus der das Studio die Fehlernummer liest.
_DIAGNOSE = ("debug", "trace_id")


def verlauf_fuer(nachrichten: list[dict[str, Any]], intern: bool) -> list[dict[str, Any]]:
    """Jede Nachricht des Verlaufs mit ``ui`` (nur gesetzte Felder); Debug-Block und Trace-ID
    nur für die Anlage."""
    return [
        {**{k: v for k, v in n.items() if intern or k not in _DIAGNOSE},
         "ui": ui_aus_gespeichert(n.get("debug")).model_dump(exclude_defaults=True)}
        for n in nachrichten
    ]
