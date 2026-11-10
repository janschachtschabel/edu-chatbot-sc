"""Plan 2026-11-10, TB-T1: die Antworten der Kernfragen und die Metadaten erreichen den Themenbaum.

- **Wahl als Teil:** ``schreibt`` an einem ``nachricht``-Schritt mit Optionen schreibt das Label der
  gewählten Option als Text-Teil — immer das deutsche (sprachfest, Review TB-T1, Befund 2). In
  der Arbeitsstands-Zeile der KI steht „Wahl: <Label>“ — Text der Redaktion, nie Eingabe der
  Person. Freitext bleibt, wie er ist (nur der Name in der Kennzeile): ihn in den Hinweis an die
  KI einzusetzen, wäre ein Einfallstor.
- **``aus_inhalten``:** ``ui_strukturentwurf`` baut den Baum aus dem Teil ``metadaten`` — der Dienst
  liest ihn auf dem Server und gibt ihn dem Generator wie ein Dokument (je Material ein Abschnitt).
"""

from __future__ import annotations

import asyncio

from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.services.ablauf import metadaten, treiber
from boerdi.services.ablauf.pruefung import pruefe


def _ablauf(**frage) -> AblaufArea:
    return AblaufArea.model_validate({"id": "kern", "titel": {"de": "Kern"}, "schritte": [
        {"id": "wofuer", "typ": "nachricht", "text": {"de": "Wofür?", "en": "What for?"},
         "optionen": [{"id": "unterricht", "label": {"de": "Unterricht planen",
                                                      "en": "Plan lessons"}, "ziel": "ende"},
                      {"id": "pool", "label": {"de": "Materialpool"}, "ziel": "ende"}],
         **frage},
        {"id": "ende", "typ": "ende", "text": {"de": "Gut: {teil.zweck}."}}]})


def _umgebung(sprache="de"):
    async def lader(name):
        return None

    return treiber.Umgebung(teile=lader, sprache=sprache)


def test_eine_wahl_schreibt_ihr_label_als_teil():
    ablauf = _ablauf(schreibt="zweck")
    assert pruefe(ablauf) == []
    lauf = asyncio.run(treiber.starten(ablauf, _umgebung())).lauf
    aus = asyncio.run(treiber.weiter_wahl(ablauf, dict(lauf), "unterricht", None, _umgebung()))
    assert ("zweck", "text", "Unterricht planen", "Wahl: Unterricht planen") in aus.neue_teile
    assert aus.texte == ["Gut: Unterricht planen."]


def test_der_wert_ist_in_jeder_sprache_das_deutsche_label():
    """Review TB-T1, Befund 2: sonst verzweigte ``wenn_wert`` je Sprache anders."""
    ablauf = _ablauf(schreibt="zweck")
    lauf = asyncio.run(treiber.starten(ablauf, _umgebung("en"))).lauf
    en = asyncio.run(treiber.weiter_wahl(ablauf, dict(lauf), "unterricht", None, _umgebung("en")))
    assert ("zweck", "text", "Unterricht planen", "Wahl: Unterricht planen") in en.neue_teile


def test_ohne_schreibt_bleibt_es_wie_bisher():
    ablauf = _ablauf()
    lauf = asyncio.run(treiber.starten(ablauf, _umgebung())).lauf
    aus = asyncio.run(treiber.weiter_wahl(ablauf, dict(lauf), "pool", None, _umgebung()))
    assert aus.neue_teile == []


def test_schreibt_an_einer_nachricht_ohne_optionen_ist_ein_befund():
    ablauf = AblaufArea.model_validate({"id": "x", "titel": {"de": "X"}, "schritte": [
        {"id": "a", "typ": "nachricht", "text": {"de": "Hallo"}, "schreibt": "zweck"},
        {"id": "ende", "typ": "ende", "text": {"de": "Ende."}}]})
    assert any("Schnellantworten" in b and "Schritt a" in b for b in pruefe(ablauf))


def _moderation(monkeypatch, urteil):
    from boerdi.ui_module import dienst

    gesehen: list[str] = []

    async def moderieren(text):
        gesehen.append(text)
        return urteil

    monkeypatch.setattr(dienst, "_moderation", lambda: moderieren)
    return gesehen


_INHALTE = {"format": "wlo.metadaten@1", "inhalte": [
    {"node_id": "a", "rolle": "inhalt", "titel": "Linsen", "beschreibung": "Sammellinsen im Alltag",
     "schlagworte": ["Linse", "Brennweite"], "faecher": ["Physik"], "stufen": ["Sek I"],
     "arten": ["Arbeitsblatt"]},
    {"node_id": "b", "rolle": "inhalt", "titel": "Spiegel", "beschreibung": "",
     "schlagworte": [], "faecher": [], "stufen": [], "arten": []}], "fehlend": []}


def test_die_metadaten_werden_ein_dokument_fuer_den_generator():
    dok = metadaten.als_dokument(_INHALTE)
    assert dok is not None and dok.format == metadaten.DOKUMENT_FORMAT
    assert [a.titel for a in dok.abschnitte] == ["Linsen", "Spiegel"]
    erster = dok.markdown[dok.abschnitte[0].start:dok.abschnitte[0].ende]
    assert "Linsen" in erster and "Brennweite" in erster and "Physik" in erster
    assert metadaten.als_dokument({"inhalte": []}) is None
    assert metadaten.als_dokument(None) is None


def test_der_dienst_nimmt_aus_inhalten_den_teil_metadaten(monkeypatch):
    from boerdi.services import strukturentwurf_dienst
    from boerdi.ui_module import dienst
    from boerdi.ui_module.katalog import katalog

    gesehen: dict = {}

    async def erzeugen(auftrag, *, llm, frist_ende, vorlage=None, dokument=None, moderieren=None):
        gesehen["dokument"] = dokument
        return strukturentwurf_dienst.Erzeugt(daten=None, grund="test")

    monkeypatch.setattr(strukturentwurf_dienst, "erzeugen", erzeugen)
    _moderation(monkeypatch, {"flagged": False})

    async def teile(name):
        return _INHALTE if name == "metadaten" else None

    from boerdi.ui_module.aufruf import Umgebung

    umgebung = Umgebung(teile=teile)
    manifest = katalog()["ui_strukturentwurf"]
    asyncio.run(dienst._strukturentwurf(manifest, {"thema": "Optik", "aus_inhalten": True},
                                        umgebung))
    assert gesehen["dokument"] is not None
    assert [a.titel for a in gesehen["dokument"].abschnitte] == ["Linsen", "Spiegel"]


def test_aus_inhalten_ohne_teil_ist_ein_fehler_fuer_die_ki():
    from boerdi.ui_module import dienst
    from boerdi.ui_module.aufruf import Umgebung
    from boerdi.ui_module.katalog import katalog

    async def teile(name):
        return None

    erg = asyncio.run(dienst._strukturentwurf(
        katalog()["ui_strukturentwurf"], {"thema": "Optik", "aus_inhalten": True},
        Umgebung(teile=teile)))
    assert erg.block is None and erg.outcome.error == "keine_inhalte"
    assert "metadaten" in erg.text


def test_aus_inhalten_schliesst_vorlage_und_dokument_aus():
    from boerdi.ui_module import dienst
    from boerdi.ui_module.aufruf import Umgebung
    from boerdi.ui_module.katalog import katalog

    async def teile(name):
        return _INHALTE

    for mehr in ({"aus_dokument": True}, {"vorlage": True}):
        erg = asyncio.run(dienst._strukturentwurf(
            katalog()["ui_strukturentwurf"], {"thema": "Optik", "aus_inhalten": True, **mehr},
            Umgebung(teile=teile, vorlage={"titel": "x", "knoten": [{"titel": "a"}]})))
        assert erg.block is None and erg.outcome.error == "argumente"


def test_die_aufforderung_gruppiert_materialien():
    from types import SimpleNamespace

    from boerdi.services import strukturentwurf_dokument

    a = SimpleNamespace(thema="Optik", anzahl_oben=5, hinweise="")
    nachrichten = strukturentwurf_dokument.aufforderung_oben(
        a, {}, metadaten.als_dokument(_INHALTE))
    text = " ".join(str(n.get("content")) for n in nachrichten)
    assert "AUS DEN MATERIALIEN" in text and "Linsen [a1]" in text


# ── Review TB-T1 ──────────────────────────────────────────────────────────────────────────────

def _schleife(**frage) -> AblaufArea:
    """Eine Frage mit Wahl und Freitext, danach zurück zur Frage (ein zweiter Durchgang)."""
    return AblaufArea.model_validate({"id": "kreis", "titel": {"de": "Kreis"}, "schritte": [
        {"id": "wofuer", "typ": "nachricht", "text": {"de": "Wofür?"}, "schreibt": "zweck",
         "optionen": [{"id": "unterricht", "label": {"de": "Unterricht planen"}, "ziel": "ende"}],
         **frage},
        {"id": "ende", "typ": "nachricht", "text": {"de": "{teil.zweck}|{teil.frei}"},
         "optionen": [{"id": "nochmal", "label": {"de": "Nochmal"}, "ziel": "wofuer"}]}]})


def _lauf_nach_wahl(ablauf, teile: dict):
    async def lader(name):
        return teile.get(name)

    umgebung = treiber.Umgebung(teile=lader)
    lauf = asyncio.run(treiber.starten(ablauf, umgebung)).lauf
    return lauf, umgebung


def test_review_9a_gleicher_name_die_wahl_leert_den_teil_nicht():
    ablauf = _schleife(freitext={"ziel": "ende", "schreibt": "zweck"})
    lauf, umgebung = _lauf_nach_wahl(ablauf, {"zweck": "alter Text"})
    aus = asyncio.run(treiber.weiter_wahl(ablauf, dict(lauf), "unterricht", None, umgebung))
    assert [t[:3] for t in aus.neue_teile] == [("zweck", "text", "Unterricht planen")]


def test_review_3_freitext_leert_eine_fruehere_wahl_anderen_namens():
    ablauf = _schleife(freitext={"ziel": "ende", "schreibt": "frei"})
    lauf, umgebung = _lauf_nach_wahl(ablauf, {"zweck": "Unterricht planen"})
    aus = asyncio.run(treiber.weiter_wahl(ablauf, dict(lauf), None, "Materialpool", umgebung))
    assert ("zweck", "text", "", "—") in aus.neue_teile
    assert ("frei", "text", "Materialpool", "Text: frei") in aus.neue_teile
    assert aus.texte == ["—|Materialpool"]   # leerer Teil zeigt „—“


def test_review_3_ohne_fruehere_wahl_kein_leerer_teil():
    ablauf = _schleife(freitext={"ziel": "ende", "schreibt": "frei"})
    lauf, umgebung = _lauf_nach_wahl(ablauf, {})
    aus = asyncio.run(treiber.weiter_wahl(ablauf, dict(lauf), None, "Materialpool", umgebung))
    assert [t[0] for t in aus.neue_teile] == ["frei"]


def test_review_9d_datensicht_nimmt_den_wert_der_wahl():
    from boerdi.domain.config_models.ablauf import AblaufTest
    from boerdi.services.ablauf import datensicht

    ablauf = _ablauf(schreibt="zweck")
    test = AblaufTest.model_validate({"name": "t", "eingaben": [
        {"bei": "wofuer", "option": "unterricht"}]})
    werte = datensicht._werte(ablauf, test)
    assert werte["zweck"] == "Unterricht planen"


def test_review_4_ein_teil_anderer_form_ist_keine_materialliste():
    assert metadaten.als_dokument({"inhalte": _INHALTE["inhalte"]}) is None   # ohne format
    zerlegt = {**_INHALTE, "inhalte": [{"titel": "Linsen", "faecher": "Physik"}]}
    dok = metadaten.als_dokument(zerlegt)
    assert "P, h" not in dok.markdown and "Fächer" not in dok.markdown


def test_review_1_ebene_eins_wird_moderiert(monkeypatch):
    from boerdi.services import strukturentwurf_dienst
    from boerdi.ui_module import dienst
    from boerdi.ui_module.aufruf import Umgebung
    from boerdi.ui_module.katalog import katalog

    async def nie(*a, **k):
        raise AssertionError("ohne Prüfung kein Entwurf")

    monkeypatch.setattr(strukturentwurf_dienst, "erzeugen", nie)
    gesehen = _moderation(monkeypatch, {"flagged": True})

    async def teile(name):
        return _INHALTE

    erg = asyncio.run(dienst._strukturentwurf(
        katalog()["ui_strukturentwurf"], {"thema": "Optik", "aus_inhalten": True},
        Umgebung(teile=teile)))
    assert erg.block is None and erg.outcome.error == "abgewiesen"
    assert "Linsen [a1]" in gesehen[0] and "Sammellinsen" in gesehen[0]


def test_review_1_ohne_urteil_entscheidet_der_ausfallmodus(monkeypatch):
    from boerdi.services import strukturentwurf_dienst
    from boerdi.settings import get_settings
    from boerdi.ui_module import dienst
    from boerdi.ui_module.aufruf import Umgebung
    from boerdi.ui_module.katalog import katalog

    _moderation(monkeypatch, {})
    monkeypatch.setattr(get_settings(), "moderation_failure_mode", "closed")

    async def teile(name):
        return _INHALTE

    async def nie(*a, **k):
        raise AssertionError("geschlossen: kein Entwurf")

    monkeypatch.setattr(strukturentwurf_dienst, "erzeugen", nie)
    erg = asyncio.run(dienst._strukturentwurf(
        katalog()["ui_strukturentwurf"], {"thema": "Optik", "aus_inhalten": True},
        Umgebung(teile=teile)))
    assert erg.outcome.error == "pruefung_fehlt"


def test_review_9g_der_ausschluss_sagt_was_zu_tun_ist():
    from boerdi.ui_module import dienst
    from boerdi.ui_module.aufruf import Umgebung
    from boerdi.ui_module.katalog import katalog

    async def teile(name):
        raise AssertionError("der Ausschluss kommt vor jedem Lesen")

    erg = asyncio.run(dienst._strukturentwurf(
        katalog()["ui_strukturentwurf"],
        {"thema": "Optik", "aus_inhalten": True, "vorlage": True}, Umgebung(teile=teile)))
    assert erg.outcome.error == "argumente" and "aus_inhalten" in erg.text


def test_review_9e_der_auszug_eines_materials():
    from boerdi.domain.dokument_gliederung import abschnitt_text

    dok = metadaten.als_dokument(_INHALTE)
    text = abschnitt_text(dok.markdown, dok.abschnitte, ["a1"], 2000)
    assert "Sammellinsen" in text and "Spiegel" not in text


def test_review_7_hinweis_bei_anderem_teilnamen():
    from boerdi.services.ablauf.pruefung import warnungen

    ablauf = AblaufArea.model_validate({
        "id": "meta", "titel": {"de": "M"}, "voraussetzungen": ["anmeldung"], "schritte": [
            {"id": "lesen", "typ": "werkzeug", "werkzeug": "metadaten_lesen",
             "argumente": {"ablage": {"$teil": "ablage"}}, "schreibt": "inhalte",
             "bei_fehler": "ende"},
            {"id": "ende", "typ": "ende", "text": {"de": "Ende."}}]})
    assert any("metadaten" in w and "inhalte" in w for w in warnungen(ablauf))

