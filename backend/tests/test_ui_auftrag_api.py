"""Paket K1b: ``POST /api/ui/auftrag/stand`` — der Stand eines Auftrags für ``ui_fortschritt``.

Kein Zug, nichts wird geschrieben: der Endpunkt sagt nur ``laeuft``, ``fertig`` oder ``fehler``;
abgeholt wird im Zug (``ablauf_auftrag_pruefen``). Er antwortet nur
- zu einer bekannten Sitzung (404), mit **bestätigter Anmeldung** (403 ``nur_angemeldet``),
- wenn der Lauf dieser Person auf **genau diesen** Auftrag wartet (Ablauf und Kürzel, sonst 409
  ``kein_auftrag``) und der Ablauf noch gilt,
- mit dem **durchgereichten** Schlüssel der Person (sonst 503 ``nicht_abrufbar``, wie K1a).
Die Job-ID geht nie hinaus.
"""

from __future__ import annotations

import copy
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import boerdi.api.ui_auftrag as api
from boerdi.api.deps import get_session
from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.main import create_app
from boerdi.services import arbeitsstand, vorgaenge
from boerdi.services.ablauf import treiber
from boerdi.services.auftraege import ablage, client
from boerdi.settings import get_settings
from tests.test_ablauf_auftrag import _roh

_SITZUNG = "bb-0123456789abcdef0123456789abcdef"
_ABLAUF = AblaufArea.model_validate(_roh())
_KUERZEL = client.kuerzel("job-1")


class _Lage:
    def __init__(self) -> None:
        self.person = True
        self.schluessel = True
        self.ablauf: AblaufArea | None = _ABLAUF
        self.lauf = {"ablauf": "lesen", "fassung": treiber.fassung(_ABLAUF), "schritt": "lesen",
                     "status": treiber.WARTET_AUFTRAG, "offener_block": None}
        self.auftrag: SimpleNamespace | None = SimpleNamespace(
            job_id="job-1", schritt="lesen", status="laeuft")
        self.stand: client.Stand | Exception = client.Stand("laeuft")
        self.abfragen: list[str] = []
        self.geschrieben: list[str] = []
        self.sitzung = True

    def vorgang(self) -> SimpleNamespace:
        return SimpleNamespace(id="v-1", titel="Lesen", akte={"lauf": copy.deepcopy(self.lauf)},
                               verfaellt_am=datetime.now(UTC) + timedelta(days=3))

    def entities(self) -> dict:
        return {arbeitsstand.VERWEIS: arbeitsstand.verweis_fuer(self.vorgang(), "person-a")}


@pytest.fixture
def lage(monkeypatch) -> _Lage:
    lg = _Lage()

    async def entities(session, session_id):
        return lg.entities() if lg.sitzung and session_id == _SITZUNG else None

    async def nichts(*_a, **_k):
        return None

    async def lesen(s, vorgang_id, aufrufer):
        return lg.vorgang() if vorgang_id == "v-1" and aufrufer == "person-a" else None

    async def offen(s, vorgang_id):
        return lg.auftrag

    async def stand(job_id):
        lg.abfragen.append(job_id)
        if isinstance(lg.stand, Exception):
            raise lg.stand
        return lg.stand

    def schreibt(name):
        async def merke(*_a, **_k):
            lg.geschrieben.append(name)
        return merke

    for name, wert in [("sitzung_entities", entities), ("verbindung_freigeben", nichts),
                       ("bestaetige_anmeldung", nichts)]:
        monkeypatch.setattr(api, name, wert)
    monkeypatch.setattr(api, "adopt_turn_auth_block", lambda request: None)
    monkeypatch.setattr(api, "uebernimm_llm_schluessel", lambda request, pflicht=True: None)
    monkeypatch.setattr(api, "has_personal_auth", lambda: lg.person)
    monkeypatch.setattr(api, "hat_zug_schluessel", lambda: lg.schluessel)
    monkeypatch.setattr(arbeitsstand, "has_personal_auth", lambda: lg.person)
    monkeypatch.setattr(arbeitsstand, "aufrufer_kennung", lambda: "person-a")
    monkeypatch.setattr(vorgaenge, "lesen", lesen)
    monkeypatch.setattr(ablage, "offen", offen)
    monkeypatch.setattr(client, "stand", stand)
    monkeypatch.setattr(api, "laden", lambda ablauf_id: lg.ablauf if ablauf_id == "lesen"
                        else None)
    for name in ("lauf_setzen", "teil_setzen"):
        monkeypatch.setattr(vorgaenge, name, schreibt(name))
    monkeypatch.setattr(ablage, "abschliessen", schreibt("abschliessen"))
    return lg


@pytest.fixture(autouse=True)
def _umgebung(monkeypatch):
    monkeypatch.setenv("STUDIO_API_KEY", "studio-schluessel-fuer-auftrag")
    monkeypatch.delenv("BOERDI_ALLOW_OPEN_ADMIN", raising=False)
    monkeypatch.setenv("RATE_LIMIT_CHAT", "off")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def web(lage):
    app = create_app()
    app.dependency_overrides[get_session] = lambda: SimpleNamespace()
    return TestClient(app, raise_server_exceptions=False)


def _stand(web, **mehr):
    return web.post("/api/ui/auftrag/stand", json={
        "session_id": _SITZUNG, "ablauf": "lesen", "kuerzel": _KUERZEL, **mehr})


@pytest.mark.parametrize(("stand", "erwartet"), [
    (client.Stand("laeuft"), "laeuft"),
    (client.Stand("fertig", {"markdown": "# geheim"}, [{"name": "a.md", "groesse": 3}]), "fertig"),
    (client.Stand("fehler"), "fehler"),
])
def test_der_stand_ohne_inhalt_und_ohne_schreiben(web, lage, stand, erwartet):
    lage.stand = stand
    r = _stand(web)
    assert r.status_code == 200, r.text
    assert r.json() == {"stand": erwartet}
    assert lage.abfragen == ["job-1"] and lage.geschrieben == []
    assert "job-1" not in r.text and "geheim" not in r.text


@pytest.mark.parametrize("aendern", [
    lambda lg: setattr(lg, "lauf", {**lg.lauf, "status": treiber.WARTET}),
    lambda lg: setattr(lg, "lauf", {**lg.lauf, "fassung": "alt"}),
    lambda lg: setattr(lg, "auftrag", None),
    lambda lg: setattr(lg, "auftrag", SimpleNamespace(job_id="job-2", schritt="lesen",
                                                      status="laeuft")),
    lambda lg: setattr(lg, "auftrag", SimpleNamespace(job_id="job-1", schritt="anders",
                                                      status="laeuft")),
    lambda lg: setattr(lg, "ablauf", None),
    lambda lg: setattr(lg, "ablauf", AblaufArea.model_validate(_roh(aktiv=False))),
])
def test_nur_zum_wartenden_auftrag_dieser_person(web, lage, aendern):
    aendern(lage)
    r = _stand(web)
    assert (r.status_code, r.json()["detail"]) == (409, "kein_auftrag")
    assert lage.abfragen == [] and lage.geschrieben == []


def test_ein_anderer_ablauf_oder_ein_anderes_kuerzel(web, lage):
    assert _stand(web, ablauf="anders").status_code == 409
    assert _stand(web, kuerzel="0" * 12).status_code == 409
    assert lage.abfragen == []


def test_unbekannte_sitzung(web, lage):
    lage.sitzung = False
    r = _stand(web)
    assert (r.status_code, r.json()["detail"]) == (404, "sitzung_unbekannt")


def test_nur_angemeldet(web, lage):
    lage.person = False
    r = _stand(web)
    assert (r.status_code, r.json()["detail"]) == (403, "nur_angemeldet")
    assert lage.abfragen == []


def test_ohne_durchgereichten_schluessel_nicht_abrufbar(web, lage):
    lage.schluessel = False
    r = _stand(web)
    assert (r.status_code, r.json()["detail"]) == (503, "nicht_abrufbar")
    assert lage.abfragen == []


@pytest.mark.parametrize(("grund", "status", "code"), [
    ("fehler", 503, "nicht_abrufbar"), ("voll", 503, "nicht_abrufbar"),
    # Review K1b, Befund 4: endgültige Gründe beenden das Nachfragen (statt 30 Minuten weiter).
    ("unbekannt", 409, "kein_auftrag"), ("aus", 409, "kein_auftrag"),
    ("abgewiesen", 403, "abgewiesen"),
])
def test_gruende_der_b_api(web, lage, grund, status, code):
    lage.stand = client.AuftragFehler(grund)
    r = _stand(web)
    assert (r.status_code, r.json()["detail"]) == (status, code)


def test_befund_6_eine_andere_person_derselben_sitzung_sieht_den_auftrag_nicht(web, lage,
                                                                             monkeypatch):
    monkeypatch.setattr(arbeitsstand, "aufrufer_kennung", lambda: "person-b")
    r = _stand(web)
    assert (r.status_code, r.json()["detail"]) == (409, "kein_auftrag")
    assert lage.abfragen == []


def test_befund_2_keine_verbindung_waehrend_der_anmeldung(web, lage, monkeypatch):
    folge: list[str] = []

    async def frei(session):
        folge.append("frei")

    async def anmeldung():
        folge.append("anmeldung")

    monkeypatch.setattr(api, "verbindung_freigeben", frei)
    monkeypatch.setattr(api, "bestaetige_anmeldung", anmeldung)
    assert _stand(web).status_code == 200
    assert folge[:2] == ["frei", "anmeldung"]


@pytest.mark.parametrize("feld", [{"kuerzel": "XYZ"}, {"kuerzel": "a" * 13}, {"ablauf": ""},
                                  {"ablauf": "a" * 200}, {"session_id": "kurz"}])
def test_eingaben_werden_geprueft(web, lage, feld):
    assert _stand(web, **feld).status_code == 422
    assert lage.abfragen == []
