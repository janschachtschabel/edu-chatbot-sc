"""Paket U3-2a: ``POST /api/ui/dokumente`` und ``/loeschen`` — Bremsen, Codes, Ablage.

Umwandlung und Moderation sind ersetzt (eigene Tests in ``test_dokument_aufnahme``); hier zählt,
was der Endpunkt selbst entscheidet und dass er vor jeder Arbeit abweist, was nicht darf.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import boerdi.api.ui_dokumente as api
from boerdi.api.deps import get_session
from boerdi.domain.config_models.upload import UploadSettings
from boerdi.main import create_app
from boerdi.services.dokumente import ablage
from boerdi.services.dokumente.aufnahme import Abweisung, Aufbereitet
from boerdi.services.rate_limits import RateVerdict
from boerdi.settings import get_settings
from boerdi.ui_module.antwort import OFFENE_FRAGE
from boerdi.ui_module.namen import UPLOAD

_PFAD = "/api/ui/dokumente"
_SITZUNG = "bb-0123456789abcdef0123456789abcdef"
_BLOCK = "b0000001"
_KENNUNG = "11111111-2222-4333-8444-555555555555"
_MD = b"# Lehrplan\n\n## Mechanik\nx\n\n## Optik\ny\n"


class _DB:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


class _Lage:
    def __init__(self) -> None:
        self.db = _DB()
        self.entities: dict | None = {OFFENE_FRAGE: {"block_id": _BLOCK, "modul": UPLOAD}}
        self.cfg = UploadSettings()
        self.person = True
        self.ereignisse: list[dict] = []
        self.aufbereitet: list[tuple[bytes, str, int]] = []
        self.gespeichert: list[dict] = []
        self.geloescht: list[tuple] = []
        self.ergebnis: Aufbereitet | Abweisung = Aufbereitet(
            format="md", markdown="# Lehrplan", befund={"abschnitte": 3, "warnungen": []},
            gliederung=[{"id": "a1"}], vorschau=["Lehrplan", "Mechanik"])
        self.speichern_wirft: Exception | None = None


@pytest.fixture
def lage(monkeypatch) -> _Lage:
    lg = _Lage()

    async def entities(session, session_id):
        return lg.entities if session_id == _SITZUNG else None

    async def frei(session_id, ip="", lang="de"):
        return RateVerdict(allowed=True)

    async def ereignis(session, session_id, message, decision, ip="", rate_limited=False):
        lg.ereignisse.append({"message": message, "decision": decision,
                              "rate_limited": rate_limited})

    async def aufbereiten(rumpf, name, *, max_seiten, frist_s, moderieren):
        lg.aufbereitet.append((rumpf, name, max_seiten))
        return lg.ergebnis

    async def speichern(s, **kw):
        if lg.speichern_wirft:
            raise lg.speichern_wirft
        lg.gespeichert.append(kw)
        return _KENNUNG

    async def loeschen(s, session_id, upload_id):
        lg.geloescht.append((session_id, upload_id))

    async def nichts(*_a, **_k):
        return None

    monkeypatch.setattr(api, "sitzung_entities", entities)
    async def vorhanden(session, session_id):
        return True

    monkeypatch.setattr(api, "sitzung_vorhanden", vorhanden)
    monkeypatch.setattr(api, "check_rate_limit", frei)
    monkeypatch.setattr(api, "log_safety_event", ereignis)
    monkeypatch.setattr(api, "aufbereiten", aufbereiten)
    monkeypatch.setattr(api, "verbindung_freigeben", nichts)
    monkeypatch.setattr(api, "bestaetige_anmeldung", nichts)
    monkeypatch.setattr(api, "adopt_turn_auth_block", lambda request: None)
    monkeypatch.setattr(api, "load_upload_config", lambda: lg.cfg)
    monkeypatch.setattr(api, "has_personal_auth", lambda: lg.person)
    monkeypatch.setattr(api, "aufrufer_kennung", lambda: "person-a")
    monkeypatch.setattr(ablage, "speichern", speichern)
    monkeypatch.setattr(ablage, "loeschen", loeschen)
    return lg


@pytest.fixture(autouse=True)
def _umgebung(monkeypatch):
    monkeypatch.setenv("STUDIO_API_KEY", "studio-schluessel-fuer-dokumente")
    monkeypatch.delenv("BOERDI_ALLOW_OPEN_ADMIN", raising=False)
    monkeypatch.setenv("RATE_LIMIT_CHAT", "off")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def client(lage):
    app = create_app()
    app.dependency_overrides[get_session] = lambda: lage.db
    return TestClient(app, raise_server_exceptions=False)


def _post(client, *, rumpf: bytes = _MD, name: str = "Lehrplan.md", **felder):
    daten = {"session_id": _SITZUNG, "block_id": _BLOCK, **felder}
    return client.post(_PFAD, data=daten, files={"datei": (name, rumpf, "text/markdown")})


def test_ein_dokument_wird_aufbereitet_abgelegt_und_befundet(client, lage):
    r = _post(client)
    assert r.status_code == 200, r.text
    assert r.json() == {"upload_id": _KENNUNG, "name": "Lehrplan.md", "format": "md",
                        "befund": {"abschnitte": 3, "warnungen": []},
                        "ueberschriften_vorschau": ["Lehrplan", "Mechanik"]}
    [g] = lage.gespeichert
    assert g["session_id"] == _SITZUNG and g["block_id"] == _BLOCK and g["aufrufer"] == "person-a"
    assert g["groesse"] == len(_MD) and g["ttl_h"] == 24 and g["markdown"] == "# Lehrplan"
    assert lage.db.commits == 1
    assert "markdown" not in r.json()                # der Text geht nicht zurück ins Widget


def test_ohne_anmeldung_aber_erlaubt_ohne_aufrufer(client, lage):
    lage.person = False
    lage.cfg = UploadSettings(dokument_ohne_anmeldung=True)
    assert _post(client).status_code == 200
    assert lage.gespeichert[0]["aufrufer"] is None


@pytest.mark.parametrize(("aendern", "status", "code"), [
    (lambda lg: setattr(lg, "entities", None), 404, "sitzung_unbekannt"),
    (lambda lg: setattr(lg, "entities", {}), 409, "keine_anfrage"),
    (lambda lg: setattr(lg, "entities", {OFFENE_FRAGE: {"block_id": "b9999999",
                                                        "modul": UPLOAD}}), 409, "keine_anfrage"),
    (lambda lg: setattr(lg, "entities", {OFFENE_FRAGE: {"block_id": _BLOCK,
                                                        "modul": "ui_entscheidung"}}),
     409, "keine_anfrage"),
    (lambda lg: setattr(lg, "cfg", UploadSettings(dokument_im_chat=False)), 403, "aus"),
    (lambda lg: (setattr(lg, "person", False),
                 setattr(lg, "cfg", UploadSettings(dokument_ohne_anmeldung=False))),
     403, "nur_angemeldet"),
])
def test_abweisungen_vor_jeder_arbeit(client, lage, aendern, status, code):
    aendern(lage)
    r = _post(client)
    assert (r.status_code, r.json()["detail"]) == (status, code)
    assert lage.aufbereitet == [] and lage.gespeichert == []


def test_zu_gross_nach_der_studio_grenze(client, lage):
    lage.cfg = UploadSettings(max_mb=1)
    r = _post(client, rumpf=b"x" * (1024 * 1024 + 1))
    assert (r.status_code, r.json()["detail"]) == (413, "zu_gross")
    assert lage.aufbereitet == []


def test_die_rumpf_grenze_des_pfads_greift_vor_dem_endpunkt(client, lage):
    from boerdi.api.body_limit import body_limit_for

    assert body_limit_for(_PFAD) == (UploadSettings.OBERGRENZE_MB + 1) * 1024 * 1024
    assert body_limit_for(_PFAD + "/loeschen") == 16 * 1024


def test_die_seitengrenze_kommt_aus_dem_studio(client, lage):
    lage.cfg = UploadSettings(max_seiten=12)
    _post(client)
    assert lage.aufbereitet[0][2] == 12


def test_abweisung_des_dienstes_kommt_als_code(client, lage):
    lage.ergebnis = Abweisung(415, "bild")
    r = _post(client)
    assert (r.status_code, r.json()["detail"]) == (415, "bild")
    assert lage.gespeichert == [] and lage.ereignisse == []


def test_moderation_schreibt_ein_ereignis_ohne_inhalt(client, lage):
    lage.ergebnis = Abweisung(400, "abgewiesen")
    r = _post(client)
    assert (r.status_code, r.json()["detail"]) == (400, "abgewiesen")
    [e] = lage.ereignisse
    assert e["message"] == "" and e["decision"] == {"reasons": ["upload:moderation"]}


def test_zwei_zugleich_ergibt_409_statt_500(client, lage):
    from sqlalchemy.exc import IntegrityError

    lage.speichern_wirft = IntegrityError("insert", {}, Exception("unique"))
    r = _post(client)
    assert (r.status_code, r.json()["detail"]) == (409, "laeuft_schon")
    assert lage.db.rollbacks == 1


def test_inzwischen_geloeschte_sitzung_ergibt_404(client, lage, monkeypatch):
    from sqlalchemy.exc import IntegrityError

    async def weg(session, session_id):
        return False

    monkeypatch.setattr(api, "sitzung_vorhanden", weg)
    lage.speichern_wirft = IntegrityError("insert", {}, Exception("fk"))
    r = _post(client)
    assert (r.status_code, r.json()["detail"]) == (404, "sitzung_unbekannt")


@pytest.mark.parametrize("felder", [{"block_id": "B!"}, {"session_id": "x y"}])
def test_unbrauchbare_kennungen_422_ohne_arbeit(client, lage, felder):
    assert _post(client, **felder).status_code == 422
    assert lage.aufbereitet == []


def test_reservierte_sitzung_ist_nicht_oeffentlich(client, lage):
    r = client.post(_PFAD, data={"session_id": "eval-0123456789abcdef", "block_id": _BLOCK},
                    files={"datei": ("a.md", _MD, "text/markdown")})
    assert r.status_code == 422 and lage.aufbereitet == []


def test_innere_drosselung_429_mit_ereignis(client, lage, monkeypatch):
    async def gedrosselt(session_id, ip="", lang="de"):
        return RateVerdict(allowed=False, reason="session_minute", blocked_message="langsam")

    monkeypatch.setattr(api, "check_rate_limit", gedrosselt)
    assert _post(client).status_code == 429
    assert lage.aufbereitet == [] and lage.ereignisse[0]["rate_limited"] is True


def test_loeschen_ist_immer_204(client, lage):
    r = client.post(_PFAD + "/loeschen", json={"session_id": _SITZUNG, "upload_id": _KENNUNG})
    assert r.status_code == 204 and r.content == b""
    assert lage.geloescht == [(_SITZUNG, _KENNUNG)] and lage.db.commits == 1


def test_loeschen_nimmt_nur_uuid(client, lage):
    r = client.post(_PFAD + "/loeschen", json={"session_id": _SITZUNG, "upload_id": "x"})
    assert r.status_code == 422 and lage.geloescht == []
