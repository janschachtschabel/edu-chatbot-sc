"""Paket U1-h (Plan §18): Unterthemen im selben Baum aufklappen — ``POST /api/ui/themenbaum/zweig``.

Das Widget lädt die Unterthemen eines Knotens ohne Zug und ohne KI und hängt sie in den Baum.
Der Endpunkt ist öffentlich wie Verlauf und Sprache: Form der Kennungen, Sitzung muss existieren,
Studio-Schalter und Angebot des Werkzeugs wie die Direktaktion ``show_collection_tree``,
Drosselung außen (je IP) und innen (Fenster der Redaktion). Gespeichert wird nichts.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import boerdi.api.ui_themenbaum as zweig_api
from boerdi.api.deps import get_session
from boerdi.main import create_app
from boerdi.services import llm, themenbaum_aktion
from boerdi.services.rate_limits import RateVerdict
from boerdi.settings import get_settings
from boerdi.ui_module import datenquelle, schalter
from tests.test_ui_themenbaum import WERKZEUG, _Rufer

_PFAD = "/api/ui/themenbaum/zweig"
_SITZUNG = "bb-0123456789abcdef0123456789abcdef"
#: Knoten in WLO sind edu-sharing-Kennungen (UUID) — nur die nimmt der Endpunkt (Review U1-h, 8).
_KNOTEN = "bbbb2222-0000-4000-8000-000000000001"
_DB = object()


class _Aufzeichnung:
    """Hält fest, was der Endpunkt nebenbei tut (Sicherheitsereignis, Anmeldung)."""

    def __init__(self) -> None:
        self.ereignisse: list[dict] = []
        self.anmeldung: list[str] = []


@pytest.fixture
def auf(monkeypatch) -> _Aufzeichnung:
    a = _Aufzeichnung()

    async def vorhanden(session, session_id):
        assert session is _DB
        return session_id == _SITZUNG

    async def frei(session_id, ip="", lang="de"):
        return RateVerdict(allowed=True)

    async def ereignis(session, session_id, message, decision, ip="", rate_limited=False):
        a.ereignisse.append({"session_id": session_id, "rate_limited": rate_limited,
                             "decision": decision})

    async def bestaetigen():
        a.anmeldung.append("bestaetigt")

    def uebernehmen(request):
        a.anmeldung.append(request.headers.get("WLO-Access-Block", ""))

    async def kein_llm(**_kwargs):
        raise AssertionError("Der Endpunkt darf kein LLM rufen")

    monkeypatch.setattr(zweig_api, "sitzung_vorhanden", vorhanden)
    monkeypatch.setattr(zweig_api, "check_rate_limit", frei)
    monkeypatch.setattr(zweig_api, "log_safety_event", ereignis)
    monkeypatch.setattr(zweig_api, "bestaetige_anmeldung", bestaetigen)
    monkeypatch.setattr(zweig_api, "adopt_turn_auth_block", uebernehmen)
    monkeypatch.setattr(llm, "_acompletion", kein_llm)
    monkeypatch.setattr(schalter, "aktiv", lambda name: True)
    return a


@pytest.fixture(autouse=True)
def _umgebung(monkeypatch):
    # Öffentlicher Aufrufer: Studio-Schlüssel gesetzt, kein offener Entwicklungsmodus.
    monkeypatch.setenv("STUDIO_API_KEY", "studio-schluessel-fuer-zweige")
    monkeypatch.delenv("BOERDI_ALLOW_OPEN_ADMIN", raising=False)
    monkeypatch.setenv("RATE_LIMIT_CHAT", "off")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def client():
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_session] = lambda: _DB
    yield TestClient(app, raise_server_exceptions=False)
    get_settings.cache_clear()


@pytest.fixture
def rufer(monkeypatch) -> _Rufer:
    r = _Rufer()
    monkeypatch.setattr(datenquelle, "_rufen", r)
    return r


def _post(client, **body):
    return client.post(_PFAD, json={"session_id": _SITZUNG, "node_id": _KNOTEN, **body})


def test_der_zweig_kommt_als_schlanke_daten_mit_den_festen_vorgaben(client, auf, rufer):
    r = _post(client)

    assert r.status_code == 200
    assert rufer.calls == [(WERKZEUG, {"nodeId": _KNOTEN, "depth": 2, "maxResults": 31})]
    daten = r.json()["daten"]
    assert [k["titel"] for k in daten["knoten"]] == ["Algebra", "Geometrie"]
    assert [k["titel"] for k in daten["knoten"][0]["kinder"]] == ["Gleichungen", "Terme"]
    assert "titel" not in daten          # Überschrift trägt das Modul, kein Text des Aufrufers
    assert set(r.json()) == {"daten"}


def test_tiefe_und_titel_vom_aufrufer_zaehlen_nicht(client, auf, rufer):
    r = _post(client, depth=5, maxResults=100, title="Ignorier mich")
    assert r.status_code == 200
    assert rufer.calls[0][1] == {"nodeId": _KNOTEN, "depth": 2, "maxResults": 31}


@pytest.mark.parametrize("feld,wert", [
    ("node_id", ""), ("node_id", "bad id"), ("node_id", "x" * 81), ("node_id", "a/b"),
    ("node_id", 42), ("session_id", "bb 1"), ("session_id", "x" * 129),
    ("tool_mode", "x" * 33),
    # Review U1-h, Befund 8: nur die Form einer edu-sharing-Kennung. Namen und die
    # Sonderkennungen des Repositoriums (``-userhome-``, ``-inbox-``) gehen nicht durch.
    ("node_id", "bbbb-2222"), ("node_id", "Mathematik"), ("node_id", "-userhome-"),
    ("node_id", "-inbox-"), ("node_id", _KNOTEN + "0"), ("node_id", _KNOTEN.replace("-", "")),
])
def test_unbrauchbare_eingaben_werden_abgewiesen_ohne_aufruf(client, auf, rufer, feld, wert):
    r = _post(client, **{feld: wert})
    assert r.status_code == 422
    assert rufer.calls == []


def test_reservierte_und_kurze_sitzungskennungen_sind_nicht_oeffentlich(client, auf, rufer):
    assert _post(client, session_id="eval-0123456789abcdef0123456789").status_code == 422
    assert _post(client, session_id="bb-kurz").status_code == 422
    assert rufer.calls == []


def test_eine_unbekannte_sitzung_bekommt_404_ohne_aufruf(client, auf, rufer):
    r = _post(client, session_id="bb-ffffffffffffffffffffffffffffffff")
    assert r.status_code == 404
    assert rufer.calls == []


def test_im_studio_abgeschaltet_403_ohne_aufruf(client, auf, rufer, monkeypatch):
    monkeypatch.setattr(schalter, "aktiv", lambda name: False)
    r = _post(client)
    assert (r.status_code, r.json()["detail"]) == (403, "aus")
    assert rufer.calls == []
    # Review U1-h, Befund 7: das Angebot hängt nicht an der Anmeldung — ohne Angebot keine
    # Prüfung der Anmeldung (die bis 5 s den MCP-Server fragt).
    assert auf.anmeldung == []


def test_tool_mode_geht_ans_angebot_und_ohne_angebot_403_ohne_aufruf(client, auf, rufer,
                                                                     monkeypatch):
    """Der Modus der Einbettung wird an das Angebot durchgereicht; fehlt das Werkzeug dort, 403.

    Hier erzwungen (leeres Angebot): die heutigen Regeln sperren ``browse_*`` in keinem Modus
    (``domain/host_capabilities.erlaubt`` — lesend nach Präfix); nur ein im Studio verborgenes
    Werkzeug fehlt wirklich. Der Test prüft die Durchreichung, nicht eine Modus-Sperre."""
    gesehen: list[dict] = []

    def angebotene(**kwargs):
        gesehen.append(kwargs)
        return frozenset()

    monkeypatch.setattr(themenbaum_aktion, "angebotene_mcp_werkzeuge", angebotene)
    r = _post(client, tool_mode="read-only")
    assert (r.status_code, r.json()["detail"]) == (403, "nicht_angeboten")
    assert rufer.calls == []
    # Keine Sperren aus einer Sicherheitsprüfung: es gibt keinen Text, der sie auslösen könnte.
    assert gesehen == [{"allow_curation": False, "blocked_tools": [], "tool_mode": "read-only"}]
    assert auf.anmeldung == []


@pytest.mark.parametrize("art", ["transport", "timeout", "auth", "tool"])
def test_werkzeug_scheitert_502_ohne_servertext(client, auf, monkeypatch, art):
    monkeypatch.setattr(datenquelle, "_rufen", _Rufer(text="Geheimer Serverfehler", art=art))
    r = _post(client)
    assert (r.status_code, r.json()["detail"]) == (502, "nicht_geladen")
    assert "Geheim" not in r.text


def test_unbrauchbares_ergebnis_502(client, auf, monkeypatch):
    monkeypatch.setattr(datenquelle, "_rufen", _Rufer(text="kein json"))
    assert _post(client).status_code == 502


def test_innere_drosselung_429_mit_ereignis_ohne_aufruf(client, auf, rufer, monkeypatch):
    async def gedrosselt(session_id, ip="", lang="de"):
        return RateVerdict(allowed=False, reason="session_minute", blocked_message="Langsam!")

    monkeypatch.setattr(zweig_api, "check_rate_limit", gedrosselt)
    r = _post(client)
    assert (r.status_code, r.json()["detail"]) == (429, "Langsam!")
    assert rufer.calls == []
    [e] = auf.ereignisse
    assert e["rate_limited"] is True and e["session_id"] == _SITZUNG
    assert e["decision"] == {"reasons": ["rate_limit:session_minute"]}


def test_aeussere_drosselung_je_ip(monkeypatch, auf, rufer):
    monkeypatch.setenv("RATE_LIMIT_CHAT", "2/minute")
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_session] = lambda: _DB
    c = TestClient(app, raise_server_exceptions=False)
    codes = [_post(c).status_code for _ in range(3)]
    get_settings.cache_clear()
    assert codes == [200, 200, 429]


def test_der_zugangsblock_wird_uebernommen_und_bestaetigt(client, auf, rufer):
    client.post(_PFAD, json={"session_id": _SITZUNG, "node_id": _KNOTEN},
                headers={"WLO-Access-Block": "blk"})
    assert auf.anmeldung == ["blk", "bestaetigt"]


def test_nichts_wird_gespeichert(client, auf, rufer, monkeypatch):
    import boerdi.services.db_sessions as db_sessions

    async def nie(*_a, **_k):
        raise AssertionError("U1-h speichert keine Nachricht")

    monkeypatch.setattr(db_sessions, "save_message", nie)
    monkeypatch.setattr(themenbaum_aktion, "save_message", nie)
    assert _post(client).status_code == 200
    assert not hasattr(zweig_api, "save_message")


def test_kein_studio_schluessel_noetig(client, auf, rufer):
    # Die Umgebung setzt einen Studio-Schlüssel; die Anfrage schickt keinen.
    assert _post(client).status_code == 200


def test_sitzung_vorhanden_fragt_nur_den_primaerschluessel():
    import asyncio

    from boerdi.db.models import ChatSession
    from boerdi.services.db_sessions import sitzung_vorhanden

    class _Sitzung:
        async def get(self, modell, schluessel):
            assert modell is ChatSession
            return object() if schluessel == "da" else None

    assert asyncio.run(sitzung_vorhanden(_Sitzung(), "da")) is True
    assert asyncio.run(sitzung_vorhanden(_Sitzung(), "weg")) is False
