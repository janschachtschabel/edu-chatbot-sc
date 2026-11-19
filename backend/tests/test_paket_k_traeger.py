"""Paket K2/K3 (Plan 2026-11-17): wer einen Auftrag trägt — der MCP oder der Direktweg der b-api.

- Review A4/A7 (19.11.): der MCP-Weg nur für Schritte mit ``repo_schreibt`` — der MCP führt
  ``wlo_start_flow``, ``wlo_flow_status`` und ``wlo_cancel_flow`` und die Person ist bestätigt
  angemeldet → **MCP** (auch bei Delegation).
- Flows ohne ``repo_schreibt`` gehen den Direktweg, nur mit ``darf_jobs()`` (wie vor Paket K).
- Sonst kein Träger, mit Grund.
"""

from __future__ import annotations

import asyncio

import pytest

from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.i18n import bot_text
from boerdi.services import llm_auth
from boerdi.services.ablauf import auftrag_zug, treiber, zug_basis
from boerdi.services.auftraege import client, mcp_starter
from boerdi.services.mcp import faehigkeiten
from boerdi.ui_module import dienst_upload

TOKEN = "bdt_" + "d" * 40


@pytest.fixture
def lage(monkeypatch):
    """Ein Zustand je Achse — die Tests drehen daran."""
    z = {"mcp": True, "anmeldung": True, "darf_jobs": True, "eingerichtet": True}
    monkeypatch.setattr(mcp_starter, "verfuegbar", lambda: z["mcp"])
    monkeypatch.setattr(auftrag_zug, "has_personal_auth", lambda: z["anmeldung"])
    monkeypatch.setattr(auftrag_zug, "darf_jobs", lambda: z["darf_jobs"])
    monkeypatch.setattr(client, "freigeschaltet", lambda: z["eingerichtet"])
    return z


@pytest.mark.parametrize(("mcp", "anmeldung", "darf", "eingerichtet", "schreibt", "erwartet"), [
    (True, True, True, True, True, ("mcp", "")),
    (True, True, False, False, True, ("mcp", "")),    # Delegation / ohne b-api-Einrichtung
    (False, True, True, True, True, (None, "ohne_mcp")),
    (False, True, True, True, False, ("direkt", "")),
    (True, True, True, True, False, ("direkt", "")),  # A4: lesend nie über den MCP
    (False, True, False, True, False, (None, "ohne_schluessel")),
    (False, True, True, False, False, (None, "nicht_eingerichtet")),
    (True, False, True, True, True, (None, "ohne_anmeldung")),
    (False, False, True, True, False, (None, "ohne_anmeldung")),
])
def test_matrix_des_traegers(lage, mcp, anmeldung, darf, eingerichtet, schreibt, erwartet):
    lage.update(mcp=mcp, anmeldung=anmeldung, darf_jobs=darf, eingerichtet=eingerichtet)
    assert auftrag_zug.traeger(repo_schreibt=schreibt) == erwartet


def test_bei_delegation_ohne_direktweg_nennt_der_grund_die_delegation(lage):
    lage.update(mcp=False, darf_jobs=False)
    llm_auth.setze_llm_schluessel(f"Bearer {TOKEN}")
    try:
        assert auftrag_zug.traeger() == (None, "delegation")
        lage["mcp"] = True
        assert auftrag_zug.traeger() == (None, "delegation")     # lesend: kein MCP-Weg
        assert auftrag_zug.traeger(repo_schreibt=True) == ("mcp", "")
    finally:
        llm_auth.setze_llm_schluessel("")


def test_der_starter_traegt_seinen_weg(lage, monkeypatch):
    gerufen: list = []

    async def ueber_mcp(flow, eingaben):
        gerufen.append(("mcp", flow))
        return mcp_starter.PRAEFIX + "job-1"

    async def direkt(flow, eingaben):
        gerufen.append(("direkt", flow))
        return "job-2"

    _mcp_startet(monkeypatch, ueber_mcp)
    monkeypatch.setattr(client, "starten", direkt)
    starte = auftrag_zug.starter().fuer(True)
    assert starte.traeger == "mcp"
    assert asyncio.run(starte("f/x", {})) == "mcp:job-1"
    starte = auftrag_zug.starter().fuer(False)
    assert starte.traeger == "direkt"
    assert asyncio.run(starte("f/x", {})) == "job-2"
    assert gerufen == [("mcp", "f/x"), ("direkt", "f/x")]
    lage["darf_jobs"] = False
    assert auftrag_zug.starter().fuer(False).traeger is None
    lage["anmeldung"] = False
    assert auftrag_zug.starter() is None


# ── Treiber: der Direktweg startet keinen schreibenden Flow ─────────────────────────────────

def _ablauf(repo_schreibt: bool) -> AblaufArea:
    return AblaufArea.model_validate({
        "id": "meta", "titel": {"de": "Meta"}, "aktiv": True, "ausloeser": [{"art": "knopf"}],
        "voraussetzungen": ["anmeldung"], "schritte": [
            {"id": "frage", "typ": "nachricht", "text": {"de": "Metadaten erzeugen?"},
             "optionen": [{"id": "ja", "label": {"de": "Ja"}, "ziel": "lauf"},
                          {"id": "nein", "label": {"de": "Nein"}, "ziel": "ohne"}]},
            {"id": "lauf", "typ": "auftrag", "flow": "f/meta", "argumente": {"x": "1"},
             "schreibt": "ergebnis", "bei_fehler": "ohne", "text": {"de": "Ich starte."},
             **({"repo_schreibt": True} if repo_schreibt else {})},
            {"id": "fertig", "typ": "ende", "text": {"de": "Fertig."}},
            {"id": "ohne", "typ": "ende", "text": {"de": "Ohne Metadaten."}}]})


async def _nichts(_name):
    return None


def _am_auftrag(ablauf: AblaufArea, starter, *, freigeben: bool = True) -> treiber.Ausgabe:
    """„Ja“ an der Rückfrage. Paket N4: legt der Schritt eine Freigabe vor, gibt ``freigeben`` sie
    gleich frei wie ``auftrag_freigabe_zug.freigeben`` (ohne Sitzung) — die Tests vor N4 starteten
    im selben Zug."""
    lauf = {"ablauf": ablauf.id, "fassung": treiber.fassung(ablauf), "status": treiber.WARTET_WAHL,
            "schritt": "frage"}
    umgebung = treiber.Umgebung(teile=_nichts, auftrag_starten=starter)
    aus = asyncio.run(treiber.weiter_wahl(ablauf, lauf, "ja", None, umgebung))
    if not freigeben or aus.auftrag_freigabe is None:
        return aus
    # Review N4 (6): die echte Freigabe (``auftrag_freigabe_zug.starten``), ohne Sitzung
    from boerdi.services.ablauf import auftrag_freigabe, auftrag_freigabe_zug

    entities: dict = {}
    auftrag_freigabe.merken(entities, aus.auftrag_freigabe, ablauf.id, "de")
    return asyncio.run(auftrag_freigabe_zug.starten(ablauf, aus.lauf, umgebung,
                                                    entities[auftrag_freigabe.KEY]))


def _mcp_startet(monkeypatch, starten) -> None:
    """Paket N4: über den MCP geht ein Start über Vorschau (Box) und Bestätigung — ``starten``
    steht hier für beides zusammen (wie vorher ``mcp_starter.starten``): die Vorschau gelingt, die
    Bestätigung ruft ``starten``."""
    from boerdi.services.auftraege import mcp_vorschau

    async def vorschau(_flow, _eingaben):
        return mcp_vorschau.Vorschau(token="ct", laeuft_ab=9e9)

    async def bestaetigen(flow, eingaben, _token):
        return await starten(flow, eingaben)

    monkeypatch.setattr(mcp_vorschau, "vorschau", vorschau)
    monkeypatch.setattr(mcp_vorschau, "bestaetigen", bestaetigen)
    monkeypatch.setattr(mcp_starter, "starten", starten)


@pytest.mark.parametrize(("mcp", "repo_schreibt", "weg"), [
    (False, True, None), (False, False, "direkt"), (True, True, "mcp"), (True, False, "direkt")])
def test_repo_schreibt_nur_ueber_den_mcp(lage, monkeypatch, mcp, repo_schreibt, weg):
    lage["mcp"] = mcp
    gerufen: list = []

    async def ueber_mcp(flow, eingaben):
        gerufen.append("mcp")
        return mcp_starter.PRAEFIX + "job-1"

    async def direkt(flow, eingaben):
        gerufen.append("direkt")
        return "job-2"

    _mcp_startet(monkeypatch, ueber_mcp)
    monkeypatch.setattr(client, "starten", direkt)
    aus = _am_auftrag(_ablauf(repo_schreibt), auftrag_zug.starter())
    assert gerufen == ([weg] if weg else [])
    if weg:
        assert aus.lauf["status"] == treiber.WARTET_AUFTRAG
    else:
        assert aus.texte[0] == bot_text("de", "action.ablauf.auftragNurUeberWlo")
        assert aus.texte[-1] == "Ohne Metadaten."


def test_ein_offener_start_haelt_mit_hinweis(lage, monkeypatch):
    """``outcomeOpen: true``: nie neu starten — der Schritt wartet, „Stand prüfen“ sieht nach."""
    async def offen(flow, eingaben):
        raise client.AuftragFehler("offen")

    _mcp_startet(monkeypatch, offen)
    aus = _am_auftrag(_ablauf(True), auftrag_zug.starter())
    assert aus.lauf["status"] == treiber.WARTET_AUFTRAG
    assert mcp_starter.ist_offen(aus.auftrag["job_id"])
    assert aus.texte[-1] == bot_text("de", "action.ablauf.auftragOffen")


def test_ein_abgelehnter_start_ueber_den_mcp_nimmt_den_ersatzweg(lage, monkeypatch):
    async def nein(flow, eingaben):
        raise client.AuftragFehler("abgewiesen", code="EDU_USER_REQUIRED")

    _mcp_startet(monkeypatch, nein)
    aus = _am_auftrag(_ablauf(True), auftrag_zug.starter())
    assert aus.texte == [bot_text("de", "action.ablauf.auftragAbgelehntPerson"),
                         "Ohne Metadaten."]


# ── K3: „gründlich über WLO“ und das Upload-Feld ────────────────────────────────────────────

@pytest.mark.parametrize(("mcp", "darf", "erschliessen"), [
    (True, False, True),      # MCP-Träger, auch ohne b-api-Schlüssel (Delegation)
    (False, True, False),     # nur der Direktweg: der Metadaten-Flow schreibt ins Repository
    (False, False, False),
])
def test_wlo_erschliessen_folgt_dem_traeger(lage, monkeypatch, mcp, darf, erschliessen):
    lage.update(mcp=mcp, darf_jobs=darf)
    monkeypatch.setattr(zug_basis, "_wlo_ablage", lambda: True)
    monkeypatch.setattr(client, "freigegebene_flows",
                        lambda: frozenset({zug_basis.METADATEN_FLOW}))
    monkeypatch.setattr(client, "erlaubt", lambda flow: True)
    assert zug_basis.wlo_erschliessen() is erschliessen


def test_wlo_erschliessen_braucht_den_freigegebenen_flow(lage, monkeypatch):
    monkeypatch.setattr(zug_basis, "_wlo_ablage", lambda: True)
    monkeypatch.setattr(client, "freigegebene_flows", lambda: frozenset({"anderer/flow"}))
    assert zug_basis.wlo_erschliessen() is False


@pytest.fixture
def upload(monkeypatch):
    from boerdi.domain.config_models.upload import UploadSettings

    faehigkeiten.vergessen()
    faehigkeiten.uebernehmen([{"name": dienst_upload.ABLAGE_WERKZEUG}])
    monkeypatch.setattr(dienst_upload, "load_upload_config",
                        lambda: UploadSettings(ablage_in_wlo=True, dokument_im_chat=True))
    monkeypatch.setattr(dienst_upload, "has_personal_auth", lambda: True)
    yield
    faehigkeiten.vergessen()


@pytest.mark.parametrize("erschliessen", [True, False])
def test_upload_schalter_und_satz_folgen_dem_traeger(upload, monkeypatch, erschliessen):
    """Die Ablage selbst hängt nicht am Träger (Ablage geht, Metadaten vielleicht nicht) — der
    Satz an die KI verspricht Metadaten nur, wenn der Träger sie erzeugen kann."""
    monkeypatch.setattr(zug_basis, "wlo_erschliessen", lambda: erschliessen)
    schalter = dienst_upload.schalter()
    assert schalter["ablage_in_wlo"] is True
    satz = dienst_upload._ablage_satz(schalter)
    assert ("Metadaten" in satz and "nicht" not in satz) is erschliessen
    if not erschliessen:
        assert "Metadaten erzeugen geht hier gerade nicht" in satz
