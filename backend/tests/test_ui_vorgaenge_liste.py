"""AS-Ud (Plan 2026-11-09 §5j): „Meine Vorgänge“ — ``POST /api/ui/vorgaenge/liste`` und
``POST /api/ui/vorgaenge/loeschen``.

- Dieselben Rechte wie ``/offen``: nur mit bestätigter Anmeldung (403 ``nur_angemeldet``), die
  Besitzerin ist die Kennung der Anmeldung, ``no-store`` (Ud-2).
- Die Liste nennt die eigenen, nicht abgeschlossenen Vorgänge **anderer** Gespräche (Ud-1).
- Löschen nur für einen eigenen Vorgang eines anderen Gesprächs, sonst 404 ``unbekannt`` ohne
  Orakel; ein offener Auftrag endet nach dem Festschreiben auch bei der b-api (Ud-3).
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import boerdi.api.ui_vorgaenge as api
from boerdi.api.deps import get_session
from boerdi.main import create_app
from boerdi.services import vorgaenge
from tests.test_ui_vorgaenge_api import _umgebung  # noqa: F401 — autouse-Fixture

_HIER = "bb-0123456789abcdef0123456789abcdef"
_DORT = "bb-fedcba9876543210fedcba9876543210"
_V_DORT = "0a1b2c3d-0000-4000-8000-000000000001"
_V_HIER = "0a1b2c3d-0000-4000-8000-000000000002"
_ZEIT = datetime(2026, 11, 7, 9, 30, tzinfo=UTC)


class _Lage:
    def __init__(self) -> None:
        self.person = True
        self.entities: dict = {}
        self.ereignisse: list = []
        self.auftrag: str | None = "job-7"
        self.vorgaenge = {
            _V_DORT: SimpleNamespace(id=_V_DORT, titel="Lesen", status="wartet_auftrag",
                                     zweck="lesen",
                                     session_id=_DORT, geaendert=_ZEIT,
                                     akte={"lauf": {"ablauf": "lesen",
                                                    "status": "wartet_auftrag"}}),
            _V_HIER: SimpleNamespace(id=_V_HIER, titel="Hier", status="aktiv", zweck="x",
                                     session_id=_HIER,
                                     geaendert=_ZEIT, akte={}),
        }


class _Sitzung:
    def __init__(self, lage: _Lage) -> None:
        self.lage = lage

    async def commit(self):
        self.lage.ereignisse.append("commit")


@pytest.fixture
def lage(monkeypatch) -> _Lage:
    lg = _Lage()

    async def nichts(*_a, **_k):
        return None

    async def eigene(s, aufrufer, *, ohne=None, ohne_id=None):
        lg.ereignisse.append(("eigene", aufrufer, ohne, ohne_id))
        return [v for v in lg.vorgaenge.values() if v.session_id != ohne and v.id != ohne_id]

    async def sperren(s, vid, aufrufer):
        lg.ereignisse.append(("sperren", vid))

    async def lesen(s, vid, aufrufer):
        return lg.vorgaenge.get(vid) if aufrufer == "person-a" else None

    async def loeschen(s, vid, aufrufer):
        lg.ereignisse.append(("loeschen", vid, aufrufer))

    async def offen(s, vid):
        return SimpleNamespace(job_id=lg.auftrag) if lg.auftrag else None

    async def entities(s, session_id):
        return lg.entities if session_id == _HIER else None

    monkeypatch.setattr(api, "verbindung_freigeben", nichts)
    monkeypatch.setattr(api, "bestaetige_anmeldung", nichts)
    monkeypatch.setattr(api, "adopt_turn_auth_block", lambda request: None)
    monkeypatch.setattr(api, "uebernimm_llm_schluessel",
                        lambda request, pflicht: lg.ereignisse.append(("schluessel", pflicht)))
    monkeypatch.setattr(api, "has_personal_auth", lambda: lg.person)
    monkeypatch.setattr(api, "aufrufer_kennung", lambda: "person-a")
    monkeypatch.setattr(api, "sitzung_entities", entities)
    monkeypatch.setattr(vorgaenge, "eigene", eigene)
    monkeypatch.setattr(vorgaenge, "lesen", lesen)
    monkeypatch.setattr(vorgaenge, "loeschen", loeschen)
    monkeypatch.setattr(vorgaenge, "sperren", sperren)
    monkeypatch.setattr(vorgaenge, "offene", eigene)
    # der Schlüssel der Person ist durchgereicht (sonst liefe der Auftrag weiter, Q-6)
    monkeypatch.setattr(api, "hat_zug_schluessel", lambda: True)
    monkeypatch.setattr(api.auftraege_ablage, "offen", offen)
    monkeypatch.setattr(api, "bei_der_b_api_abbrechen",
                        lambda *ids: lg.ereignisse.append(("b-api", ids)))
    return lg


@pytest.fixture
def web(lage):
    app = create_app()
    app.dependency_overrides[get_session] = lambda: _Sitzung(lage)
    return TestClient(app, raise_server_exceptions=False)


def _liste(web, session_id=_HIER):
    return web.post("/api/ui/vorgaenge/liste", json={"session_id": session_id})


def _loeschen(web, vorgang=_V_DORT, session_id=_HIER):
    return web.post("/api/ui/vorgaenge/loeschen",
                    json={"session_id": session_id, "vorgang": vorgang})


# ── Liste ─────────────────────────────────────────────────────────────────────────────────────────


def test_die_liste_nennt_die_eigenen_vorgaenge_anderer_gespraeche(web, lage):
    r = _liste(web)
    assert r.status_code == 200, r.text
    assert r.json() == {"vorgaenge": [{
        "id": _V_DORT, "titel": "Lesen", "ablauf": "lesen", "status": "wartet_auftrag",
        "lauf_status": "wartet_auftrag", "session_id": _DORT, "geaendert": "2026-11-07T09:30:00Z"}]}
    assert lage.ereignisse == [("eigene", "person-a", _HIER, None)]
    assert "no-store" in r.headers["cache-control"]


def test_der_vorgang_auf_den_das_gespraech_verweist_fehlt(web, lage, monkeypatch):
    """Wie ``/offen`` (Review K2a, Befund 1): auch wenn er in einem anderen Gespräch begann."""
    from boerdi.services import arbeitsstand

    lage.entities = {"_vorgang": {"id": _V_DORT}}
    monkeypatch.setattr(arbeitsstand, "verweis", lambda ents, _wer: ents.get("_vorgang"))
    assert _liste(web).json()["vorgaenge"] == []
    # Review AS-Ud, Befund 3: in der Abfrage ausgeschlossen, nicht erst hinter ihrer Grenze
    assert lage.ereignisse == [("eigene", "person-a", _HIER, _V_DORT)]


def test_die_liste_ohne_anmeldung_nichts(web, lage):
    lage.person = False
    r = _liste(web)
    assert r.status_code == 403 and r.json()["detail"] == "nur_angemeldet"
    assert "no-store" in r.headers["cache-control"]
    assert lage.ereignisse == []


@pytest.mark.parametrize("kennung", ["kurz", "a b"])
def test_die_liste_mit_unbrauchbarer_kennung(web, lage, kennung):
    assert _liste(web, kennung).status_code == 422
    assert lage.ereignisse == []


# ── Löschen ───────────────────────────────────────────────────────────────────────────────────────


def test_loeschen_beendet_den_auftrag_erst_nach_dem_festschreiben(web, lage):
    r = _loeschen(web)
    assert r.status_code == 200, r.text
    assert r.json() == {"geloescht": True, "auftrag_laeuft_weiter": False}
    # Review AS-Ud: der Schlüssel der Person gilt (sonst bräche der b-api-Abbruch still ab);
    # die Zeile
    # ist gesperrt, bevor der Auftrag gelesen wird (ein gleichzeitig startender wartet)
    assert lage.ereignisse == [("schluessel", False), ("sperren", _V_DORT),
                               ("loeschen", _V_DORT, "person-a"), "commit", ("b-api", ("job-7",))]
    assert "no-store" in r.headers["cache-control"]


def test_loeschen_ohne_auftrag_ruft_die_b_api_nicht(web, lage):
    lage.auftrag = None
    assert _loeschen(web).status_code == 200
    assert lage.ereignisse == [("schluessel", False), ("sperren", _V_DORT),
                               ("loeschen", _V_DORT, "person-a"), "commit"]


@pytest.mark.parametrize("vorgang", [
    "0a1b2c3d-0000-4000-8000-0000000000ff",   # unbekannt (oder fremd)
    _V_HIER,                                   # der des aktuellen Gesprächs
])
def test_loeschen_ohne_treffer_sieht_immer_gleich_aus(web, lage, vorgang):
    r = _loeschen(web, vorgang)
    assert r.status_code == 404 and r.json()["detail"] == "unbekannt"
    assert "no-store" in r.headers["cache-control"]
    assert [e for e in lage.ereignisse if e[0] not in ("schluessel", "sperren")] == []


def test_loeschen_nicht_den_vorgang_auf_den_das_gespraech_verweist(web, lage, monkeypatch):
    from boerdi.services import arbeitsstand

    lage.entities = {"_vorgang": {"id": _V_DORT}}
    monkeypatch.setattr(arbeitsstand, "verweis", lambda ents, _wer: ents.get("_vorgang"))
    assert _loeschen(web).status_code == 404
    assert [e for e in lage.ereignisse if e[0] not in ("schluessel", "sperren")] == []


def test_loeschen_ohne_anmeldung_nichts(web, lage):
    lage.person = False
    r = _loeschen(web)
    assert r.status_code == 403 and r.json()["detail"] == "nur_angemeldet"
    assert "no-store" in r.headers["cache-control"]
    assert [e for e in lage.ereignisse if e[0] not in ("schluessel", "sperren")] == []


@pytest.mark.parametrize("vorgang", ["", "x" * 80, "abc/../def"])
def test_loeschen_mit_unbrauchbarer_kennung(web, lage, vorgang):
    assert _loeschen(web, vorgang).status_code == 422
    assert lage.ereignisse == []


def test_eine_gross_geschriebene_kennung_trifft(web, lage):
    """Gespeichert werden Kennungen klein (``uuid4``) — wie bei ``/wiederkehr``."""
    assert _loeschen(web, _V_DORT.upper()).status_code == 200


@pytest.mark.parametrize("aenderung", [{"status": "fertig"}, {"status": "abgebrochen"},
                                       {"session_id": None}])
def test_loeschen_nur_was_die_liste_zeigt(web, lage, aenderung):
    """Review AS-Ud, Kleinigkeit 9 (Ud-3): abgeschlossene und solche ohne Gespräch sieht die Liste
    nicht — Löschen antwortet für sie wie für Fremdes."""
    for k, wert in aenderung.items():
        setattr(lage.vorgaenge[_V_DORT], k, wert)
    assert _loeschen(web).status_code == 404
    assert [e for e in lage.ereignisse if e[0] not in ("schluessel", "sperren")] == []


def test_offen_auch_die_403_ohne_zwischenspeicher(web, lage):
    """Review AS-Ud, Befund 8: ``/offen`` teilt jetzt den Vorspann, samt ``no-store`` an 403."""
    lage.person = False
    r = web.post("/api/ui/vorgaenge/offen", json={"session_id": _HIER})
    assert r.status_code == 403 and "no-store" in r.headers["cache-control"]


def test_q6_ohne_schluessel_der_person_sagt_die_antwort_dass_der_auftrag_weiterlaeuft(web, lage,
                                                                                     monkeypatch):
    """Querschnitts-Review AS-U/BU, Q-6: ohne durchgereichten Schlüssel beendet die b-api den Job
    nicht (``bei_der_b_api_abbrechen`` tut dann nichts) — das Widget sagt es statt „endet“."""
    monkeypatch.setattr(api, "hat_zug_schluessel", lambda: False)
    assert _loeschen(web).json() == {"geloescht": True, "auftrag_laeuft_weiter": True}


def test_q6_ohne_auftrag_laeuft_nichts_weiter(web, lage, monkeypatch):
    monkeypatch.setattr(api, "hat_zug_schluessel", lambda: False)
    lage.auftrag = None
    assert _loeschen(web).json()["auftrag_laeuft_weiter"] is False


def test_q6_mit_schluessel_endet_der_auftrag(web, lage, monkeypatch):
    monkeypatch.setattr(api, "hat_zug_schluessel", lambda: True)
    assert _loeschen(web).json()["auftrag_laeuft_weiter"] is False


def test_q7_der_laufstatus_kommt_mit_auch_fuer_beendete_laeufe(web, lage):
    """Q-7: der Vorgangsstatus ist gröber (``fertig`` → ``aktiv``) — die Liste nennt den Lauf."""
    lage.vorgaenge[_V_DORT].status = "aktiv"
    lage.vorgaenge[_V_DORT].akte = {"lauf": {"ablauf": "lesen", "status": "fertig"}}
    [v] = _liste(web).json()["vorgaenge"]
    assert (v["status"], v["lauf_status"]) == ("aktiv", "fertig")
    lage.vorgaenge[_V_DORT].akte = {}
    assert _liste(web).json()["vorgaenge"][0]["lauf_status"] is None


def test_q8_der_titel_eines_ablaufs_kommt_in_der_sprache_des_widgets(web, lage, monkeypatch):
    """Q-8: der Titel wird deutsch gespeichert; stammt er vom Ablauf (``zweck``), kommt er in der
    angefragten Sprache. Ein eigener Titel (etwa eines Entwurfs) bleibt."""
    monkeypatch.setattr(api.ausloeser, "laden", lambda aid: SimpleNamespace(
        id=aid, titel={"de": "Lesen", "en": "Read"}) if aid == "lesen" else None)
    en = web.post("/api/ui/vorgaenge/liste", json={"session_id": _HIER, "sprache": "en"})
    assert en.json()["vorgaenge"][0]["titel"] == "Read"
    assert _liste(web).json()["vorgaenge"][0]["titel"] == "Lesen"
    lage.vorgaenge[_V_DORT].zweck = "sammlungsstruktur"
    en = web.post("/api/ui/vorgaenge/liste", json={"session_id": _HIER, "sprache": "en"})
    assert en.json()["vorgaenge"][0]["titel"] == "Lesen"
    offen = web.post("/api/ui/vorgaenge/offen", json={"session_id": _HIER, "sprache": "en"})
    assert offen.status_code == 200


def test_z9_erst_sperren_dann_pruefen(web, lage, monkeypatch):
    """Zweites Review, Z-9: zwischen Lesen und Sperren könnte ein Zug den Vorgang abschließen oder
    ins aktuelle Gespräch holen — darum wird erst gesperrt, dann gelesen und geprüft."""
    gelesen: list = []
    alt = vorgaenge.lesen

    async def lesen(s, vid, aufrufer):
        gelesen.append(len(lage.ereignisse))
        return await alt(s, vid, aufrufer)

    monkeypatch.setattr(vorgaenge, "lesen", lesen)
    assert _loeschen(web).status_code == 200
    sperre = lage.ereignisse.index(("sperren", _V_DORT))
    assert gelesen and gelesen[0] > sperre
