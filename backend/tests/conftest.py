"""Shared fixtures.

Settings are lru-cached (boerdi.settings.get_settings). Tests that monkeypatch
env vars need a fresh Settings read — clear the cache around EVERY test so no
test can leak env-dependent state into the next.

Und die Suite BESITZT ihre Konfiguration: ``backend/.env`` bleibt draussen.
"""

import os
import sys
from pathlib import Path

import pytest

from boerdi.settings import Settings, get_settings
from tests import db_tor

# Ein OTLP-Endpunkt aus der Shell gehört nicht in die Suite: Jedes
# ``create_app()`` baute sonst einen Exporter dorthin, und ``_reset_otel`` wartete
# beim Herunterfahren je Test 9–14 s auf einen Endpunkt ohne Empfänger (gemessen
# 2026-10-08, zweites Review 4b). Hier auf Modulebene, weil schon das Einsammeln
# ``boerdi.main`` lädt (``app = create_app()``). ``test_otel_live.py`` setzt ihn selbst.
os.environ.pop("OTEL_EXPORTER_OTLP_ENDPOINT", None)

_ENV_DATEI = Path(__file__).resolve().parents[1] / ".env"


def _schluessel_der_env_datei() -> tuple[str, ...]:
    """Die NAMEN in ``backend/.env`` — Werte braucht niemand.

    Gelesen wird die Datei selbst statt einer gepflegten Liste: was der Betreiber
    dort eintraegt, faellt damit automatisch aus den Tests heraus, ohne dass
    jemand eine zweite Stelle nachziehen muss.
    """
    if not _ENV_DATEI.exists():
        return ()
    namen = []
    for zeile in _ENV_DATEI.read_text(encoding="utf-8").splitlines():
        gestrafft = zeile.strip()
        if gestrafft and not gestrafft.startswith("#") and "=" in gestrafft:
            namen.append(gestrafft.split("=", 1)[0].strip())
    return tuple(namen)


_ENV_SCHLUESSEL = _schluessel_der_env_datei()


@pytest.fixture(autouse=True)
def _fresh_settings_cache(monkeypatch):
    """Frische Settings je Test — und ohne die Betriebs-``.env``.

    **Warum die Env-Datei ausgehaengt wird** (Befund 2026-08-19): ``Settings``
    liest ``backend/.env``, und damit las die Suite die Konfiguration des
    Rechners mit, auf dem sie lief. Als dort ``MASTER_SKILL_ENABLED=true``
    landete, wurden drei Tests rot, ohne dass sich am Produkt etwas geaendert
    hatte. Die groessere Gefahr ist die Umkehrung: **CI hat keine ``.env``, ein
    Entwicklerrechner schon** — beide liefen gegen unterschiedliche
    Konfigurationen, und ein Test konnte hier gruen und dort rot sein oder
    umgekehrt einen Fehler verdecken.

    **Zwei Wege, beide noetig.** Das Aushaengen der Env-DATEI allein genuegt
    nicht: ``litellm`` ruft beim Import ``load_dotenv()`` und kippt
    ``backend/.env`` in ``os.environ`` — gemessen 2026-08-19, ``import
    boerdi.main`` reicht dafuer. Die Werte stehen dann laengst in der
    Prozessumgebung, wo ``env_file=None`` nichts mehr ausrichtet. Deshalb
    verschwinden zusaetzlich genau die Schluessel, die in der Datei stehen.

    ``monkeypatch`` stellt beides nach jedem Test wieder her; wer eine
    Einstellung braucht, setzt sie ausdruecklich per ``monkeypatch.setenv`` —
    dieser Weg bleibt unberuehrt.
    """
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    for name in _ENV_SCHLUESSEL:
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _no_startup_warmups(monkeypatch):
    """Start-Vorwärmung (W1) in Tests stilllegen.

    ``spawn_startup_warmups`` startet echte MCP-/LLM-Round-Trips. Jeder Test, der
    den Lifespan fährt (``with TestClient(app)``), löste sie sonst mit aus — 16
    SDK-Deprecation-Warnungen und Netz-I/O in einer Unit-Suite.

    Der EINE Test, der die Verdrahtung prüfen muss
    (``test_startup_warmup.test_lifespan_actually_spawns_the_warmups``), patcht
    dasselbe Attribut selbst und gewinnt damit — die Naht bleibt also bewiesen.
    """
    import boerdi.main as main_mod
    monkeypatch.setattr(main_mod, "spawn_startup_warmups", lambda: None)


@pytest.fixture(autouse=True)
def _kein_master_skill_takt(monkeypatch):
    """Den Master-Skill-Takt (2026-10-18) in der Unit-Suite stilllegen — er holte sonst bei
    jedem Lebenszyklus mit eingeschaltetem Skill oder gefülltem Speicher echt per MCP.

    Wie bei der Vorwärmung: ``test_master_skill`` prüft die Verdrahtung, indem es dieselbe
    Naht selbst patcht.
    """
    import asyncio

    import boerdi.main as main_mod
    monkeypatch.setattr(main_mod, "starte_master_skill_takt",
                        lambda: asyncio.create_task(asyncio.sleep(3600)))


@pytest.fixture(autouse=True)
def _anmeldung_ohne_netz(monkeypatch):
    """Die Echtheitsprüfung des Zugangsblocks ohne Netz (Paket 10, Kurzaudit A-1).

    Jeder Zug mit persönlichem Block fragt ``wlo_auth_status`` — in Tests ginge das
    an den echten MCP-Server. Ersetzt wird nur diese Netzgrenze: ein wohlgeformter
    persönlicher Block gilt als Person, ihre Kennung ist sein Fingerabdruck — also
    die Bedeutung, die er vor Paket 10 hatte. Die Prüfung selbst testet
    ``test_mcp_anmeldung.py`` und holt sich dafür die echte Funktion zurück.
    """
    from boerdi.services.mcp import anmeldung, auth

    async def _als_person() -> anmeldung.Befund:
        return anmeldung.Befund(person=True, kennung=f"p:{auth.caller_fingerprint()}")

    monkeypatch.setattr(anmeldung, "_fragen", _als_person)
    anmeldung._cache.clear()


@pytest.fixture(autouse=True)
def _zustimmung_ohne_netz(monkeypatch):
    """Die LLM-Prüfung einer freien Zustimmung ohne Netz (Paket 10, A-6).

    Ersetzt wird nur der Modell-Aufruf, und zwar durch „keine Zustimmung“ — es gilt
    also die Erlaubnisliste wie vor Paket 10. ``test_zustimmung_pruefen.py`` holt sich
    die echte Funktion zurück.
    """
    from boerdi.services import zustimmung_pruefen

    async def _nein(_nachricht: str, _werkzeug: str) -> bool:
        return False

    monkeypatch.setattr(zustimmung_pruefen, "_llm_urteil", _nein)


@pytest.fixture(autouse=True)
def _reset_otel():
    """OTel nach jedem Test zurücknehmen.

    ``setup_otel`` richtet prozessweit ein: einen TracerProvider mit
    BatchSpanProcessor (eigener Worker-Thread, Flush beim Prozessende) und die
    HTTPX-/SQLAlchemy-Instrumentierung. **Befund 2026-10-08:** ``test_otel.py``
    ließ so einen OTLP-Exporter auf ``localhost:4318`` stehen; jeder spätere
    Test reihte Spans für einen Endpunkt ein, an dem niemand lauscht, und je
    nach Timing standen Exportfehler hinter der pytest-Zusammenfassung.

    Der globale TracerProvider bleibt registriert, denn OTel erlaubt
    ``set_tracer_provider`` nur einmal je Prozess. Ein späteres ``setup_otel``
    baut einen frischen Provider und reicht ihn den Instrumentierungen
    ausdrücklich durch; ``set_tracer_provider`` warnt dann nur.

    Geprüft wird über ``sys.modules``, defensiv: Ohne geladenes Modul gibt es
    nichts zurückzunehmen. (Praktisch ist es immer geladen, ``_no_startup_warmups``
    importiert ``boerdi.main``.)
    """
    yield
    otel = sys.modules.get("boerdi.obs.otel")
    if otel is None or otel._provider is None:
        return
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

    HTTPXClientInstrumentor().uninstrument()
    SQLAlchemyInstrumentor().uninstrument()
    otel._provider.shutdown()
    otel._provider = None


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """In der CI wird ein Überspringen durch ein DB-Tor ein Fehler (Paket 6, B3).

    Siehe ``tests/db_tor.py``: Die Datenbank ist dort bereitgestellt, ein still
    übersprungenes Modul hieße „grün, obwohl nicht geprüft“.
    """
    outcome = yield
    report = outcome.get_result()
    if db_tor.ist_verbotener_sprung(report, os.environ):
        report.outcome = "failed"
        report.longrepr = db_tor.FEHLERTEXT.format(grund=db_tor.sprung_grund(report))


@pytest.fixture(autouse=True)
def _drossel_frisch():
    """Gedrosselte Logzeilen (``obs/drossel``, Paket 18E) je Test frisch: sonst schluckte
    die Drossel eine Warnung, die ein früherer Test mit demselben Schlüssel schon schrieb."""
    from boerdi.obs import drossel

    drossel.zuruecksetzen()
    yield
    drossel.zuruecksetzen()
