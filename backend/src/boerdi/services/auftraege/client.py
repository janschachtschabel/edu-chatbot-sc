"""Der b-api-Client für Aufträge (Kestra-Flows) — Paket K1a, Plan 2026-11-05 §5/§9.

Bekannt (Team-Info 2026-11-03): Abfrage ``GET /api/v1/jobs/{jobId}`` → ``status``, deklarierte
``outputs``, ``files`` (mit ``downloadUrl``); 20 unfertige Jobs je Schlüssel, danach 429; Jobs 30
Tage, Dateien 7 Tage abrufbar. Offen: der Start-Pfad (K16) → ``B_API_JOBS_START_PATH``, leer = aus.

Regeln dieses Clients:

- **Betrieb schaltet frei:** nur Flows aus ``B_API_JOBS_FLOWS`` (:func:`erlaubt`), nur lesende.
- **Schlüssel des Zuges** (``llm_auth.b_api_schluessel``) — nie gespeichert, nie geloggt. Deshalb
  fragt nur ein Zug der Person ab, kein Hintergrund-Wächter. Dass es der **durchgereichte**
  Schlüssel der Person ist (nicht ``B_API_KEY`` aller), prüft ``auftrag_zug`` (Review K1a, 1).
- **Kein ``X-Edu-User-Id``** (K18 offen): ohne geprüfte Bedeutung ginge sonst eine Identität mit.
- **Dateien** nur als Name und Größe: die Adresse kann ein Token tragen.
- Fehler als :class:`AuftragFehler` mit ``grund`` (``aus``, ``nicht_erlaubt``, ``voll``,
  ``abgewiesen``, ``unbekannt``, ``fehler``) — der Aufrufer macht daraus Text, nie aus der Antwort.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Final

import httpx

from boerdi.obs.trace_id import ausgehende_koepfe
from boerdi.services.llm_auth import b_api_schluessel
from boerdi.settings import get_settings

logger = logging.getLogger(__name__)

#: Für Tests: eine ``httpx.MockTransport`` (Vertrags-Attrappe).
_transport: httpx.AsyncBaseTransport | None = None
_FRIST: Final = httpx.Timeout(20.0, connect=5.0)
_ID: Final = re.compile(r"^(?!\.+$)[A-Za-z0-9_.\-]{1,200}$")
_FLOW: Final = re.compile(r"^[A-Za-z0-9_.\-]{1,100}(/[A-Za-z0-9_.\-]{1,100})?$")
_LAEUFT: Final = frozenset({"CREATED", "QUEUED", "RUNNING", "PAUSED", "RESTARTED", "RETRYING"})
_FERTIG: Final = frozenset({"SUCCESS", "WARNING"})
_FEHLER: Final = frozenset({"FAILED", "KILLED", "CANCELLED"})
_MAX_DATEIEN: Final = 50
#: Größte übernommene Ausgabe (JSON) — größer gilt als gescheitert (Review K1a, Befund 4).
MAX_AUSGABE_BYTES: Final = 1_000_000
#: Eine Pfad-Vorlage darf den Ziel-Server nicht wechseln (Review K1a, Befund 5).
_UNSICHER: Final = ("//", "@", "?", "#", "\\")


def kuerzel(job_id: str) -> str:
    """Paket K1b: ein Prüfkürzel des Auftrags für den Browser (``ui_fortschritt``) — die Job-ID
    selbst geht nie hinaus (sie öffnet mit dem Schlüssel der Person deren Ergebnisse)."""
    return hashlib.sha256(job_id.encode()).hexdigest()[:12]


class AuftragFehler(Exception):
    def __init__(self, grund: str) -> None:
        super().__init__(grund)
        self.grund = grund


@dataclass
class Stand:
    status: str                      # laeuft | fertig | fehler
    outputs: dict[str, Any] = field(default_factory=dict)
    dateien: list[dict[str, Any]] = field(default_factory=list)


def _flows() -> frozenset[str]:
    return frozenset(f.strip() for f in get_settings().b_api_jobs_flows.split(",") if f.strip())


def _vorlage(roh: str) -> str | None:
    """Eine Pfad-Vorlage — nur ab ``/`` und ohne Zeichen, die Server oder Anfrage wechseln."""
    vorlage = roh.strip()
    if not vorlage.startswith("/") or any(z in vorlage for z in _UNSICHER):
        return None
    return vorlage


def freigeschaltet() -> bool:
    """Sind Aufträge in dieser Anlage eingerichtet (gültiger Start-Pfad gesetzt)?"""
    return _vorlage(get_settings().b_api_jobs_start_path) is not None


def erlaubt(flow: str) -> bool:
    """Darf ein Ablauf diesen Flow starten? (eingerichtet, Form, freigeschaltet)"""
    return freigeschaltet() and bool(_FLOW.fullmatch(flow or "")) and flow in _flows()


def _wurzel() -> str:
    basis = get_settings().b_api_base_url.rstrip("/")
    for ende in ("/llm", "/api/v1"):
        if basis.endswith(ende):
            basis = basis[: -len(ende)]
    return basis


def _koepfe() -> dict[str, str]:
    koepfe = dict(ausgehende_koepfe())
    if schluessel := b_api_schluessel():
        koepfe["Authorization"] = f"Bearer {schluessel}"
    return koepfe


async def _anfrage(methode: str, pfad: str, **mehr: Any) -> httpx.Response:
    try:
        async with httpx.AsyncClient(timeout=_FRIST, transport=_transport) as http:
            return await http.request(methode, _wurzel() + pfad, headers=_koepfe(), **mehr)
    except (httpx.HTTPError, httpx.InvalidURL) as fehler:
        logger.warning("Auftrag: b-api nicht erreichbar (%s)", type(fehler).__name__)
        raise AuftragFehler("fehler") from fehler


def _pruefe_antwort(antwort: httpx.Response) -> dict[str, Any]:
    if antwort.status_code == 429:
        raise AuftragFehler("voll")
    if antwort.status_code in (401, 403):
        raise AuftragFehler("abgewiesen")
    if antwort.status_code == 404:
        raise AuftragFehler("unbekannt")
    code = antwort.status_code
    if code >= 300:
        logger.warning("Auftrag: b-api antwortet %d", code)
        raise AuftragFehler("fehler")
    try:
        daten = antwort.json()
    except ValueError as fehler:
        raise AuftragFehler("fehler") from fehler
    if not isinstance(daten, dict):
        raise AuftragFehler("fehler")
    return daten


async def starten(flow: str, eingaben: dict[str, Any]) -> str:
    """Einen Auftrag starten — die Job-ID."""
    if not freigeschaltet():
        raise AuftragFehler("aus")
    if not erlaubt(flow):
        raise AuftragFehler("nicht_erlaubt")
    pfad = (_vorlage(get_settings().b_api_jobs_start_path) or "").replace("{flow}", flow)
    daten = _pruefe_antwort(await _anfrage("POST", pfad, json=eingaben))
    job = next((daten[k] for k in ("jobId", "job_id", "id") if isinstance(daten.get(k), str)), "")
    if not _ID.fullmatch(job):
        logger.warning("Auftrag: Start ohne brauchbare Job-ID")
        raise AuftragFehler("fehler")
    logger.info("Auftrag gestartet (Flow %s)", flow)
    return job


def _dateien(roh: Any) -> list[dict[str, Any]]:
    aus: list[dict[str, Any]] = []
    for d in roh if isinstance(roh, list) else []:
        if isinstance(d, dict) and isinstance(d.get("name"), str):
            groesse = d.get("size")
            aus.append({"name": d["name"][:200],
                        "groesse": groesse if isinstance(groesse, int) else None})
    return aus[:_MAX_DATEIEN]


async def stand(job_id: str) -> Stand:
    """Der Stand eines Auftrags (``laeuft``/``fertig``/``fehler``)."""
    if not _ID.fullmatch(job_id or ""):
        raise AuftragFehler("unbekannt")
    if (vorlage := _vorlage(get_settings().b_api_jobs_status_path)) is None:
        raise AuftragFehler("aus")
    daten = _pruefe_antwort(await _anfrage("GET", vorlage.replace("{job_id}", job_id)))
    roh = str(daten.get("status") or "").upper()
    if roh in _LAEUFT:
        return Stand("laeuft")
    if roh in _FEHLER:
        return Stand("fehler")
    if roh not in _FERTIG:
        # Review K1a, Befund 2: ein unbekannter Stand ist kein Fehlschlag des Auftrags — erneut
        # abfragbar (der Vertrag ist erst gegen eine Attrappe gebaut, K16).
        logger.warning("Auftrag: unbekannter Stand der b-api")
        raise AuftragFehler("fehler")
    outputs = daten.get("outputs") if isinstance(daten.get("outputs"), dict) else {}
    if len(json.dumps(outputs, ensure_ascii=False, default=str).encode()) > MAX_AUSGABE_BYTES:
        logger.warning("Auftrag: Ausgabe zu groß — gilt als gescheitert")
        return Stand("fehler")
    return Stand("fertig", outputs, _dateien(daten.get("files")))
