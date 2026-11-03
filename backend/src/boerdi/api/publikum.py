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
from boerdi.domain import ui_bloecke
from boerdi.domain.prepared_write import VERLAUF_SCHLUESSEL
from boerdi.services.agent_zugblock import DOKUMENTE_DEBUG_KEY
from boerdi.ui_module import abgeleitet, antwort

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


def ui_aus_gespeichert(debug: Any, cards: Any = None,
                       muster: dict[str, frozenset[str] | None] | None = None) -> UiInfo:
    """``ui`` aus dem gespeicherten Debug-Block einer Nachricht. Alte Nachrichten und Felder in
    unerwarteter Form ergeben leere Felder, nie einen Fehler — der Verlauf muss laden."""
    d = debug if isinstance(debug, dict) else {}
    web_links = _objekte(d.get("_web_links"))
    return UiInfo(
        pattern=_text(d.get("pattern")),
        intent=_text(d.get("intent")),
        state=_text(d.get("state")),
        tools_called=_texte(d.get("tools_called")),
        modulations={k: v for k, v in (_objekt(d.get("phase3_modulations")) or {}).items()
                     if k in MODULATIONEN},
        query_metas=_objekte(d.get("_query_metas")),
        web_links=web_links,
        type_focus=_text(d.get("_type_focus")),
        dokumente=_objekte(d.get(DOKUMENTE_DEBUG_KEY)),
        topic_page_view=_objekt(d.get("_topic_page_view")),
        prepared_write=_objekt(d.get(VERLAUF_SCHLUESSEL)),
        # Paket U1-c: die abgeleiteten Blöcke (Linkbox) stehen nicht im Debug-Block — sie
        # entstehen hier wie live aus den gespeicherten Links, mit derselben Kennung.
        ui_bloecke=abgeleitet.ergaenzt(
            ui_bloecke.aus_gespeichert(d.get(ui_bloecke.DEBUG_KEY)),
            pattern=_text(d.get("pattern")), web_links=web_links,
            type_focus=_text(d.get("_type_focus")),
            cards=cards if isinstance(cards, list) else (),
            query_metas=_objekte(d.get("_query_metas")), muster=muster),
    )


def ui_aus_debug(debug: DebugInfo) -> UiInfo:
    """``ui`` einer Antwort, live aus ihrem Debug-Block."""
    return ui_aus_gespeichert(debug.model_dump(include=_LIVE))


def antwort_fuer(resp: ChatResponse, intern: bool) -> ChatResponse:
    """Die Antwort für ``POST /api/chat`` und das Strom-``result``: mit ``ui``, ohne Freigabe
    ohne Debug-Block. Den Typ-Fokus setzt ``turn_persist`` vorher an ``ui`` — er steht in keinem
    Feld des Debug-Blocks und bleibt; ebenso die UI-Blöcke (Paket U1), die ``turn_persist`` live
    an ``ui`` setzt."""
    ui = ui_aus_debug(resp.debug) if resp.debug is not None else UiInfo()
    # Paket U1-c: abgeleitete Blöcke aus der FERTIGEN Antwort — nach ``widget_postprocess``,
    # das Links noch ergänzt. ``web_links`` bleibt daneben stehen (Entscheid: zusätzlich).
    bloecke = abgeleitet.ergaenzt(resp.ui.ui_bloecke, pattern=ui.pattern,
                                  web_links=resp.web_links, type_focus=resp.ui.type_focus,
                                  cards=resp.cards, query_metas=resp.query_metas,
                                  pagination=resp.pagination)
    resp.ui = ui.model_copy(update={"type_focus": resp.ui.type_focus, "ui_bloecke": bloecke})
    if not intern:
        resp.debug = None
    return resp


#: Nur für die Anlage: der Debug-Block und die Trace-ID, aus der das Studio die Fehlernummer liest.
_DIAGNOSE = ("debug", "trace_id")


def verlauf_fuer(nachrichten: list[dict[str, Any]], intern: bool) -> list[dict[str, Any]]:
    """Jede Nachricht des Verlaufs mit ``ui`` (nur gesetzte Felder); Debug-Block und Trace-ID
    nur für die Anlage."""
    # Die Muster einmal je Abruf — nicht je Nachricht (Paket U1-c, abgeleitete Blöcke).
    muster = abgeleitet.muster_zuordnung() if nachrichten else None
    uis = [_ui_fuer_den_verlauf(n.get("debug"), n.get("cards"), muster) for n in nachrichten]
    # Paket U1-d1: gespeichert ist jede Frage ``offen`` — beantwortet oder veraltet ergibt sich
    # erst aus den späteren Nutzernachrichten (deren Debug-Block bekommt nur die Anlage).
    antwort.status_ableiten(nachrichten, uis)
    return [
        {**{k: v for k, v in n.items() if intern or k not in _DIAGNOSE}, **_anzeige(n), "ui": ui}
        for n, ui in zip(nachrichten, uis, strict=True)
    ]


def _anzeige(nachricht: dict[str, Any]) -> dict[str, str]:
    """Der Text, den die Person live sah, falls er vom gespeicherten abweicht (geratene Box:
    gespeichert das Roh-Markdown für den Folgezug, gezeigt der Vorspann) — sonst nichts."""
    debug = nachricht.get("debug")
    text = debug.get(ui_bloecke.ANZEIGE_TEXT_KEY) if isinstance(debug, dict) else None
    return {"content": text} if isinstance(text, str) else {}


def _ui_fuer_den_verlauf(debug: Any, cards: Any = None,
                         muster: dict[str, frozenset[str] | None] | None = None) -> dict[str, Any]:
    """``ui`` mit nur gesetzten Feldern — die UI-Blöcke aber vollständig: ``exclude_defaults``
    wirkt verschachtelt und nähme einem Block sonst leere ``daten`` und ``text``."""
    ui = ui_aus_gespeichert(debug, cards, muster)
    aus = ui.model_dump(exclude_defaults=True, exclude={"ui_bloecke"})
    if ui.ui_bloecke:
        aus["ui_bloecke"] = [b.model_dump() for b in ui.ui_bloecke]
    return aus
