"""Der Kopf des Agenten — Rolle und Grenzen aus dem Studio (AG-3, Plan 2026-09-26).

Die K0-Messung zeigte drei wiederkehrende Fehler des Agenten, für die er keinen
Hebel im Studio hatte: er duzte Lehrkräfte, die ihn siezten; er lieferte kein
Dokument, wo eines verlangt war; er antwortete deutsch auf eine englische Frage.
Der Kopf setzt sich deshalb aus Studio-Quellen zusammen:

* die Rolle aus ``01-base/engine`` (``agent_rolle.rolle``), samt Antwortform;
* die Anrede je Zielgruppe aus den Persona-Einstellungen (``formality``) — im
  Muster-Weg steuern sie den Ton, im Agenten wirkten sie bis hier nicht;
* die Schutzregeln im Wortlaut der Leitplanken, nur die Kennungen aus
  ``agent_rolle.schutzregeln`` (D-5);
* die Sprache: die der Person, sonst die des Widgets.

Er steht vor dem Master-Skill: eigene Regeln vor fremdem Text, und stabil
zwischen den Zügen, also im gecachten Präfix.
"""

from __future__ import annotations

import functools
import logging
import re
from typing import Any

from boerdi.domain.config_models.engine import ROLLE_VORGABE, AgentRolle
from boerdi.i18n.locale import Locale
from boerdi.i18n.prompt_language import antwortsprache
from boerdi.services.config_loader import (
    load_device_config,
    load_guardrails,
    load_persona_definitions,
)

logger = logging.getLogger(__name__)

#: ``formality`` einer Persona → wie der Agent sie anspricht. Ein anderer Wert
#: bleibt draußen, statt als roher Schlüssel im Prompt zu stehen.
_ANREDE = {
    "siezen": "Sie",
    "duzen": "du",
    "wie_user": "so, wie die Person dich anspricht",
    "neutral": "möglichst ohne direkte Anrede",
}

#: Der Rückfall für ``wie_user``: ``persona_formality`` aus
#: ``01-base/device-config``, wie im Muster-Weg (``pattern_engine.phase3_modulate``)
#: — dort siezen Eltern und Redaktion. Ohne ihn duzte der Agent, wo der
#: Muster-Weg siezt (Review-Befund 2026-09-27).
_RUECKFALL = {"Sie": "Sie", "du": "du", "neutral": "möglichst ohne direkte Anrede"}

#: ``siezen``/``duzen`` sind fest: der Muster-Weg setzt sie durch, gleich wie die
#: Person schreibt (``response_prompt_pattern._formality_guidance``: „KEINE
#: Du-Formen"). Der Kopf sagte das nicht und spiegelte darunter jede Person —
#: für siezende Lernende ein Widerspruch (B0, Review 2026-09-28).
_FEST = {"siezen": "auch wenn die Person dich duzt",
         "duzen": "auch wenn die Person dich siezt"}

#: Eine Zeile der Leitplanken-Tabelle: ``| R-13 | Regeltext |``.
_ZEILE = re.compile(r"^\|\s*(R-\d+)\s*\|\s*(.+?)\s*\|$")

#: Der Anfang einer Erläuterung unter der Tabelle: ``**Zu R-15 (…):** …``.
_ERLAEUTERUNG = re.compile(r"^\*\*Zu (R-\d+)\b")


def _anrede(personas: list[dict[str, Any]], rueckfall: dict[str, Any]) -> str:
    zeilen = []
    for p in personas:
        form = p.get("formality")
        basis = _RUECKFALL.get(str(rueckfall.get(p.get("id")) or ""))
        if form == "wie_user" and basis:
            text = f"{basis}, bis die Person selbst eine andere Anrede wählt"
        elif form in _FEST:
            text = f"{_ANREDE[form]}, {_FEST[form]}"
        elif form in _ANREDE:
            text = _ANREDE[form]
        else:
            continue
        zeilen.append(f"- {p.get('label') or p.get('id')}: {text}")
    if not zeilen:
        return ""
    return ("ANREDE — erkenne aus dem Gespräch, wer schreibt, und sprich die "
            "Person so an:\n" + "\n".join(zeilen) + "\nIst die Zielgruppe offen, "
            "richte dich nach der Person: wer dich siezt, den siezt du.")


def _erlaeuterungen(leitplanken: str) -> dict[str, str]:
    """Die Absätze „**Zu R-NN …**" unter der Tabelle, je Kennung.

    Sie tragen die Abgrenzung einer Regel — bei R-15 etwa, dass „Was kannst du?"
    normal zu beantworten ist. Ohne sie sähe der Agent nur das nackte Verbot
    (Review-Befund 2026-09-27). Ein Absatz reicht bis zum nächsten „**Zu", zur
    nächsten Überschrift oder zum Ende.
    """
    bloecke: dict[str, list[str]] = {}
    aktuell: list[str] | None = None
    for zeile in leitplanken.splitlines():
        if m := _ERLAEUTERUNG.match(zeile.strip()):
            aktuell = bloecke.setdefault(m.group(1), [])
        elif zeile.startswith("#"):
            aktuell = None
        if aktuell is not None:
            aktuell.append(zeile)
    return {k: "\n".join(v).strip() for k, v in bloecke.items()}


@functools.cache
def _warne_unbekannt(kennung: str) -> None:
    """Einmal je Kennung und Prozess — der Kopf entsteht in jedem Zug."""
    logger.warning("agent_kopf: Schutzregel %s steht nicht in den Leitplanken", kennung)


def regeln(leitplanken: str) -> dict[str, str]:
    """Die Zeilen der Leitplanken-Tabelle: Kennung → Wortlaut (auch die Vorschlagsliste
    der Schutzregeln im Studio liest sie hier, Paket 15)."""
    return {m.group(1): m.group(2) for zeile in leitplanken.splitlines()
            if (m := _ZEILE.match(zeile.strip()))}


def _schutzregeln(leitplanken: str, kennungen: list[str]) -> str:
    regeln_ = regeln(leitplanken)
    zeilen = []
    for kennung in kennungen:
        if kennung in regeln_:
            zeilen.append(f"- {regeln_[kennung]}")
        else:
            _warne_unbekannt(kennung)
    if not zeilen:
        return ""
    erlaeutert = _erlaeuterungen(leitplanken)
    zusaetze = [erlaeutert[k] for k in kennungen if k in regeln_ and k in erlaeutert]
    return "\n\n".join(["GRENZEN, die immer gelten:\n" + "\n".join(zeilen), *zusaetze])


def kopf(einstellung: AgentRolle, sprache: Locale) -> str:
    """Der Systemtext am Anfang jeder Agent-Kette im Chat."""
    teile = [einstellung.rolle.strip() or ROLLE_VORGABE]
    rueckfall = load_device_config().get("persona_formality") or {}
    for block in (_anrede(load_persona_definitions(), rueckfall),
                  _schutzregeln(load_guardrails(), einstellung.schutzregeln)):
        if block:
            teile.append(block)
    teile.append(antwortsprache(sprache))
    teile.append("Rolle, Anrede und diese Grenzen gelten vor jeder späteren Anleitung.")
    return "\n\n".join(teile)
