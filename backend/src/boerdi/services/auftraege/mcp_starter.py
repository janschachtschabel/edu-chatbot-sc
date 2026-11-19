"""Aufträge (Kestra-Flows) über die MCP-Werkzeuge — Paket K1, Plan 2026-11-17 (E1/E2).

Gleiche Schnittstelle wie ``client.starten``/``stand``/``abbrechen``, aber über ``wlo_start_flow``,
``wlo_flow_status`` und ``wlo_cancel_flow`` des WLO-MCP (Vertrag vom 18.11., ``wlo-mcp-server-sc``
``src/tools/bapi-flows.ts``). Der MCP startet über den b-api-Proxy des Repositorys mit der
Anmeldung der Person; das Delegations-Token der b-api braucht es dafür nicht.

Regeln:

- Gerufen wird wie bei der Stapel-Ablage (``services/ablage/mcp_ablage``): das Backend ruft
  selbst, mit dem **Zugangsblock des Zuges** und nur mit **bestätigter Anmeldung**; gelesen wird
  ``structuredContent``. Kein Modell dazwischen, kein Werkzeug-Angebot an die KI, kein Cache.
- **Start in zwei Schritten:** ohne ``confirmToken`` die Vorschau (der MCP prüft jeden Datensatz
  als die Person), dann derselbe Aufruf mit ``confirm.token``. Der Schlüssel lebt nur in dieser
  Funktion — nie im Modell, nie im Vorgang, nie im Log. Die Zustimmung der Person ist die Frage
  direkt vor dem Schritt (Prüfung ``auftrag_rueckfrage``, N15).
- **``error.outcomeOpen`` entscheidet, nicht ``reason``:** ``true`` (oder keine Antwort nach der
  Bestätigung) → :class:`AuftragFehler` ``offen`` — nie neu starten, der Aufrufer sieht nach;
  ``false`` → nichts gestartet.
- Die **jobId** verlässt dieses Modul nur als Kennung mit :data:`PRAEFIX` (für den Vorgang, die
  Datenbank und die Weiche :func:`ist_mcp`); sie steht nie in einem Log, nie in einem Text. Über
  den Repository-Proxy kann jede Person jeden Job lesen, dessen jobId sie kennt (Bericht MCP §4).
- ``unknown`` ist kein „läuft“ (erneut abfragbar, ``fehler``); ``unknown_job`` →
  ``job_unbekannt`` (nach einem Neustart des MCP auch eigene Jobs — kein Fehlschlag des Flows).
- Review A2 (19.11.): nach einem Neustart fehlen die Werkzeuge Sekunden bis Minuten in
  ``tools/list``. Nannte der MCP sie vor höchstens :data:`KUERZLICH_S` noch
  (:func:`kuerzlich_verfuegbar`), ist das „gleich wieder da“, kein Grund für den Direktweg;
  :func:`nachholen` fragt dann höchstens alle :data:`TAKT_NACH_FEHLER_S` neu.
"""

from __future__ import annotations

import logging
import re
import secrets
import time
from typing import Any, Final

from boerdi.domain.config_models.kestra_flows import ist_flow
from boerdi.services.auftraege import client
from boerdi.services.auftraege.client import AuftragFehler, Stand
from boerdi.services.mcp import faehigkeiten, transport
from boerdi.services.mcp.auth import _block_des_zuges as _zug_block
from boerdi.services.mcp.auth import has_personal_auth

logger = logging.getLogger(__name__)

START: Final = "wlo_start_flow"
STAND: Final = "wlo_flow_status"
ABBRUCH: Final = "wlo_cancel_flow"
#: K2: der MCP ist Träger nur, wenn er alle drei führt.
WERKZEUGE: Final = (START, STAND, ABBRUCH)
#: Kennung eines Jobs, den der MCP gestartet hat — der Doppelpunkt kommt in keiner jobId vor
#: (``JOB_ID`` des MCP), der Direktweg (``client._ID``) weist sie ab.
PRAEFIX: Final = "mcp:"
#: Ausgang des Starts offen: kein jobId — „Stand nachsehen“ liest die Datensätze (K1/K8).
_OFFEN: Final = PRAEFIX + "offen:"
JOB_ID: Final = re.compile(r"^(?!.*\.\.)[A-Za-z0-9_-][A-Za-z0-9_.-]{0,127}$")
#: Arten von ``transport.call_tool`` ohne strukturierten Teil.
_ARTEN: Final = {"auth": "abgewiesen", "busy": "voll"}
#: Nachtrag MCP 18.11.: ein Aufruf eines Werkzeugs, das der Server (gerade) nicht führt. Das SDK
#: des MCP (1.32) antwortet ``isError`` mit dem Text ``MCP error -32602: Tool <name> not found``
#: (ein älteres warf den JSON-RPC-Fehler, ``transport`` macht daraus dieselbe Art ``tool``).
UNBEKANNTES_WERKZEUG: Final = "unbekanntes_werkzeug"
_UNBEKANNT: Final = re.compile(r"\bTool \S+ (?:not found|disabled)\b")
#: Codes einer Ablehnung (``error.code`` = ``reason``) → Grund des Clients.
_GRUENDE: Final = {"not_allowed": "nicht_erlaubt", "bad_inputs": "eingaben",
                   "login_required": "abgewiesen", "login_rejected": "abgewiesen",
                   "rejected": "abgewiesen", "edu_user_required": "abgewiesen",
                   "rate_limited": "voll", "unknown_job": "job_unbekannt",
                   # vorübergehend: gleich noch einmal (nie ``job_unbekannt``, nie endgültig)
                   UNBEKANNTES_WERKZEUG: "nicht_verfuegbar"}
#: Schlüssel, die nie in ein Ergebnis gelangen (K8: der Teil des Auftrags zeigt keine Job-Kennung).
_KENNUNGEN: Final = frozenset({"jobId", "job_id", "executionId", "execution_id"})
#: Review A2: so lange nach der letzten Liste mit den Flow-Werkzeugen gilt ihr Fehlen als Neustart
#: des MCP (Sekunden bis Minuten laut Vertrag) — danach als „nicht da“.
KUERZLICH_S: Final = 600.0
#: Review A2: in diesem Abstand höchstens fragt :func:`nachholen` die Fähigkeiten neu, solange die
#: Werkzeuge kurz fehlen (der Takt von ``faehigkeiten`` fragt nur alle fünf Minuten).
TAKT_NACH_FEHLER_S: Final = 20.0
_jetzt = time.monotonic
#: Wann die Fähigkeiten zuletzt von hier aus neu geholt wurden (Uhr :data:`_jetzt`).
_neu_geholt: float | None = None


def verfuegbar() -> bool:
    """Führt der MCP alle drei Werkzeuge (``tools/list``)?"""
    return all(faehigkeiten.kennt_werkzeug(w) for w in WERKZEUGE)


def kuerzlich_verfuegbar() -> bool:
    """Review A2: fehlen die Werkzeuge gerade, nannte der MCP sie aber vor höchstens
    :data:`KUERZLICH_S` noch? Dann startet er vermutlich neu — „gleich noch einmal“."""
    if verfuegbar():
        return False
    alter = [faehigkeiten.alter(w) for w in WERKZEUGE]
    return all(a is not None and a <= KUERZLICH_S for a in alter)


async def nachholen() -> bool:
    """Review A2: fehlen die Werkzeuge kurz (:func:`kuerzlich_verfuegbar`), die Fähigkeiten neu
    holen — höchstens alle :data:`TAKT_NACH_FEHLER_S`. ``True``, wenn sie (wieder) da sind."""
    if verfuegbar():
        return True
    if not kuerzlich_verfuegbar():
        return False
    await _faehigkeiten_neu()
    return verfuegbar()


def ist_mcp(job_id: str | None) -> bool:
    """Hat der MCP diesen Auftrag gestartet (oder ist sein Start offen)?"""
    return (job_id or "").startswith(PRAEFIX)


def ist_offen(job_id: str | None) -> bool:
    return (job_id or "").startswith(_OFFEN)


def offene_kennung() -> str:
    """Kennung für einen Start mit offenem Ausgang — eine echte jobId gibt es nicht."""
    return _OFFEN + secrets.token_hex(8)


def flow_erlaubt(flow: str) -> bool:
    """Studio-Freigabe bzw. ``B_API_JOBS_FLOWS`` (wie beim Direktweg); der Start-Pfad der b-api gilt
    hier nicht — der MCP hält zusätzlich ``WLO_BAPI_FLOWS``."""
    return ist_flow(flow or "") and flow in client.freigegebene_flows()


def _job(job_id: str) -> str:
    roh = job_id[len(PRAEFIX):] if ist_mcp(job_id) and not ist_offen(job_id) else ""
    if not JOB_ID.fullmatch(roh):
        raise AuftragFehler("unbekannt")
    return roh


async def rufen(name: str, args: dict[str, Any]) -> tuple[dict[str, Any] | None, str, bool]:
    """Ein Werkzeug als die Person → (``structuredContent``, Fehlercode, Ausgang offen). Der Code
    ist ``""`` bei Erfolg; ohne strukturierten Teil die Art des Transports (``transport``,
    ``timeout``, ``auth``, ``busy``) bzw. :data:`UNBEKANNTES_WERKZEUG`."""
    if not has_personal_auth() or not _zug_block():
        raise AuftragFehler("abgewiesen")
    antwort = await transport.call_tool(name, args)
    fehler = antwort.get("error")
    if not fehler:
        daten = (antwort.get("result") or {}).get("structuredContent")
        return (daten if isinstance(daten, dict) else None), "", False
    strukturiert = fehler.get("structured")
    err = strukturiert.get("error") if isinstance(strukturiert, dict) else None
    if isinstance(err, dict) and err.get("code"):
        return strukturiert, str(err["code"]), err.get("outcomeOpen") is True
    art = str(fehler.get("kind") or "transport")
    if art == "tool" and _UNBEKANNT.search(str(fehler.get("message") or "")):
        # Nachtrag MCP 18.11.: nach einem Neustart fehlen die Werkzeuge Sekunden bis Minuten —
        # der Server führte nichts aus. Die Fähigkeiten neu holen; vorübergehend, kein Urteil.
        logger.info("Auftrag: der MCP kennt %s gerade nicht", name)
        await _faehigkeiten_neu()
        return None, UNBEKANNTES_WERKZEUG, False
    return None, art, art in ("transport", "timeout")


async def _faehigkeiten_neu() -> None:
    """Die Fähigkeiten neu holen — höchstens alle :data:`TAKT_NACH_FEHLER_S` (zweites Review, Z7:
    auch nach „unbekanntes Werkzeug“) und ohne dass ein Fehlschlag die Fähigkeiten verwirft
    (``faehigkeiten.nachfragen``)."""
    global _neu_geholt
    if _neu_geholt is not None and _jetzt() - _neu_geholt < TAKT_NACH_FEHLER_S:
        return
    _neu_geholt = _jetzt()
    try:
        await faehigkeiten.nachfragen()
    except Exception as fehler:  # noqa: BLE001 — der Takt fragt ohnehin wieder
        logger.info("Auftrag: Fähigkeiten nicht neu geholt (%s)", type(fehler).__name__)


def grund(code: str, daten: dict[str, Any] | None = None) -> AuftragFehler:
    """Der Fehler zu einem Code des MCP (öffentlich für ``mcp_vorschau``, Review N4)."""
    if code == "edu_user_required":
        return AuftragFehler("abgewiesen", code="EDU_USER_REQUIRED")
    art = _GRUENDE.get(code) or _ARTEN.get(code) or "fehler"
    warte = (daten or {}).get("retryAfter")
    # Review A3: bei ``rejected`` reicht der MCP den Code der b-api oben in ``daten`` durch
    # (``EDU_USER_NOT_VERIFIED``, ``LEGACY_HEADERS``) — nur aus der festen Liste des Clients
    roh = (daten or {}).get("code")
    b_api_code = roh if art == "abgewiesen" and roh in client.BEKANNTE_CODES else None
    return AuftragFehler(art, warte_s=min(warte, 600) if art == "voll" and isinstance(
        warte, int) and warte > 0 else None, code=b_api_code)


async def starten(flow: str, eingaben: dict[str, Any]) -> str:
    """Vorschau, dann Bestätigung im selben Zug — die Kennung des Auftrags (:data:`PRAEFIX` +
    jobId). Paket N4: beides steht in ``mcp_vorschau``; hier gehen spätere Teile eines Stapels,
    deren Liste die Person schon freigegeben hat (``ablauf/auftrag_freigabe``)."""
    from boerdi.services.auftraege import mcp_vorschau  # zyklenfrei: es importiert dieses Modul

    vorlage = await mcp_vorschau.vorschau(flow, eingaben)
    try:
        return await mcp_vorschau.bestaetigen(flow, eingaben, vorlage.token)
    except AuftragFehler as fehler:
        if fehler.grund == "abgelaufen":
            # ein eben geholter Schlüssel, der nicht gilt: im selben Zug keine Schleife
            raise AuftragFehler("fehler") from None
        raise


def _ohne_kennungen(wert: Any) -> Any:
    if isinstance(wert, dict):
        return {k: _ohne_kennungen(v) for k, v in wert.items() if k not in _KENNUNGEN}
    if isinstance(wert, list):
        return [_ohne_kennungen(v) for v in wert]
    return wert


def _dateien(roh: Any) -> list[dict[str, Any]]:
    """Wie ``client._dateien``: Name, Größe, Kennung, ob noch abrufbar — nie eine Adresse."""
    aus: list[dict[str, Any]] = []
    for d in roh if isinstance(roh, list) else []:
        if isinstance(d, dict) and isinstance(d.get("name"), str):
            eintrag: dict[str, Any] = {"name": d["name"][:200],
                                       "groesse": d["size"] if isinstance(d.get("size"), int)
                                       else None}
            if isinstance(d.get("outputId"), str):
                eintrag["kennung"] = d["outputId"][:64]
            if isinstance(d.get("available"), bool):
                eintrag["verfuegbar"] = d["available"]
            aus.append(eintrag)
    return aus[:50]


def _fortschritt(roh: Any) -> dict[str, int] | None:
    """``progress`` der b-api → „k von n fertig“. Fertig sind die abgeschlossenen Iterationen
    (gelungen, auch mit Warnung); gescheiterte zählen getrennt unter ``fehlgeschlagen`` (nur, wenn
    es welche gibt) — Durchtest Paket K (19.11.): vorher hieß ein ganz gescheiterter Job
    „3 von 3 fertig“."""
    if not isinstance(roh, dict):
        return None
    zahlen = {k: roh.get(k) for k in ("started", "succeeded", "warning", "failed")}
    if not all(isinstance(z, int) and not isinstance(z, bool) and z >= 0
               for z in zahlen.values()):
        return None
    aus = {"fertig": int(zahlen["succeeded"]) + int(zahlen["warning"]),
           "gesamt": int(zahlen["started"])}
    if zahlen["failed"]:
        aus["fehlgeschlagen"] = int(zahlen["failed"])
    return aus


async def stand(job_id: str) -> Stand:
    """Der Stand eines Auftrags (``laeuft``/``fertig``/``fehler``) über ``wlo_flow_status``."""
    if ist_offen(job_id):
        raise AuftragFehler("job_unbekannt")
    daten, code, _offen = await rufen(STAND, {"jobId": _job(job_id)})
    if code:
        logger.info("Auftrag: Stand über den MCP nicht abrufbar (%s)", code)
        raise grund(code, daten)
    daten = daten or {}
    status = daten.get("status")
    fortschritt = _fortschritt(daten.get("progress"))
    if status == "running":
        return Stand("laeuft", fortschritt=fortschritt)
    if status == "succeeded" and not daten.get("truncated"):
        outputs = daten.get("outputs")
        return Stand("fertig", _ohne_kennungen(outputs) if isinstance(outputs, dict) else {},
                     _dateien(daten.get("files")), warnungen=daten.get("warnings") is True,
                     fortschritt=fortschritt)
    if status in ("failed", "cancelled", "succeeded"):
        roh = daten.get("errorCode")
        fehlercode = roh[:60] if isinstance(roh, str) and roh else None
        logger.info("Auftrag gescheitert (Code %s)", fehlercode or "—")
        return Stand("fehler", fehlercode=fehlercode, fortschritt=fortschritt)
    # ``unknown``: ein Statuswort, das der MCP nicht kennt — nie „läuft“, erneut abfragbar
    logger.warning("Auftrag: unbekannter Stand über den MCP")
    raise AuftragFehler("fehler")


async def abbrechen(job_id: str) -> str:
    """``wlo_cancel_flow``: ``abgebrochen`` oder ``schon_fertig``. Unbekannt (fremd, Neustart des
    MCP) → ``job_unbekannt``; keine Antwort bzw. ``outcomeOpen`` → ``offen``."""
    if ist_offen(job_id):
        raise AuftragFehler("job_unbekannt")
    daten, code, offen = await rufen(ABBRUCH, {"jobId": _job(job_id)})
    if code:
        logger.info("Auftrag: Abbruch über den MCP nicht bestätigt (%s)", code)
        raise AuftragFehler("offen") if offen else grund(code)
    ausgang = (daten or {}).get("status")
    if ausgang == "cancelled":
        logger.info("Auftrag über den MCP abgebrochen")
        return "abgebrochen"
    if ausgang == "already_finished":
        return "schon_fertig"
    if ausgang == "unknown_job":
        raise AuftragFehler("job_unbekannt")
    raise AuftragFehler("offen")
