"""Plan 2026-11-07, Paket N2: Anmeldung über ``/auth/status``, Gnadenfrist, Frist, Abmelden.

* CB-7: ``GET /auth/status`` statt einer MCP-Sitzung — mit Bearer und Client-Schlüssel; 401 =
  abgelehnt, 404 = Rückfall auf das Werkzeug, 429/5xx/Netz = unklar.
* CB-4: unklar nach einer Bestätigung derselben Person in den letzten 30 min → weiter Person;
  ohne frühere Bestätigung anonym, aber nicht gemerkt. Eine offene Abnahme bleibt liegen.
* R1: ``expiresAt`` geht ans Widget und begrenzt die Bestätigung.
* R2: ``POST /api/auth/abmelden`` widerruft den Block per Bearer am MCP-Server.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from boerdi.services.mcp import anmelde_endpunkte, anmeldung, auth, schutz
from boerdi.services.mcp.http_fabrik import CLIENT_KEY_HEADER

_BLOCK = "wlo2.persoenlich-status"
_ECHT_FRAGEN = anmeldung._fragen


@pytest.fixture(autouse=True)
def _sauber(monkeypatch):
    from boerdi.settings import get_settings

    monkeypatch.setattr(anmeldung, "_fragen", _ECHT_FRAGEN)
    monkeypatch.setattr(get_settings(), "mcp_auth_token", SecretStr(""), raising=False)
    anmeldung._cache.clear()
    anmeldung._pause.clear()
    auth.set_turn_auth_block(None)
    yield
    anmeldung._cache.clear()
    anmeldung._pause.clear()
    auth.set_turn_auth_block(None)


def _einstellen(monkeypatch, **werte) -> None:
    from boerdi.settings import get_settings

    for name, wert in werte.items():
        monkeypatch.setattr(get_settings(), name, wert)


def _mcp(monkeypatch, antwort) -> list[httpx.Request]:
    """Der MCP-Server als ``httpx.MockTransport``; ``antwort`` ist eine Response oder eine
    Funktion der Anfrage."""
    gesehen: list[httpx.Request] = []

    def _handler(anfrage: httpx.Request) -> httpx.Response:
        gesehen.append(anfrage)
        return antwort(anfrage) if callable(antwort) else antwort

    echt = httpx.AsyncClient
    monkeypatch.setattr(anmelde_endpunkte.httpx, "AsyncClient",
                        lambda **kw: echt(transport=httpx.MockTransport(_handler), **kw))
    return gesehen


def _person(**extra) -> httpx.Response:
    return httpx.Response(200, json={"mode": "user", "authenticated": True,
                                     "authority": "lehrerin", "credential": "ticket", **extra})


def _zug(block: str | None = _BLOCK) -> dict:
    async def lauf():
        auth.set_turn_auth_block(block)
        befund = await anmeldung.bestaetige_anmeldung()
        return {"person": auth.has_personal_auth(), "mit_block": auth.has_auth_token(),
                "abgelehnt": anmeldung.abgelehnt_in_diesem_zug(),
                "unklar": auth.zug_anmeldung_unklar(), "ablauf": auth.zug_ablauf(),
                "befund": befund}
    return asyncio.run(lauf())


# ── CB-7: der Endpunkt ───────────────────────────────────────────────────────
def test_die_anfrage_traegt_block_und_client_schluessel(monkeypatch):
    _einstellen(monkeypatch, mcp_client_key=SecretStr("c" * 40))
    gesehen = _mcp(monkeypatch, _person())
    assert _zug()["person"]
    anfrage = gesehen[0]
    assert (anfrage.method, anfrage.url.path) == ("GET", "/auth/status")
    assert anfrage.headers["authorization"] == f"Bearer {_BLOCK}"
    assert anfrage.headers[CLIENT_KEY_HEADER] == "c" * 40


def test_401_ist_abgelehnt(monkeypatch):
    _mcp(monkeypatch, httpx.Response(401, json={"error": "revoked"}))
    zug = _zug()
    assert zug["abgelehnt"] and not zug["mit_block"]


def test_404_faellt_auf_das_werkzeug_zurueck(monkeypatch):
    _mcp(monkeypatch, httpx.Response(404))
    werkzeug: list[str] = []

    async def call_tool(name, args=None, *, url=None):
        werkzeug.append(name)
        return {"result": {"content": [], "structuredContent": {
            "mode": "user", "authenticated": True, "authority": "lehrerin"}}}

    monkeypatch.setattr(anmeldung.transport, "call_tool", call_tool)
    assert _zug()["person"]
    assert werkzeug == ["wlo_auth_status"]


@pytest.mark.parametrize("antwort", [
    httpx.Response(502),
    httpx.Response(200, json={"mode": "user", "authenticated": False, "authority": None}),
    httpx.Response(200, json={"mode": "user", "authenticated": False, "authority": None,
                              "upstream": "unreachable"}),
], ids=["502", "repository-stumm", "upstream-unreachable"])
def test_ohne_verwertbare_antwort_unklar_und_nicht_gemerkt(monkeypatch, antwort):
    gesehen = _mcp(monkeypatch, antwort)
    zug = _zug()
    assert not zug["person"] and zug["mit_block"] and zug["unklar"] and not zug["abgelehnt"]
    _zug()
    assert len(gesehen) == 2          # nicht gemerkt: der nächste Zug fragt wieder


def test_upstream_ok_macht_aus_authority_null_eine_ablehnung(monkeypatch):
    """Antwort des MCP-Teams auf Befund 2: ``upstream`` trennt Ablehnung und Ausfall."""
    _mcp(monkeypatch, httpx.Response(200, json={
        "mode": "user", "authenticated": False, "authority": None, "upstream": "ok"}))
    zug = _zug()
    assert zug["abgelehnt"] and not zug["mit_block"]


def test_eine_429_wartet_die_genannte_frist_ab(monkeypatch):
    """Antwort des MCP-Teams zu ``too_many_logins``: wer vor ``Retry-After`` fragt, bekommt
    wieder 429 und verbraucht sein Budget — also nicht fragen, bis die Frist um ist."""
    uhr = [1000.0]
    monkeypatch.setattr(anmeldung.time, "monotonic", lambda: uhr[0])
    gesehen = _mcp(monkeypatch, httpx.Response(
        429, headers={"Retry-After": "120"},
        json={"error": "x", "code": "too_many_logins", "retryAfter": 120}))
    assert _zug()["unklar"]
    uhr[0] += 60
    assert _zug()["unklar"]
    assert len(gesehen) == 1              # in der Frist nicht gefragt
    uhr[0] += 61
    _zug()
    assert len(gesehen) == 2


def test_ein_erschoepftes_budget_pausiert_fuer_alle_bloecke(monkeypatch):
    """``rate_limited`` gilt für den ganzen Chatbot — jede weitere Person bekäme sonst noch eine
    429; ``too_many_logins`` nur für den einen Block."""
    uhr = [1000.0]
    monkeypatch.setattr(anmeldung.time, "monotonic", lambda: uhr[0])
    gesehen = _mcp(monkeypatch, httpx.Response(
        429, headers={"Retry-After": "40"}, json={"error": "x", "code": "rate_limited"}))
    assert _zug()["unklar"]
    assert _zug("wlo2.persoenlich-zweite-person")["unklar"]
    assert len(gesehen) == 1
    uhr[0] += 41
    _zug("wlo2.persoenlich-zweite-person")
    assert len(gesehen) == 2


def test_der_anmelde_schutz_pausiert_nur_den_einen_block(monkeypatch):
    gesehen = _mcp(monkeypatch, httpx.Response(
        429, headers={"Retry-After": "600"}, json={"error": "x", "code": "too_many_logins"}))
    _zug()
    _zug("wlo2.persoenlich-zweite-person")
    assert len(gesehen) == 2


def test_ein_positives_urteil_schlaegt_upstream(monkeypatch):
    _mcp(monkeypatch, _person(upstream="unreachable"))
    assert _zug()["person"]


def test_in_der_pause_traegt_die_gnadenfrist(monkeypatch):
    uhr = [1000.0]
    monkeypatch.setattr(anmeldung.time, "monotonic", lambda: uhr[0])
    antworten = [_person(), httpx.Response(429, headers={"Retry-After": "600"})]
    gesehen = _mcp(monkeypatch, lambda _a: antworten.pop(0))
    _zug()
    uhr[0] += anmeldung.POSITIV_S + 1
    zweite = _zug()
    uhr[0] += 120
    dritte = _zug()
    assert zweite["person"] and dritte["person"] and dritte["unklar"]
    assert len(gesehen) == 2


def test_bei_offenem_schalter_wird_nicht_gefragt(monkeypatch):
    gesehen = _mcp(monkeypatch, _person())
    url = anmelde_endpunkte.transport.resolve_mcp_url()
    for _ in range(3):
        schutz.melde_fehler(url)
    assert _zug()["unklar"]
    assert gesehen == []


# ── CB-4: Gnadenfrist ────────────────────────────────────────────────────────
def test_eine_stoerung_nach_bestaetigung_behaelt_die_person(monkeypatch):
    uhr = [1000.0]
    monkeypatch.setattr(anmeldung.time, "monotonic", lambda: uhr[0])
    antworten = [_person(), httpx.Response(503)]
    _mcp(monkeypatch, lambda _a: antworten.pop(0))
    erste = _zug()
    uhr[0] += anmeldung.POSITIV_S + 1
    zweite = _zug()
    assert erste["person"] and zweite["person"] and zweite["unklar"]
    assert zweite["befund"].kennung == erste["befund"].kennung


def test_nach_der_gnadenfrist_gilt_die_person_nicht_mehr(monkeypatch):
    _einstellen(monkeypatch, auth_grace_s=600.0)
    uhr = [1000.0]
    monkeypatch.setattr(anmeldung.time, "monotonic", lambda: uhr[0])
    antworten = [_person(), httpx.Response(503)]
    _mcp(monkeypatch, lambda _a: antworten.pop(0))
    _zug()
    uhr[0] += 601
    zug = _zug()
    assert not zug["person"] and zug["unklar"] and zug["mit_block"]


def test_eine_abgelaufene_frist_hebt_die_gnade_auf(monkeypatch):
    vorbei = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    antworten = [_person(expiresAt=vorbei), httpx.Response(503)]
    _mcp(monkeypatch, lambda _a: antworten.pop(0))
    assert _zug()["person"]
    assert not _zug()["person"]       # die Bestätigung galt nicht über die Frist hinaus


# ── R1: die Frist geht ans Widget ────────────────────────────────────────────
def test_die_frist_des_blocks_steht_im_zug(monkeypatch):
    spaeter = (datetime.now(UTC) + timedelta(hours=11)).isoformat()
    _mcp(monkeypatch, _person(expiresAt=spaeter))
    assert _zug()["ablauf"] == spaeter


def test_eine_bestaetigung_gilt_hoechstens_bis_zur_frist():
    bald = (datetime.now(UTC) + timedelta(seconds=60)).isoformat()
    befund = anmeldung.Befund(person=True, kennung="p:x", ablauf=bald)
    # Toleranz: Testuhr (datetime.now) und die Uhr in ``_gueltig_s`` laufen unter Windows um
    # Bruchteile auseinander (gesehen 10.11.: 60.0000002)
    assert 0 < anmeldung._gueltig_s(befund) <= 60 + 1e-3


# ── R2: Abmelden ─────────────────────────────────────────────────────────────
def test_abmelden_widerruft_per_bearer(monkeypatch):
    _einstellen(monkeypatch, mcp_client_key=SecretStr("c" * 40))
    gesehen = _mcp(monkeypatch, httpx.Response(200, json={"revoked": True}))
    from boerdi.main import create_app

    antwort = TestClient(create_app()).post("/api/auth/abmelden",
                                            headers={"WLO-Access-Block": _BLOCK})
    assert antwort.json() == {"widerrufen": True, "erreicht": True}
    anfrage = gesehen[0]
    assert (anfrage.method, anfrage.url.path) == ("POST", "/auth/revoke")
    assert anfrage.headers["authorization"] == f"Bearer {_BLOCK}"
    assert anfrage.content == b""


def test_nach_dem_abmelden_gilt_der_block_sofort_als_abgewiesen(monkeypatch):
    """Review 2026-11-07, Befund 4: eine kopierte Fassung hielte der Speicher sonst noch
    Minuten für eine Person."""
    antworten = [_person(), httpx.Response(200, json={"revoked": True})]
    _mcp(monkeypatch, lambda _a: antworten.pop(0))
    assert _zug()["person"]
    from boerdi.main import create_app

    TestClient(create_app()).post("/api/auth/abmelden", headers={"WLO-Access-Block": _BLOCK})
    zug = _zug()
    assert zug["abgelehnt"] and not zug["person"]


@pytest.mark.parametrize("block", [None, "wlo-anon.v1", "kein-block"])
def test_ohne_persoenlichen_block_geht_nichts_hinaus(monkeypatch, block):
    gesehen = _mcp(monkeypatch, httpx.Response(200, json={"revoked": True}))
    from boerdi.main import create_app

    koepfe = {"WLO-Access-Block": block} if block else {}
    antwort = TestClient(create_app()).post("/api/auth/abmelden", headers=koepfe)
    assert antwort.json() == {"widerrufen": False, "erreicht": False}
    assert gesehen == []


def test_ein_unerreichbarer_server_sagt_es(monkeypatch):
    def _weg(_a):
        raise httpx.ConnectError("weg")

    _mcp(monkeypatch, _weg)
    assert asyncio.run(anmelde_endpunkte.widerrufen(_BLOCK)) is None
