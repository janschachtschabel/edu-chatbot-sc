"""Plan 2026-11-15 (Webseitenführung als Ablauf), WF-3: ``{wahl.<teil>}`` zeigt die Beschriftung der
gewählten Option in der Sprache des Zugs. Der Teil speichert weiter das deutsche Label
(``treiber.wahl_wert``); ``{teil.gruppe}`` zeigte im Englischen „Lehrkraft“."""

from __future__ import annotations

import asyncio

from boerdi.api.schemas import Environment
from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.services.ablauf import wahl_zug, zug
from boerdi.services.ablauf.pruefung import pruefe
from tests.test_ablauf_zug import (
    _S,
    _req,
    umgebung,  # noqa: F401 — Fixture
)


def _ablauf(text="Für {wahl.gruppe}: los.", schreibt="gruppe"):
    return AblaufArea.model_validate({
        "id": "probe", "titel": {"de": "Probe"}, "aktiv": True, "ausloeser": [{"art": "knopf"}],
        "schritte": [
            {"id": "w", "typ": "nachricht", "text": {"de": "Wer?", "en": "Who?"},
             "schreibt": schreibt, "optionen": [
                 {"id": "lehrkraft", "label": {"de": "Lehrkraft", "en": "Teachers"}, "ziel": "t"},
                 {"id": "presse", "label": {"de": "Presse"}, "ziel": "t"}]},
            {"id": "t", "typ": "nachricht", "text": {"de": text, "en": text.replace("Für", "For")}},
            {"id": "e", "typ": "ende"}]})


def _lauf(umgebung, sprache, getippt):  # noqa: F811
    umgebung.katalog["wert"] = {**umgebung.katalog["wert"],
                                "ablaeufe": [_ablauf().model_dump(exclude_none=True)]}
    env = Environment(locale=sprache)
    state: dict = {"entities": {}}
    asyncio.run(zug.starten(_S(), _req(action=zug.AKTION, action_params={"ablauf": "probe"})
                            .model_copy(update={"environment": env}), state))
    return asyncio.run(wahl_zug.getippt(
        _S(), _req().model_copy(update={"message": getippt, "environment": env}), state))


def test_die_wahl_in_der_sprache_des_zugs(umgebung):  # noqa: F811 — Fixture
    assert "For Teachers: los." in _lauf(umgebung, "en", "Lehrkraft").content
    assert "Für Lehrkraft: los." in _lauf(umgebung, "de", "Lehrkraft").content


def test_ohne_englische_beschriftung_gilt_die_deutsche(umgebung):  # noqa: F811 — Fixture
    assert "For Presse: los." in _lauf(umgebung, "en", "Presse").content


def test_die_pruefung_kennt_nur_teile_einer_wahl():
    assert pruefe(_ablauf()) == []
    befunde = pruefe(_ablauf(text="Für {wahl.unbekannt}: los."))
    assert any("wahl.unbekannt" in b for b in befunde)


def test_review_wahl_in_einem_freigabe_satz_wird_geprueft():
    a = _ablauf()
    roh = a.model_dump(exclude_none=True)
    roh["schritte"][1] = {"id": "t", "typ": "werkzeug", "werkzeug": "wlo_update_content",
                          "argumente": {"nodeId": "x"}, "freigabe": {"de": "Für {wahl.weg}?"},
                          "bei_fehler": "e"}
    befunde = pruefe(AblaufArea.model_validate(roh))
    assert any("wahl.weg" in b for b in befunde)


def test_review_getippter_freitext_bleibt_entschaerft_und_kein_fester_text():
    from boerdi.services.ablauf import treiber

    a = _ablauf()

    async def teile(_name):
        return "{teil.geheim}"

    text, fremd = asyncio.run(treiber.wahl_einsetzen("Für {wahl.gruppe}.", a, "de", teile))
    assert fremd and "{teil.geheim}" not in text

    async def nichts(_name):
        return None

    text, fremd = asyncio.run(treiber.wahl_einsetzen("Für {wahl.gruppe}.", a, "de", nichts))
    assert text == "Für —." and not fremd
