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
from boerdi.domain.config_models.ablauf import STARTKNOPF_ZEICHEN, AblaufArea, Schritt
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
    if not treiber.gilt(ablauf, lauf):
        return None
    schritt = next((s for s in ablauf.schritte if s.id == lauf.get("schritt")), None)
    if schritt is None or schritt.typ != "agent" or schritt.agent is None:
        return None
    return ablauf, schritt


def mit_schrittmodulen(pattern_output: dict[str, Any], schritt: Schritt) -> dict[str, Any]:
    """Querschnitts-Review TW, Befund 5: im Muster-Weg bietet ein Muster nur die UI-Module an, die
    es unter ``tools:`` nennt — am KI-Schritt kommen die des Schritts dazu (sonst entstünde dort
    kein Entwurf, und die Vorgaben wirkten nie). Gibt eine Kopie zurück."""
    from boerdi.ui_module.katalog import katalog
    from boerdi.ui_module.namen import UI_WERKZEUGE_KEY

    module = [w for w in (schritt.agent.werkzeuge if schritt.agent else []) if w in katalog()]
    if not module:
        return pattern_output
    bisher = list(pattern_output.get(UI_WERKZEUGE_KEY) or [])
    neu = {**pattern_output, UI_WERKZEUGE_KEY: list(dict.fromkeys([*bisher, *module]))}
    if pattern_output.get("degradation") and pattern_output.get("missing_slots"):
        # Zweites Review TW, Befund 3: ein fehlender Slot des Musters (etwa ``thema``) leerte sonst
        # auch die Module des Schritts — der Hinweis fragt selbst nach. Die übrigen Werkzeuge des
        # Musters bleiben weg (Nach-Review): sonst suchte die KI ohne Thema.
        neu.update(degradation=False, missing_slots=[], tools=[])
    return neu


def vorgaben(schritt: Schritt, lang: str) -> str:
    """TW-2: die Vorgaben der Redaktion für die Module dieses Schritts — in der Sprache, sonst
    Deutsch, sonst leer."""
    texte = (schritt.agent.vorgaben if schritt.agent else None) or {}
    return ((texte.get(lang) or "").strip() or (texte.get("de") or "").strip())


def start_knopf(ablauf: AblaufArea, schritt_id: str, lang: str) -> str | None:
    """TW-3: der Startknopf des KI-Schritts — ein gewöhnliches Label (in der Sprache, sonst
    Deutsch); nie eine Direktaktion: ``|`` wird ``/``, ein Label mit ``__`` am Anfang zählt
    nicht."""
    schritt = next((s for s in ablauf.schritte if s.id == schritt_id), None)
    texte = (schritt.agent.startknopf if schritt and schritt.agent else None) or {}
    label = (texte.get(lang) or "").strip() or (texte.get("de") or "").strip()
    label = " ".join(label.replace("|", "/").split())[:STARTKNOPF_ZEICHEN]
    return label if label and not label.startswith("__") else None


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


def zuege_bisher(entities: dict[str, Any], ablauf_id: str, schritt_id: str) -> int:
    """Review TW-3, Befund 4: wie viele KI-Züge an diesem Schritt schon liefen (0: keiner)."""
    bisher = entities.get(ZUEGE_KEY)
    if isinstance(bisher, dict) and bisher.get("schritt") == f"{ablauf_id}/{schritt_id}":
        return int(bisher.get("zuege") or 0)
    return 0


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
