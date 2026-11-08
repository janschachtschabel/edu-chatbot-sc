"""Paket U3-3a: ``POST /api/ui/ablage/{vorbereiten,datei,abschluss}`` — Übertragen in WLO.

Das MCP ist ersetzt (``mcp_ablage``, eigene Tests); hier zählt, was der Endpunkt entscheidet:
- nur mit **bestätigter Anmeldung** (403 ``nur_angemeldet`` vor jedem MCP-Aufruf), nur mit dem
  Studio-Schalter ``ablage_in_wlo`` (403 ``aus``), nur zu einer offenen Frage von ``ui_upload``
  (409);
- die Vorschau des Servers wird Teil ``ablage`` im Vorgang (mit Prüf-Kürzel des Freigabe-Schlüssels,
  nie dem Schlüssel selbst); jede Datei schreibt ihren Stand dorthin;
- ein Index zweimal → das alte Ergebnis ohne zweiten Aufruf; ein fremder Schlüssel → 409;
- Fehler des MCP als Codes; die KI sieht nur Zahlen (Kurztext des Teils).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import boerdi.api.ui_ablage as api
from boerdi.api.deps import get_session
from boerdi.domain.config_models.upload import UploadSettings
from boerdi.main import create_app
from boerdi.services.ablage import mcp_ablage, vorgang_teil
from boerdi.services.rate_limits import RateVerdict
from boerdi.settings import get_settings
from boerdi.ui_module.antwort import OFFENE_FRAGE
from boerdi.ui_module.namen import UPLOAD

_SITZUNG = "bb-0123456789abcdef0123456789abcdef"
_BLOCK = "b0000001"
_TOKEN = "tok-abcdefghijklmnop.0123456789ab"
_PLAN = {"batchToken": _TOKEN, "layout": "folder", "folderName": "Physik 7", "count": 2,
         "totalBytes": 10, "entries": [
             {"index": 0, "title": "Mechanik", "ext": "pdf", "size": 5, "fileName": "mechanik.pdf"},
             {"index": 1, "title": "Optik", "ext": "pdf", "size": 5, "fileName": "optik.pdf"}]}


class _DB:
    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


class _Lage:
    def __init__(self) -> None:
        self.db = _DB()
        self.entities: dict | None = {OFFENE_FRAGE: {"block_id": _BLOCK, "modul": UPLOAD}}
        self.cfg = UploadSettings(ablage_in_wlo=True)
        self.person = True
        self.teil: dict | None = None
        self.mcp: list[tuple] = []
        self.fehler: str | None = None
        self.ablegen: dict | Exception = {"status": "stored", "nodeId": "n-0",
                                          "folderDenied": False}
        self.speichern_ok = True
        self.abschluss: dict = {"status": "stored", "nodeId": "n-vorgang"}
        self.plan: dict = dict(_PLAN)
        self.folge: list[str] = []


@pytest.fixture
def lage(monkeypatch) -> _Lage:
    lg = _Lage()

    async def entities(session, session_id):
        return lg.entities if session_id == _SITZUNG else None

    async def frei(session_id, ip="", lang="de"):
        lg.folge.append("drossel")
        return RateVerdict(allowed=True)

    async def anmeldung():
        lg.folge.append("anmeldung")

    async def nichts(*_a, **_k):
        return None

    async def vorbereiten(ordner, eintraege):
        lg.mcp.append(("vorbereiten", ordner, eintraege))
        if lg.fehler:
            raise mcp_ablage.AblageFehler(lg.fehler)
        return dict(lg.plan)

    async def hochladen(strom, laenge, name):
        daten = b"".join([teil async for teil in strom])
        lg.mcp.append(("hochladen", daten, laenge, name))
        if lg.fehler:
            raise mcp_ablage.AblageFehler(lg.fehler)
        return {"ref": "r" * 24, "sha256": "a" * 64, "size": laenge, "ext": "pdf"}

    async def ablegen(token, index, ref):
        lg.mcp.append(("ablegen", token, index, ref))
        if isinstance(lg.ablegen, Exception):
            raise lg.ablegen
        if "nodeId" in lg.ablegen:
            return {**lg.ablegen, "nodeId": f"n-{index}"}
        return dict(lg.ablegen)

    async def abschliessen(token):
        lg.mcp.append(("abschluss", token))
        return dict(lg.abschluss)

    async def teil_lesen(s, session_id, entities):
        return lg.teil

    async def teil_speichern(s, session_id, entities, wert, neu=None, nur_dieser=False):
        # Wie ``teile_speichern``: mit ``neu`` wird der Wert unter der Sperre berechnet.
        if not lg.speichern_ok:
            return False
        if neu is not None:
            wert = await neu()
            if wert is None:
                return False
        lg.teil = wert
        return True

    for name, wert in [("sitzung_entities", entities), ("sitzung_entities_frisch", entities),
                       ("check_rate_limit", frei),
                       ("log_safety_event", nichts), ("verbindung_freigeben", nichts),
                       ("bestaetige_anmeldung", anmeldung), ("update_session", nichts)]:
        monkeypatch.setattr(api, name, wert)
    monkeypatch.setattr(api, "adopt_turn_auth_block", lambda request: None)
    monkeypatch.setattr(api, "load_upload_config", lambda: lg.cfg)
    monkeypatch.setattr(api, "has_personal_auth", lambda: lg.person)
    monkeypatch.setattr(api, "get_repo_base_url", lambda: "https://repo.test")
    for name, wert in [("vorbereiten", vorbereiten), ("datei_hochladen", hochladen),
                       ("datei_ablegen", ablegen), ("abschliessen", abschliessen)]:
        monkeypatch.setattr(mcp_ablage, name, wert)
    monkeypatch.setattr(vorgang_teil, "lesen", teil_lesen)
    monkeypatch.setattr(vorgang_teil, "speichern", teil_speichern)
    return lg


@pytest.fixture(autouse=True)
def _umgebung(monkeypatch):
    monkeypatch.setenv("STUDIO_API_KEY", "studio-schluessel-fuer-ablage")
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


_EINTRAEGE = [{"titel": "Mechanik", "sha256": "a" * 64, "groesse": 5, "art": "pdf"},
              {"titel": "Optik", "sha256": "b" * 64, "groesse": 5, "art": "pdf"}]


def _vorbereiten(client, **mehr):
    return client.post("/api/ui/ablage/vorbereiten", json={
        "session_id": _SITZUNG, "block_id": _BLOCK, "ordner": "Physik 7", "eintraege": _EINTRAEGE,
        **mehr})


def _datei(client, index=0, token=_TOKEN):
    return client.post("/api/ui/ablage/datei", data={
        "session_id": _SITZUNG, "block_id": _BLOCK, "batch_token": token, "index": str(index)},
        files={"datei": ("Mechanik.pdf", b"%PDF-", "application/pdf")})


def test_vorbereiten_gibt_die_vorschau_und_haelt_den_plan(client, lage):
    r = _vorbereiten(client)
    assert r.status_code == 200, r.text
    daten = r.json()
    # Querschnitts-Review (NIT): ein Wortschatz — der des Moduls, nicht der des MCP.
    assert daten["batch_token"] == _TOKEN and daten["layout"] == "ordner"
    assert [e["name"] for e in daten["eintraege"]] == ["mechanik.pdf", "optik.pdf"]
    assert lage.teil["format"] == "wlo.ablage@1" and lage.teil["ordner"] == "Physik 7"
    assert _TOKEN not in str(lage.teil)                     # nur das Prüf-Kürzel
    assert [e["stand"] for e in lage.teil["inhalte"]] == ["offen", "offen"]


@pytest.mark.parametrize(("aendern", "status", "code"), [
    (lambda lg: setattr(lg, "person", False), 403, "nur_angemeldet"),
    (lambda lg: setattr(lg, "cfg", UploadSettings(ablage_in_wlo=False)), 403, "aus"),
    (lambda lg: setattr(lg, "entities", {}), 409, "keine_anfrage"),
    (lambda lg: setattr(lg, "entities", None), 404, "sitzung_unbekannt"),
])
def test_vorbereiten_weist_vor_jedem_mcp_aufruf_ab(client, lage, aendern, status, code):
    aendern(lage)
    r = _vorbereiten(client)
    assert (r.status_code, r.json()["detail"]) == (status, code)
    assert lage.mcp == []


def test_ein_mcp_fehler_wird_ein_code(client, lage):
    lage.fehler = "kein_recht"
    r = _vorbereiten(client)
    assert (r.status_code, r.json()["detail"]) == (403, "kein_recht")


def test_eine_datei_geht_als_strom_hin_und_ihr_stand_in_den_vorgang(client, lage):
    _vorbereiten(client)
    r = _datei(client, 0)
    assert r.status_code == 200, r.text
    assert r.json() == {"index": 0, "stand": "stored", "node_id": "n-0",
                        "link": "https://repo.test/edu-sharing/components/render/n-0",
                        "ordner_verweigert": False,
                        "bereits": False}
    hoch = next(m for m in lage.mcp if m[0] == "hochladen")
    assert hoch[1] == b"%PDF-" and hoch[2] == 5
    [erste, _] = lage.teil["inhalte"]
    assert erste["stand"] == "stored" and erste["node_id"] == "n-0"
    assert "1 von 2 abgelegt" in vorgang_teil.zusammenfassung(lage.teil)


def test_ein_index_zweimal_gibt_das_alte_ergebnis_ohne_zweiten_aufruf(client, lage):
    _vorbereiten(client)
    _datei(client, 0)
    vorher = len(lage.mcp)
    r = _datei(client, 0)
    assert r.json()["bereits"] is True and r.json()["stand"] == "stored"
    assert len(lage.mcp) == vorher


@pytest.mark.parametrize(("index", "token", "status", "code"), [
    (5, _TOKEN, 400, "index"),
    (0, "tok-fremd-0000000000.000000000000", 409, "fremder_stapel"),
])
def test_unpassende_dateien(client, lage, index, token, status, code):
    _vorbereiten(client)
    r = _datei(client, index, token)
    assert (r.status_code, r.json()["detail"]) == (status, code)


def test_abschluss_legt_den_vorgang_ab(client, lage):
    _vorbereiten(client)
    _datei(client, 0)
    r = client.post("/api/ui/ablage/abschluss", json={"session_id": _SITZUNG, "block_id": _BLOCK,
                                                      "batch_token": _TOKEN})
    assert r.status_code == 200 and r.json()["stand"] == "stored"
    assert lage.teil["vorgang_node_id"] == "n-vorgang" and lage.teil["abgeschlossen"] is True



# ── Review U3-3a ────────────────────────────────────────────────────────────────────────────

def test_ein_endgueltiger_fehlschlag_wird_nicht_noch_einmal_geschickt(client, lage):
    """Befund 1: jeder zweite Versuch kostete einen verwaisten Platz im MCP-Speicher."""
    lage.ablegen = {"status": "failed", "detail": "403"}
    _vorbereiten(client)
    assert _datei(client, 0).json()["stand"] == "failed"
    vorher = len(lage.mcp)
    r = _datei(client, 0)
    assert r.json()["bereits"] is True and r.json()["stand"] == "failed"
    assert len(lage.mcp) == vorher


def test_ein_grund_des_mcp_laesst_den_eintrag_offen(client, lage):
    """Befund 2: nichts angelegt (Platz fehlt) → 409 erneut, der Eintrag bleibt offen."""
    lage.ablegen = {"status": "failed", "reason": "slot_missing"}
    _vorbereiten(client)
    r = _datei(client, 0)
    assert (r.status_code, r.json()["detail"]) == (409, "erneut")
    assert lage.teil["inhalte"][0]["stand"] == "offen"


def test_keine_antwort_beim_ablegen_ist_unklar(client, lage):
    """Befund 2 / T2: die Datei KANN abgelegt sein — „unverified“, nicht „offen“."""
    lage.ablegen = mcp_ablage.AblageFehler("zu_langsam")
    _vorbereiten(client)
    r = _datei(client, 0)
    assert (r.status_code, r.json()["detail"]) == (504, "zu_langsam")
    assert lage.teil["inhalte"][0]["stand"] == "unverified"


def test_ohne_gespeicherten_teil_kein_schluessel(client, lage):
    """Befund 4: sonst scheiterte jede Datei an fremder_stapel."""
    lage.speichern_ok = False
    r = _vorbereiten(client)
    assert (r.status_code, r.json()["detail"]) == (503, "nicht_gespeichert")


def test_eine_andere_groesse_geht_gar_nicht_erst_hin(client, lage):
    """Befund 8."""
    _vorbereiten(client)
    r = client.post("/api/ui/ablage/datei", data={
        "session_id": _SITZUNG, "block_id": _BLOCK, "batch_token": _TOKEN, "index": "0"},
        files={"datei": ("Mechanik.pdf", b"%PDF-1.7 viel laenger", "application/pdf")})
    assert (r.status_code, r.json()["detail"]) == (400, "groesse")
    assert not any(m[0] == "hochladen" for m in lage.mcp)


def test_abschluss_ohne_abgelegte_datei(client, lage):
    lage.abschluss = {"status": "failed", "reason": "nothing_stored"}
    _vorbereiten(client)
    r = client.post("/api/ui/ablage/abschluss", json={"session_id": _SITZUNG, "block_id": _BLOCK,
                                                      "batch_token": _TOKEN})
    assert (r.status_code, r.json()["detail"]) == (409, "nichts_abgelegt")


def test_logs_ohne_dateinamen(client, lage, caplog):
    """T3: der Dateiname erscheint in keinem Log."""
    _vorbereiten(client)
    client.post("/api/ui/ablage/datei", data={
        "session_id": _SITZUNG, "block_id": _BLOCK, "batch_token": _TOKEN, "index": "0"},
        files={"datei": ("Zeugnis Max Mustermann.pdf", b"%PDF-", "application/pdf")})
    assert "Mustermann" not in caplog.text


def test_die_grenzen_der_pfade():
    """T3: Rumpf-Grenzen der drei Pfade."""
    from boerdi.api.body_limit import body_limit_for
    from boerdi.domain.config_models.upload import UploadSettings as U

    assert body_limit_for("/api/ui/ablage/datei") == (U.OBERGRENZE_MB + 1) * 1024 * 1024
    assert body_limit_for("/api/ui/ablage/vorbereiten") == 256 * 1024
    assert body_limit_for("/api/ui/ablage/abschluss") == 256 * 1024



# ── U3-3b ───────────────────────────────────────────────────────────────────────────────────

def test_ohne_knoten_kein_link(client, lage):
    """Ein Fehlschlag hat keinen Knoten — dann auch keinen Link (das Modul baut keine Adressen)."""
    lage.ablegen = {"status": "failed", "detail": "403"}
    _vorbereiten(client)
    r = _datei(client, 0)
    assert r.json()["link"] is None


# ── Querschnitts-Review 2026-11-06 (Q1) ─────────────────────────────────────────────────────

def _abschluss(client, block=_BLOCK):
    return client.post("/api/ui/ablage/abschluss", json={"session_id": _SITZUNG, "block_id": block,
                                                      "batch_token": _TOKEN})


def test_m2_ein_zug_mitten_im_stapel_bricht_ihn_nicht_ab(client, lage):
    """Ein getipptes „danke“ schließt die offene Frage — der Stapel gehört trotzdem weiter dazu."""
    _vorbereiten(client)
    assert _datei(client, 0).status_code == 200
    lage.entities = {}
    r = _datei(client, 1)
    assert r.status_code == 200, r.text
    assert _abschluss(client).status_code == 200
    assert lage.teil["abgeschlossen"] is True


def test_m2_ein_anderer_block_bekommt_den_stapel_nicht(client, lage):
    _vorbereiten(client)
    lage.entities = {}
    r = client.post("/api/ui/ablage/datei", data={
        "session_id": _SITZUNG, "block_id": "b0000099", "batch_token": _TOKEN, "index": "0"},
        files={"datei": ("Mechanik.pdf", b"%PDF-", "application/pdf")})
    assert (r.status_code, r.json()["detail"]) == (409, "fremder_stapel")
    assert (_abschluss(client, "b0000099").status_code) == 409


def test_m2_vorbereiten_braucht_weiter_die_offene_frage(client, lage):
    lage.entities = {}
    assert _vorbereiten(client).json()["detail"] == "keine_anfrage"


def test_m3_ohne_antwort_wird_beim_naechsten_versuch_eingeloest(client, lage):
    """Das MCP ist je Index idempotent: ein zweiter Versuch bringt den wahren Stand."""
    lage.ablegen = mcp_ablage.AblageFehler("zu_langsam")
    _vorbereiten(client)
    assert _datei(client, 0).status_code == 504
    assert lage.teil["inhalte"][0]["ohne_antwort"] is True
    lage.ablegen = {"status": "stored", "nodeId": "n-0", "already": True}
    vorher = len(lage.mcp)
    r = _datei(client, 0)
    assert r.status_code == 200 and r.json()["stand"] == "stored"
    assert len(lage.mcp) > vorher
    assert "ohne_antwort" not in lage.teil["inhalte"][0]


def test_m3_ein_vom_mcp_gemeldetes_unklar_bleibt_endgueltig(client, lage):
    lage.ablegen = {"status": "unverified"}
    _vorbereiten(client)
    assert _datei(client, 0).json()["stand"] == "unverified"
    vorher = len(lage.mcp)
    r = _datei(client, 0)
    assert r.json()["bereits"] is True and len(lage.mcp) == vorher


def test_ein_offener_stapel_wird_nicht_ueberschrieben(client, lage):
    _vorbereiten(client)
    _datei(client, 0)
    lage.plan = {**_PLAN, "batchToken": "tok-zweiter-stapel.0123456789"}
    r = _vorbereiten(client)
    assert (r.status_code, r.json()["detail"]) == (409, "stapel_offen")
    assert lage.teil["inhalte"][0]["node_id"] == "n-0"


def test_nach_ablauf_der_freigabe_bleiben_die_abgelegten_als_frueher(client, lage):
    _vorbereiten(client)
    _datei(client, 0)
    lage.teil["erstellt"] = "2026-01-01T00:00:00+00:00"
    lage.plan = {**_PLAN, "batchToken": "tok-zweiter-stapel.0123456789"}
    r = _vorbereiten(client)
    assert r.status_code == 200, r.text
    assert lage.teil["frueher"] == [{"titel": "Mechanik", "node_id": "n-0", "rolle": "inhalt"}]
    assert [e["stand"] for e in lage.teil["inhalte"]] == ["offen", "offen"]


def test_ein_abgeschlossener_stapel_darf_ersetzt_werden(client, lage):
    _vorbereiten(client)
    _datei(client, 0)
    _abschluss(client)
    lage.plan = {**_PLAN, "batchToken": "tok-zweiter-stapel.0123456789"}
    assert _vorbereiten(client).status_code == 200


def test_vorbereiten_prueft_die_groesse_vor_dem_mcp(client, lage):
    zu_gross = [{**_EINTRAEGE[0], "groesse": 11 * 1024 * 1024}, _EINTRAEGE[1]]
    r = _vorbereiten(client, eintraege=zu_gross)
    assert (r.status_code, r.json()["detail"]) == (413, "zu_gross")
    assert lage.mcp == []


def test_vorbereiten_drosselt_vor_der_anmeldung(client, lage):
    _vorbereiten(client)
    assert lage.folge.index("drossel") < lage.folge.index("anmeldung")


def test_ein_verweigerter_ordner_heisst_flach(client, lage):
    lage.ablegen = {"status": "stored", "nodeId": "n-0", "folderDenied": True}
    _vorbereiten(client)
    _datei(client, 0)
    assert lage.teil["layout"] == "flach"



# ── Review Q1 ───────────────────────────────────────────────────────────────────────────────

def test_wechselt_der_stapel_mitten_in_einer_datei_geht_ihr_ergebnis_nach_frueher(client, lage,
                                                                                monkeypatch):
    """Review Q1, Befund 2: ein zweiter Tab bereitet vor, während Datei 0 von Stapel A beim MCP
    ist —
    As Ergebnis landet nicht in Bs Eintrag 0, sondern als früher abgelegt."""
    _vorbereiten(client)
    echt = mcp_ablage.datei_ablegen

    async def mitten_drin(token, index, ref):
        lage.teil = vorgang_teil.aus_plan({**_PLAN, "batchToken": "tok-zweiter-stapel.0123456789"},
                                          "tok-zweiter-stapel.0123456789", _BLOCK)
        return await echt(token, index, ref)

    monkeypatch.setattr(mcp_ablage, "datei_ablegen", mitten_drin)
    _datei(client, 0)
    assert lage.teil["token_kuerzel"] == vorgang_teil.kuerzel("tok-zweiter-stapel.0123456789")
    assert lage.teil["inhalte"][0]["stand"] == "offen"
    assert lage.teil["frueher"] == [{"titel": "Mechanik", "node_id": "n-0", "rolle": "inhalt"}]


def test_ein_abschluss_schreibt_keinen_fremden_stapel_ab(client, lage, monkeypatch):
    _vorbereiten(client)
    _datei(client, 0)
    echt = mcp_ablage.abschliessen

    async def mitten_drin(token):
        lage.teil = vorgang_teil.aus_plan({**_PLAN, "batchToken": "tok-zweiter-stapel.0123456789"},
                                          "tok-zweiter-stapel.0123456789", _BLOCK)
        return await echt(token)

    monkeypatch.setattr(mcp_ablage, "abschliessen", mitten_drin)
    _abschluss(client)
    assert lage.teil["abgeschlossen"] is False
