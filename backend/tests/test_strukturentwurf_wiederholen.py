"""Plan 2026-11-19, A1 (E3, S1): vorübergehende Fehler des Anbieters beim Strukturentwurf.

Ein 503 (``ServiceUnavailableError``) und seine Geschwister werden **einmal** nach einer kurzen
Pause wiederholt, wenn die Frist es erlaubt. Bleibt es dabei, sagt der Dienst ``voruebergehend`` —
nicht den Sammelgrund ``fehler``, dessen Text die KI in die Sackgasse „antworte ohne Entwurf“
schickte. Kein echtes LLM: die Naht ``llm`` ist eine Attrappe (``test_strukturentwurf_dienst``).
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
import litellm
import pytest

from boerdi.services import strukturentwurf_dienst as dienst
from boerdi.services import strukturentwurf_lauf as lauf_teil
from boerdi.services import strukturentwurf_wiederholen as wiederholen
from boerdi.ui_module import aufruf
from boerdi.ui_module.dienst_fehler import FEHLER
from boerdi.ui_module.namen import STRUKTURENTWURF
from tests.test_strukturentwurf_dienst import Attrappe, _auftrag, _erzeugen, _k, _titel


def _503() -> Exception:
    return litellm.exceptions.ServiceUnavailableError("503", "openai", "gpt-6-luna")


class Mehrmals(Attrappe):
    """Wirft beim Ziel (``oben`` oder Titel) die ersten ``mal`` Aufrufe den Fehler."""

    def __init__(self, *args: Any, ziel: str, fehler: Exception, mal: int, **mehr: Any) -> None:
        super().__init__(*args, **mehr)
        self.ziel, self.wurf, self.rest_mal = ziel, fehler, mal

    async def __call__(self, nachrichten, *rest):
        auftrag = json.loads(nachrichten[-1]["content"].split("\n", 1)[1])
        ziel = auftrag["knoten"]["titel"] if "knoten" in auftrag else "oben"
        if ziel == self.ziel and self.rest_mal > 0:
            self.rest_mal -= 1
            self.aufrufe.append({"auftrag": auftrag, "geworfen": True})
            raise self.wurf
        return await super().__call__(nachrichten, *rest)


@pytest.fixture(autouse=True)
def _ohne_pause(monkeypatch):
    monkeypatch.setattr(wiederholen, "PAUSE_S", 0.0)


def _mit_netzfehler(fehler: Exception) -> Exception:
    fehler.__cause__ = httpx.ConnectError("weg")
    return fehler


@pytest.mark.parametrize("fehler", [
    _503(),
    litellm.exceptions.InternalServerError("500", "openai", "m"),
    litellm.exceptions.BadGatewayError("502", "openai", "m"),
    # Review A, MINOR 4: ``litellm.Timeout`` erbt von ``openai.APITimeoutError``
    litellm.exceptions.Timeout("zu langsam", "m", "openai"),
    _mit_netzfehler(litellm.exceptions.APIConnectionError("weg", "openai", "m")),
])
def test_voruebergehend_erkennt_die_klassen_des_anbieters(fehler):
    assert wiederholen.voruebergehend(fehler)


@pytest.mark.parametrize("fehler", [
    ValueError("kaputt"), litellm.exceptions.BadRequestError("400", "m", "openai"),
    TimeoutError(),
    # Review A, MINOR 4: LiteLLM macht JEDE Ausnahme ohne Status zum ``APIConnectionError`` — ohne
    # Netzfehler in der Kette ist es ein Programmfehler, kein vorübergehender
    litellm.exceptions.APIConnectionError("TypeError im Adapter", "openai", "m")])
def test_anderes_ist_nicht_voruebergehend(fehler):
    assert not wiederholen.voruebergehend(fehler)


async def test_ein_503_bei_ebene_eins_wird_wiederholt_und_der_entwurf_entsteht():
    llm = Mehrmals([_k("Licht", 2)], {"Licht": [_k("Quellen"), _k("Schatten")]},
                   ziel="oben", fehler=_503(), mal=1)
    erg = await _erzeugen(_auftrag(), llm)
    assert erg.grund is None
    assert _titel(erg.daten["knoten"]) == ["Licht", "Quellen", "Schatten"]
    assert len(llm.aufrufe) == 3                  # oben zweimal, dann Licht


async def test_zwei_503_bei_ebene_eins_ergeben_voruebergehend():
    llm = Mehrmals([_k("Licht", 2)], ziel="oben", fehler=_503(), mal=2)
    erg = await _erzeugen(_auftrag(), llm)
    assert (erg.daten, erg.grund) == (None, "voruebergehend")
    assert len(llm.aufrufe) == 2                  # genau einmal wiederholt


async def test_ohne_zeit_fuer_die_wiederholung_gleich_voruebergehend(monkeypatch):
    monkeypatch.setattr(wiederholen, "PAUSE_S", 30.0)
    llm = Mehrmals([_k("Licht")], ziel="oben", fehler=_503(), mal=1)
    erg = await _erzeugen(_auftrag(), llm, frist=dienst.MINDEST_REST_S + 10)
    assert (erg.daten, erg.grund) == (None, "voruebergehend")
    assert len(llm.aufrufe) == 1


async def test_ein_anderer_fehler_wird_nicht_wiederholt():
    llm = Mehrmals([_k("Licht")], ziel="oben", fehler=ValueError("kaputt"), mal=1)
    erg = await _erzeugen(_auftrag(), llm)
    assert (erg.daten, erg.grund) == (None, "fehler")
    assert len(llm.aufrufe) == 1


async def test_ein_503_bei_unterpunkten_wird_wiederholt():
    llm = Mehrmals([_k("Licht", 2)], {"Licht": [_k("Quellen"), _k("Schatten")]},
                   ziel="Licht", fehler=_503(), mal=1)
    erg = await _erzeugen(_auftrag(), llm)
    licht = erg.daten["knoten"][0]
    assert [k["titel"] for k in licht["kinder"]] == ["Quellen", "Schatten"]
    assert "ausstehend" not in licht


async def test_zwei_503_bei_unterpunkten_lassen_den_punkt_ausstehend():
    llm = Mehrmals([_k("Licht", 2)], {"Licht": [_k("Quellen"), _k("Schatten")]},
                   ziel="Licht", fehler=_503(), mal=2)
    erg = await _erzeugen(_auftrag(), llm)
    assert erg.grund is None and erg.daten["knoten"][0]["ausstehend"] is True


async def test_der_text_an_die_ki_sagt_gleich_nochmal_statt_ohne_entwurf(monkeypatch):
    async def attrappe(auftrag, **_):
        return dienst.Erzeugt(None, "voruebergehend")

    monkeypatch.setattr(dienst, "erzeugen", attrappe)
    ende = asyncio.get_running_loop().time() + 60
    erg = await aufruf.asynchron(STRUKTURENTWURF, {"thema": "Optik"},
                                 aufruf.Umgebung(frist_ende=ende))
    assert erg.block is None and erg.outcome.error == "voruebergehend"
    assert erg.text == FEHLER["voruebergehend"].format(name=STRUKTURENTWURF)
    assert "nochmal" in erg.text and "ohne Entwurf" not in erg.text
    assert "nicht noch einmal auf" in erg.text


async def test_die_pause_der_wiederholung_haelt_keinen_platz(monkeypatch):
    """Review A, NIT 13: während ein Punkt auf seine Wiederholung wartet, darf ein anderer rufen —
    die Pause liegt außerhalb der Sperre des Entwurfs."""
    monkeypatch.setattr(wiederholen, "PAUSE_S", 0.2)
    monkeypatch.setattr(lauf_teil, "parallel", lambda: 1)
    llm = Mehrmals([_k("Licht", 2), _k("Spiegel", 2)],
                   {"Licht": [_k("Quellen"), _k("Schatten")], "Spiegel": [_k("Eben"), _k("Hohl")]},
                   ziel="Licht", fehler=_503(), mal=1)
    erg = await _erzeugen(_auftrag(), llm)
    folge = [a["auftrag"].get("knoten", {}).get("titel", "oben") for a in llm.aufrufe]
    assert folge == ["oben", "Licht", "Spiegel", "Licht"]
    assert all(k.get("kinder") for k in erg.daten["knoten"])
