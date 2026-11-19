"""Der b-api-Client für Aufträge (Kestra-Flows) — Paket K1a, Plan 2026-11-05 §5/§9.

Vertrag (B-API-Handbuch 2026-11-07, am Staging gemessen):

- Start ``POST /api/v1/jobs/flows/{ns}/{id}`` → 202 mit ``jobId``. ``B_API_JOBS_START_PATH``
  leer = Vorgabe ``/api/v1/jobs/flows/{flow}`` (Paket KF); ein Wert ohne führendes ``/`` (etwa
  ``aus``) schaltet Aufträge ab. ``Authorization: Bearer`` geht auch beim Start.
- Abfrage ``GET /api/v1/jobs/{jobId}`` → ``status`` (``QUEUED``, ``RUNNING``, ``SUCCEEDED``,
  ``FAILED``, ``CANCELLED``), ``outputs``, ``files`` (``available``/``reason``), ``warnings``,
  ``error.code``. Abbrechen ``DELETE /api/v1/jobs/{jobId}``.
- 20 unfertige Jobs je Schlüssel, danach 429 mit ``Retry-After``; Jobs 30 Tage, Dateien 7 Tage.

Regeln dieses Clients:

- **Freigabe** (Paket KF, Plan 2026-11-12): die Flows aus dem Studio (``01-base/kestra-flows``),
  mit ``B_API_JOBS_FLOWS`` als Obergrenze; ohne Studio-Freigabe die Umgebung wie bisher
  (:func:`erlaubt`). Der Start-Pfad hat die Vorgabe :data:`START_PFAD_VORGABE`.
- **Schlüssel des Zuges** (``llm_auth.b_api_schluessel``) — nie gespeichert, nie geloggt. Deshalb
  fragt nur ein Zug der Person ab, kein Hintergrund-Wächter. Dass es der **durchgereichte**
  Schlüssel der Person ist (nicht ``B_API_KEY`` aller), prüft ``auftrag_zug`` (Review K1a, 1).
- **Kein Personen-Kopf** (Paket D, Plan 2026-11-17): ``X-Edu-User-Id`` hat die b-api abgeschafft
  (mit Schlüssel 403 ``LEGACY_HEADERS``). Eine Person gilt nur, wenn das Repository für sie bürgt
  (``/rest/bapi/**`` — Paket K über den MCP). Nie ``X-API-KEY``: er hätte Vorrang.
- **Delegation** (``llm_auth.zug_art() == "delegation"``): das Token deckt keine Jobs und endet mit
  der Anfrage — kein Abbruch im Hintergrund (:func:`abbrechen_im_hintergrund`).
- **Schreibende Flows** sind erlaubt (N15); der Schritt trägt dann den Vermerk ``repo_schreibt``.
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
import secrets
from dataclasses import dataclass, field
from typing import Any, Final

import httpx

from boerdi.domain.config_models.kestra_flows import ist_flow
from boerdi.obs.trace_id import ausgehende_koepfe
from boerdi.services.config_loader.kestra_flows import load_kestra_flows
from boerdi.services.llm_auth import KeinDelegationsToken, b_api_schluessel, zug_art
from boerdi.settings import get_settings

logger = logging.getLogger(__name__)

#: Für Tests: eine ``httpx.MockTransport`` (Vertrags-Attrappe).
_transport: httpx.AsyncBaseTransport | None = None
_FRIST: Final = httpx.Timeout(20.0, connect=5.0)
_ID: Final = re.compile(r"^(?!\.+$)[A-Za-z0-9_.\-]{1,200}$")
#: Die Statuswerte der B-API (``QUEUED``, ``RUNNING``, ``SUCCEEDED``, ``FAILED``,
#: ``CANCELLED``) — dazu die Kestra-Namen, gegen die K1a vor dem Vertrag gebaut war
#: (unschädlich, falls einer durchkommt).
_LAEUFT: Final = frozenset({"QUEUED", "RUNNING", "CREATED", "PAUSED", "RESTARTED", "RETRYING"})
_FERTIG: Final = frozenset({"SUCCEEDED", "SUCCESS", "WARNING"})
_FEHLER: Final = frozenset({"FAILED", "CANCELLED", "KILLED"})
#: So lange hält die b-api einen Job (Kopf: „Jobs 30 Tage“) — Paket K7: Frist der Rückkehr.
JOB_TAGE: Final = 30
#: Längste übernommene Wartezeit aus ``Retry-After`` (Sekunden).
_WARTE_DECKEL_S: Final = 600
_MAX_DATEIEN: Final = 50
#: Kennung einer Datei (``outputId``) — ohne Punkt und Schrägstrich (K2d-2).
_DATEI: Final = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
#: Größte übernommene Ausgabe (JSON) — größer gilt als gescheitert (Review K1a, Befund 4).
MAX_AUSGABE_BYTES: Final = 1_000_000
#: Eine Pfad-Vorlage darf den Ziel-Server nicht wechseln (Review K1a, Befund 5).
_UNSICHER: Final = ("//", "@", "?", "#", "\\")


#: Paket AS-8a: Kennung eines Auftrags im Trockenlauf (Probe der Studio-Vorschau) — die b-api sieht
#: sie nie: ``stand``, ``abbrechen`` und ``datei`` antworten selbst.
TROCKEN_PRAEFIX: Final = "trocken-"
_TROCKEN: Final = re.compile(r"^trocken-[0-9a-f]{16}$")


def trocken_kennung() -> str:
    """Eine Job-ID für den Trockenlauf; besteht die Prüfung ``_ID`` wie eine echte."""
    return TROCKEN_PRAEFIX + secrets.token_hex(8)


def ist_trocken(job_id: str) -> bool:
    return bool(_TROCKEN.fullmatch(job_id or ""))


def kuerzel(job_id: str) -> str:
    """Paket K1b: ein Prüfkürzel des Auftrags für den Browser (``ui_fortschritt``) — die Job-ID
    selbst geht nie hinaus (sie öffnet mit dem Schlüssel der Person deren Ergebnisse)."""
    return hashlib.sha256(job_id.encode()).hexdigest()[:12]


#: Plan 2026-11-16, Durchtest TG-7 (m5): die Fehlercodes der b-api, die ins Log dürfen — eine
#: feste Liste, nie freier Servertext (``test_log_ohne_inhalt``). Gemessen 16.11.: ein Start mit
#: einem Konto, das die b-api nicht kennt bzw. freigibt, antwortet 403 ``EDU_USER_NOT_VERIFIED``.
#: Paket D (b-api seit 10.11.): 400 ``EDU_USER_REQUIRED`` — die Ursprungsanfrage hatte keine
#: verifizierte Person; 403 ``LEGACY_HEADERS`` — ein abgeschaffter Kopf (``X-Edu-User-Id``).
BEKANNTE_CODES: Final = frozenset({"EDU_USER_NOT_VERIFIED", "EDU_USER_REQUIRED", "LEGACY_HEADERS"})


class AuftragFehler(Exception):
    def __init__(self, grund: str, *, warte_s: int | None = None, code: str | None = None) -> None:
        super().__init__(grund)
        self.grund = grund
        #: Bei ``voll``: die Wartezeit der B-API (``Retry-After``), sonst ``None``.
        self.warte_s = warte_s
        #: m5: bei ``abgewiesen`` ein Code aus :data:`BEKANNTE_CODES`, sonst ``None``.
        self.code = code


def _abweisungs_code(antwort: httpx.Response) -> str | None:
    """m5: der Code einer Abweisung (``error.code`` oder ``code``), nur aus der festen Liste."""
    try:
        daten = antwort.json()
    except ValueError:
        return None
    if not isinstance(daten, dict):
        return None
    fehler = daten.get("error")
    for roh in (fehler.get("code") if isinstance(fehler, dict) else None, daten.get("code")):
        if isinstance(roh, str) and roh in BEKANNTE_CODES:
            return roh
    return None


@dataclass
class Stand:
    status: str                      # laeuft | fertig | fehler
    outputs: dict[str, Any] = field(default_factory=dict)
    dateien: list[dict[str, Any]] = field(default_factory=list)
    #: ``warnings`` der B-API: einzelne Iterationen endeten mit Warnung oder Fehler.
    warnungen: bool = False
    #: ``error.code`` eines gescheiterten Jobs (dokumentiert nur ``TIMEOUT``), sonst ``None``.
    fehlercode: str | None = None
    #: Paket K1 (``progress`` über den MCP): ``{"fertig": k, "gesamt": n}`` — nur Zahlen.
    fortschritt: dict[str, int] | None = None


def _ganz(z: Any) -> bool:
    return isinstance(z, int) and not isinstance(z, bool)


def fortschritt_zahlen(fortschritt: Any) -> dict[str, int]:
    """Paket K6 (E16): ``fertig``/``gesamt`` aus :attr:`Stand.fortschritt` — nur ganze Zahlen mit
    ``0 <= fertig <= gesamt`` und ``gesamt > 0``; sonst nichts. Durchtest Paket K (19.11.): dazu
    ``fehlgeschlagen``, wenn es eine ganze Zahl ``>= 1`` ist und mit ``fertig`` nicht über
    ``gesamt`` geht (sonst fällt nur sie weg). Eine Prüfung für ``/api/ui/auftrag/stand`` und den
    Satz im Chat (drittes Review)."""
    if not isinstance(fortschritt, dict):
        return {}
    fertig, gesamt = fortschritt.get("fertig"), fortschritt.get("gesamt")
    if not (_ganz(fertig) and _ganz(gesamt) and 0 <= fertig <= gesamt and gesamt > 0):
        return {}
    aus = {"fertig": fertig, "gesamt": gesamt}
    if _ganz(fehl := fortschritt.get("fehlgeschlagen")) and 1 <= fehl <= gesamt - fertig:
        aus["fehlgeschlagen"] = fehl
    return aus


#: Paket KF (K-E3): der Start-Pfad der b-api (Handbuch 2026-11-07, am Staging gemessen) — gilt,
#: wenn ``B_API_JOBS_START_PATH`` leer ist.
START_PFAD_VORGABE: Final = "/api/v1/jobs/flows/{flow}"


#: Rückmeldung 16.11. (Review M1/M2): ab Werk freigegeben, solange weder das Studio noch
#: ``B_API_JOBS_FLOWS`` etwas festlegen — der Metadaten-Flow des Wegs „Themenbaum aus eigenen
#: Inhalten“ (der MCP legt die Knoten an, der Flow erzeugt mit ihren IDs Volltexte und Metadaten).
#: Im Code, nicht im Seed: ein Seed-Eintrag wirkte als Studio-Liste und nähme einer Anlage mit
#: gesetzter Variable still alle anderen Flows; sein Werksabgleich scheiterte sonst an der Grenze.
WERKSVORGABE: Final = frozenset({"edusharing.chatbot/node-metadata-write"})


def _obergrenze() -> frozenset[str] | None:
    """``B_API_JOBS_FLOWS`` — ``None``, wenn nicht gesetzt."""
    roh = frozenset(f.strip() for f in get_settings().b_api_jobs_flows.split(",") if f.strip())
    return roh or None


def _flows() -> frozenset[str]:
    """Paket KF (K-E2): die wirksam freigegebenen Flows."""
    obergrenze = _obergrenze()
    studio = studio_flows()
    if studio is None:
        return obergrenze or WERKSVORGABE
    return frozenset(studio) if obergrenze is None else frozenset(studio) & obergrenze


def studio_flows() -> list[str] | None:
    """Die im Studio freigegebenen Flows (``01-base/kestra-flows``), ``None`` ohne Freigabe."""
    return load_kestra_flows()


def freigegebene_flows() -> frozenset[str]:
    """Die heute wirksam freigegebenen Flows (Review TW-6, Befund 5: für den Wächter)."""
    return _flows()


def obergrenze() -> frozenset[str] | None:
    """Für den Katalog (``flow_katalog``): die Obergrenze der Umgebung, ``None`` ohne."""
    return _obergrenze()


def freigeschaltete_flows() -> list[str]:
    """Paket K2c-1: die Freischaltliste für die Auswahl im Studio — nur Flows in gültiger Form, und
    nur, wenn Aufträge überhaupt eingerichtet sind (Review K2c-1, Befund 3: sonst schlüge das Studio
    einen Flow vor, den „Prüfen“ danach als nicht freigeschaltet meldet)."""
    if not freigeschaltet():
        return []
    return sorted(f for f in _flows() if ist_flow(f))


def _vorlage(roh: str) -> str | None:
    """Eine Pfad-Vorlage — nur ab ``/`` und ohne Zeichen, die Server oder Anfrage wechseln."""
    vorlage = roh.strip()
    if not vorlage.startswith("/") or any(z in vorlage for z in _UNSICHER):
        return None
    return vorlage


def _start_pfad() -> str | None:
    """Die Start-Vorlage — leer: die Vorgabe; ein unsicherer Wert schaltet aus (``None``)."""
    roh = get_settings().b_api_jobs_start_path.strip()
    return _vorlage(roh or START_PFAD_VORGABE)


def freigeschaltet() -> bool:
    """Sind Aufträge eingerichtet: ein gültiger Start-Pfad und mindestens ein freigegebener Flow
    (Paket KF, K-E3; vorher genügte der gesetzte Pfad)?"""
    return _start_pfad() is not None and any(ist_flow(f) for f in _flows())


def erlaubt(flow: str) -> bool:
    """Darf ein Ablauf diesen Flow starten? (eingerichtet, Form, freigeschaltet)"""
    return freigeschaltet() and bool(ist_flow(flow or "")) and flow in _flows()


def _wurzel() -> str:
    basis = get_settings().b_api_base_url.rstrip("/")
    for ende in ("/llm", "/api/v1"):
        if basis.endswith(ende):
            basis = basis[: -len(ende)]
    return basis


def _koepfe() -> dict[str, str]:
    koepfe = dict(ausgehende_koepfe())
    try:
        schluessel = b_api_schluessel()
    except KeinDelegationsToken as fehler:
        # Paket D (E4): kein Token mehr (aufgelegt) bzw. unbrauchbar — kein Aufruf, kein Rückfall
        raise AuftragFehler("fehler") from fehler
    if schluessel:
        koepfe["Authorization"] = f"Bearer {schluessel}"
    return koepfe


async def _anfrage(methode: str, pfad: str, **mehr: Any) -> httpx.Response:
    try:
        async with httpx.AsyncClient(timeout=_FRIST, transport=_transport) as http:
            return await http.request(methode, _wurzel() + pfad,
                                      headers=_koepfe(), **mehr)
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
        # Paket D: ein Repository-Scope ohne verifizierte Person — eine Abweisung mit eigenem
        # Satz, keine falsche Eingabe. Sonst passen die Eingaben nicht zum Schema des Flows.
        if _abweisungs_code(antwort) == "EDU_USER_REQUIRED":
            logger.warning("Auftrag: b-api weist ab (400, Code EDU_USER_REQUIRED)")
            raise AuftragFehler("abgewiesen", code="EDU_USER_REQUIRED")
        raise AuftragFehler("eingaben")
    if antwort.status_code in (401, 403):
        # Durchtest TG-7, m5: mit dem Code der b-api (aus der festen Liste) — sonst blieb im Log
        # nur „abgewiesen“, und niemand sah, dass die b-api die Person nicht freigibt
        code, status = _abweisungs_code(antwort), antwort.status_code
        logger.warning("Auftrag: b-api weist ab (%d, Code %s)", status, code or "unbekannt")
        raise AuftragFehler("abgewiesen", code=code)
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
    pfad = (_start_pfad() or "").replace("{flow}", flow)
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
    """Der Stand eines Auftrags (``laeuft``/``fertig``/``fehler``). Im Trockenlauf sofort fertig,
    ohne Ausgaben — echte Ergebnisse spielen die Testfälle durch (Plan §5n, P-5)."""
    if ist_trocken(job_id):
        return Stand("fertig")
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
    if ist_trocken(job_id):
        return "abgebrochen"
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
    if (ist_trocken(job_id) or not _ID.fullmatch(job_id or "")
            or not _DATEI.fullmatch(kennung or "")):
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
    Zuges reist im kopierten Kontext mit; ohne ihn antwortet die B-API mit 404 (fremder Job).

    Paket D (E4): mit Delegations-Token nie — es endet mit der Anfrage, ein Aufruf danach wäre
    eine 401. Der Job läuft dann im Repository zu Ende (Abbruch über den MCP: Paket K)."""
    if not _ID.fullmatch(job_id or "") or ist_trocken(job_id):
        return
    if zug_art() == "delegation":
        logger.info("Auftrag läuft im Repository zu Ende (Delegation: kein Abbruch danach)")
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
