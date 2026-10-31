"""Paket 17 (D1): der interne Port — Liveness, Readiness, gemeinsames Ende mit dem Hauptserver.

Leitfaden „Übergabe an Team 6“: Infrastruktur-Endpunkte (``/health``, ``/ready``,
``/metrics``) gehören auf einen zweiten, nur im Cluster erreichbaren Port; Kubernetes nutzt
ihn für Liveness- und Readiness-Probes. Beide Server laufen in EINEM Prozess (eine Registry
für die Metriken); der Hauptserver führt die Signale, der interne endet nach ihm.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from boerdi.api.intern import create_intern_app
from boerdi.settings import get_settings


class _Verbindung:
    def __init__(self, fehler: Exception | None) -> None:
        self._fehler = fehler

    async def __aenter__(self):
        if self._fehler:
            raise self._fehler
        return self

    async def __aexit__(self, *exc) -> None:
        return None

    async def execute(self, _sql) -> None:
        return None


class _Engine:
    def __init__(self, fehler: Exception | None = None) -> None:
        self._fehler = fehler

    def connect(self) -> _Verbindung:
        return _Verbindung(self._fehler)


def _intern(engine=None, *, beendet: bool = False) -> TestClient:
    # Ohne Engine gilt der Hauptserver als noch nicht gestartet (Review Phase D, C5).
    return TestClient(create_intern_app(
        FastAPI(), beendet=lambda: beendet, gestartet=lambda: engine is not None,
        probe_engine=engine))


def test_liveness_braucht_keine_datenbank() -> None:
    r = _intern().get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_nicht_bereit_solange_der_start_laeuft() -> None:
    r = _intern().get("/ready")
    assert r.status_code == 503
    assert r.json()["status"] == "not_ready"


def test_bereit_mit_erreichbarer_datenbank(monkeypatch) -> None:
    monkeypatch.setenv("BOERDI_VERSION", "0.6.0")
    get_settings.cache_clear()
    r = _intern(_Engine()).get("/ready")
    get_settings.cache_clear()
    assert r.status_code == 200
    assert r.json() == {"status": "ready", "version": "0.6.0"}


def test_nicht_bereit_ohne_datenbank() -> None:
    r = _intern(_Engine(OSError("verbindung abgelehnt"))).get("/ready")
    assert r.status_code == 503
    assert "datenbank" in r.json()["grund"]
    assert "verbindung abgelehnt" not in r.text  # keine Interna nach außen


def test_nicht_bereit_sobald_der_hauptserver_endet() -> None:
    """Beim Herunterfahren soll der Pod sofort aus dem Service fallen, nicht erst nach 30 s."""
    r = _intern(_Engine(), beendet=True).get("/ready")
    assert r.status_code == 503
    assert r.json()["grund"] == "beendet"


def test_die_interne_app_hat_keine_offene_spec() -> None:
    client = _intern()
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404


# ── Einstieg: zwei Server, ein Prozess ──────────────────────────────────────

def test_die_server_lauschen_auf_den_beiden_ports(monkeypatch) -> None:
    from boerdi import serve

    monkeypatch.setenv("INTERNAL_PORT", "9101")
    get_settings.cache_clear()
    haupt, intern = serve.baue_server(FastAPI(), FastAPI())
    get_settings.cache_clear()
    assert (haupt.config.port, intern.config.port) == (8100, 9101)
    assert haupt.config.timeout_graceful_shutdown == 30
    assert haupt.config.proxy_headers is True
    assert intern.config.lifespan == "off"  # der Lifespan gehört der Haupt-App


def test_der_interne_server_ueberlaesst_die_signale_dem_hauptserver() -> None:
    """Uvicorn setzt je Server eigene Signal-Handler; der zweite überschriebe den ersten,
    und ein SIGTERM erreichte nur einen der beiden — der Prozess endete nie."""
    import signal

    from boerdi import serve

    _haupt, intern = serve.baue_server(FastAPI(), FastAPI())
    vorher = signal.getsignal(signal.SIGINT)
    with intern.capture_signals():
        assert signal.getsignal(signal.SIGINT) is vorher


async def test_der_interne_server_endet_nach_dem_hauptserver() -> None:
    from boerdi import serve

    ablauf: list[str] = []

    class _Intern:
        should_exit = False

        async def serve(self) -> None:
            while not self.should_exit:
                await asyncio.sleep(0.001)
            ablauf.append("intern beendet")

    class _Haupt:
        async def serve(self) -> None:
            await asyncio.sleep(0.01)
            ablauf.append("haupt beendet")

    await asyncio.wait_for(serve.laufen(_Haupt(), _Intern()), timeout=2)
    assert ablauf == ["haupt beendet", "intern beendet"]


def test_beendet_folgt_dem_hauptserver() -> None:
    from boerdi import serve

    haupt = SimpleNamespace(should_exit=False)
    frage = serve.beendet_von(haupt)
    assert frage() is False
    haupt.should_exit = True
    assert frage() is True


@pytest.mark.parametrize("pfad", ["/health", "/ready"])
def test_kopfanfragen_fuer_proben(pfad) -> None:
    r = _intern(_Engine()).head(pfad)
    assert r.status_code == 200


# ── Paket 19 (Audit 2026-10-31, M-1): der Config-Abgleich zählt mit ──────────────

class _Store:
    def __init__(self, bereit: bool) -> None:
        self._bereit = bereit

    def bereit(self) -> bool:
        return self._bereit


def _intern_mit_store(store) -> TestClient:
    haupt = FastAPI()
    haupt.state.config_store = store
    return TestClient(create_intern_app(
        haupt, beendet=lambda: False, gestartet=lambda: True, probe_engine=_Engine()))


def test_ohne_frische_konfiguration_nicht_bereit() -> None:
    r = _intern_mit_store(_Store(False)).get("/ready")
    assert r.status_code == 503
    assert r.json()["grund"] == "konfiguration"


def test_mit_frischer_konfiguration_bereit() -> None:
    r = _intern_mit_store(_Store(True)).get("/ready")
    assert r.status_code == 200
