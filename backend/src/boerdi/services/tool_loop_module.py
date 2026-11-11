"""UI-Module als Werkzeuge im Muster-Weg (Paket U1-d2, U-F4).

Die Vorrunde der Muster-Schleife (``tool_loop._run_tool_loop``) für Modul-Aufrufe — wie die der
Ergebnis-Dokumente und aus demselben Grund: ``respond_to_user`` verlässt die Runde mit ``break``,
und stünde die Antwort vor der Frage, ginge die Frage verloren. Module ohne Datenquelle sind
virtuell: nie an den MCP, kein Eintrag in ``tools_called``.

Die Regeln sind die der Agent-Schleife (``agent_loop``, U1-d1): nur angebotene Module, der Aufruf
wird gegen ``eingabe`` geprüft (ein Fehler geht an die KI zurück), höchstens eine Frage je Antwort.
Die Blöcke legt die Vorrunde im ``session_state`` ab (:data:`MODUL_BLOECKE_KEY`) — die Schleife
kennt kein ``ctx``, wie bei ``_gelieferte_dokumente``. ``graph/nodes/respond`` holt sie mit
``pop`` ab, merkt sich die Frage und nimmt die Schnellantworten weg.

Seit U1-e asynchron: ein Modul mit Datenquelle (``ui_themenbaum``) holt seine Daten über das
MCP-Werkzeug; die KI bekommt nur die Quittung (``ui_module/datenquelle``). Seit U2 ebenso ein
Modul mit Dienst (``ui_strukturentwurf``, über ``ui_module/aufruf``) — mit dem Token-Zähler des
Zugs und dem gemerkten Entwurf als Vorlage (seit dem dritten Review U2). Dieser Aufruf steht wie
jeder MCP-Aufruf in ``tools_called``, ``outcomes`` und der Werkzeugzeit (Review U1-e, Befund 6);
seine Frist ist die des Transports (``MCP_CALL_TIMEOUT_S``) wie für die übrigen Werkzeuge der
Schleife. Liefert er keinen Block, meldet die Vorrunde das (:attr:`Vorrunde.ohne_block`): eine
Antwort derselben Runde gilt dann nicht (Befund 1).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Collection, Iterable
from dataclasses import dataclass, field
from typing import Any, Final

from boerdi.api.schemas_ui import UiBlock
from boerdi.domain.ui_bloecke import GENUG_BLOECKE, platz_fuer_anzeige
from boerdi.domain.werkzeug_angebot import NICHT_ANGEBOTEN
from boerdi.obs.zeiten import schritt
from boerdi.services import teil_verweise
from boerdi.ui_module.antwort import ZWEITE_FRAGE, frage_quittung
from boerdi.ui_module.aufruf import Umgebung, asynchron
from boerdi.ui_module.strukturentwurf_merken import vorlage as entwurf_vorlage
from boerdi.ui_module.werkzeuge import (
    ist_abfragendes_modul,
    ist_asynchron,
    ist_modul_werkzeug,
    modul_aufruf_annehmen,
)

_logger = logging.getLogger(__name__)

#: Wo der Muster-Weg die Blöcke der Modul-Werkzeuge ablegt; gehört DIESEM Zug. Bewusst nicht
#: ``domain/ui_bloecke.DEBUG_KEY`` (gespeicherte Blöcke im Debug-Block, Review U1-d2).
MODUL_BLOECKE_KEY: Final = "_modul_bloecke_zug"
#: U3-2b: der Lader für das Dokument der Sitzung (``services/dokumente/stand.lader``) — oberste
#: Ebene des ``session_state`` wie die Blöcke: er stirbt mit dem Zug, gespeichert wird er nie.
DOKUMENT_LADER_KEY: Final = "_dokument_lader_zug"
#: Paket V1: der Teil-Lader des aktiven Vorgangs — wie der Dokument-Lader nur für diesen Zug.
TEIL_LADER_KEY: Final = "_teil_lader_zug"
#: Plan 2026-11-11, TW-2: die Vorgaben des KI-Schritts eines Laufs (``ki_schritt.vorgaben``) und
#: die Werkzeuge des Schritts, für die sie gelten — nur für diesen Zug.
VORGABEN_KEY: Final = "_modul_vorgaben_zug"


@dataclass(slots=True)
class Vorrunde:
    """Was die Vorrunde erledigt hat — und ob ein Modul mit Datenquelle ohne Block blieb."""

    erledigt: set[str] = field(default_factory=set)
    ohne_block: bool = False


def offene_frage(session_state: dict) -> UiBlock | None:
    """Der abfragende Block dieses Zugs — oder ``None``."""
    return next((b for b in session_state.get(MODUL_BLOECKE_KEY) or []
                 if b.art == "abfragen"), None)


def _vorgaben_fuer(name: str, eintrag: Any) -> str:
    """Review TW-2, Befund 4: die Vorgaben nur für ein Modul, das der KI-Schritt nennt."""
    if isinstance(eintrag, tuple) and len(eintrag) == 2 and name in eintrag[1]:
        return str(eintrag[0] or "")
    return ""


def _anzeigende(session_state: dict) -> int:
    return sum(1 for b in session_state.get(MODUL_BLOECKE_KEY) or [] if b.art != "abfragen")


async def _ergebnis(name: str, roh_args: Any, angeboten: Collection[str],
                    session_state: dict, vorrunde: Vorrunde,
                    tools_called: list[str], outcomes: list, dokumente: int,
                    usage_acc: dict[str, Any] | None) -> str:
    if name not in angeboten:
        _logger.warning("tool-call %s: nicht angeboten, verworfen", name)
        return NICHT_ANGEBOTEN
    # Ein Platz bleibt der Frage (Review U1 gesamt, Befund 3); eine Antwort derselben Runde gilt
    # wie bei einem fehlenden Block nicht — sie verwiese womöglich auf die Anzeige.
    if (not ist_abfragendes_modul(name)
            and not platz_fuer_anzeige(dokumente + _anzeigende(session_state))):
        _logger.info("Modul-Werkzeug %s: kein Platz mehr in dieser Antwort", name)
        vorrunde.ohne_block = True
        return GENUG_BLOECKE
    try:
        args = json.loads(roh_args or "{}")
    except (json.JSONDecodeError, TypeError):
        args = None   # → die Prüfung gegen ``eingabe`` meldet die fehlenden Felder
    if isinstance(args, dict):
        # Paket V2 (Review, Befund 2): wie in der Agent-Schleife — nur Teile, die das Modul liest.
        args, fehlt = await teil_verweise.einsetzen(args, session_state.get(TEIL_LADER_KEY), name)
        if fehlt:
            return teil_verweise.fehlertext(fehlt)
    if ist_asynchron(name):
        # U2: eine zweite Frage kostet keinen Dienst-Aufruf; ohne Laufrist gilt die des Dienstes.
        if ist_abfragendes_modul(name) and offene_frage(session_state) is not None:
            return ZWEITE_FRAGE
        tools_called.append(name)
        with schritt("respond.werkzeuge"):
            # Drittes Review U2, Befund 2: der gemerkte Entwurf (``respond`` merkt ihn vorher).
            ergebnis = await asynchron(name, args, Umgebung(
                usage_acc=usage_acc, vorlage=entwurf_vorlage(session_state.get("entities") or {}),
                dokument=session_state.get(DOKUMENT_LADER_KEY),
                teile=session_state.get(TEIL_LADER_KEY), verfuegbar=frozenset(angeboten),
                vorgaben=_vorgaben_fuer(name, session_state.get(VORGABEN_KEY))))
        outcomes.append(ergebnis.outcome)
        if ergebnis.block is not None:
            session_state.setdefault(MODUL_BLOECKE_KEY, []).append(ergebnis.block)
        else:
            vorrunde.ohne_block = True
        return ergebnis.text
    block, fehler = modul_aufruf_annehmen(name, args)
    if block is None:
        _logger.info("Modul-Werkzeug %s: unbrauchbare Argumente", name)
        return fehler or ""
    if block.art == "abfragen" and offene_frage(session_state) is not None:
        return ZWEITE_FRAGE
    session_state.setdefault(MODUL_BLOECKE_KEY, []).append(block)
    return frage_quittung(block) if block.art == "abfragen" else "OK"


async def nimm_module_an(tool_calls: Iterable[Any], angeboten: Collection[str],
                         session_state: dict, messages: list[dict], *,
                         tools_called: list[str], outcomes: list, dokumente: int = 0,
                         usage_acc: dict[str, Any] | None = None) -> Vorrunde:
    """Alle Modul-Aufrufe der Runde annehmen und quittieren; Rückgabe: ihre Aufruf-Kennungen und
    ob eine Datenquelle ohne Block blieb. ``dokumente``: die schon gelieferten Dokumente des Zugs
    (sie belegen Anzeige-Plätze)."""
    vorrunde = Vorrunde()
    for tc in tool_calls:
        if not ist_modul_werkzeug(tc.function.name):
            continue
        vorrunde.erledigt.add(tc.id)
        messages.append({"role": "tool", "tool_call_id": tc.id, "content": await _ergebnis(
            tc.function.name, tc.function.arguments, angeboten, session_state, vorrunde,
            tools_called, outcomes, dokumente, usage_acc)})
    return vorrunde
