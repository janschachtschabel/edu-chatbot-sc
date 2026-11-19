"""Paket N4 (Plan 2026-11-19): Vorschau und Bestätigung eines Starts über den MCP, getrennt.

``mcp_starter.starten`` rief beides im selben Zug (Paket K, Entscheid 1). Für die Freigabe-Box holt
der Server erst die Vorschau (:func:`vorschau`), zeigt sie, und erst „Freigeben“ bestätigt mit dem
gespeicherten Schlüssel (:func:`bestaetigen`). Drahtform: ``wlo-mcp-server-sc``
``src/tools/bapi-flows.ts`` (``confirm.token``, ``confirm.expiresAt``, ``confirm.preview.items`` als
``nodeId „Titel“``; ein Datensatz mit Problem lässt die GANZE Vorschau scheitern —
``bad_inputs``/``upstream_error`` mit ``problems``).

Der Schlüssel verlässt dieses Modul nur in :class:`Vorschau` an den Aufrufer, der ihn serverseitig
hält (``ablauf/auftrag_freigabe``) — nie im Log, nie im Text.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Final

from boerdi.domain.write_confirm import TOKEN_TTL_SECONDS
from boerdi.services.auftraege.client import AuftragFehler
from boerdi.services.auftraege.mcp_starter import (
    JOB_ID,
    PRAEFIX,
    START,
    flow_erlaubt,
    grund,
    rufen,
)

logger = logging.getLogger(__name__)

#: Probleme eines Datensatzes laut MCP (``PROBLEM_TEXT``); ein anderer Wert heißt ``unbekannt``.
PROBLEME: Final = frozenset({"not_found", "not_readable", "not_a_record", "is_reference",
                             "not_writable", "unchecked"})
#: Nach diesen Codes der Bestätigung ist nichts gestartet, der Schlüssel aber nicht mehr gut — eine
#: neue Vorschau hilft (``confirmOrExplain``: ``outcomeOpen: false``).
_NEU_VORLEGEN: Final = frozenset({"confirm_expired", "confirm_mismatch"})


class VorschauFehler(AuftragFehler):
    """Die Vorschau scheiterte; ``probleme`` nennt Datensätze, die nicht mitgehen können."""

    def __init__(self, grund: str, probleme: list[tuple[str, str]], **mehr: Any) -> None:
        super().__init__(grund, **mehr)
        self.probleme = probleme


@dataclass(frozen=True)
class Vorschau:
    token: str
    #: Bis wann der Schlüssel gilt (Epoche, höchstens die eigene Frist).
    laeuft_ab: float
    #: nodeId → Titel aus ``preview.items`` (ohne Anführungszeichen).
    titel: dict[str, str] = field(default_factory=dict)


def _frist(roh: Any, jetzt: float) -> float:
    """``expiresAt`` des MCP, höchstens die eigene Frist. Liegt sie schon beim Holen in der
    Vergangenheit (Uhrenversatz zwischen den Servern), gilt die eigene — sonst wäre die Vorschau
    nie einlösbar; ein wirklich abgelaufener Schlüssel kommt als ``confirm_expired`` zurück."""
    eigene = jetzt + TOKEN_TTL_SECONDS
    try:
        frist = datetime.fromisoformat(str(roh).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return eigene
    return eigene if frist <= jetzt else min(frist, eigene)


def _titel(items: Any) -> dict[str, str]:
    """``nodeId „Titel“`` → ``{nodeId: Titel}``. Review N4 (7): ein fremder Flow zeigt seine
    Eingaben als JSON — dessen ``node_ids`` zählen ohne Titel; andere Zeilen fallen weg."""
    aus: dict[str, str] = {}
    for zeile in items if isinstance(items, list) else []:
        kennung, _, rest = str(zeile).partition(" ")
        if kennung and rest.startswith("„") and rest.endswith("“"):
            aus[kennung] = rest[1:-1][:200]
            continue
        try:
            eingaben = json.loads(str(zeile))
        except ValueError:
            continue
        ids = eingaben.get("node_ids") if isinstance(eingaben, dict) else None
        for k in ids if isinstance(ids, list) else []:
            if isinstance(k, str) and k:
                aus.setdefault(k, "")
    return aus


def _probleme(daten: dict[str, Any] | None) -> list[tuple[str, str]]:
    roh = (daten or {}).get("problems")
    return [(str(p["nodeId"]), p["problem"] if p.get("problem") in PROBLEME else "unbekannt")
            for p in roh if isinstance(p, dict) and isinstance(p.get("nodeId"), str)
            ] if isinstance(roh, list) else []


async def vorschau(flow: str, eingaben: dict[str, Any]) -> Vorschau:
    """``wlo_start_flow`` ohne Schlüssel. Wirft :class:`VorschauFehler` (mit ``probleme``) bzw.
    ``AuftragFehler``; ohne Schlüssel startet nichts."""
    if not flow_erlaubt(flow):
        raise AuftragFehler("nicht_erlaubt")
    daten, code, _offen = await rufen(START, {"flow": flow, "inputs": eingaben})
    if code:
        logger.info("Auftrag: Vorschau des MCP abgelehnt (%s)", code)
        fehler = grund(code, daten)
        if probleme := _probleme(daten):
            raise VorschauFehler(fehler.grund, probleme, warte_s=fehler.warte_s, code=fehler.code)
        raise fehler
    bestaetigung = (daten or {}).get("confirm")
    token = bestaetigung.get("token") if isinstance(bestaetigung, dict) else None
    if (daten or {}).get("status") != "preview" or not isinstance(token, str) or not token:
        logger.warning("Auftrag: Vorschau des MCP ohne Schlüssel")
        raise AuftragFehler("fehler")
    vorschau_daten = bestaetigung.get("preview") if isinstance(bestaetigung, dict) else None
    items = vorschau_daten.get("items") if isinstance(vorschau_daten, dict) else None
    return Vorschau(token=token, laeuft_ab=_frist(bestaetigung.get("expiresAt"), time.time()),
                    titel=_titel(items))


async def bestaetigen(flow: str, eingaben: dict[str, Any], token: str) -> str:
    """Derselbe Aufruf mit ``confirmToken`` — die Kennung des Auftrags (``mcp:<jobId>``).

    - ``confirm_expired``/``confirm_mismatch`` ohne offenen Ausgang → ``abgelaufen`` (nichts
      gestartet, eine neue Vorschau hilft);
    - offener Ausgang, keine Antwort, ``isError`` ohne Code (Review A6) → ``offen`` — nie neu
      starten;
    - ``replayed: true`` (ein zweites „Freigeben“ bis zum MCP) ist derselbe Job."""
    if not flow_erlaubt(flow):
        raise AuftragFehler("nicht_erlaubt")
    daten, code, offen = await rufen(START, {"flow": flow, "inputs": eingaben,
                                              "confirmToken": token})
    if code:
        if offen or code == "tool":
            logger.warning("Auftrag: Ausgang des Starts offen (%s) — kein neuer Start", code)
            raise AuftragFehler("offen")
        if code in _NEU_VORLEGEN:
            logger.info("Auftrag: Schlüssel nicht mehr gültig (%s) — neue Vorschau", code)
            raise AuftragFehler("abgelaufen")
        logger.info("Auftrag nicht gestartet (%s)", code)
        raise grund(code, daten)
    job = (daten or {}).get("jobId")
    if (daten or {}).get("status") != "started" or not isinstance(job, str) \
            or not JOB_ID.fullmatch(job):
        # ``inProgress`` oder 202 ohne brauchbare jobId: ein Job KANN laufen
        logger.warning("Auftrag: Start über den MCP ohne brauchbare Kennung — Ausgang offen")
        raise AuftragFehler("offen")
    if (daten or {}).get("replayed") is True:
        logger.info("Auftrag: Bestätigung wiederholt — derselbe Job (Flow %s)", flow)
    else:
        logger.info("Auftrag über den MCP gestartet (Flow %s)", flow)
    return PRAEFIX + job
