"""Paket RB-1 (2026-11-09): offene Befunde aus AS-D bis AS-4 im Backend.

- Die Rechtsstufe der Sicherheitsprüfung sieht auch lange Prüftexte ganz (Startdaten einer
  Direktaktion; Nachprüfung Querschnitt AS-4).
- Der Wartezähler der Umwandlung sinkt erst, wenn der Lauf vorbei ist — auch nach einem Abbruch
  (vorbestehend, Review 2 zu P1).
- Ein Dienst nennt seine Argumente; die Prüfung meldet unbekannte und fehlende (Querschnitt AS-D).
- Das Studio bekommt die Werkzeuge eines Ablaufschritts als Katalog (``ablauf_werkzeuge``).
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.services.ablauf import typen, werkzeuge
from boerdi.services.ablauf.pruefung import pruefe

# ── Rechtsstufe ─────────────────────────────────────────────────────────────


def test_die_rechtsstufe_sieht_auch_einen_langen_prueftext_ganz(monkeypatch):
    from boerdi.services.safety import legal

    gesehen: list[str] = []

    async def antwort(messages, **_k):
        gesehen.append(messages[-1]["content"])
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="{}"))])

    monkeypatch.setattr(legal, "chat_completion", antwort)
    text = "a" * 2500 + " start.thema: ENDE"
    asyncio.run(legal.classify_legal(text))
    assert gesehen and gesehen[0].endswith("ENDE")


# ── Wartezähler der Umwandlung ──────────────────────────────────────────────


_PDF = b"%PDF-1.4\n/Count 1\n"


def _kind_bis(ende: asyncio.Event, fehler: Exception | None = None):
    """Ein Ausführer, dessen Ende der Test bestimmt — keine festen Wartezeiten (Review RB-1, 3)."""
    async def kind(funktion, *args):  # noqa: ANN001 — Signatur von im_kindprozess
        await ende.wait()
        if fehler is not None:
            raise fehler
        return funktion(*args)
    return kind


async def _bis_null(umwandlung) -> int:  # noqa: ANN001
    for _ in range(200):
        if umwandlung._wartende == 0:
            break
        await asyncio.sleep(0.01)
    return umwandlung._wartende


@pytest.fixture
def umwandlung(monkeypatch):
    from boerdi.services.dokumente import umwandlung as modul

    monkeypatch.setattr(modul, "wandle_datei", lambda pfad, vorgeprueft=False: "Text")
    monkeypatch.setattr(modul, "_wartende", 0)
    return modul


def test_ein_abbruch_haelt_den_zaehler_bis_der_lauf_vorbei_ist(umwandlung):
    async def ablauf():
        ende = asyncio.Event()
        aufgabe = asyncio.ensure_future(umwandlung.wandle(
            _PDF, "pdf", max_seiten=300, frist_s=5, ausfuehren=_kind_bis(ende)))
        await asyncio.sleep(0)
        await asyncio.sleep(0.05)
        aufgabe.cancel()
        with pytest.raises(asyncio.CancelledError):
            await aufgabe
        waehrend = umwandlung._wartende
        ende.set()
        return waehrend, await _bis_null(umwandlung)

    assert asyncio.run(ablauf()) == (1, 0)


def test_die_frist_haelt_den_zaehler_bis_der_lauf_vorbei_ist(umwandlung, monkeypatch):
    monkeypatch.setattr(umwandlung, "PLATZ_FRIST_S", 0)
    monkeypatch.setattr(umwandlung, "_PUFFER_S", 0)

    async def ablauf():
        ende = asyncio.Event()
        aus = await umwandlung.wandle(_PDF, "pdf", max_seiten=300, frist_s=0.05,
                                      ausfuehren=_kind_bis(ende))
        waehrend = umwandlung._wartende
        ende.set()
        return aus.art, waehrend, await _bis_null(umwandlung)

    assert asyncio.run(ablauf()) == ("umwandlung_zu_langsam", 1, 0)


def test_ein_fehler_im_lauf_senkt_den_zaehler_ohne_liegengebliebene_ausnahme(umwandlung):
    gemeldet: list[dict] = []

    async def ablauf():
        asyncio.get_running_loop().set_exception_handler(
            lambda _l, kontext: gemeldet.append(kontext))
        ende = asyncio.Event()
        ende.set()
        with pytest.raises(RuntimeError):
            await umwandlung.wandle(_PDF, "pdf", max_seiten=300, frist_s=5,
                                    ausfuehren=_kind_bis(ende, RuntimeError("kaputt")))
        return await _bis_null(umwandlung)

    assert asyncio.run(ablauf()) == 0
    import gc
    gc.collect()
    assert not gemeldet


def test_nach_einer_absage_startet_der_kindprozess_nicht_mehr(umwandlung, monkeypatch):
    """Review RB-1, Befund 1: wartete der Lauf noch auf den Platz, wandelt er nach der Absage nicht
    mehr um — der Platz gehört dann der nächsten Datei."""
    from boerdi.services.rag import umwandeln_kind

    gestartet: list[object] = []
    monkeypatch.setattr(umwandeln_kind, "_ausfuehren", lambda *a: gestartet.append(a) or "Text")

    async def ablauf():
        platz = umwandeln_kind._einer()
        await platz.acquire()           # ein anderer Lauf hält den Platz
        aufgabe = asyncio.ensure_future(umwandlung.wandle(_PDF, "pdf", max_seiten=300, frist_s=5))
        await asyncio.sleep(0.05)
        aufgabe.cancel()
        with pytest.raises(asyncio.CancelledError):
            await aufgabe
        platz.release()
        return await _bis_null(umwandlung), platz.locked()

    assert asyncio.run(ablauf()) == (0, False)
    assert gestartet == []


# ── Argumente der Dienste ───────────────────────────────────────────────────


def test_jeder_dienst_nennt_seine_argumente():
    assert set(typen.DIENST_EINGABE) == set(werkzeuge.DIENSTE)


def _mit_dienst(argumente):
    return AblaufArea.model_validate({"id": "d", "titel": {"de": "D"}, "schritte": [
        {"id": "w", "typ": "werkzeug", "werkzeug": "abdeckung_zaehlen", "argumente": argumente,
         "schreibt": "zahlen", "bei_fehler": "e"},
        {"id": "e", "typ": "ende"}]})


def test_unbekannte_und_fehlende_argumente_eines_dienstes_sind_befunde():
    befunde = pruefe(_mit_dienst({"entwrf": {"$teil": "draft"}}))
    assert any("entwrf" in b and "kennt" in b for b in befunde), befunde
    assert any("entwurf" in b and "braucht" in b for b in befunde), befunde
    assert not any("kennt" in b or "braucht" in b
                   for b in pruefe(_mit_dienst({"entwurf": {"$teil": "draft"}})))


# ── Katalog der Werkzeuge ───────────────────────────────────────────────────


def test_das_studio_bekommt_die_werkzeuge_als_katalog():
    from boerdi.api import config_choices

    werte = {c["value"] for c in config_choices._SOURCES["ablauf_werkzeuge"]()}
    assert set(werkzeuge.DIENSTE) <= werte
    assert set(werkzeuge.LESENDE_MCP) <= werte
    assert {n for n in werte if werkzeuge.schreibend(n)} == {
        n for n in werte if werkzeuge.schreibend(n) and werkzeuge.freigebbar(n)}
    schema = AblaufArea.model_json_schema()
    werkzeug = str(schema["$defs"]["Schritt"]["properties"]["werkzeug"])
    assert "ablauf_werkzeuge" in werkzeug


# ── Ein Wanderer für alle Verweissuchen ─────────────────────────────────────


def test_ein_wanderer_traegt_tiefe_und_grenze():
    from boerdi.services.teil_verweise import TIEFE, alle_verweise

    def tief(n):
        wert = {"$teil": "a", "pfad": "x"}
        for _ in range(n):
            wert = {"k": wert}
        return wert

    assert alle_verweise(tief(0)) == [("a", "x", {"$teil": "a", "pfad": "x"}, 0)]
    assert [t for *_r, t in alle_verweise(tief(TIEFE))] == [TIEFE]
    assert alle_verweise(tief(TIEFE + 1)) == []
    assert len(alle_verweise(tief(TIEFE + 1), bis=32)) == 1
    assert typen.verweise(tief(TIEFE + 1)) == []
    assert alle_verweise([{"$teil": "a"}, "x", {"$teil": "b"}]) == [
        ("a", None, {"$teil": "a"}, 1), ("b", None, {"$teil": "b"}, 1)]
