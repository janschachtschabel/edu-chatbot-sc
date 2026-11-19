"""Review N1/N2 (2026-11-19): Fach und Stufe fürs Schreiben nur genau oder über Alias.

Die Wortregeln des Filter-Resolvers (``_fuzzy_lookup``, Stufen 2 und 3) erzeugten mit dem echten
WLO-Vokabular falsche Werte — gemessen am 19.11.: „Technik“ → Arbeitslehre (Wortanfang in
„arbeit wirtschaft technik“), „Geschichte/Politik“ → Geschichte, „Politik und Wirtschaft“ →
Politik, „Sekundarstufe I und II“ → Sekundarstufe I (längstes enthaltenes Label). Für Filter ist
das tragbar, fürs Schreiben nicht: dort gilt nur Label oder Alias, sonst leer. Die Einträge unten
sind Auszüge aus ``lookup_wlo_vocabulary`` (Stand 19.11.2026).

Dazu: das Signal für einen verworfenen Wert (``fach_geprueft``/``stufe_geprueft``), ein Laden je
Vokabular auch bei gleichzeitigen Aufrufen, und die Kurzangaben holen beide Listen zugleich."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from boerdi.services.dokumente import inhalt_angaben as ia
from boerdi.services.mcp import client as mcp_client
from boerdi.services.mcp import vokabular_labels as vl
from tests.helfer_vokabular import leeren, mit_vokabular

_D = "http://w3id.org/openeduhub/vocabs/discipline/"
_E = "http://w3id.org/openeduhub/vocabs/educationalContext/"
_WLO = {
    "discipline": (
        "- **Arbeitslehre** | Aliases: career education, arbeit wirtschaft technik, awt, "
        f"polytechnik\n  URI: {_D}020\n"
        f"- **Elektrotechnik** | Aliases: electrical engineering\n  URI: {_D}04003\n"
        f"- **Geografie** | Aliases: geography, erdkunde, geographie, geo\n  URI: {_D}220\n"
        f"- **Geschichte** | Aliases: history\n  URI: {_D}240\n"
        "- **Politik** | Aliases: politics, politische bildung, sozialkunde, gemeinschaftskunde\n"
        f"  URI: {_D}480\n"
        "- **Wirtschaftskunde** | Aliases: economics, wirtschaftswissenschaften, economy, vwl, "
        f"bwl, wirtschaftslehre\n  URI: {_D}700\n"),
    "educationalContext": (
        "- **Sekundarstufe I** | Aliases: sekundarstufe 1, secondary i, sek i, sek1\n"
        f"  URI: {_E}sekundarstufe_1\n"
        "- **Sekundarstufe II** | Aliases: sekundarstufe 2, secondary ii, sek ii, oberstufe\n"
        f"  URI: {_E}sekundarstufe_2\n"),
}


@pytest.fixture
def wlo(monkeypatch):
    gefragt = mit_vokabular(monkeypatch, _WLO)
    yield gefragt
    leeren()


def _run(coro):
    return asyncio.run(coro)


# ── MINOR 2: nur Label oder Alias ────────────────────────────────────────────

@pytest.mark.parametrize(("wert", "erwartet"), [
    ("Technik", None),
    ("Geschichte/Politik", None),
    ("Politik und Wirtschaft", None),
    ("Wirtschaft", None),
    ("Erdkunde", "Geografie"),
    ("AWT", "Arbeitslehre"),
    ("  Politische   Bildung ", "Politik"),
    ("geschichte", "Geschichte"),
])
def test_fach_nur_genau_oder_ueber_alias(wlo, wert, erwartet):
    assert _run(vl.fach(wert)) == erwartet


@pytest.mark.parametrize(("wert", "erwartet"), [
    ("Sekundarstufe I und II", None),
    ("Sek I", "Sekundarstufe I"),
    ("Oberstufe", "Sekundarstufe II"),
])
def test_stufe_nur_genau_oder_ueber_alias(wlo, wert, erwartet):
    assert _run(vl.stufe(wert)) == erwartet


# ── MINOR 3: Signal für einen verworfenen Wert ───────────────────────────────

def test_ein_verworfenes_fach_wird_gemeldet(wlo):
    assert _run(vl.fach_geprueft("Wirtschaft")) == vl.Abbildung(label=None, verworfen="Wirtschaft")
    assert _run(vl.fach_geprueft("Erdkunde")) == vl.Abbildung(label="Geografie", verworfen=None)
    assert _run(vl.stufe_geprueft("Sekundarstufe I und II")) == vl.Abbildung(
        label=None, verworfen="Sekundarstufe I und II")


def test_leer_ist_nicht_verworfen(wlo):
    assert _run(vl.fach_geprueft("  ")) == vl.Abbildung(label=None, verworfen=None)
    assert _run(vl.fach_geprueft(None)) == vl.Abbildung(label=None, verworfen=None)


def test_ohne_vokabular_wird_nichts_verworfen():
    """``conftest``: kein Vokabular — die Prüfer des Entwurfs, kein Hinweis."""
    assert _run(vl.fach_geprueft("Wirtschaft")) == vl.Abbildung(label="Wirtschaft", verworfen=None)


# ── NIT 5: ein Laden je Vokabular, beide Listen zugleich ─────────────────────

def test_gleichzeitige_aufrufe_laden_einmal(monkeypatch):
    gefragt = mit_vokabular(monkeypatch, _WLO, warten=0.05)

    async def alle():
        return await asyncio.gather(vl.fach("Erdkunde"), vl.fach("Geschichte"),
                                    vl.stufe("Sek I"), vl.stufe("Oberstufe"))

    try:
        assert _run(alle()) == ["Geografie", "Geschichte", "Sekundarstufe I", "Sekundarstufe II"]
        assert sorted(gefragt) == ["discipline", "educationalContext"]
    finally:
        leeren()


def test_kurzangaben_holen_beide_listen_zugleich(monkeypatch):
    laufend = 0
    hoechst = 0

    async def mcp(name: str, args: dict[str, Any]) -> str:
        nonlocal laufend, hoechst
        laufend += 1
        hoechst = max(hoechst, laufend)
        await asyncio.sleep(0.05)
        laufend -= 1
        return _WLO[args["vocabulary"]]

    mit_vokabular(monkeypatch, _WLO)
    monkeypatch.setattr(mcp_client, "call_mcp_tool", mcp)

    async def llm(_nachrichten):
        return {"titel": "T"}

    try:
        _run(ia.ermitteln("Text", "a.pdf", llm=llm))
        assert hoechst == 2
    finally:
        leeren()
