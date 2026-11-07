"""Wann ein Werkzeugaufruf ein zweites Mal hinausgeht (Plan 2026-11-07, CB-2 und CB-6).

Zwei Fälle, beide auf dem Ergebnis-Dict von ``transport.call_tool``:

* **Ausgelastet** (CB-2/S2). Ein 429/503 des Servers oder ``upstream_busy`` des Repositorys:
  nichts lief. Nennt der Server eine Wartezeit bis ``MCP_BUSY_RETRY_MAX_S``, wird sie einmal
  abgewartet; eine längere beendet den Aufruf als „ausgelastet“ — nicht sofort wiederholen.
  ``upstream_busy`` mit ``requiresNewPreview`` kam NACH der Einlösung eines Schlüssels: derselbe
  Aufruf bekäme nur dieselbe Antwort (S3) — kein zweiter Versuch.
* **Bestätigter Schreibaufruf ohne Antwort** (CB-6/S3). Der Server behält die erste Antwort eines
  eingelösten Schlüssels 30 Minuten, gebunden an Anmeldung und Angaben. Derselbe Aufruf mit
  demselben Schlüssel bringt sie zurück (``replayed``) oder sagt, dass sie noch läuft
  (``inProgress``) — geschrieben wird dabei nichts ein zweites Mal. Kennt der Server den
  Schlüssel nicht mehr (``confirm_*``: Neustart, Frist), bleibt der Ausgang offen wie zuvor.
  Pläne nehmen nicht teil: sie setzen über ihren ``continuationToken`` fort.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from boerdi.domain.write_confirm import is_plan
from boerdi.settings import get_settings

logger = logging.getLogger(__name__)

Rufe = Callable[[], Awaitable[dict[str, Any]]]

#: ``inProgress``: so oft fragen und so lange dazwischen warten.
NACHFRAGEN = 4
NACHFRAGE_ABSTAND_S = 2.5
#: Höchstens so lange dauert das Nachholen insgesamt — der erste Aufruf hat schon gewartet.
NACHHOLEN_FRIST_S = 20.0


def _strukturfehler(fehler: dict[str, Any]) -> dict[str, Any]:
    sc = fehler.get("structured")
    e = sc.get("error") if isinstance(sc, dict) else None
    return e if isinstance(e, dict) else {}


def _sekunden(wert: Any) -> float | None:
    if isinstance(wert, bool) or not isinstance(wert, int | float) or wert < 0:
        return None
    return float(wert)


def kurze_wartezeit(result: dict[str, Any]) -> float | None:
    """Die Wartezeit, nach der ``result`` einmal wiederholt wird — ``None``: nicht wiederholen."""
    fehler = result.get("error")
    if not isinstance(fehler, dict):
        return None
    if fehler.get("kind") == "busy" and fehler.get("grund") in ("rate_limited", "unavailable"):
        warte = _sekunden(fehler.get("retry_after"))
    elif fehler.get("kind") == "tool":
        e = _strukturfehler(fehler)
        if e.get("code") != "upstream_busy" or e.get("requiresNewPreview"):
            return None
        warte = _sekunden(e.get("retryAfter"))
    else:
        return None
    return warte if warte is not None and warte <= get_settings().mcp_busy_retry_max_s else None


async def nach_kurzer_wartezeit(result: dict[str, Any], rufe: Rufe) -> dict[str, Any]:
    """``result`` — oder, nach einer kurzen Wartezeit des Servers, ein zweiter Aufruf."""
    warte = kurze_wartezeit(result)
    if warte is None:
        return result
    await asyncio.sleep(warte)
    return await rufe()


def _nimmt_teil(tool_name: str, result: dict[str, Any]) -> bool:
    fehler = result.get("error")
    return (isinstance(fehler, dict) and fehler.get("kind") in ("transport", "timeout")
            and not is_plan(tool_name))


async def bestaetigten_aufruf_nachholen(tool_name: str, result: dict[str, Any],
                                        rufe: Rufe) -> dict[str, Any]:
    """Einem bestätigten Schreibaufruf ohne Antwort die Antwort nachholen (S3), sonst ``result``."""
    if not _nimmt_teil(tool_name, result):
        return result
    try:
        async with asyncio.timeout(NACHHOLEN_FRIST_S):
            for _ in range(NACHFRAGEN):
                erneut = await rufe()
                if "error" in erneut:
                    return _fehler_nachgeholt(tool_name, result, erneut)
                sc = (erneut.get("result") or {}).get("structuredContent") or {}
                if isinstance(sc, dict) and sc.get("inProgress"):
                    await asyncio.sleep(NACHFRAGE_ABSTAND_S)
                    continue
                logger.info("MCP tool %s: Antwort des bestätigten Aufrufs nachgeholt (%s)",
                            tool_name, "wiederholt" if sc.get("replayed") else "ausgeführt")
                return ohne_wiederholungshinweis(erneut)
    except TimeoutError:
        pass
    logger.warning("MCP tool %s: Antwort des bestätigten Aufrufs nicht nachzuholen — Ausgang "
                   "offen", tool_name)
    return result


def _fehler_nachgeholt(tool_name: str, result: dict[str, Any],
                       erneut: dict[str, Any]) -> dict[str, Any]:
    """Ein Fehler beim Nachholen: die Antwort des Servers zum ersten Aufruf — außer er weiß
    nichts mehr davon (``confirm_*``), kennt die Anmeldung nicht mehr (``login_*``, 401) oder
    antwortete wieder nicht. Dann bleibt der Ausgang offen (``result``)."""
    fehler = erneut["error"]
    code = str(_strukturfehler(fehler).get("code") or "")
    # Ohne Code (ein Server vor dem 07.11.) ist „unbekannt oder benutzt“ nicht von einer echten
    # Ablehnung zu unterscheiden — offen lassen, die vorsichtige Richtung.
    if fehler.get("kind") != "tool" or not code or code.startswith(("confirm_", "login_")):
        logger.warning("MCP tool %s: Nachholen ohne Ergebnis (%s) — Ausgang offen",
                       tool_name, code or fehler.get("kind") or "transport")
        return result
    return erneut


def ohne_wiederholungshinweis(result: dict[str, Any]) -> dict[str, Any]:
    """Eine wiederholte Antwort (``replayed``) trägt vorn den Satz des Servers „schon eingelöst
    — hier die Antwort von damals“. Für die Person ist es die Antwort auf ihr Ja; der Satz fällt
    weg, ``replayed`` bleibt im strukturierten Teil."""
    daten = result.get("result") or {}
    sc = daten.get("structuredContent")
    inhalt = daten.get("content") or []
    if not (isinstance(sc, dict) and sc.get("replayed") and len(inhalt) > 1):
        return result
    return {**result, "result": {**daten, "content": inhalt[1:]}}
