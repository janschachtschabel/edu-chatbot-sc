"""Paket 18C, Aufgabe 2.1: der Kanarienvogel — Logs tragen keine Inhalte.

Ein Markierwort (``MARKE``) steht in allem, was Inhalt ist: in der Nachricht der
Person, in der Sitzungs-ID, in jeder Modellantwort, im Thema und in der Begründung des
Klassifikators und in den Beschreibungen der MCP-Treffer. Dann läuft je Weg ein
echter Zug über ``POST /api/chat`` — Muster, Agent, Direktaktion,
Canvas-Schnellweg und Fehlerblase —, und JEDER Logeintrag wird mitgeschnitten:
Wurzel-Logger und alle eigenen Logger auf DEBUG, die Fremd-Logger (LiteLLM, OpenAI-SDK,
MCP-SDK, httpcore, SQLAlchemy …) wie im Betrieb gedeckelt, ``LOG_CONTENT`` aus. Kein Eintrag
darf das Wort enthalten — weder in der Nachricht noch im Traceback.

**Titel öffentlicher Materialien und Sammlungen sind erlaubt** (Plan
``2026-10-29-paket-18cd-datenbedarf.md`` §1: öffentliche Katalogdaten, keine
Personendaten, nötig zum Prüfen von Treffern und Auflösung). Deshalb steht das
Wort in den MCP-Antworten nur in Beschreibungen und Texten, nie in Titeln —
sonst meldete der Test Zeilen, die bleiben dürfen.

Gefälscht wird nur an Prozessgrenzen: das Modell (``llm._acompletion``), der
Klassifikator (``classify._acreate``, instructor), der MCP-Server
(``transport.call_tool``) und die Einbettung (``llm._aembedding``). Die Moderation
läuft ohne Schlüssel nicht. Echt sind Graph, Knoten, Werkskonfiguration (Seed)
und eine frisch migrierte Wegwerf-Datenbank.

Rot heißt: eine Logzeile trägt Inhalt; die Fehlermeldung nennt sie als
``Logger | Stufe | Nachricht[:200] | Ort`` (so entstand die Arbeitsliste der Phase 2).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

# Früh geladen, damit ihre Logger beim Mitschnitt schon stehen und mit umgestellt
# werden (ein erst im Zug angelegter Logger behielte eine eigene Stufe).
import httpcore  # noqa: F401
import httpx  # noqa: F401
import litellm  # noqa: F401
import mcp  # noqa: F401
import openai  # noqa: F401
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, text
from sqlalchemy.pool import NullPool

from boerdi.api.deps import get_session
from boerdi.api.schemas import ClassificationResult
from boerdi.db.session import make_engine, make_session_factory
from boerdi.i18n import bot_text
from boerdi.main import create_app
from boerdi.obs.drittlogger import drittlogger_einstellen
from boerdi.services import classify, llm, seed_io
from boerdi.services import config_loader as cl
from boerdi.services.mcp import arg_resolvers, transport
from boerdi.services.mcp import client as mcp_client
from boerdi.services.mcp.tool_cache import _TOOL_CACHE, _TOOL_META_CACHE
from boerdi.settings import Settings, get_settings
from tests import pg_utils

pytestmark = [
    pytest.mark.pg,
    pytest.mark.skipif(not pg_utils.pg_available(), reason=pg_utils.SKIP_REASON),
]

MARKE = "KANARIE7Q"
_DB = "boerdi_kanarienvogel_test"
_SEEDS = Path(__file__).resolve().parents[1] / "seeds"
_UMGEBUNG = {"locale": "de", "page": "/", "device": "desktop"}


# ── Mitschnitt ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class _Eintrag:
    logger: str
    stufe: str
    text: str
    vorlage: str
    ort: str


def _ort(record: logging.LogRecord) -> str:
    teile = Path(record.pathname).parts
    for anker in ("site-packages", "src"):
        if anker in teile:
            rest = teile[len(teile) - teile[::-1].index(anker):]
            return f"{'/'.join(rest)}:{record.lineno}"
    return f"{Path(record.pathname).name}:{record.lineno}"


class _Fang(logging.Handler):
    """Nimmt jeden Eintrag so auf, wie ein Formatierer ihn ausgäbe: Nachricht samt
    Argumenten, Traceback und Stapel (``obs/log_format.JsonFormatter``)."""

    def __init__(self) -> None:
        super().__init__(logging.NOTSET)
        self.eintraege: list[_Eintrag] = []
        self._format = logging.Formatter()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            nachricht = record.getMessage()
        except Exception:  # noqa: BLE001 — eine kaputte Vorlage zählt mit ihren Teilen
            nachricht = f"{record.msg!s} {record.args!r}"
        teile = [nachricht]
        if record.exc_info:
            teile.append(self._format.formatException(record.exc_info))
        elif record.exc_text:
            teile.append(record.exc_text)
        if record.stack_info:
            teile.append(self._format.formatStack(record.stack_info))
        self.eintraege.append(_Eintrag(
            logger=record.name, stufe=record.levelname, text="\n".join(teile),
            vorlage=str(record.msg), ort=_ort(record)))


class _WieVorher(logging.Filter):
    """Für die übrigen Handler (pytest, Konsole): sie sehen während des Mitschnitts
    nur, was sie ohne ihn gesehen hätten — sonst stünde jede SQL-Zeile im Bericht."""

    def __init__(self, stufen: dict[str, int], sonst: int) -> None:
        super().__init__()
        self._stufen, self._sonst = stufen, sonst

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno >= self._stufen.get(record.name, self._sonst)


@contextlib.contextmanager
def _mitschnitt() -> Iterator[list[_Eintrag]]:
    """Wurzel auf DEBUG, alle anderen Logger erben, keiner abgeschaltet, ein Fänger an der
    Wurzel und an jedem Logger, der nicht weiterreicht. Danach alles wie vorher."""
    fang = _Fang()
    wurzel = logging.getLogger()
    vorher_aus = logging.root.manager.disable
    alle = [wurzel] + [lg for lg in list(logging.root.manager.loggerDict.values())
                       if isinstance(lg, logging.Logger)]
    vorher = [(lg, lg.level, lg.disabled) for lg in alle]

    def schwelle(lg: logging.Logger) -> int:
        aus = logging.CRITICAL + 1 if lg.disabled else 0
        return max(aus, lg.getEffectiveLevel(), vorher_aus + 1)

    wie_vorher = _WieVorher({lg.name: schwelle(lg) for lg in alle}, schwelle(wurzel))
    fremde = {h for lg in alle for h in lg.handlers}
    logging.disable(logging.NOTSET)
    for h in fremde:
        h.addFilter(wie_vorher)
    for lg in alle:
        # Wurzel auf DEBUG (``LOG_LEVEL=DEBUG``), jeder andere erbt — wie im Betrieb, wo nur
        # die Wurzel eine Stufe bekommt; eigene Stufen setzt danach ``drittlogger_einstellen``.
        lg.setLevel(logging.DEBUG if lg is wurzel else logging.NOTSET)
        lg.disabled = False
        if lg is wurzel or not lg.propagate:
            lg.addHandler(fang)
    # Die Fremd-Logger wie im Betrieb (``main._configure_logging``): gedeckelt, ``LOG_CONTENT``
    # aus. Die Deckel selbst prüft ``test_drittlogger.py``; ungedeckelt zeigte SQLAlchemy auf
    # DEBUG Ergebniszeilen samt Sitzungs-ID und Texten.
    drittlogger_einstellen(log_content=False)
    try:
        yield fang.eintraege
    finally:
        for lg, stufe, aus in vorher:
            lg.removeHandler(fang)
            lg.setLevel(stufe)
            lg.disabled = aus
        for h in fremde:
            h.removeFilter(wie_vorher)
        logging.disable(vorher_aus)


def _arbeitsliste(funde: list[_Eintrag]) -> list[str]:
    """Je Stelle eine Zeile (gleicher Logger, Stufe, Vorlage und Ort), mit Anzahl."""
    stellen: dict[tuple[str, str, str, str], tuple[_Eintrag, int]] = {}
    for e in funde:
        schluessel = (e.logger, e.stufe, e.vorlage, e.ort)
        erster, n = stellen.get(schluessel, (e, 0))
        stellen[schluessel] = (erster, n + 1)
    zeilen = []
    for erster, n in stellen.values():
        nachricht = erster.text[:200].replace("\n", "⏎")
        mal = f" (×{n})" if n > 1 else ""
        zeilen.append(f"{erster.logger} | {erster.stufe} | {nachricht} | {erster.ort}{mal}")
    return zeilen


def _ohne_marke(eintraege: list[_Eintrag], weg: str) -> None:
    funde = [e for e in eintraege if MARKE.lower() in e.text.lower()]
    if funde:
        zeilen = _arbeitsliste(funde)
        pytest.fail(
            f"{weg}: das Markierwort {MARKE} steht in {len(funde)} Logeinträgen "
            f"({len(zeilen)} Stellen):\n" + "\n".join(zeilen), pytrace=False)


# ── Attrappen an den Prozessgrenzen ──────────────────────────────────────────

_ANTWORT = (f"{MARKE}: Zu Ihrer Suche habe ich passende Materialien zur Optik gefunden. "
            "Das Arbeitsblatt erklärt die Lichtbrechung mit einfachen Versuchen.")
_SCHNELLANTWORTEN = [f"Mehr zu {MARKE}", f"{MARKE} für Klasse 8"]
_MATERIAL = (
    f"# Arbeitsblatt: {MARKE}\n\n"
    f"## Einstieg\n{MARKE} beschreibt, wie Licht an Grenzflächen gebrochen wird. "
    "Lies den Text und markiere die Fachbegriffe.\n\n"
    f"## Aufgaben\n1. Erkläre {MARKE} mit eigenen Worten.\n"
    "2. Zeichne den Strahlengang an einer Glasplatte.\n\n"
    f"## Lösungen\n1. {MARKE} ist die Richtungsänderung des Lichts.\n"
    "2. Der Strahl knickt zum Lot hin ab.\n"
)
_LERNPFAD = (
    f"# Lernpfad {MARKE}\n\n"
    f"## Schritt 1: Einstieg\n{MARKE} beginnt mit einem Alltagsphänomen. "
    "Die Lernenden beobachten einen Stab im Wasserglas.\n"
    "- Material: [Optik für Einsteiger](https://example.org/optik-1)\n\n"
    f"## Schritt 2: Vertiefung\nMit dem Video wird {MARKE} an Beispielen erklärt "
    "und in einer Skizze festgehalten.\n"
    "- Material: [Licht und Schatten](https://example.org/optik-2)\n"
)


def _nutzung() -> SimpleNamespace:
    return SimpleNamespace(prompt_tokens=120, completion_tokens=40, total_tokens=160,
                           prompt_tokens_details=None, completion_tokens_details=None)


def _aufruf(name: str, args: dict, nr: int) -> SimpleNamespace:
    return SimpleNamespace(id=f"call_{nr}", type="function",
                           function=SimpleNamespace(name=name, arguments=json.dumps(args)))


def _rolle(nachricht: Any) -> str:
    if isinstance(nachricht, dict):
        return str(nachricht.get("role") or "")
    return str(getattr(nachricht, "role", "") or "")


def _inhalt(nachricht: Any) -> str:
    wert = (nachricht.get("content") if isinstance(nachricht, dict)
            else getattr(nachricht, "content", ""))
    if isinstance(wert, list):
        return " ".join(str(t.get("text", "")) for t in wert if isinstance(t, dict))
    return str(wert or "")


class _Modell:
    """``llm._acompletion`` wie ein Anbieter: mit Werkzeugen erst ein Suchaufruf,
    nach dem Ergebnis die Antwort (über ``respond_to_user``, wenn angeboten); ohne
    Werkzeuge je nach Auftrag Schnellantworten, Material, Rechtsprüfung oder Text.
    Jede Antwort trägt das Markierwort."""

    def __init__(self) -> None:
        self.arten: list[str] = []

    async def __call__(self, **kw: Any) -> Any:
        art, inhalt, aufrufe = self._antwort(kw)
        self.arten.append(art)
        modell = str(kw.get("model") or "gpt-x").split("/")[-1]
        if kw.get("stream"):
            return self._strom(inhalt, aufrufe, modell)
        nachricht = SimpleNamespace(role="assistant", content=inhalt, tool_calls=aufrufe)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=nachricht,
                                     finish_reason="tool_calls" if aufrufe else "stop")],
            usage=_nutzung(), model=modell)

    def _antwort(self, kw: dict) -> tuple[str, str | None, list | None]:
        nachrichten = list(kw.get("messages") or [])
        werkzeuge = [w.get("function", {}).get("name", "") for w in kw.get("tools") or []]
        if werkzeuge:
            nr = len(self.arten) + 1
            hat_ergebnis = any(_rolle(m) == "tool" for m in nachrichten)
            suche = next((w for w in ("search_wlo_content", "search_wlo_all")
                          if w in werkzeuge),
                         next((w for w in werkzeuge if w.startswith("search")), None))
            if not hat_ergebnis and suche:
                return "suche", None, [_aufruf(suche, {"query": f"{MARKE} Optik"}, nr)]
            if "respond_to_user" in werkzeuge:
                args = {"text": _ANTWORT, "quick_replies": _SCHNELLANTWORTEN}
                return "antwort_werkzeug", None, [_aufruf("respond_to_user", args, nr)]
            return "antwort", _ANTWORT, None
        if kw.get("response_format"):
            befund = {"risk": 0.0, "reason": f"{MARKE} ist unbedenklich"}
            return "recht", json.dumps({k: befund for k in (
                "strafrecht", "jugendschutz", "persoenlichkeitsrechte", "datenschutz")}), None
        letzte = _inhalt(nachrichten[-1]) if nachrichten else ""
        alles = " ".join(_inhalt(m) for m in nachrichten)
        if letzte.startswith("Nutzernachricht:"):
            return "schnellantworten", "\n".join(_SCHNELLANTWORTEN), None
        if letzte.startswith("User term:"):
            return "vokabular", "NONE", None
        if "Erstelle folgendes Material" in alles:
            return "material", _MATERIAL, None
        return "text", _LERNPFAD, None

    @staticmethod
    async def _strom(inhalt: str | None, aufrufe: list | None, modell: str):
        def stueck(delta: Any = None, ende: str | None = None, nutzung: Any = None):
            wahl = [] if delta is None and ende is None else [
                SimpleNamespace(delta=delta, finish_reason=ende)]
            return SimpleNamespace(choices=wahl, usage=nutzung, model=modell)

        if inhalt:
            yield stueck(SimpleNamespace(role="assistant", content=inhalt, tool_calls=None))
        for i, a in enumerate(aufrufe or []):
            yield stueck(SimpleNamespace(role="assistant", content=None, tool_calls=[
                SimpleNamespace(index=i, id=a.id, function=a.function)]))
        yield stueck(SimpleNamespace(role=None, content=None, tool_calls=None),
                     ende="tool_calls" if aufrufe else "stop")
        yield stueck(nutzung=_nutzung())


class _Klassifikator:
    """``classify._acreate`` (instructor): das vorgegebene Ergebnis samt Rohantwort."""

    def __init__(self) -> None:
        self.ergebnis = ClassificationResult()
        self.aufrufe = 0

    async def __call__(self, **_kw: Any) -> tuple[ClassificationResult, Any]:
        self.aufrufe += 1
        roh = SimpleNamespace(usage=_nutzung(), model="gpt-x", choices=[])
        return self.ergebnis.model_copy(deep=True), roh


def _treffer(nr: int, titel: str, beschreibung: str, art: str = "content") -> dict:
    return {
        "nodeId": f"5b6c2f1e-0000-4a5b-9c8d-00000000000{nr}",
        "title": titel,
        "description": beschreibung,
        "url": f"https://example.org/optik-{nr}",
        "learningResourceTypes": ["Arbeitsblatt"],
        "disciplines": ["Physik"],
        "educationalContexts": ["Sekundarstufe I"],
        "license": "CC BY 4.0",
        "publisher": "Beispielverlag",
        "nodeType": art,
    }


class _WloServer:
    """``transport.call_tool`` wie der WLO-MCP-Server (JSON-Umschlag). Das Wort steht
    in Beschreibungen und Texten, nie in Titeln (siehe Modulkopf)."""

    def __init__(self) -> None:
        self.aufrufe: list[tuple[str, dict]] = []

    async def call_tool(self, tool_name: str, arguments: dict | None = None, *,
                        url: str | None = None) -> dict:
        args = dict(arguments or {})
        self.aufrufe.append((tool_name, args))
        if tool_name == "get_wikipedia_summary":
            # Wie der echte Server für ein Kunstwort im Thema: kein Artikel.
            daten: dict = {"query": args.get("query", ""), "found": False, "summary": None}
        else:
            daten = {"total": 2, "count": 2, "results": [
                _treffer(1, "Optik für Einsteiger",
                         f"{MARKE}: Arbeitsblatt mit Versuchen zur Lichtbrechung."),
                _treffer(2, "Licht und Schatten",
                         f"Video: so erklärt {MARKE} die Ausbreitung des Lichts."),
            ]}
        return {"result": {"content": [{"type": "text", "text": json.dumps(daten)}]}}

    def werkzeuge(self) -> list[str]:
        return [name for name, _ in self.aufrufe]


async def _einbettung(**_kw: Any) -> Any:
    return SimpleNamespace(data=[{"embedding": [0.01] * 1536, "index": 0}])


class _Stoerung:
    """Ein Datenbank-Aussetzer an der Treibergrenze: der erste Schreibvorgang in
    ``messages``, sobald ``scharf()`` gilt, bricht mit einer Meldung OHNE Inhalt ab."""

    def __init__(self, scharf: Callable[[], bool]) -> None:
        self._scharf = scharf
        self.ausgeloest = 0

    def __call__(self, _conn, _cursor, statement, _params, _context, _executemany):
        if (self._scharf() and not self.ausgeloest
                and statement.lstrip().upper().startswith("INSERT INTO MESSAGES")):
            self.ausgeloest += 1
            raise ConnectionResetError("Verbindung zur Datenbank abgebrochen")


# ── Welt ─────────────────────────────────────────────────────────────────────

class _Werkslager:
    """Die Werkskonfiguration (``backend/seeds``) im Speicher statt aus der DB."""

    def __init__(self) -> None:
        self.areas: dict[str, dict] = {}

    async def put(self, area: str, data: dict, updated_by: str = "", **_bedingung) -> int:
        self.areas[area] = data
        return 1

    def get_cached(self, area: str) -> dict | None:
        return self.areas.get(area)

    def cached_areas(self) -> list[str]:
        return list(self.areas)

    def clear_cache(self, area: str | None = None) -> None:
        if area is None:
            self.areas.clear()
        else:
            self.areas.pop(area, None)


def _caches_leeren() -> None:
    """Prozessweite Caches, die die MCP-Attrappe sonst über den Test hinaus prägte:
    Werkzeug-Antworten und die einmal geladenen Vokabulare der Filter-Auflösung."""
    _TOOL_CACHE.clear()
    _TOOL_META_CACHE.clear()
    for eintraege in arg_resolvers._label_to_uri_cache.values():
        eintraege.clear()
    for vokabular in arg_resolvers._label_cache_loaded:
        arg_resolvers._label_cache_loaded[vokabular] = False
    arg_resolvers._llm_vocab_cache.clear()


@pytest.fixture(scope="module")
def datenbank():
    pg_utils.create_migrated_db(_DB)
    engine = make_engine(Settings(_env_file=None, database_url=pg_utils.sqlalchemy_url(_DB)),
                         poolclass=NullPool)
    yield engine
    asyncio.run(engine.dispose())
    pg_utils.drop_db(_DB)


@pytest.fixture(scope="module")
def werkskonfiguration():
    lager = _Werkslager()
    asyncio.run(seed_io.import_tree(_SEEDS, lager.put))
    cl.bind_store(lager)
    yield lager
    cl.bind_store(None)


@pytest.fixture
def welt(monkeypatch, datenbank, werkskonfiguration) -> Iterator[SimpleNamespace]:
    for name in ("OPENAI_API_KEY", "B_API_KEY", "B_API_KEY_STAGING", "B_API_KEY_PROD",
                 "CHAT_TOKEN_STREAMING", "MASTER_SKILL_ENABLED"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("EMBED_BACKEND", "api")
    monkeypatch.setenv("LOG_CONTENT", "false")
    monkeypatch.setenv("RATE_LIMIT_CHAT", "off")
    get_settings.cache_clear()

    modell, klassifikator, server = _Modell(), _Klassifikator(), _WloServer()
    monkeypatch.setattr(llm, "_acompletion", modell)
    monkeypatch.setattr(llm, "_aembedding", _einbettung)
    monkeypatch.setattr(classify, "_acreate", klassifikator)
    monkeypatch.setattr(transport, "call_tool", server.call_tool)
    monkeypatch.setattr(mcp_client, "_get_server_url_for_tool",
                        lambda _t: "https://mcp.invalid/mcp")
    _caches_leeren()

    sitzungen = make_session_factory(datenbank)

    async def _sitzung():
        async with sitzungen() as sitzung:
            yield sitzung

    app = create_app()
    app.dependency_overrides[get_session] = _sitzung
    yield SimpleNamespace(client=TestClient(app), modell=modell, klassifikator=klassifikator,
                          server=server, engine=datenbank)
    _caches_leeren()
    get_settings.cache_clear()


def _zug(welt: SimpleNamespace, *, engine: str, **body: Any) -> tuple[dict, list[_Eintrag]]:
    body.setdefault("environment", dict(_UMGEBUNG))
    with _mitschnitt() as eintraege:
        antwort = welt.client.post("/api/chat", json=body,
                                   headers={"X-Boerdi-Engine": engine})
    assert antwort.status_code == 200, antwort.text
    return antwort.json(), eintraege


def _gespeichert(engine, sitzung_id: str) -> list[dict]:
    async def lesen() -> list[dict]:
        async with engine.connect() as conn:
            zeilen = await conn.execute(text(
                "SELECT role, content, debug FROM messages "
                "WHERE session_id = :sid ORDER BY id"), {"sid": sitzung_id})
            return [dict(z) for z in zeilen.mappings().all()]

    return asyncio.run(lesen())


def _antworten(engine, sitzung_id: str) -> list[dict]:
    return [z for z in _gespeichert(engine, sitzung_id) if z["role"] == "assistant"]


def _beantwortet(modell: _Modell) -> bool:
    """Hat die Antwortrunde (Werkzeugschleife bzw. Agent-Schleife) geantwortet?"""
    return any(art in ("antwort", "antwort_werkzeug") for art in modell.arten)


def _suche_klassifiziert() -> ClassificationResult:
    return ClassificationResult(
        persona_id="P-LEH", intent_id="I03", intent_confidence=0.92, next_state="S3",
        entities={"thema": f"{MARKE} Optik", "stufe": "Sekundarstufe I",
                  "medientyp": "Arbeitsblatt"},
        pattern_id_hint="M05", pattern_reasoning=f"Suche nach {MARKE} mit Filtern",
        tool_id_hint="search_wlo_content", tool_reasoning=f"{MARKE} im Bestand suchen",
    )


# ── Je Weg ein Zug ───────────────────────────────────────────────────────────

def test_muster_weg_schreibt_keine_inhalte_ins_log(welt):
    welt.klassifikator.ergebnis = _suche_klassifiziert()
    sid = f"bb-{MARKE}-muster"

    antwort, eintraege = _zug(welt, engine="pattern", session_id=sid,
                              message=f"{MARKE}: Zeig mir Arbeitsblätter zur Optik für Klasse 8")

    assert welt.klassifikator.aufrufe == 1
    assert "search_wlo_content" in welt.server.werkzeuge()
    assert _beantwortet(welt.modell), welt.modell.arten
    assert MARKE in antwort["content"]
    gespeichert = _antworten(welt.engine, sid)
    assert len(gespeichert) == 1 and MARKE in gespeichert[0]["content"]
    _ohne_marke(eintraege, "Muster-Weg")


def test_agent_weg_schreibt_keine_inhalte_ins_log(welt):
    sid = f"bb-{MARKE}-agent"

    antwort, eintraege = _zug(welt, engine="agent", session_id=sid,
                              message=f"{MARKE}: Welche Materialien gibt es zur Optik?")

    assert welt.klassifikator.aufrufe == 0  # die Agent-Maschine klassifiziert nicht
    assert "search_wlo_content" in welt.server.werkzeuge()
    assert "suche" in welt.modell.arten and _beantwortet(welt.modell), welt.modell.arten
    assert MARKE in antwort["content"]
    gespeichert = _antworten(welt.engine, sid)
    assert len(gespeichert) == 1 and MARKE in gespeichert[0]["content"]
    _ohne_marke(eintraege, "Agent-Weg")


def test_direktaktion_schreibt_keine_inhalte_ins_log(welt):
    """Der Lernpfad-Knopf einer Sammlung (``generate_learning_path``): Sammlungsinhalt
    vom MCP, Lernpfad vom Modell, gespeichert ohne Klassifikator."""
    sid = f"bb-{MARKE}-aktion"

    antwort, eintraege = _zug(
        welt, engine="pattern", session_id=sid,
        message=f"{MARKE}: Erstelle einen Lernpfad aus dieser Sammlung",
        action="generate_learning_path",
        action_params={"collection_id": "c0ffee00-0000-4a5b-9c8d-000000000001",
                       "title": "Optik"},
    )

    assert welt.klassifikator.aufrufe == 0
    assert "get_collection_contents" in welt.server.werkzeuge()
    assert "text" in welt.modell.arten, "kein Lernpfad vom Modell"
    gespeichert = _antworten(welt.engine, sid)
    assert len(gespeichert) == 1
    assert gespeichert[0]["debug"]["pattern"] == "ACTION: generate_learning_path"
    assert MARKE in gespeichert[0]["content"]
    assert antwort["content"] or antwort.get("inline_documents")
    _ohne_marke(eintraege, "Direktaktion")


def test_canvas_schnellweg_schreibt_keine_inhalte_ins_log(welt):
    welt.klassifikator.ergebnis = ClassificationResult(
        persona_id="P-LEH", intent_id="I05", intent_confidence=0.95, next_state="S3",
        entities={"thema": f"{MARKE}-Optik", "material_typ": "arbeitsblatt"},
        pattern_id_hint="M10", pattern_reasoning=f"Material zu {MARKE} erzeugen",
    )
    sid = f"bb-{MARKE}-canvas"

    antwort, eintraege = _zug(welt, engine="pattern", session_id=sid,
                              message=f"Erstelle ein Arbeitsblatt zum Thema {MARKE}-Optik")

    assert welt.klassifikator.aufrufe == 1
    assert "material" in welt.modell.arten, "kein Material vom Modell"
    gespeichert = _antworten(welt.engine, sid)
    assert len(gespeichert) == 1
    assert "canvas_service.generate_canvas_content" in gespeichert[0]["debug"]["tools_called"]
    assert MARKE in gespeichert[0]["content"]
    assert antwort["content"] or antwort.get("inline_documents")
    _ohne_marke(eintraege, "Canvas-Schnellweg")


def test_fehlerblase_schreibt_keine_inhalte_ins_log(welt):
    """Alle Modellaufrufe fangen ihre Fehler selbst — die Fehlerblase erreicht ein
    Zug, wenn das Speichern der Antwort scheitert. Der Aussetzer kommt erst NACH
    Klassifikator, Suche und Modell, und seine Meldung trägt kein Markierwort: was
    im Log steht, stammt aus dem Zug davor oder aus dem Abfangen."""
    welt.klassifikator.ergebnis = _suche_klassifiziert()
    sid = f"bb-{MARKE}-fehler"
    stoerung = _Stoerung(scharf=lambda: bool(welt.modell.arten))
    event.listen(welt.engine.sync_engine, "before_cursor_execute", stoerung)
    try:
        antwort, eintraege = _zug(welt, engine="pattern", session_id=sid,
                                  message=f"{MARKE}: Zeig mir Arbeitsblätter zur Optik")
    finally:
        event.remove(welt.engine.sync_engine, "before_cursor_execute", stoerung)

    assert stoerung.ausgeloest == 1
    assert welt.klassifikator.aufrufe == 1
    assert "search_wlo_content" in welt.server.werkzeuge()
    assert _beantwortet(welt.modell), welt.modell.arten
    # Paket 18C/D (3.4): die Blase trägt die Fehlernummer, nicht die Fehlerklasse.
    assert "ConnectionResetError" not in antwort["content"]
    assert antwort["content"].startswith(bot_text("de", "error.internal", nummer="").split("(")[0])
    gespeichert = _antworten(welt.engine, sid)
    assert [z["debug"]["pattern"] for z in gespeichert] == ["ERROR: unhandled_chat_exception"]
    _ohne_marke(eintraege, "Fehlerblase")
