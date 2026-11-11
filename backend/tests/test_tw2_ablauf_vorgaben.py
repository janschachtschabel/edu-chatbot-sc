"""Plan 2026-11-11, TW-2: Vorgaben der Redaktion je Ablauf-Schritt gehen an die Module.

- Ein KI-Schritt trägt ``agent.vorgaben`` (je Sprache, Textfläche, höchstens 2000 Zeichen).
  Das ist redaktioneller Text, keine Eingabe der Person.
- Wartet ein Lauf an diesem Schritt, bekommt die Umgebung der Module die Vorgaben, auf beiden
  Wegen (Agent und Muster).
- ``ui_strukturentwurf`` hängt sie an den Systemteil des Generators. Die Daten der Person (Thema,
  Hinweise) bleiben im Nutzerteil.
"""

from __future__ import annotations

import asyncio

import pytest
from pydantic import ValidationError

from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.services import strukturentwurf_prompt as prompt
from boerdi.services.ablauf import ki_schritt


def _ablauf(**agent) -> AblaufArea:
    return AblaufArea.model_validate({"id": "tb", "titel": {"de": "TB"}, "schritte": [
        {"id": "entwurf", "typ": "agent", "text": {"de": "Los?"},
         "agent": {"werkzeuge": ["ui_strukturentwurf"], **agent}},
        {"id": "ende", "typ": "ende", "text": {"de": "Ende."}}]})


def test_das_feld_am_ki_schritt_und_seine_grenze():
    schritt = _ablauf(vorgaben={"de": "Lernfelder oben.", "en": "Learning fields first."})
    assert ki_schritt.vorgaben(schritt.schritte[0], "en") == "Learning fields first."
    nur_de = _ablauf(vorgaben={"de": "Lernfelder oben."}).schritte[0]
    assert ki_schritt.vorgaben(nur_de, "en") == "Lernfelder oben."
    assert ki_schritt.vorgaben(_ablauf().schritte[0], "de") == ""
    with pytest.raises(ValidationError):
        _ablauf(vorgaben={"de": "x" * 2001})


def test_die_vorgaben_stehen_im_systemteil_nicht_bei_den_daten():
    nachrichten = prompt.oben(thema="Karate", fach=None, bildungsstufe=None, anzahl_oben=8,
                              hinweise="Kata zuerst", vorgaben="Ebene 1 nach Graduierung.")
    system, nutzer = nachrichten[0]["content"], nachrichten[1]["content"]
    assert "Vorgaben der Redaktion" in system and "Ebene 1 nach Graduierung." in system
    assert "Graduierung" not in nutzer and "Kata zuerst" in nutzer
    ohne = prompt.oben(thema="Karate", fach=None, bildungsstufe=None, anzahl_oben=8,
                       hinweise="")
    assert "Vorgaben der Redaktion" not in ohne[0]["content"]


def test_auch_unterthemen_und_dokument_tragen_sie():
    for nachrichten in (
        prompt.unterthemen(entwurf="K", thema="K", fach=None, bildungsstufe=None, hinweise="",
                           pfad=["K"], knoten={"titel": "Kata"}, geschwister=[], anzahl=3,
                           letzte_ebene=True, vorgaben="V1"),
        prompt.oben_aus_dokument(thema="L", fach=None, bildungsstufe=None, anzahl_oben=8,
                                 hinweise="", gliederung="- A [a1]", anfang="", vorgaben="V1"),
        prompt.oben_aus_inhalten(thema="L", fach=None, bildungsstufe=None, anzahl_oben=8,
                                 hinweise="", gliederung="- A [a1]", anfang="", vorgaben="V1")):
        assert "V1" in nachrichten[0]["content"]


def test_der_dienst_gibt_die_vorgaben_der_umgebung_weiter(monkeypatch):
    from boerdi.services import strukturentwurf_dienst
    from boerdi.ui_module import dienst
    from boerdi.ui_module.aufruf import Umgebung
    from boerdi.ui_module.katalog import katalog

    gesehen: dict = {}

    async def erzeugen(auftrag, **_k):
        gesehen["auftrag"] = auftrag
        return strukturentwurf_dienst.Erzeugt(daten=None, grund="test")

    monkeypatch.setattr(strukturentwurf_dienst, "erzeugen", erzeugen)
    asyncio.run(dienst._strukturentwurf(katalog()["ui_strukturentwurf"], {"thema": "Karate"},
                                        Umgebung(vorgaben="Nach Graduierung.")))
    assert gesehen["auftrag"].vorgaben == "Nach Graduierung."


def test_der_muster_weg_reicht_sie_durch(monkeypatch):
    from boerdi.api.schemas_debug import ToolOutcome
    from boerdi.services import tool_loop_module
    from boerdi.ui_module.datenquelle import Ergebnis

    gesehen: dict = {}

    async def asynchron(name, args, umgebung=None):
        gesehen["umgebung"] = umgebung
        return Ergebnis(None, "t", ToolOutcome(tool=name, status="error", error="test"))

    monkeypatch.setattr(tool_loop_module, "asynchron", asynchron)
    for werkzeuge, erwartet in ((frozenset({"ui_strukturentwurf"}), "Nach Graduierung."),
                                (frozenset({"search_wlo_all"}), "")):
        state = {tool_loop_module.VORGABEN_KEY: ("Nach Graduierung.", werkzeuge)}
        asyncio.run(tool_loop_module._ergebnis(
            "ui_strukturentwurf", '{"thema": "Karate"}', ["ui_strukturentwurf"], state,
            tool_loop_module.Vorrunde(), [], [], 0, None))
        # Review TW-2, Befund 4: nur an Module, die der Schritt nennt
        assert gesehen["umgebung"].vorgaben == erwartet


# ── Review TW-2 ───────────────────────────────────────────────────────────────────────────────

def test_review_1_geleerte_vorgaben_sind_nicht_gesetzt():
    from boerdi.services.ablauf import treiber

    leer = _ablauf(vorgaben={"de": " "}, startknopf={"de": ""})
    assert leer.schritte[0].agent.vorgaben is None and leer.schritte[0].agent.startknopf is None
    assert treiber.fassung(leer) == treiber.fassung(_ablauf())


def test_review_2_jeder_aufruf_des_entwurfs_traegt_die_vorgaben():
    """Ebene 1, Ebene 2 und das Dokument — fehlt ``vorgaben=`` an einer Stelle, fällt es auf."""
    from boerdi.services import strukturentwurf_dienst as dienst
    from tests.test_strukturentwurf_dienst import Attrappe, _k
    from tests.test_strukturentwurf_dokument import _dokument

    class Mitschrift(Attrappe):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.systeme: list[str] = []

        async def __call__(self, nachrichten, *a, **k):
            self.systeme.append(nachrichten[0]["content"])
            return await super().__call__(nachrichten, *a, **k)

    for dokument in (None, _dokument()):
        llm = Mitschrift([_k("Kata", 2), _k("Kumite")], {"Kata": [_k("Heian"), _k("Tekki")]})

        async def los(llm=llm, dokument=dokument):
            ende = asyncio.get_running_loop().time() + 60
            return await dienst.erzeugen(dienst.Auftrag(thema="Karate", tiefe=2, vorgaben="VVV"),
                                         llm=llm, frist_ende=ende, dokument=dokument)

        asyncio.run(los())
        assert len(llm.systeme) >= 2 and all("VVV" in s for s in llm.systeme)

