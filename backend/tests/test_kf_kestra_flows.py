"""Paket KF (Plan 2026-11-12): Kestra-Flows im Studio freigeben.

- **Bereich** ``01-base/kestra-flows`` (``kestra.flows``): ``namespace/flowId``, ohne Doppelte.
- **Regel** (K-E2): im Studio freigegeben → diese, mit ``B_API_JOBS_FLOWS`` als Obergrenze; im
  Studio nichts → ``B_API_JOBS_FLOWS`` wie bisher.
- **Start-Pfad** (K-E3): leer → Vorgabe ``/api/v1/jobs/flows/{flow}``; ein unsicherer schaltet aus;
  eingerichtet = gültiger Pfad und mindestens ein Flow.
- **Auswahl** (K-E4): die aktiven Flows der b-api für ``B_API_KEY``, in der Obergrenze, dazu die
  schon freigegebenen; ohne Antwort nur diese.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest
from pydantic import ValidationError

from boerdi.domain.config_models import AREA_MODELS
from boerdi.domain.config_models.kestra_flows import KestraFlowsArea, ist_flow
from boerdi.services.auftraege import client, flow_katalog
from boerdi.settings import get_settings


@pytest.fixture
def umgebung(monkeypatch):
    """Ohne Variablen der Aufträge; die Studio-Liste über den Lader."""
    for name in ("B_API_JOBS_START_PATH", "B_API_JOBS_FLOWS"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("B_API_BASE_URL", "https://b-api.example/api/v1/llm")
    monkeypatch.setenv("B_API_KEY", "schluessel-der-anlage")
    get_settings.cache_clear()
    studio: list[str] = []
    # leer = im Studio nichts freigegeben (der Lader meldet dann ``None``)
    monkeypatch.setattr(client, "load_kestra_flows", lambda: list(studio) or None)
    flow_katalog.leeren()
    yield studio
    get_settings.cache_clear()
    flow_katalog.leeren()


# ── Bereich ─────────────────────────────────────────────────────────────────────────────────

def test_der_bereich_ist_registriert_und_prueft_die_form():
    assert AREA_MODELS["01-base/kestra-flows"] is KestraFlowsArea
    roh = {"kestra": {"flows": ["edusharing.chatbot/node-metadata-write",
                                " edusharing.chatbot/node-metadata-write ", "wlo/volltext"]}}
    assert KestraFlowsArea.model_validate(roh).kestra.flows == [
        "edusharing.chatbot/node-metadata-write", "wlo/volltext"]
    assert KestraFlowsArea.model_validate({}).kestra.flows == []
    for falsch in ("../etc", "wlo/..", "..", "a/b/c", "mit leerzeichen", "x" * 300):
        with pytest.raises(ValidationError):
            KestraFlowsArea.model_validate({"kestra": {"flows": [falsch]}})
        assert not ist_flow(falsch)                          # dieselbe Prüfung beim Start
    assert ist_flow("edusharing.chatbot/node-metadata-write") and ist_flow("v1.2/flow-a")


# ── Regel und Start-Pfad ────────────────────────────────────────────────────────────────────

def test_im_studio_freigegeben_reicht_ohne_umgebungsvariablen(umgebung):
    umgebung.append("edusharing.chatbot/node-metadata-write")
    assert client.freigeschaltet()
    assert client.erlaubt("edusharing.chatbot/node-metadata-write")
    assert not client.erlaubt("wlo/volltext")
    assert client.freigeschaltete_flows() == ["edusharing.chatbot/node-metadata-write"]


def test_die_umgebung_ist_obergrenze(umgebung, monkeypatch):
    monkeypatch.setenv("B_API_JOBS_FLOWS", "wlo/volltext, wlo/datei-zu-markdown")
    get_settings.cache_clear()
    umgebung.extend(["wlo/volltext", "edusharing.chatbot/node-metadata-write"])
    assert client.freigeschaltete_flows() == ["wlo/volltext"]
    assert not client.erlaubt("edusharing.chatbot/node-metadata-write")
    assert not client.erlaubt("wlo/datei-zu-markdown")      # nur Obergrenze, nicht freigegeben


def test_ohne_studio_liste_gilt_die_umgebung_wie_bisher(umgebung, monkeypatch):
    monkeypatch.setenv("B_API_JOBS_FLOWS", "wlo/volltext")
    get_settings.cache_clear()
    assert client.erlaubt("wlo/volltext") and client.freigeschaltete_flows() == ["wlo/volltext"]


def test_ohne_freigabe_sind_auftraege_aus(umgebung):
    assert not client.freigeschaltet() and not client.erlaubt("wlo/volltext")
    assert client.freigeschaltete_flows() == []


def test_ein_unsicherer_start_pfad_schaltet_aus(umgebung, monkeypatch):
    umgebung.append("wlo/volltext")
    monkeypatch.setenv("B_API_JOBS_START_PATH", "//boese.example/{flow}")
    get_settings.cache_clear()
    assert not client.freigeschaltet() and not client.erlaubt("wlo/volltext")


def test_der_start_geht_an_die_vorgabe(umgebung, monkeypatch):
    umgebung.append("wlo/volltext")
    gesehen: list[httpx.Request] = []

    def behandle(request: httpx.Request) -> httpx.Response:
        gesehen.append(request)
        return httpx.Response(202, json={"jobId": "job-1"})

    monkeypatch.setattr(client, "_transport", httpx.MockTransport(behandle))
    assert asyncio.run(client.starten("wlo/volltext", {})) == "job-1"
    assert gesehen[0].url.path == "/api/v1/jobs/flows/wlo/volltext"


# ── Auswahl aus der b-api ───────────────────────────────────────────────────────────────────

_ANTWORT = [
    {"namespace": "edusharing.chatbot", "flowId": "node-metadata-write", "active": True,
     "description": "Generates metadata for repository nodes.\n\nPer node id …"},
    {"namespace": "wlo", "flowId": "alt", "active": False, "description": "abgeschaltet"},
    {"namespace": "wlo", "flowId": "volltext", "active": True, "description": ""},
    {"namespace": "kaputt", "active": True},
]


def _bapi(monkeypatch, antwort=None, status=200):
    gesehen: list[httpx.Request] = []

    def behandle(request: httpx.Request) -> httpx.Response:
        gesehen.append(request)
        return httpx.Response(status, json=_ANTWORT if antwort is None else antwort)

    monkeypatch.setattr(client, "_transport", httpx.MockTransport(behandle))
    return gesehen


def test_die_auswahl_nennt_die_aktiven_flows_der_bapi(umgebung, monkeypatch):
    gesehen = _bapi(monkeypatch)
    vorschlaege = asyncio.run(flow_katalog.vorschlaege())
    assert vorschlaege == [
        ("edusharing.chatbot/node-metadata-write",
         "edusharing.chatbot/node-metadata-write — Generates metadata for repository nodes."),
        ("wlo/volltext", "wlo/volltext"),
    ]
    assert gesehen[0].url.path == "/api/v1/jobs/flows"
    assert gesehen[0].headers["authorization"] == "Bearer schluessel-der-anlage"
    asyncio.run(flow_katalog.vorschlaege())
    assert len(gesehen) == 1                                    # zwischengespeichert


def test_die_auswahl_haelt_die_obergrenze_und_zeigt_freigegebene(umgebung, monkeypatch):
    monkeypatch.setenv("B_API_JOBS_FLOWS", "wlo/volltext, wlo/eigen")
    get_settings.cache_clear()
    umgebung.append("wlo/eigen")                     # freigegeben, die b-api kennt ihn nicht
    _bapi(monkeypatch)
    assert [w for w, _ in asyncio.run(flow_katalog.vorschlaege())] == ["wlo/eigen", "wlo/volltext"]


@pytest.mark.parametrize(("antwort", "status"), [(None, 500), ({"kein": "liste"}, 200)])
def test_ohne_brauchbare_antwort_nur_die_freigegebenen(umgebung, monkeypatch, antwort, status):
    umgebung.append("wlo/volltext")
    _bapi(monkeypatch, antwort, status)
    assert asyncio.run(flow_katalog.vorschlaege()) == [("wlo/volltext", "wlo/volltext")]


def test_der_katalog_im_studio(umgebung, monkeypatch):
    from boerdi.api import config_choices

    _bapi(monkeypatch)
    katalog = asyncio.run(config_choices.get_choices())
    assert [e["value"] for e in katalog["kestra_flows"]] == [
        "edusharing.chatbot/node-metadata-write", "wlo/volltext"]


# ── Review KF ──────────────────────────────────────────────────────────────────────────────

def test_review_1_der_abruf_hat_fuenf_sekunden(umgebung, monkeypatch):
    gesehen: dict = {}

    async def anfrage(methode, pfad, **mehr):
        gesehen.update(mehr, methode=methode, pfad=pfad)
        return httpx.Response(200, json=[])

    monkeypatch.setattr(client, "_anfrage", anfrage)
    asyncio.run(flow_katalog.vorschlaege())
    assert gesehen["timeout"] == httpx.Timeout(5.0) and gesehen["pfad"] == "/api/v1/jobs/flows"


def test_review_2_ohne_schluessel_der_anlage_kein_abruf(umgebung, monkeypatch):
    monkeypatch.setenv("B_API_KEY", "")
    get_settings.cache_clear()
    umgebung.append("wlo/volltext")
    gesehen = _bapi(monkeypatch)
    assert asyncio.run(flow_katalog.vorschlaege()) == [("wlo/volltext", "wlo/volltext")]
    assert gesehen == []


def test_review_2_der_zwischenspeicher_laeuft_ab(umgebung, monkeypatch):
    uhr = {"t": 1000.0}
    monkeypatch.setattr(flow_katalog.time, "monotonic", lambda: uhr["t"])
    gesehen = _bapi(monkeypatch, status=500)
    asyncio.run(flow_katalog.vorschlaege())
    uhr["t"] += 59
    asyncio.run(flow_katalog.vorschlaege())
    assert len(gesehen) == 1                             # Fehlschlag gemerkt …
    uhr["t"] += 2
    gesehen = _bapi(monkeypatch)
    asyncio.run(flow_katalog.vorschlaege())
    assert len(gesehen) == 1                             # … nach 60 s neu, jetzt mit Antwort
    uhr["t"] += 299
    asyncio.run(flow_katalog.vorschlaege())
    assert len(gesehen) == 1
    uhr["t"] += 2
    asyncio.run(flow_katalog.vorschlaege())
    assert len(gesehen) == 2                             # nach 300 s neu


def test_review_3_ein_unlesbarer_bestand_schliesst(monkeypatch):
    from boerdi.services.config_loader import kestra_flows as lader

    monkeypatch.setattr(lader, "area", lambda _k: {"kestra": {"flows": ["wlo/volltext", "../x"]}})
    assert lader.load_kestra_flows() == ["wlo/volltext"]          # nur die gültigen
    monkeypatch.setattr(lader, "area", lambda _k: {"kestra": {"flows": "kaputt"}})
    assert lader.load_kestra_flows() == []                        # nichts — nicht die Umgebung
    monkeypatch.setattr(lader, "area", lambda _k: {})
    assert lader.load_kestra_flows() is None                      # nicht gesetzt: Umgebung


def test_review_4_speichern_ausserhalb_der_obergrenze_wird_abgewiesen(monkeypatch):
    from fastapi import HTTPException

    from boerdi.api.config_guards import _assert_area_document_safe

    monkeypatch.setenv("B_API_JOBS_FLOWS", "wlo/volltext")
    get_settings.cache_clear()
    try:
        _assert_area_document_safe("01-base/kestra-flows",
                                   {"kestra": {"flows": ["wlo/volltext"]}}, "de")
        with pytest.raises(HTTPException) as fehler:
            _assert_area_document_safe(
                "01-base/kestra-flows",
                {"kestra": {"flows": ["wlo/volltext", "edusharing.chatbot/node-metadata-write"]}},
                "de")
        assert fehler.value.status_code == 400
        assert "edusharing.chatbot/node-metadata-write" in fehler.value.detail
        assert "wlo/volltext" in fehler.value.detail                 # was erlaubt ist
        monkeypatch.delenv("B_API_JOBS_FLOWS")
        get_settings.cache_clear()
        _assert_area_document_safe(                                   # ohne Obergrenze frei
            "01-base/kestra-flows",
            {"kestra": {"flows": ["edusharing.chatbot/node-metadata-write"]}}, "de")
    finally:
        get_settings.cache_clear()


def test_review_5_aus_schaltet_auftraege_ab(umgebung, monkeypatch):
    umgebung.append("wlo/volltext")
    monkeypatch.setenv("B_API_JOBS_START_PATH", "aus")
    get_settings.cache_clear()
    assert not client.freigeschaltet() and not client.erlaubt("wlo/volltext")


def test_review_7_8_nur_aktive_und_ohne_steuerzeichen(umgebung, monkeypatch):
    _bapi(monkeypatch)
    werte = dict(asyncio.run(flow_katalog.vorschlaege()))
    assert "wlo/ohne-angabe" not in werte and "wlo/alt" not in werte
    assert "‮" not in werte["edusharing.chatbot/node-metadata-write"]


def test_review_1211_7_aus_heisst_keine_auftraege(monkeypatch):
    """Befund 7: mit gesetzter Umgebung ließ sich „keiner“ nicht ausdrücken."""
    from boerdi.services.config_loader import kestra_flows as lader

    monkeypatch.setattr(lader, "area", lambda _k: {"kestra": {"an": False, "flows": ["wlo/a"]}})
    assert lader.load_kestra_flows() == []
    monkeypatch.setenv("B_API_JOBS_FLOWS", "wlo/a")
    get_settings.cache_clear()
    monkeypatch.setattr(client, "load_kestra_flows", lader.load_kestra_flows)
    try:
        assert not client.erlaubt("wlo/a") and not client.freigeschaltet()
    finally:
        get_settings.cache_clear()


def test_review_1211_8_ein_genutzter_flow_laesst_sich_nicht_entziehen(monkeypatch):
    from fastapi import HTTPException

    from boerdi.api.config_guards import _assert_area_document_safe
    from boerdi.domain.config_models.ablauf import AblaufArea
    from boerdi.services.ablauf import ausloeser

    def ablauf(aktiv):
        return AblaufArea.model_validate({
            "id": "mit_auftrag", "titel": {"de": "A"}, "aktiv": aktiv,
            "voraussetzungen": ["anmeldung"], "ausloeser": [{"art": "knopf"}],
            "schritte": [{"id": "lauf", "typ": "auftrag", "flow": "wlo/volltext",
                          "schreibt": "text", "weiter": "ende"},
                         {"id": "ende", "typ": "ende", "text": {"de": "fertig"}}]})

    monkeypatch.delenv("B_API_JOBS_FLOWS", raising=False)
    get_settings.cache_clear()
    monkeypatch.setattr(ausloeser, "katalog", lambda: [ablauf(True)])
    # heute freigegeben (Review TW-6, Befund 5: nur Entzogenes zählt)
    monkeypatch.setattr(client, "load_kestra_flows", lambda: ["wlo/volltext"])
    with pytest.raises(HTTPException) as fehler:
        _assert_area_document_safe("01-base/kestra-flows",
                                   {"kestra": {"flows": ["wlo/anderer"]}}, "de")
    assert "mit_auftrag" in fehler.value.detail and "wlo/volltext" in fehler.value.detail
    with pytest.raises(HTTPException):
        _assert_area_document_safe("01-base/kestra-flows",
                                   {"kestra": {"an": False, "flows": ["wlo/volltext"]}}, "de")
    _assert_area_document_safe("01-base/kestra-flows",           # behält ihn: in Ordnung
                               {"kestra": {"flows": ["wlo/volltext"]}}, "de")
    monkeypatch.setattr(ausloeser, "katalog", lambda: [ablauf(False)])
    _assert_area_document_safe("01-base/kestra-flows",           # ausgeschaltet: darf weg
                               {"kestra": {"flows": []}}, "de")


def test_review_1211_9_gesamtfrist_des_abrufs(umgebung, monkeypatch):
    async def haengt(*_a, **_k):
        await asyncio.sleep(60)

    monkeypatch.setattr(client, "_anfrage", haengt)
    monkeypatch.setattr(flow_katalog, "_ZEITLIMIT", httpx.Timeout(0.05))
    umgebung.append("wlo/volltext")
    assert asyncio.run(flow_katalog.vorschlaege()) == [("wlo/volltext", "wlo/volltext")]


def test_review_tw6_5_der_waechter_nur_einzeln_und_nur_fuer_entzogenes(monkeypatch):
    from boerdi.api.config_guards import _assert_area_document_safe, pruefe_bereiche
    from boerdi.domain.config_models.ablauf import AblaufArea
    from boerdi.services.ablauf import ausloeser

    nutzer = AblaufArea.model_validate({
        "id": "nutzer", "titel": {"de": "N"}, "aktiv": True, "voraussetzungen": ["anmeldung"],
        "ausloeser": [{"art": "knopf"}],
        "schritte": [{"id": "lauf", "typ": "auftrag", "flow": "wlo/nie-frei", "schreibt": "t",
                      "weiter": "ende"}, {"id": "ende", "typ": "ende", "text": {"de": "x"}}]})
    monkeypatch.delenv("B_API_JOBS_FLOWS", raising=False)
    get_settings.cache_clear()
    monkeypatch.setattr(ausloeser, "katalog", lambda: [nutzer])
    monkeypatch.setattr(client, "load_kestra_flows", lambda: None)
    # ein nie freigegebener Flow sperrt das Speichern nicht
    _assert_area_document_safe("01-base/kestra-flows", {"kestra": {"flows": ["wlo/a"]}}, "de")
    # ein Satz Bereiche (Werksabgleich, Wiederherstellen) prüft den Wächter nicht
    monkeypatch.setattr(client, "load_kestra_flows", lambda: ["wlo/nie-frei"])
    pruefe_bereiche({"01-base/kestra-flows": {"kestra": {"flows": []}}}, "de")
