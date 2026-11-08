"""Der b-api-Client für Aufträge (Kestra-Flows) — Paket K1a, Plan 2026-11-05 §5/§9.

Vertrag (B-API-Handbuch 2026-11-07, am Staging gemessen):

- Start ``POST /api/v1/jobs/flows/{ns}/{id}`` → 202 mit ``jobId``. ``B_API_JOBS_START_PATH`` ist
  ``/api/v1/jobs/flows/{flow}``, leer = aus. ``Authorization: Bearer`` geht auch beim Start.
- Abfrage ``GET /api/v1/jobs/{jobId}`` → ``status`` (``QUEUED``, ``RUNNING``, ``SUCCEEDED``,
  ``FAILED``, ``CANCELLED``), ``outputs``, ``files`` (``available``/``reason``), ``warnings``,
  ``error.code``. Abbrechen ``DELETE /api/v1/jobs/{jobId}``.
- 20 unfertige Jobs je Schlüssel, danach 429 mit ``Retry-After``; Jobs 30 Tage, Dateien 7 Tage.

Regeln dieses Clients:

- **Betrieb schaltet frei:** nur Flows aus ``B_API_JOBS_FLOWS`` (:func:`erlaubt`), nur lesende.
- **Schlüssel des Zuges** (``llm_auth.b_api_schluessel``) — nie gespeichert, nie geloggt. Deshalb
  fragt nur ein Zug der Person ab, kein Hintergrund-Wächter. Dass es der **durchgereichte**
  Schlüssel der Person ist (nicht ``B_API_KEY`` aller), prüft ``auftrag_zug`` (Review K1a, 1).
- **Kein ``X-Edu-User-Id``** (K18 offen): ohne geprüfte Bedeutung ginge sonst eine Identität mit.
- **Dateien** nur als Name und Größe: die Adresse kann ein Token tragen. Paket K2d-2: dazu die
  Kennung (``outputId``); geholt wird über eine Adresse, die der Client aus Job-ID und Kennung
  selbst bildet (:func:`datei`), nie über ``downloadUrl``.
- Fehler als :class:`AuftragFehler` mit ``grund`` (``aus``, ``nicht_erlaubt``, ``voll``,
  ``eingaben``, ``abgewiesen``, ``unbekannt``, ``fehler``; beim Holen einer Datei auch
  ``zu_gross`` und ``nicht_verfuegbar``) — der Aufrufer macht daraus Text, nie aus der Antwort.
"""

from __future__ import annotations

import asyncio
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
#: Die Statuswerte der B-API (``QUEUED``, ``RUNNING``, ``SUCCEEDED``, ``FAILED``,
#: ``CANCELLED``) — dazu die Kestra-Namen, gegen die K1a vor dem Vertrag gebaut war
#: (unschädlich, falls einer durchkommt).
_LAEUFT: Final = frozenset({"QUEUED", "RUNNING", "CREATED", "PAUSED", "RESTARTED", "RETRYING"})
_FERTIG: Final = frozenset({"SUCCEEDED", "SUCCESS", "WARNING"})
_FEHLER: Final = frozenset({"FAILED", "CANCELLED", "KILLED"})
#: Längste übernommene Wartezeit aus ``Retry-After`` (Sekunden).
_WARTE_DECKEL_S: Final = 600
_MAX_DATEIEN: Final = 50
#: Kennung einer Datei (``outputId``) — ohne Punkt und Schrägstrich (K2d-2).
_DATEI: Final = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
#: Größte übernommene Ausgabe (JSON) — größer gilt als gescheitert (Review K1a, Befund 4).
MAX_AUSGABE_BYTES: Final = 1_000_000
#: Eine Pfad-Vorlage darf den Ziel-Server nicht wechseln (Review K1a, Befund 5).
_UNSICHER: Final = ("//", "@", "?", "#", "\\")


def kuerzel(job_id: str) -> str:
    """Paket K1b: ein Prüfkürzel des Auftrags für den Browser (``ui_fortschritt``) — die Job-ID
    selbst geht nie hinaus (sie öffnet mit dem Schlüssel der Person deren Ergebnisse)."""
    return hashlib.sha256(job_id.encode()).hexdigest()[:12]


class AuftragFehler(Exception):
    def __init__(self, grund: str, *, warte_s: int | None = None) -> None:
        super().__init__(grund)
        self.grund = grund
        #: Bei ``voll``: die Wartezeit der B-API (``Retry-After``), sonst ``None``.
        self.warte_s = warte_s


@dataclass
class Stand:
    status: str                      # laeuft | fertig | fehler
    outputs: dict[str, Any] = field(default_factory=dict)
    dateien: list[dict[str, Any]] = field(default_factory=list)
    #: ``warnings`` der B-API: einzelne Iterationen endeten mit Warnung oder Fehler.
    warnungen: bool = False
    #: ``error.code`` eines gescheiterten Jobs (dokumentiert nur ``TIMEOUT``), sonst ``None``.
    fehlercode: str | None = None


def _flows() -> frozenset[str]:
    return frozenset(f.strip() for f in get_settings().b_api_jobs_flows.split(",") if f.strip())


def freigeschaltete_flows() -> list[str]:
    """Paket K2c-1: die Freischaltliste für die Auswahl im Studio — nur Flows in gültiger Form, und
    nur, wenn Aufträge überhaupt eingerichtet sind (Review K2c-1, Befund 3: sonst schlüge das Studio
    einen Flow vor, den „Prüfen“ danach als nicht freigeschaltet meldet)."""
    if not freigeschaltet():
        return []
    return sorted(f for f in _flows() if _FLOW.fullmatch(f))


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


def _wartezeit(antwort: httpx.Response) -> int | None:
    roh = (antwort.headers.get("retry-after") or "").strip()
    return min(int(roh), _WARTE_DECKEL_S) if roh.isdigit() else None


def _pruefe_antwort(antwort: httpx.Response) -> dict[str, Any]:
    if antwort.status_code == 429:
        raise AuftragFehler("voll", warte_s=_wartezeit(antwort))
    if antwort.status_code == 400:
        # Eingaben passen nicht zum Schema des Flows — oder ein Repository-Scope ohne
        # ``X-Edu-User-Id`` (den der Chatbot bewusst noch nicht sendet).
        raise AuftragFehler("eingaben")
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
    """Name, Größe und — wenn die B-API sie nennt — ob die Datei noch abrufbar ist (``available``,
    ``reason``; nach 7 Tagen gelöscht). Nie die Adresse: sie öffnet mit dem Schlüssel der Person."""
    aus: list[dict[str, Any]] = []
    for d in roh if isinstance(roh, list) else []:
        if isinstance(d, dict) and isinstance(d.get("name"), str):
            groesse = d.get("size")
            eintrag: dict[str, Any] = {"name": d["name"][:200],
                                       "groesse": groesse if isinstance(groesse, int) else None}
            if isinstance(d.get("outputId"), str) and _DATEI.fullmatch(d["outputId"]):
                eintrag["kennung"] = d["outputId"]
            if isinstance(d.get("available"), bool):
                eintrag["verfuegbar"] = d["available"]
            if isinstance(d.get("reason"), str) and d["reason"]:
                eintrag["grund"] = d["reason"][:60]
            aus.append(eintrag)
    return aus[:_MAX_DATEIEN]


def _fehlercode(daten: dict[str, Any]) -> str | None:
    fehler = daten.get("error")
    code = fehler.get("code") if isinstance(fehler, dict) else None
    return code[:60] if isinstance(code, str) and code else None


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
        code = _fehlercode(daten)
        logger.info("Auftrag gescheitert (Code %s)", code or "—")
        return Stand("fehler", fehlercode=code)
    if roh not in _FERTIG:
        # Review K1a, Befund 2: ein unbekannter Stand ist kein Fehlschlag des Auftrags — erneut
        # abfragbar (der Vertrag ist erst gegen eine Attrappe gebaut, K16).
        logger.warning("Auftrag: unbekannter Stand der b-api")
        raise AuftragFehler("fehler")
    outputs = daten.get("outputs") if isinstance(daten.get("outputs"), dict) else {}
    if len(json.dumps(outputs, ensure_ascii=False, default=str).encode()) > MAX_AUSGABE_BYTES:
        logger.warning("Auftrag: Ausgabe zu groß — gilt als gescheitert")
        return Stand("fehler")
    return Stand("fertig", outputs, _dateien(daten.get("files")),
                 warnungen=daten.get("warnings") is True)


async def abbrechen(job_id: str) -> str:
    """Einen Auftrag bei der B-API abbrechen: ``abgebrochen`` (200/202/204), ``schon_fertig`` (409).
    Fremd oder unbekannt: :class:`AuftragFehler` ``unbekannt`` (404)."""
    if not _ID.fullmatch(job_id or ""):
        raise AuftragFehler("unbekannt")
    if (vorlage := _vorlage(get_settings().b_api_jobs_status_path)) is None:
        raise AuftragFehler("aus")
    antwort = await _anfrage("DELETE", vorlage.replace("{job_id}", job_id))
    if antwort.status_code in (200, 202, 204):
        logger.info("Auftrag bei der b-api abgebrochen")
        return "abgebrochen"
    if antwort.status_code == 409:
        return "schon_fertig"
    _pruefe_antwort(antwort)
    raise AuftragFehler("fehler")


async def datei(job_id: str, kennung: str, max_bytes: int) -> bytes:
    """Paket K2d-2: eine Datei eines fertigen Auftrags — ``GET {status}/files/{outputId}`` mit dem
    Schlüssel des Zuges, höchstens ``max_bytes`` (mehr: ``zu_gross``, ohne den Rest zu lesen).
    Keine Weiterleitung: der Schlüssel ginge sonst mit, wohin die Antwort zeigt. Unkomprimiert
    (Review K2d-2, Befund 6): ein gepacktes Stück wüchse beim Entpacken vor dem Deckel; eine
    angekündigte Länge über dem Deckel wird gar nicht erst gelesen."""
    if not _ID.fullmatch(job_id or "") or not _DATEI.fullmatch(kennung or ""):
        raise AuftragFehler("unbekannt")
    if (vorlage := _vorlage(get_settings().b_api_jobs_status_path)) is None:
        raise AuftragFehler("aus")
    pfad = vorlage.replace("{job_id}", job_id) + "/files/" + kennung
    try:
        async with httpx.AsyncClient(timeout=_FRIST, transport=_transport) as http:
            async with http.stream("GET", _wurzel() + pfad,
                                   headers={**_koepfe(), "Accept-Encoding": "identity"},
                                   follow_redirects=False) as antwort:
                if antwort.status_code == 404:
                    raise AuftragFehler("unbekannt")
                if antwort.status_code == 410:
                    # zweites Review K2d-2, Befund 4: nach den 7 Tagen gelöscht — wie ``files[]``
                    # mit ``available: false``
                    raise AuftragFehler("nicht_verfuegbar")
                if antwort.status_code in (401, 403):
                    raise AuftragFehler("abgewiesen")
                if antwort.status_code == 429:
                    raise AuftragFehler("voll", warte_s=_wartezeit(antwort))
                if (code := antwort.status_code) != 200:
                    logger.warning("Auftrag: Datei — b-api antwortet %d", code)
                    raise AuftragFehler("fehler")
                if antwort.headers.get("content-encoding", "identity") not in ("", "identity"):
                    raise AuftragFehler("fehler")      # gepackt trotz ``identity``: nicht lesen
                laenge = antwort.headers.get("content-length", "")
                if laenge.isdigit() and int(laenge) > max_bytes:
                    raise AuftragFehler("zu_gross")
                teile: list[bytes] = []
                gelesen = 0
                async for stueck in antwort.aiter_bytes():  # gepackt ist oben abgewiesen
                    gelesen += len(stueck)
                    if gelesen > max_bytes:
                        raise AuftragFehler("zu_gross")
                    teile.append(stueck)
                return b"".join(teile)
    except (httpx.HTTPError, httpx.InvalidURL) as fehler:
        logger.warning("Auftrag: Datei nicht abrufbar (%s)", type(fehler).__name__)
        raise AuftragFehler("fehler") from fehler


#: Laufende Abbrüche — gehalten, damit die Tasks nicht vorzeitig eingesammelt werden.
_abbrueche: set[asyncio.Task[None]] = set()


def abbrechen_im_hintergrund(job_id: str) -> None:
    """Einen ersetzten oder abgebrochenen Auftrag auch bei der B-API beenden — ohne dass der Zug
    darauf wartet (keine DB-Verbindung über den Rundlauf) und ohne zu werfen. Der Schlüssel des
    Zuges reist im kopierten Kontext mit; ohne ihn antwortet die B-API mit 404 (fremder Job)."""
    if not _ID.fullmatch(job_id or ""):
        return

    async def lauf() -> None:
        try:
            await abbrechen(job_id)
        except AuftragFehler as fehler:
            logger.info("Auftrag nicht abgebrochen (%s)", fehler.grund)
        except Exception as fehler:  # noqa: BLE001 — „wirft nie“; nur die Art, nie der Schlüssel
            logger.warning("Auftrag nicht abgebrochen (%s)", type(fehler).__name__)

    task = asyncio.get_running_loop().create_task(lauf())
    _abbrueche.add(task)
    task.add_done_callback(_abbrueche.discard)
