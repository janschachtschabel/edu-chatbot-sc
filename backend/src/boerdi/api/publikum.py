"""Was welches Publikum von einer Antwort bekommt (Paket 18C/D).

Phase 3: ``ui`` (``api/schemas_ui``) kommt **zusätzlich** zum Debug-Block an die Antwort, an das
Strom-``result`` und an jede Nachricht im Verlauf — eine Ableitung, drei Ausgänge. Der
Debug-Block bleibt unverändert, damit das bisherige Widget weiterläuft; Phase 4 stellt das Widget
auf ``ui`` um und gibt ``debug`` nur noch dem Studio.
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


def antwort_mit_ui(resp: ChatResponse) -> ChatResponse:
    """Die Antwort mit ``ui`` — für ``POST /api/chat`` und das Strom-``result``."""
    resp.ui = ui_aus_debug(resp.debug)
    return resp


def verlauf_mit_ui(nachrichten: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Jede Nachricht des Verlaufs mit ``ui`` (nur gesetzte Felder)."""
    return [{**n, "ui": ui_aus_gespeichert(n.get("debug")).model_dump(exclude_defaults=True)}
            for n in nachrichten]
