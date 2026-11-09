"""Paket K2d-2 (Plan 2026-11-08, Entscheid F3): Dateien eines Auftrags holen — gedeckelt und nur
die, die der Schritt nennt (``dateien_holen: [outputId]``).

- Der Client bildet die Adresse selbst aus Job-ID und ``outputId``
  (``/api/v1/jobs/{jobId}/files/{outputId}``, Job-Vertrag) — nie aus ``downloadUrl`` — und holt mit
  dem Schlüssel des Zuges, höchstens so viel wie ein Upload darf.
- Jede Datei geht durch dieselbe Aufbereitung wie ein Upload (Art, Umwandlung, Moderation); ihr Text
  steht im Teil des Ergebnisses unter ``texte.<outputId>`` — lesbar mit ``$teil`` und ``pfad``
  (K2d-1). Was nicht ging, steht unter ``dateien_fehlen.<outputId>`` mit einem Code.
- ``dateien_holen`` gibt es nur am Auftragsschritt, höchstens drei, Kennungen ohne Punkt.
"""

from __future__ import annotations

import asyncio
import time

import httpx
import pytest
from pydantic import ValidationError

from boerdi.domain.config_models.ablauf import AblaufArea, Schritt
from boerdi.services.ablauf.pruefung import pruefe
from boerdi.services.auftraege import client, dateien
from tests.test_ablauf_auftrag import freigeschaltet, im_zug  # noqa: F401 — der Zug mit Attrappen
from tests.test_auftraege_vertrag import _job, bapi  # noqa: F401 — die Vertrags-Attrappe

_DATEIEN = [{"outputId": "report", "name": "report.md", "size": 12, "available": True,
             "downloadUrl": "https://anderswo.example/geheim?token=1"},
            {"outputId": "alt", "name": "alt.md", "size": 9, "available": False,
             "reason": "EXPIRED"}]


def test_der_stand_nennt_die_kennung_der_dateien(bapi):  # noqa: F811
    bapi["antworten"][("GET", "/api/v1/jobs/job-1")] = _job("SUCCEEDED", outputs={},
                                                            files=_DATEIEN)
    stand = asyncio.run(client.stand("job-1"))
    assert [d["kennung"] for d in stand.dateien] == ["report", "alt"]
    assert "anderswo" not in str(stand.dateien)


def test_eine_datei_holen_die_adresse_bildet_der_client(bapi):  # noqa: F811
    bapi["antworten"][("GET", "/api/v1/jobs/job-1/files/report")] = httpx.Response(
        200, content=b"# Bericht\n\nText.", headers={"content-type": "text/markdown"})
    assert asyncio.run(client.datei("job-1", "report", 1000)) == b"# Bericht\n\nText."
    [anfrage] = [r for r in bapi["gesehen"] if r.url.path.endswith("/files/report")]
    assert anfrage.url.host != "anderswo.example"
    assert anfrage.headers["authorization"].startswith("Bearer ")


def test_eine_zu_grosse_datei_wird_nicht_ganz_gelesen(bapi):  # noqa: F811
    bapi["antworten"][("GET", "/api/v1/jobs/job-1/files/report")] = httpx.Response(
        200, content=b"x" * 5000)
    with pytest.raises(client.AuftragFehler) as fehler:
        asyncio.run(client.datei("job-1", "report", 1000))
    assert fehler.value.grund == "zu_gross"


@pytest.mark.parametrize(("status", "grund"), [(404, "unbekannt"), (410, "nicht_verfuegbar"),
                                               (403, "abgewiesen"), (302, "fehler"),
                                               (500, "fehler")])
def test_fehler_beim_holen(bapi, status, grund):  # noqa: F811
    bapi["antworten"][("GET", "/api/v1/jobs/job-1/files/report")] = httpx.Response(
        status, headers={"location": "https://anderswo.example/x"} if status == 302 else {})
    with pytest.raises(client.AuftragFehler) as fehler:
        asyncio.run(client.datei("job-1", "report", 1000))
    assert fehler.value.grund == grund


def test_eine_kennung_mit_fremden_zeichen_wird_nicht_geholt(bapi):  # noqa: F811
    for kennung in ("../job-2", "a/b", "a.b", "", "x" * 65):
        with pytest.raises(client.AuftragFehler):
            asyncio.run(client.datei("job-1", kennung, 1000))
    assert bapi["gesehen"] == []


# ── Holen und Aufbereiten ────────────────────────────────────────────────────────────────────

@pytest.fixture
def aufbereitung(monkeypatch):
    geholt: list[tuple[str, str, int]] = []
    inhalte = {"report": b"# Bericht\n\nText.", "boese": b"schlimm"}

    async def datei(job_id, kennung, max_bytes):
        geholt.append((job_id, kennung, max_bytes))
        if kennung not in inhalte:
            raise client.AuftragFehler("unbekannt")
        return inhalte[kennung]

    async def aufbereiten(rumpf, name, **_k):
        if rumpf == b"schlimm":
            return dateien.Abweisung(400, "abgewiesen")
        return dateien.Aufbereitet(format="md", markdown=rumpf.decode(), befund={},
                                   gliederung=[], vorschau=[])

    monkeypatch.setattr(client, "datei", datei)
    monkeypatch.setattr(dateien, "aufbereiten", aufbereiten)
    return geholt


def _stand_dateien():
    return [{"kennung": "report", "name": "report.md", "groesse": 12, "verfuegbar": True},
            {"kennung": "alt", "name": "alt.md", "groesse": 9, "verfuegbar": False},
            {"kennung": "boese", "name": "b.md", "groesse": 7},
            {"kennung": "riesig", "name": "r.pdf", "groesse": 10**9}]


def test_nur_die_genannten_dateien_als_text_der_rest_mit_code(aufbereitung, monkeypatch):
    monkeypatch.setattr(dateien, "MAX_DATEIEN", 5)
    texte, fehlen = asyncio.run(dateien.holen(
        "job-1", _stand_dateien(), ["report", "alt", "boese", "riesig", "nichtda"]))
    assert texte == {"report": "# Bericht\n\nText."}
    assert fehlen == {"alt": "nicht_verfuegbar", "boese": "abgewiesen", "riesig": "zu_gross",
                      "nichtda": "unbekannt"}
    # geholt wurden nur die, die es geben konnte — höchstens die Grenze eines Uploads
    assert [k for _j, k, _m in aufbereitung] == ["report", "boese"]
    assert all(m == dateien.max_bytes() for _j, _k, m in aufbereitung)


def test_hoechstens_drei_dateien_je_schritt(aufbereitung):
    texte, fehlen = asyncio.run(dateien.holen(
        "job-1", _stand_dateien(), ["alt", "riesig", "boese", "report"]))
    assert texte == {} and set(fehlen) == {"alt", "riesig", "boese"}


def test_ohne_genannte_dateien_wird_nichts_geholt(aufbereitung):
    assert asyncio.run(dateien.holen("job-1", _stand_dateien(), [])) == ({}, {})
    assert aufbereitung == []


def test_ein_langer_text_wird_gekuerzt(aufbereitung, monkeypatch):
    monkeypatch.setattr(dateien, "MAX_ZEICHEN", 5)
    texte, _ = asyncio.run(dateien.holen("job-1", _stand_dateien(), ["report"]))
    assert texte == {"report": "# Ber"}


# ── Modell und Prüfung ──────────────────────────────────────────────────────────────────────

def test_dateien_holen_hoechstens_drei_kennungen_ohne_punkt():
    Schritt.model_validate({"id": "a", "typ": "auftrag", "dateien_holen": ["report", "seite-2"]})
    for falsch in (["a.b"], ["a/b"], ["a", "b", "c", "d"]):
        with pytest.raises(ValidationError):
            Schritt.model_validate({"id": "a", "typ": "auftrag", "dateien_holen": falsch})
    nur_bei = Schritt.model_json_schema()["properties"]["dateien_holen"]["x-nur-bei"]
    assert nur_bei == {"feld": "typ", "werte": ["auftrag"]}


def test_die_pruefung_meldet_dateien_holen_an_einem_anderen_schritt():
    ablauf = AblaufArea.model_validate({"id": "p", "titel": {"de": "P"}, "schritte": [
        {"id": "m", "typ": "nachricht", "dateien_holen": ["report"]}, {"id": "e", "typ": "ende"}]})
    assert any("dateien_holen" in b for b in pruefe(ablauf))


def test_die_fassung_eines_schritts_ohne_dateien_holen_bleibt():
    from tests.test_ablauf_studio_k2c1 import test_die_auszeichnung_aendert_weder_daten_noch_fassung

    test_die_auszeichnung_aendert_weder_daten_noch_fassung()  # die Goldfassung aus K2c-1


# ── Im Zug: „Stand prüfen“ holt die Dateien ──────────────────────────────────────────────────

def test_beim_abholen_stehen_die_texte_im_teil(im_zug, monkeypatch, aufbereitung):  # noqa: F811
    from boerdi.services.ablauf import ausloeser
    from tests.test_ablauf_auftrag import _SCHRITTE, _pruefe, _roh, _starte

    schritte = [{**_SCHRITTE[0], "argumente": {"text": "fest"},
                 "dateien_holen": ["report", "alt"]}, *_SCHRITTE[1:]]
    katalog = {"ablaeufe": [_roh(schritte=schritte)]}
    monkeypatch.setattr(ausloeser, "area", lambda key: katalog if key == ausloeser.BEREICH else {})
    state: dict = {"entities": {}}
    _starte(state)
    im_zug.staende.append(client.Stand("fertig", {"n": 1}, [
        {"kennung": "report", "name": "report.md", "groesse": 12},
        {"kennung": "alt", "name": "alt.md", "groesse": 9, "verfuegbar": False}]))
    antwort = _pruefe(state)
    assert antwort.content == "Gelesen."
    [v] = im_zug.speicher.v.values()
    wert = v.akte["teile"]["volltext"]["wert"]
    assert wert["texte"] == {"report": "# Bericht\n\nText."}
    assert wert["dateien_fehlen"] == {"alt": "nicht_verfuegbar"}
    assert [k for _j, k, _m in aufbereitung] == ["report"]


def test_ohne_dateien_holen_bleibt_das_ergebnis_wie_bisher(im_zug, aufbereitung):  # noqa: F811
    from tests.test_ablauf_auftrag import _pruefe, _starte

    state: dict = {"entities": {}}
    _starte(state)
    im_zug.staende.append(client.Stand("fertig", {"n": 1}, []))
    _pruefe(state)
    [v] = im_zug.speicher.v.values()
    assert v.akte["teile"]["volltext"]["wert"] == {"outputs": {"n": 1}, "dateien": []}
    assert aufbereitung == []


# ── Review K2d-2 ─────────────────────────────────────────────────────────────────────────────

def test_review_429_und_angekuendigte_laenge_und_gepackt(bapi):  # noqa: F811
    pfad = ("GET", "/api/v1/jobs/job-1/files/report")
    for antwort, grund in (
            (httpx.Response(429, headers={"retry-after": "5"}), "voll"),
            (httpx.Response(200, content=b"x", headers={"content-length": "5000"}), "zu_gross"),
            (httpx.Response(200, content=b"x", headers={"content-encoding": "gzip"}), "fehler")):
        bapi["antworten"][pfad] = antwort
        with pytest.raises(client.AuftragFehler) as fehler:
            asyncio.run(client.datei("job-1", "report", 1000))
        assert fehler.value.grund == grund
    assert all(r.headers.get("accept-encoding") == "identity" for r in bapi["gesehen"])


def test_review_der_deckel_liest_den_rest_nicht(bapi):  # noqa: F811
    gelesen: list[int] = []

    async def stuecke():
        for i in range(10):
            gelesen.append(i)
            yield b"x" * 400

    bapi["antworten"][("GET", "/api/v1/jobs/job-1/files/report")] = httpx.Response(
        200, content=stuecke())
    with pytest.raises(client.AuftragFehler) as fehler:
        asyncio.run(client.datei("job-1", "report", 1000))
    assert fehler.value.grund == "zu_gross" and len(gelesen) < 10


def test_review_nach_abgewiesenem_schluessel_keine_weitere_anfrage(monkeypatch):
    gefragt: list[str] = []

    async def datei(job_id, kennung, max_bytes):
        gefragt.append(kennung)
        raise client.AuftragFehler("abgewiesen")

    monkeypatch.setattr(client, "datei", datei)
    _texte, fehlen = asyncio.run(dateien.holen("job-1", [
        {"kennung": k, "name": f"{k}.md"} for k in ("a", "b", "c")], ["a", "b", "c"]))
    assert gefragt == ["a"]
    assert fehlen == {"a": "schluessel_abgewiesen", "b": "schluessel_abgewiesen",
                      "c": "schluessel_abgewiesen"}


def test_review_die_gesamtfrist(monkeypatch):
    async def langsam(job_id, kennung, max_bytes):
        await asyncio.sleep(5)
        return b""

    monkeypatch.setattr(client, "datei", langsam)
    _texte, fehlen = asyncio.run(dateien.holen("job-1", [
        {"kennung": "a", "name": "a.md"}, {"kennung": "b", "name": "b.md"}], ["a", "b"],
        frist_s=1.5))
    assert fehlen == {"a": "zu_langsam", "b": "zu_langsam"}


def test_review2_die_gesamtfrist_gilt_auch_fuer_die_aufbereitung(monkeypatch):
    async def datei(job_id, kennung, max_bytes):
        return b"# T\n\nText."

    async def langsam(*_a, **_k):
        await asyncio.sleep(5)

    monkeypatch.setattr(client, "datei", datei)
    monkeypatch.setattr(dateien, "aufbereiten", langsam)
    beginn = time.monotonic()
    _texte, fehlen = asyncio.run(dateien.holen("job-1", [{"kennung": "a", "name": "a.md"}], ["a"],
                                                frist_s=2.0))
    assert fehlen == {"a": "zu_langsam"} and time.monotonic() - beginn < 4


def test_review2_nach_voll_keine_weitere_anfrage(monkeypatch):
    gefragt: list[str] = []

    async def datei(job_id, kennung, max_bytes):
        gefragt.append(kennung)
        raise client.AuftragFehler("voll")

    monkeypatch.setattr(client, "datei", datei)
    _texte, fehlen = asyncio.run(dateien.holen("job-1", [
        {"kennung": k, "name": f"{k}.md"} for k in ("a", "b")], ["a", "b"]))
    assert gefragt == ["a"] and fehlen == {"a": "voll", "b": "voll"}


def _echte_aufbereitung(monkeypatch, rumpf: bytes, urteil: dict):
    stufen: list[str] = []

    async def datei(job_id, kennung, max_bytes):
        return rumpf

    async def moderieren(text, *, stufe):
        stufen.append(stufe)
        return urteil

    monkeypatch.setattr(client, "datei", datei)
    monkeypatch.setattr(dateien, "moderate", moderieren)
    erg = asyncio.run(dateien.holen("job-1", [{"kennung": "r", "name": "r.md"}], ["r"]))
    return erg, stufen


def test_review_dieselbe_aufbereitung_wie_ein_upload(monkeypatch):
    from boerdi.settings import get_settings

    (texte, fehlen), stufen = _echte_aufbereitung(
        monkeypatch, "# Bericht\n\nEin Absatz über Optik und Licht.".encode(), {"flagged": False})
    assert "Optik" in texte["r"] and fehlen == {} and stufen == ["auftrag_datei"]
    (_t, fehlen), _ = _echte_aufbereitung(monkeypatch, b"# Schlimm\n\nText.", {"flagged": True})
    assert fehlen == {"r": "abgewiesen"}
    (_t, fehlen), _ = _echte_aufbereitung(monkeypatch, b"\x89PNG\r\n\x1a\n" + b"0" * 64, {})
    assert fehlen == {"r": "bild"}
    monkeypatch.setenv("MODERATION_FAILURE_MODE", "closed")
    get_settings.cache_clear()
    try:
        (_t, fehlen), _ = _echte_aufbereitung(monkeypatch, b"# T\n\nText.", {})
        assert fehlen == {"r": "pruefung_fehlt"}
        # zweites Review, Befund 1: die Moderation fehlte nur — „Stand prüfen“ versucht es erneut
        assert "pruefung_fehlt" in dateien.VORUEBERGEHEND
    finally:
        get_settings.cache_clear()


def test_review_ein_voruebergehender_fehler_verbraucht_das_ergebnis_nicht(
        im_zug, monkeypatch):  # noqa: F811
    from boerdi.i18n import bot_text
    from boerdi.services.ablauf import auftrag_zug, ausloeser
    from tests.test_ablauf_auftrag import _SCHRITTE, _pruefe, _roh, _starte

    schritte = [{**_SCHRITTE[0], "argumente": {"text": "fest"}, "dateien_holen": ["report"]},
                *_SCHRITTE[1:]]
    katalog = {"ablaeufe": [_roh(schritte=schritte)]}
    monkeypatch.setattr(ausloeser, "area", lambda key: katalog if key == ausloeser.BEREICH else {})

    async def holen(job_id, d, kennungen):
        return {}, {"report": "ausgelastet"}

    monkeypatch.setattr(dateien, "holen", holen)
    state: dict = {"entities": {}}
    _starte(state)
    fertig = client.Stand("fertig", {}, [{"kennung": "report", "name": "r.md"}])
    for _ in range(auftrag_zug.DATEI_VERSUCHE - 1):
        im_zug.staende.append(fertig)
        antwort = _pruefe(state)
        assert antwort.content == bot_text("de", "action.ablauf.dateienSpaeter")
        assert antwort.quick_replies and im_zug.ablage.auftraege[0].status == "laeuft"
    # der letzte Versuch geht ohne die Datei weiter (der Schritt liest sie nicht: es geht weiter)
    im_zug.staende.append(fertig)
    _pruefe(state)
    assert im_zug.ablage.auftraege[0].status == "fertig"
    [v] = im_zug.speicher.v.values()
    assert v.akte["teile"]["volltext"]["wert"]["dateien_fehlen"] == {"report": "ausgelastet"}
    assert auftrag_zug.DATEI_VERSUCHE_KEY not in state["entities"]


def test_review2_der_zaehler_traegt_nur_das_kuerzel(im_zug, monkeypatch):  # noqa: F811
    from boerdi.services.ablauf import auftrag_zug, ausloeser
    from tests.test_ablauf_auftrag import _SCHRITTE, _pruefe, _roh, _starte

    schritte = [{**_SCHRITTE[0], "argumente": {"text": "fest"}, "dateien_holen": ["report"]},
                *_SCHRITTE[1:]]
    katalog = {"ablaeufe": [_roh(schritte=schritte)]}
    monkeypatch.setattr(ausloeser, "area", lambda key: katalog if key == ausloeser.BEREICH else {})
    ergebnisse = [({}, {"report": "fehler"}), ({"report": "# Text"}, {})]

    async def holen(job_id, d, kennungen):
        return ergebnisse.pop(0)

    monkeypatch.setattr(dateien, "holen", holen)
    state: dict = {"entities": {}}
    _starte(state)
    fertig = client.Stand("fertig", {}, [{"kennung": "report", "name": "r.md"}])
    im_zug.staende.append(fertig)
    _pruefe(state)
    merk = state["entities"][auftrag_zug.DATEI_VERSUCHE_KEY]
    job_id = im_zug.ablage.auftraege[0].job_id
    assert merk == {"auftrag": client.kuerzel(job_id), "n": 1}
    assert job_id not in str(state["entities"])
    # der nächste Versuch gelingt: der Zähler ist weg, der Text im Ergebnis
    im_zug.staende.append(fertig)
    _pruefe(state)
    assert auftrag_zug.DATEI_VERSUCHE_KEY not in state["entities"]
    [v] = im_zug.speicher.v.values()
    assert v.akte["teile"]["volltext"]["wert"]["texte"] == {"report": "# Text"}
