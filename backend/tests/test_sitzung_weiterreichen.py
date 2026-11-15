"""Anmeldung aus der WLO-Sitzung über unser Backend (Plan 2026-11-15, SA-16).

Der Browser schickt das Sitzungs-Cookie des Repositorys nur an Adressen unter ``/edu-sharing``
auf dessen Host. Eine eigene Ingress-Regel (Helm-Werte ``sessionIngress``, wie beim md-editor)
leitet genau einen Pfad dort auf ``POST /api/auth/session`` dieses Backends; das Backend reicht
den Tausch an ``POST /auth/session`` des MCP-Servers weiter. Gepinnt wird, was dabei nicht
passieren darf: dass fremde Cookies, fremde Herkünfte oder Antwortteile des MCP durchgehen, dass
etwas im Protokoll landet, und dass der Weg ohne ``MCP_SESSION_URL`` überhaupt antwortet.
"""

from __future__ import annotations

import logging

import httpx
import pytest
from fastapi.testclient import TestClient

from boerdi.services.mcp import sitzung_tausch

_REPO = "https://repository.example.org"
_ADRESSE = f"{_REPO}/edu-sharing/services/boerdi/auth/session"
_SITZUNG = "0123456789ABCDEF0123456789ABCDEF"
_ANDERE = "FEDCBA9876543210FEDCBA9876543210"
_BLOCK = "wlo2.QUJD-_x=.aXY.Y3Q"


def _einstellen(monkeypatch, **werte) -> None:
    from boerdi.settings import get_settings

    for name, wert in werte.items():
        monkeypatch.setattr(get_settings(), name, wert)


def _mcp(monkeypatch, antwort) -> list[httpx.Request]:
    gesehen: list[httpx.Request] = []

    def _handler(anfrage: httpx.Request) -> httpx.Response:
        gesehen.append(anfrage)
        if isinstance(antwort, Exception):
            raise antwort
        return antwort(anfrage) if callable(antwort) else antwort

    echt = httpx.AsyncClient
    monkeypatch.setattr(sitzung_tausch.httpx, "AsyncClient",
                        lambda **kw: echt(transport=httpx.MockTransport(_handler), **kw))
    return gesehen


@pytest.fixture
def client(monkeypatch):
    _einstellen(monkeypatch, mcp_session_url=_ADRESSE,
                mcp_server_url="https://mcp.example.org/mcp")
    from boerdi.main import create_app

    return TestClient(create_app())


def _tausch(client, *, cookie=f"JSESSIONID={_SITZUNG}", origin=_REPO,
            content_type="application/json", koerper="{}", host="repository.example.org",
            pfad="/api/auth/session"):
    koepfe = {"Content-Type": content_type}
    if origin is not None:
        koepfe["Origin"] = origin
    if cookie is not None:
        koepfe["Cookie"] = cookie
    if host is not None:
        koepfe["Host"] = host
    return client.post(pfad, headers=koepfe, content=koerper)


def _ok(**extra) -> httpx.Response:
    return httpx.Response(200, json={"ok": True, "block": _BLOCK, "authority": "lehrerin",
                                     "displayName": "Lea Lehrerin", **extra})


def test_reicht_den_tausch_weiter_und_gibt_die_antwort_zurueck(client, monkeypatch):
    gesehen = _mcp(monkeypatch, _ok())
    antwort = _tausch(client)
    assert antwort.status_code == 200
    assert antwort.json() == {"ok": True, "block": _BLOCK, "authority": "lehrerin",
                              "displayName": "Lea Lehrerin"}
    assert antwort.headers["cache-control"] == "no-store"

    anfrage = gesehen[0]
    assert (anfrage.method, str(anfrage.url)) == ("POST", "https://mcp.example.org/auth/session")
    assert anfrage.headers["origin"] == _REPO
    assert anfrage.headers["cookie"] == f"JSESSIONID={_SITZUNG}"
    assert anfrage.headers["content-type"] == "application/json"
    assert anfrage.content == b"{}"
    assert "authorization" not in anfrage.headers, "nie zusammen mit dem Cookie"


def test_nur_die_zwei_cookies_der_sitzung_gehen_weiter(client, monkeypatch):
    gesehen = _mcp(monkeypatch, _ok())
    _tausch(client, cookie=f"theme=dunkel; JSESSIONID={_SITZUNG}; INGRESSCOOKIE=abc.123|x; "
                           "boerdi_studio_auth=geheim; _ga=1; INGRESSCOOKIE=zweites")
    assert gesehen[0].headers["cookie"] == f"JSESSIONID={_SITZUNG}; INGRESSCOOKIE=abc.123|x"


@pytest.mark.parametrize("cookie", [
    f"JSESSIONID={_SITZUNG}; JSESSIONID={_ANDERE}",
    # Review 2026-11-15: zweimal dieselbe untergeschobene Sitzung vor der echten — der MCP sähe
    # sonst zwei gleiche Werte und nähme die untergeschobene.
    "JSESSIONID=AAAA0000AAAA0000AAAA0000AAAA0000; JSESSIONID=AAAA0000AAAA0000AAAA0000AAAA0000; "
    f"JSESSIONID={_SITZUNG}",
])
def test_zwei_verschiedene_sitzungen_weist_schon_die_route_ab(client, monkeypatch, cookie):
    gesehen = _mcp(monkeypatch, _ok())
    antwort = _tausch(client, cookie=cookie)
    assert antwort.status_code == 400
    assert "zwei" in antwort.json()["error"]
    assert gesehen == []


def test_dieselbe_sitzung_doppelt_geht_einmal_weiter(client, monkeypatch):
    gesehen = _mcp(monkeypatch, _ok())
    _tausch(client, cookie=f"JSESSIONID={_SITZUNG}; JSESSIONID={_SITZUNG}")
    assert gesehen[0].headers["cookie"] == f"JSESSIONID={_SITZUNG}"


@pytest.mark.parametrize("cookie", [None, "", "theme=dunkel", "JSESSIONID=", "JSESSIONID=a b",
                                    "JSESSIONID=" + "x" * 300, "JSESSIONID=a\"b",
                                    "JSESSIONID=kurz", "JSESSIONID=" + "a|" * 10,
                                    f"jsessionid={_SITZUNG}", f"JSESSIONID = {_SITZUNG}"])
def test_ohne_brauchbare_sitzung_wird_der_mcp_nicht_gefragt(client, monkeypatch, cookie):
    gesehen = _mcp(monkeypatch, _ok())
    antwort = _tausch(client, cookie=cookie)
    assert antwort.status_code == 400
    assert gesehen == []


@pytest.mark.parametrize("origin", [None, "https://fremd.example", "http://repository.example.org",
                                    "https://repository.example.org:8443", "null"])
def test_nur_von_der_herkunft_des_repositorys(client, monkeypatch, origin):
    gesehen = _mcp(monkeypatch, _ok())
    antwort = _tausch(client, origin=origin)
    assert antwort.status_code == 403
    assert antwort.json()["code"] == "origin_not_allowed"
    assert gesehen == []


@pytest.mark.parametrize("origin", ["https://REPOSITORY.example.org", f"{_REPO}/"])
def test_die_herkunft_wird_wie_im_browser_verglichen(client, monkeypatch, origin):
    _mcp(monkeypatch, _ok())
    assert _tausch(client, origin=origin).status_code == 200


def test_ein_standard_port_in_der_adresse_sperrt_nicht(monkeypatch):
    # Review 2026-11-15: ``https://repo:443`` ergab eine Herkunft, die kein Browser schickt.
    from boerdi.domain.mcp_herkunft import sitzungs_adresse

    assert sitzungs_adresse(
        "https://repository.example.org:443/edu-sharing/services/boerdi/auth/session") == _ADRESSE


@pytest.mark.parametrize("host", ["chat.example.org", "repository.example.org.evil", None])
def test_nur_ueber_den_host_des_repositorys(client, monkeypatch, host):
    # Über den Host des Chats ist die Route nicht zu erreichen — dort kommen keine
    # Repository-Cookies an, und Fremde könnten sonst das Budget am MCP verbrauchen.
    gesehen = _mcp(monkeypatch, _ok())
    antwort = _tausch(client, host=host) if host else client.post(
        "/api/auth/session", headers={"Origin": _REPO, "Content-Type": "application/json",
                                      "Cookie": f"JSESSIONID={_SITZUNG}"}, content="{}")
    assert antwort.status_code == 404
    assert gesehen == []


def test_der_pfad_am_repository_braucht_kein_rewrite(client, monkeypatch):
    # Die Ingress-Regel reicht den Pfad unverändert weiter; dieselbe Funktion antwortet dort.
    from boerdi.api.sitzung import PFAD_AM_REPOSITORY

    gesehen = _mcp(monkeypatch, _ok())
    antwort = _tausch(client, pfad=PFAD_AM_REPOSITORY)
    assert antwort.status_code == 200
    assert str(gesehen[0].url) == "https://mcp.example.org/auth/session"


def test_der_pfad_am_repository_steht_nicht_im_api_dokument(client):
    from boerdi.api.sitzung import PFAD_AM_REPOSITORY

    assert PFAD_AM_REPOSITORY not in client.app.openapi()["paths"]
    assert PFAD_AM_REPOSITORY == "/edu-sharing/services/boerdi/auth/session"


def test_nur_json(client, monkeypatch):
    gesehen = _mcp(monkeypatch, _ok())
    assert _tausch(client, content_type="text/plain").status_code == 415
    assert gesehen == []
    assert _tausch(client, content_type="application/json; charset=utf-8").status_code == 200


def test_ohne_mcp_session_url_gibt_es_den_weg_nicht(monkeypatch):
    _einstellen(monkeypatch, mcp_session_url="")
    gesehen = _mcp(monkeypatch, _ok())
    from boerdi.main import create_app

    antwort = _tausch(TestClient(create_app()))
    assert antwort.status_code == 404
    assert antwort.json()["error"].startswith("Die Übernahme einer WLO-Sitzung")
    assert gesehen == []


@pytest.mark.parametrize("status", [400, 403, 404, 415, 429, 503])
def test_die_urteile_des_mcp_gehen_mit_ihrem_status_durch(client, monkeypatch, status):
    _mcp(monkeypatch, httpx.Response(status, json={"error": "Text", "code": "c", "retryAfter": 7},
                                     headers={"Retry-After": "7"}))
    antwort = _tausch(client)
    assert antwort.status_code == status
    # Die Wartezeit reist im Rumpf; den Kopf setzt die IP-Drossel des Backends selbst.
    assert antwort.json() == {"error": "Text", "code": "c", "retryAfter": 7}


def test_nur_bekannte_felder_kommen_zurueck(client, monkeypatch):
    _mcp(monkeypatch, _ok(secret="x", credential={"a": 1}, stacktrace="..."))
    assert set(_tausch(client).json()) == {"ok", "block", "authority", "displayName"}


def test_falsche_formen_im_rumpf_fallen_weg(client, monkeypatch):
    _mcp(monkeypatch, httpx.Response(200, json={"ok": "ja", "block": 7, "authority": ["x"],
                                                "displayName": "x" * 500}))
    rumpf = _tausch(client).json()
    assert "ok" not in rumpf and "block" not in rumpf and "authority" not in rumpf
    assert len(rumpf["displayName"]) <= 200


@pytest.mark.parametrize("antwort", [httpx.Response(200, text="<html>"),
                                     httpx.Response(500, json={"error": "intern"}),
                                     httpx.Response(302, headers={"Location": "https://x"})])
def test_was_kein_urteil_ist__wird_502(client, monkeypatch, antwort):
    _mcp(monkeypatch, antwort)
    assert _tausch(client).status_code == 502


@pytest.mark.parametrize("fehler", [httpx.ConnectError("weg"), httpx.ReadTimeout("langsam")])
def test_ist_der_mcp_nicht_zu_erreichen__503_mit_wartezeit(client, monkeypatch, fehler):
    _mcp(monkeypatch, fehler)
    antwort = _tausch(client)
    assert antwort.status_code == 503
    assert antwort.json()["code"] == "upstream_unreachable"
    assert isinstance(antwort.json()["retryAfter"], int)


def test_die_gesamtfrist_gilt_fuer_den_ganzen_abruf(client, monkeypatch):
    # Review 2026-11-15: Verbindungs- und Lesefrist addierten sich über die des Widgets (10 s).
    import asyncio

    monkeypatch.setattr(sitzung_tausch, "_FRIST_S", 0.05)

    async def _langsam(_anfrage):
        await asyncio.sleep(1)
        return _ok()

    echt = httpx.AsyncClient
    monkeypatch.setattr(sitzung_tausch.httpx, "AsyncClient",
                        lambda **kw: echt(transport=httpx.MockTransport(_langsam), **kw))
    antwort = _tausch(client)
    assert antwort.status_code == 503


def test_bei_offenem_ausfall_schalter_wird_nicht_gefragt(client, monkeypatch):
    gesehen = _mcp(monkeypatch, _ok())
    monkeypatch.setattr(sitzung_tausch.schutz, "ist_offen", lambda _url: True)
    assert _tausch(client).status_code == 503
    assert gesehen == []


def test_die_gesamtgrenze_schuetzt_das_budget_am_mcp(client, monkeypatch):
    # Review 2026-11-15: Ohne Client-Schlüssel zählen beim MCP alle Tausche auf die Adresse des
    # Backends, im selben Topf wie das Abmelden. Gefälschte Kopfzeilen sollen ihn nicht leeren.
    gesehen = _mcp(monkeypatch, _ok())
    _einstellen(monkeypatch, mcp_session_exchange_rpm=2)
    assert [_tausch(client).status_code for _ in range(2)] == [200, 200]
    antwort = _tausch(client)
    assert antwort.status_code == 429
    assert antwort.json()["code"] == "rate_limited"
    assert 1 <= antwort.json()["retryAfter"] <= 60
    assert len(gesehen) == 2


def test_nichts_landet_im_protokoll(client, monkeypatch, caplog):
    antworten = iter([_ok(), httpx.ConnectError("weg"), httpx.Response(200, text="<html>")])

    def _naechste(_anfrage):
        weiter = next(antworten)
        if isinstance(weiter, Exception):
            raise weiter
        return weiter

    _mcp(monkeypatch, _naechste)
    with caplog.at_level(logging.DEBUG):
        _tausch(client, cookie=f"JSESSIONID={_SITZUNG}; INGRESSCOOKIE=abc")
        _tausch(client)
        _tausch(client)
    text = caplog.text
    assert _SITZUNG not in text and _BLOCK not in text and "INGRESSCOOKIE=abc" not in text


def test_traegt_den_client_schluessel(client, monkeypatch):
    from pydantic import SecretStr

    _einstellen(monkeypatch, mcp_client_key=SecretStr("k" * 40))
    gesehen = _mcp(monkeypatch, _ok())
    _tausch(client)
    assert gesehen[0].headers["x-wlo-client-key"] == "k" * 40


def test_nur_eine_gueltige_ip_geht_als_adresse_hinaus(client, monkeypatch):
    # Der Testclient heißt „testclient“ — kein Kopfwert für den MCP. Die Adresse kommt wie bei der
    # Drossel aus ``peer_ip`` (hinter Traefik mit ``TRUST_FORWARDED_FOR`` die der Person).
    gesehen = _mcp(monkeypatch, _ok())
    _tausch(client)
    assert "x-forwarded-for" not in gesehen[0].headers

    from boerdi.api import sitzung

    monkeypatch.setattr(sitzung, "peer_ip", lambda _r: "203.0.113.7")
    _tausch(client)
    assert gesehen[1].headers["x-forwarded-for"] == "203.0.113.7"


@pytest.mark.parametrize(("wert", "je_adresse"), [(20, 10), (1000, 60)])
def test_je_adresse_gilt_eine_grenze__fuer_beide_pfade_gemeinsam(client, monkeypatch, wert,
                                                               je_adresse):
    # Weit: Eine Schulklasse hinter einem Router tauscht beim Laden auf einmal (MCP 1.3.0 zählt
    # sie dort je genannter Adresse). Beide Pfade teilen sich die Grenze (Review 2026-11-15).
    from boerdi.api.sitzung import PFAD_AM_REPOSITORY

    _schluessel(monkeypatch)
    _einstellen(monkeypatch, mcp_session_exchange_rpm=wert)
    _mcp(monkeypatch, _ok())
    stati = [_tausch(client, pfad=PFAD_AM_REPOSITORY if i % 2 else "/api/auth/session").status_code
             for i in range(je_adresse + 1)]
    assert stati[:je_adresse] == [200] * je_adresse
    assert stati[je_adresse] == 429


def test_was_vorher_abgelehnt_wird__zaehlt_nicht_zur_gesamtgrenze(client, monkeypatch):
    gesehen = _mcp(monkeypatch, _ok())
    _einstellen(monkeypatch, mcp_session_exchange_rpm=1)
    assert _tausch(client, content_type="text/plain").status_code == 415
    assert _tausch(client, cookie="theme=dunkel").status_code == 400
    assert _tausch(client).status_code == 200
    assert len(gesehen) == 1


def test_die_gesamtgrenze_gilt_auch_ohne_drossel(client, monkeypatch):
    # ``RATE_LIMIT_CHAT=off`` schaltet die Grenze je Adresse ab — die Gesamtgrenze bleibt.
    _einstellen(monkeypatch, rate_limit_chat="off")
    _mcp(monkeypatch, _ok())
    _einstellen(monkeypatch, mcp_session_exchange_rpm=2)
    assert [_tausch(client).status_code for _ in range(3)] == [200, 200, 429]


def _schluessel(monkeypatch) -> None:
    from pydantic import SecretStr

    _einstellen(monkeypatch, mcp_client_key=SecretStr("k" * 40))


@pytest.mark.parametrize(("schluessel", "wert", "erwartet"), [
    # Vorgabe 20: Ohne ausdrücklichen Wert ändert sich nichts, auch mit Schlüssel — ein MCP vor
    # 1.3.0 zählt sonst alles im Topf der Adresse (Review SA-17).
    (False, 20, "20/minute"), (True, 20, "20/minute"),
    # Weit nur mit Schlüssel: Ohne ihn landen beim MCP alle Tausche im Topf von 30 je Minute.
    (False, 200, "20/minute"), (True, 200, "200/minute"),
    (False, 5, "5/minute"), (True, 5, "5/minute"),
])
def test_die_gesamtgrenze(monkeypatch, schluessel, wert, erwartet):
    if schluessel:
        _schluessel(monkeypatch)
    _einstellen(monkeypatch, mcp_session_exchange_rpm=wert)
    assert sitzung_tausch.gesamtgrenze() == erwartet


@pytest.mark.parametrize(("wert", "erwartet"), [(20, "10/minute"), (21, "60/minute")])
def test_die_grenze_je_adresse_folgt_der_gesamtgrenze(monkeypatch, wert, erwartet):
    # Ohne weite Grenze nimmt eine Adresse höchstens die Hälfte (Review SA-17).
    from boerdi.api.sitzung import grenze_je_adresse

    _schluessel(monkeypatch)
    _einstellen(monkeypatch, mcp_session_exchange_rpm=wert)
    assert grenze_je_adresse() == erwartet


def test_mit_schluessel_gilt_die_weite_gesamtgrenze_auch_ohne_drossel(client, monkeypatch):
    _schluessel(monkeypatch)
    _einstellen(monkeypatch, rate_limit_chat="off", mcp_session_exchange_rpm=3)
    _mcp(monkeypatch, _ok())
    assert [_tausch(client).status_code for _ in range(4)] == [200, 200, 200, 429]


def test_der_wert_ist_begrenzt():
    from pydantic import ValidationError

    from boerdi.settings import Settings

    assert Settings(_env_file=None).mcp_session_exchange_rpm == 20
    for falsch in (0, 1001):
        with pytest.raises(ValidationError):
            Settings(_env_file=None, MCP_SESSION_EXCHANGE_RPM=falsch)


@pytest.mark.parametrize("host", ["REPOSITORY.example.org", "repository.example.org:443"])
def test_host_wie_im_browser(client, monkeypatch, host):
    _mcp(monkeypatch, _ok())
    assert _tausch(client, host=host).status_code == 200


def test_zwei_sitzungen_hinterlassen_eine_logzeile_ohne_wert(client, monkeypatch, caplog):
    _mcp(monkeypatch, _ok())
    with caplog.at_level(logging.WARNING):
        _tausch(client, cookie=f"JSESSIONID={_SITZUNG}; JSESSIONID={_ANDERE}")
    assert "mehr als eine JSESSIONID" in caplog.text
    assert _SITZUNG not in caplog.text and _ANDERE not in caplog.text


def test_kein_hsts_am_pfad_des_repositorys(client, monkeypatch):
    # Die Regel des Repository-Hosts gilt dort; unsere ohne includeSubDomains ersetzte sie.
    from boerdi.api.sitzung import PFAD_AM_REPOSITORY

    _einstellen(monkeypatch, hsts_max_age=86400)
    _mcp(monkeypatch, _ok())
    from boerdi.main import create_app

    neu = TestClient(create_app())
    assert "strict-transport-security" not in _tausch(neu, pfad=PFAD_AM_REPOSITORY).headers
    assert "strict-transport-security" in _tausch(neu).headers
