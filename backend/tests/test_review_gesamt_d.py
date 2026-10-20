"""Paket 17, Gesamt-Review Teil D: Betrieb und Übergabe.

Jeder Test hält einen Befund fest, der zuerst rot war.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY

from boerdi import serve
from boerdi.settings import get_settings

_WURZEL = Path(__file__).resolve().parents[2]


def _wert(name: str, **labels: str) -> float:
    return REGISTRY.get_sample_value(name, labels) or 0.0


def test_den_weitergeleiteten_koepfen_traut_nur_die_eingestellte_liste(monkeypatch) -> None:
    """D1: fest ``"*"`` machte ``TRUST_FORWARDED_FOR=false`` wirkungslos — Uvicorn setzte die
    Client-Adresse schon aus jedem X-Forwarded-For."""
    monkeypatch.setenv("FORWARDED_ALLOW_IPS", "10.0.0.0/8")
    get_settings.cache_clear()
    try:
        haupt, _intern = serve.baue_server(FastAPI(), FastAPI())
    finally:
        get_settings.cache_clear()
    assert haupt.config.forwarded_allow_ips == "10.0.0.0/8"


def test_ohne_einstellung_bleibt_compose_beim_alten_verhalten(monkeypatch) -> None:
    """Compose veröffentlicht keinen App-Port; dort kommt XFF nur von traefik."""
    monkeypatch.delenv("FORWARDED_ALLOW_IPS", raising=False)
    get_settings.cache_clear()
    try:
        haupt, _intern = serve.baue_server(FastAPI(), FastAPI())
    finally:
        get_settings.cache_clear()
    assert haupt.config.forwarded_allow_ips == "*"


def test_keep_alive_ueberdauert_den_proxy() -> None:
    """D5: Uvicorn schloss nach 5 s; Ingress (60 s) und traefik (90 s) halten länger offen und
    schicken die nächste Anfrage auf eine schließende Verbindung (502)."""
    haupt, _intern = serve.baue_server(FastAPI(), FastAPI())
    assert haupt.config.timeout_keep_alive > 90


def test_der_container_ist_erst_gesund_wenn_er_bereit_ist() -> None:
    """D2: ``/health`` am internen Port antwortet schon während des Lifespans — traefik schickte
    Verkehr, bevor 8100 lauschte."""
    zeile = next(z for z in (_WURZEL / "Dockerfile").read_text(encoding="utf-8").splitlines()
                 if "urlopen" in z)
    assert "/ready" in zeile and "/health'" not in zeile


def test_methoden_label_bleibt_endlich(monkeypatch) -> None:
    """D3: jede Methode ein eigenes Label — anonym vervielfachbar."""
    from boerdi.main import create_app

    monkeypatch.setenv("RATE_LIMIT_PUBLIC", "off")
    get_settings.cache_clear()
    client = TestClient(create_app(), raise_server_exceptions=False)
    vorher = sum(_wert("boerdi_http_requests_total", route="andere", method="OTHER", status=s)
                 for s in ("400", "404", "405"))
    client.request("FROBNICATE", "/gibt-es-nicht")
    nachher = sum(_wert("boerdi_http_requests_total", route="andere", method="OTHER", status=s)
                  for s in ("400", "404", "405"))
    get_settings.cache_clear()
    assert nachher == vorher + 1


def test_ein_405_auf_bekanntem_pfad_zaehlt_als_sammel_route(monkeypatch) -> None:
    """D3: eine Vorlage nur für Anfragen, die eine Route trafen."""
    from boerdi.main import create_app

    monkeypatch.setenv("RATE_LIMIT_PUBLIC", "off")
    get_settings.cache_clear()
    client = TestClient(create_app(), raise_server_exceptions=False)
    vorher = _wert("boerdi_http_requests_total", route="andere", method="DELETE", status="405")
    client.delete("/api/chat")
    get_settings.cache_clear()
    assert _wert("boerdi_http_requests_total", route="andere", method="DELETE",
                 status="405") == vorher + 1


def _values() -> dict:
    return yaml.safe_load((_WURZEL / "deploy/helm/values.example.yaml").read_text(encoding="utf-8"))


def test_ingress_laesst_die_groessten_koerper_durch() -> None:
    """D4: ingress-nginx deckelt auf 1 MiB; Spracheingabe (11 MiB) und Wiederherstellen
    (151 MiB) scheiterten mit 413 am Ingress."""
    from boerdi.api.body_limit import body_limit_for

    groesste = max(body_limit_for(p) for p in (
        "/api/chat", "/api/speech/transcribe", "/api/config/restore", "/api/config/factory/upload"))
    wert = _values()["ingress"]["annotations"]["nginx.ingress.kubernetes.io/proxy-body-size"]
    mib = int(re.fullmatch(r"(\d+)m", wert).group(1))
    assert mib * 1024 * 1024 >= groesste


def test_die_gnadenfrist_rechnet_mit_der_echten_uvicorn_frist() -> None:
    """D7: fest 30 s im Test; dazu Luft über der Summe."""
    from boerdi.api.sse import NACHLAUF_FRIST_S

    v = _values()
    uvicorn_s = serve.baue_server(FastAPI(), FastAPI())[0].config.timeout_graceful_shutdown
    pre_stop = v["lifecycle"]["preStopSleepSeconds"]
    from boerdi.services.laeufe_beenden import _FRIST_S as abschluss_s

    assert (v["terminationGracePeriodSeconds"]
            >= abschluss_s + uvicorn_s + NACHLAUF_FRIST_S + 5 + 5 + pre_stop + 5)


def test_keine_anleitung_prueft_api_health_ohne_schluessel() -> None:
    """D6: ``/api/health`` verlangt seit Paket 17 den Studio-Schlüssel."""
    ohne = []
    for rel in ("deploy/README.md", "deploy/INSTALL-schnellstart.md", "INSTALL.md",
                "docs/browser-plugin-einbindung.md"):
        for nr, zeile in enumerate((_WURZEL / rel).read_text(encoding="utf-8").splitlines(), 1):
            if "/api/health" in zeile and "curl" in zeile and "X-Studio-Key" not in zeile:
                ohne.append(f"{rel}:{nr}")
            if "Verbindung prüfen" in zeile and "/api/health" in zeile:
                ohne.append(f"{rel}:{nr}")
    assert not ohne, ohne
