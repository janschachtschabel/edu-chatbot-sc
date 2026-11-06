"""Der wartende ``agent``-Schritt im gewöhnlichen Zug (Paket A2b, Plan 2026-11-05 §9).

Wartet ein Lauf am ``agent``-Schritt (``treiber.WARTET_KI``), ist jeder getippte Zug ein Zug der
KI — mit drei Zutaten:

- :func:`zeile`: ``[ABLAUFSCHRITT — …]`` vor der Nachricht (beide Maschinen): Ablauf, Schritt,
  Hinweis der Redaktion, die erlaubten Werkzeuge, das Budget und der Verweis auf „Weiter im
  Ablauf“. Nach ``zuege`` Zügen sagt sie, dass das Budget erschöpft ist — **kein** automatisches
  Weitergehen, die Person bleibt am Steuer.
- :func:`einengen` (nur Agent-Modus): nur die Werkzeuge des Schritts plus die virtuellen
  (Antwort, Inhaltsrahmen, Ergebnis). Schreibende kann ein Schritt nicht nennen (``pruefung``).
- :func:`weiter_knopf`: die Schnellantwort ``__action__|Weiter im Ablauf|ablauf_weiter|{ablauf}``.

Gilt nur, solange der Ablauf aktiv ist und seine Schritte unverändert (``fassung`` im Verweis);
sonst ist der Zug ein gewöhnlicher. Die Züge zählen je Schritt in der Sitzung (:func:`zaehlen`).
"""

from __future__ import annotations

import json
from typing import Any, Final

from boerdi.domain.antwort_werkzeug import RESPOND_TO_USER
from boerdi.domain.config_models.ablauf import AblaufArea, Schritt
from boerdi.domain.inline_documents import INHALTSRAHMEN
from boerdi.domain.result_delivery import LIEFERE_ERGEBNIS
from boerdi.i18n import bot_text
from boerdi.services import arbeitsstand
from boerdi.services.ablauf import ausloeser, treiber

AKTION: Final = "ablauf_weiter"
#: In ``entities``: die Züge am aktuellen Schritt —
#: ``{"schritt": "<ablauf>/<schritt>", "zuege": n}``.
ZUEGE_KEY: Final = "_ablauf_ki_zuege"
_VIRTUELL: Final = frozenset({RESPOND_TO_USER, INHALTSRAHMEN, LIEFERE_ERGEBNIS})
_ZEILE_ZEICHEN: Final = 500
#: Hinweis und Titel gedeckelt, damit Budget und Knopf nie abgeschnitten werden (Review A2b, 3).
HINWEIS_ZEICHEN: Final = 200
_TITEL_ZEICHEN: Final = 60


def fuer_zug(session_state: dict[str, Any], session_id: str, safety: Any
             ) -> tuple[AblaufArea, Schritt] | None:
    """:func:`aktueller` — aber nicht in einem Zug, dem die Sicherheitsprüfung ein Muster vorgibt
    (Krise M01, Ablehnung M02) oder ein hohes Risiko bescheinigt: dort weder Zeile noch Zählung
    (Review A2b, Befund 1)."""
    if safety is not None and (getattr(safety, "enforced_pattern", None)
                               or getattr(safety, "risk_level", "") == "high"):
        return None
    return aktueller(session_state, session_id)


def aktueller(session_state: dict[str, Any], session_id: str) -> tuple[AblaufArea, Schritt] | None:
    """Ablauf und ``agent``-Schritt, an dem ein Lauf dieser Person wartet — oder ``None``."""
    vw = arbeitsstand.verweis(session_state.get("entities") or {},
                              arbeitsstand.aufrufer_fuer(session_id))
    lauf = (vw or {}).get("lauf")
    if not isinstance(lauf, dict) or lauf.get("status") != treiber.WARTET_KI:
        return None
    ablauf = ausloeser.laden(lauf.get("ablauf"))
    if ablauf is None or not ablauf.aktiv or lauf.get("fassung") != treiber.fassung(ablauf):
        return None
    schritt = next((s for s in ablauf.schritte if s.id == lauf.get("schritt")), None)
    if schritt is None or schritt.typ != "agent" or schritt.agent is None:
        return None
    return ablauf, schritt


def _ohne_klammern(text: str) -> str:
    """Eine Klammer im Studio-Text schlösse die Zeile vorzeitig (wie Review V1, Befund 6)."""
    return " ".join(text.replace("[", "(").replace("]", ")").split())


def zeile(ablauf: AblaufArea, schritt: Schritt, lang: str, *, zuege: int,
          angeboten: set[str] | None = None, eingeengt: bool = True) -> str:
    """Die Zeile für die KI (≤ 500 Zeichen). ``zuege``: der wievielte Zug am Schritt dieser ist.
    ``angeboten``: nur diese Werkzeuge nennen (was nach Sperre und Einengung übrig ist);
    ``eingeengt=False`` (Muster-Weg): „bevorzuge“ statt „nur“ — dort engt nichts ein."""
    agent = schritt.agent
    if agent is None:
        return ""
    knopf_text = bot_text(lang, "action.ablauf.weiterKnopf")
    hinweis = ((agent.hinweis or {}).get(lang) or (agent.hinweis or {}).get("de") or "").strip()
    titel = (ablauf.titel.get(lang) or ablauf.titel.get("de") or ablauf.id)[:_TITEL_ZEICHEN]
    if zuege > agent.zuege:
        budget = (f"Das Budget dieses Schritts ist erschöpft: bitte die Person, mit dem Knopf "
                  f"„{knopf_text}“ fortzufahren.")
    else:
        budget = (f"Zug {zuege} von {agent.zuege}; weiter geht es mit dem Knopf „{knopf_text}“ "
                  "unter deiner Antwort.")
    teile = [f"Ablauf „{titel}“, Schritt {schritt.id}.", budget]
    if hinweis:
        teile.append(hinweis[:HINWEIS_ZEICHEN].rstrip(".") + ".")
    namen = [w for w in agent.werkzeuge if angeboten is None or w in angeboten]
    if namen:
        teile.append(f"{'Nur diese' if eingeengt else 'Bevorzuge diese'} Werkzeuge: "
                     f"{', '.join(namen)}.")
    if agent.ausgabe:
        teile.append(f"Ziel: der Teil {agent.ausgabe}.")
    kopf = "[ABLAUFSCHRITT — "
    inhalt = _ohne_klammern(" ".join(teile))
    return kopf + inhalt[:_ZEILE_ZEICHEN - len(kopf) - 1] + "]"


def zaehlen(entities: dict[str, Any], ablauf: AblaufArea, schritt: Schritt) -> int:
    """Diesen Zug am Schritt mitzählen — der wievielte er ist (ein neuer Schritt beginnt bei 1)."""
    schluessel = f"{ablauf.id}/{schritt.id}"
    bisher = entities.get(ZUEGE_KEY)
    n = (int(bisher.get("zuege") or 0) if isinstance(bisher, dict)
         and bisher.get("schritt") == schluessel else 0) + 1
    entities[ZUEGE_KEY] = {"schritt": schluessel, "zuege": n}
    return n


def einengen(tools: list[dict[str, Any]], schritt: Schritt) -> list[dict[str, Any]]:
    """Nur die Werkzeuge des Schritts und die virtuellen — in der Reihenfolge des Angebots."""
    erlaubt = set(schritt.agent.werkzeuge if schritt.agent else ()) | _VIRTUELL
    return [t for t in tools if (t.get("function") or {}).get("name") in erlaubt]


def knopf(ablauf_id: str, lang: str) -> str:
    """Die Schnellantwort „Weiter im Ablauf“ für ``ablauf_id``."""
    label = bot_text(lang, "action.ablauf.weiterKnopf").replace("|", "/")
    return f"__action__|{label}|{AKTION}|" + json.dumps({"ablauf": ablauf_id}, ensure_ascii=False)


def weiter_knopf(session_id: str, session_state: dict[str, Any], lang: str) -> str | None:
    """Der Knopf „Weiter im Ablauf“, solange ein Lauf am ``agent``-Schritt wartet."""
    if (treffer := aktueller(session_state, session_id)) is None:
        return None
    return knopf(treffer[0].id, lang)
