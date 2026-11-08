"""Paket K2a: ``POST /api/ui/vorgaenge/offen`` — wartende Vorgänge der angemeldeten Person in
anderen Gesprächen, damit das Widget „Gespräch fortsetzen“ anbieten kann.

- Nur mit **bestätigter Anmeldung** (403 ``nur_angemeldet``); die Besitzerin ist die Kennung der
  Anmeldung, nie eine mitgeschickte ID.
- Die Kennung des anderen Gesprächs (``session_id``) ist dessen Geheimnis — sie geht nur an die
  Besitzerin, und die Antwort wird nicht zwischengespeichert (``no-store``).
- Das aktuelle Gespräch fragt nach sich selbst nicht (``ohne``).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import boerdi.api.ui_vorgaenge as api
from boerdi.api.deps import get_session
from boerdi.main import create_app
from boerdi.services import vorgaenge
from boerdi.settings import get_settings

_HIER = "bb-0123456789abcdef0123456789abcdef"
_DORT = "bb-fedcba9876543210fedcba9876543210"
_ZEIT = datetime(2026, 11, 7, 9, 30, tzinfo=UTC)


class _Lage:
    def __init__(self) -> None:
        self.person = True
        self.entities: dict = {}
        self.gefragt: list[tuple[str, str | None]] = []
        self.liste = [SimpleNamespace(
            id="v-1", titel="Lesen", status="wartet_auftrag", session_id=_DORT, geaendert=_ZEIT,
            akte={"lauf": {"ablauf": "lesen", "status": "wartet_auftrag"}})]


@pytest.fixture
def lage(monkeypatch) -> _Lage:
    lg = _Lage()

    async def nichts(*_a, **_k):
        return None

    async def offene(s, aufrufer, *, ohne=None):
        lg.gefragt.append((aufrufer, ohne))
        return lg.liste

    async def entities(s, session_id):
        return lg.entities if session_id == _HIER else None

    monkeypatch.setattr(api, "verbindung_freigeben", nichts)
    monkeypatch.setattr(api, "bestaetige_anmeldung", nichts)
    monkeypatch.setattr(api, "adopt_turn_auth_block", lambda request: None)
    monkeypatch.setattr(api, "has_personal_auth", lambda: lg.person)
    monkeypatch.setattr(api, "aufrufer_kennung", lambda: "person-a")
    monkeypatch.setattr(vorgaenge, "offene", offene)
    monkeypatch.setattr(api, "sitzung_entities", entities)
    return lg


@pytest.fixture(autouse=True)
def _umgebung(monkeypatch):
    monkeypatch.setenv("STUDIO_API_KEY", "studio-schluessel-fuer-vorgaenge")
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


def _offen(web, session_id=_HIER):
    return web.post("/api/ui/vorgaenge/offen", json={"session_id": session_id})


def test_die_wartenden_vorgaenge_der_person(web, lage):
    r = _offen(web)
    assert r.status_code == 200, r.text
    assert r.json() == {"vorgaenge": [{
        "titel": "Lesen", "ablauf": "lesen", "status": "wartet_auftrag", "session_id": _DORT,
        "geaendert": "2026-11-07T09:30:00Z"}]}
    assert lage.gefragt == [("person-a", _HIER)]
    assert "no-store" in r.headers["cache-control"]


def test_ohne_anmeldung_nichts(web, lage):
    lage.person = False
    r = _offen(web)
    assert r.status_code == 403 and r.json()["detail"] == "nur_angemeldet"
    assert lage.gefragt == []


def test_ohne_lauf_kein_ablauf(web, lage):
    lage.liste[0].akte = {"lauf": None}
    assert _offen(web).json()["vorgaenge"][0]["ablauf"] is None


@pytest.mark.parametrize("kennung", ["kurz", "eval-0123456789abcdef", "a b"])
def test_eine_unbrauchbare_kennung_wird_abgewiesen(web, lage, kennung):
    assert _offen(web, kennung).status_code == 422
    assert lage.gefragt == []


def _vorgang(vid, titel):
    return SimpleNamespace(id=vid, titel=titel, status="wartet_person", session_id=_DORT,
                           geaendert=_ZEIT, akte={"lauf": None})


def test_nur_der_juengste_geht_hinaus(web, lage):
    """Review K2a, Befund 7: das Widget nutzt nur den jüngsten — eine Kennung weniger draußen."""
    lage.liste = [_vorgang("v-1", "Neu"), _vorgang("v-2", "Alt")]
    assert [v["titel"] for v in _offen(web).json()["vorgaenge"]] == ["Neu"]


def test_nicht_der_vorgang_des_aktuellen_gespraechs(web, lage):
    """Review K2a, Befund 1: eine neue Sitzung übernimmt den jüngsten offenen Vorgang ohnehin
    (``arbeitsstand.auffrischen``) — dann führt er schon hier weiter, kein Hinweis auf A."""
    from boerdi.services import arbeitsstand

    lage.liste = [_vorgang("v-1", "Hier schon"), _vorgang("v-2", "Woanders")]
    hier = SimpleNamespace(id="v-1", titel="Hier schon", akte={"lauf": None},
                           verfaellt_am=datetime.now(UTC) + timedelta(days=3))
    lage.entities = {arbeitsstand.VERWEIS: arbeitsstand.verweis_fuer(hier, "person-a")}
    assert [v["titel"] for v in _offen(web).json()["vorgaenge"]] == ["Woanders"]
