"""Plan 2026-11-19, A4 (E1, E2, Befund S4): Ebene 1 aus dem ganzen Text eines Dokuments.

Hat das Markdown höchstens ``GANZTEXT_ZEICHEN`` Zeichen, sieht Ebene 1 den ganzen Text (``text``)
statt Gliederung + Anfang — die Lernfelder eines Lehrplans erkennt das Modell im Text, auch wenn
die Gliederung sie nicht zeigt (E1). Darüber bleibt der bisherige Weg. Was ganz ans Modell geht,
ist vorher moderiert (E2, Stand nach den Reviews): in Stücken zu ``STUECK_ZEICHEN`` mit
Überlappung, nacheinander, unter eigener Stufe und an die Frist gebunden; nur mit dieser Zusage
(``ganz_moderiert``) gilt der Weg „ganz“. Läuft die Moderation im Modus ``open`` ab, gilt der Weg
„gliederung“ (drittes Review, MAJOR 4).
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import Any

import pytest

from boerdi.domain.dokument_gliederung import gliederung, zusammenfuehren
from boerdi.services import strukturentwurf_dienst as dienst
from boerdi.services import strukturentwurf_dokument as sd
from boerdi.services.ablauf.metadaten import DOKUMENT_FORMAT
from boerdi.settings import get_settings
from boerdi.ui_module import dienst as modul_dienst
from boerdi.ui_module import dienst_ganztext, katalog
from boerdi.ui_module.aufruf import Umgebung
from tests.test_strukturentwurf_dokument import _MD

_SATZ = "Die tragende Ordnung (Lernfelder, Themenfelder, Kapitel) steht im Text"


def _dokument(md: str = _MD, **mehr: Any):
    abschnitte, _ = gliederung(md)
    return SimpleNamespace(markdown=md, abschnitte=abschnitte, **mehr)


def _lang(zeichen: int) -> str:
    absatz = "Lernfeld Kunden beraten und Brillen anpassen. " * 20
    teile = [f"## Lernfeld {i}\n{absatz}\n" for i in range(1, zeichen // len(absatz) + 2)]
    return ("# Rahmenlehrplan\n" + "".join(teile))[:zeichen]


def _auftrag_oben(dokument, ganz: bool = True) -> tuple[str, dict]:
    # ``ganz``: der Aufrufer hat den ganzen Text moderiert (zweites Review A, MINOR 5)
    text = (sd.ganzer_text(dokument) or "") if ganz else ""
    nachrichten = sd.aufforderung_oben(dienst.Auftrag(thema="Optik"), {}, dokument, text=text)
    return nachrichten[0]["content"], json.loads(nachrichten[1]["content"].split("\n", 1)[1])


# ── Aufforderung (E1) ────────────────────────────────────────────────────────────────────────────

def test_unter_der_grenze_geht_der_ganze_text_an_ebene_eins():
    system, auftrag = _auftrag_oben(_dokument())
    dok = auftrag["dokument"]
    assert "anfang" not in dok and _SATZ in system
    assert "Newton." in dok["text"] and "Schall." in dok["text"]     # auch das Ende
    assert "- 1 Mechanik [a" in dok["gliederung"]                     # Kennungen bleiben


def test_ueber_der_grenze_bleiben_gliederung_und_anfang():
    md = _lang(sd.GANZTEXT_ZEICHEN + 1)
    system, auftrag = _auftrag_oben(_dokument(md))
    dok = auftrag["dokument"]
    assert "text" not in dok and len(dok["anfang"]) == sd.DOKUMENT_ANFANG
    assert _SATZ not in system


def test_an_der_grenze_noch_der_ganze_text():
    md = _lang(sd.GANZTEXT_ZEICHEN)
    assert sd.ganzer_text(_dokument(md)) == md


def test_mehrere_dokumente_zusammen_unter_der_grenze():
    abschnitte, md = zusammenfuehren([("A.pdf", gliederung(_MD)[0], _MD),
                                      ("B.pdf", gliederung(_MD)[0], _MD)])
    dokument = SimpleNamespace(markdown=md, abschnitte=abschnitte, anfang="# A.pdf", dokumente=2)
    system, auftrag = _auftrag_oben(dokument)
    assert auftrag["dokument"]["text"] == md and "MEHREREN DOKUMENTEN" in system and _SATZ in system


def test_mehrere_dokumente_zusammen_ueber_der_grenze():
    eins = _lang(sd.GANZTEXT_ZEICHEN // 2 + 10)
    abschnitte, md = zusammenfuehren([("A", gliederung(eins)[0], eins),
                                      ("B", gliederung(eins)[0], eins)])
    dokument = SimpleNamespace(markdown=md, abschnitte=abschnitte, anfang="# A", dokumente=2)
    assert sd.ganzer_text(dokument) is None
    assert _auftrag_oben(dokument)[1]["dokument"]["anfang"] == "# A"


def test_die_materialien_der_person_bleiben_beim_anfang():
    dokument = _dokument(format=DOKUMENT_FORMAT)
    assert sd.ganzer_text(dokument) is None
    assert "anfang" in _auftrag_oben(dokument)[1]["dokument"]


async def test_der_dienst_schickt_den_ganzen_text():
    from tests.test_strukturentwurf_dienst import Attrappe, _k

    llm = Attrappe([_k("Mechanik")])
    ende = asyncio.get_running_loop().time() + 60
    await dienst.erzeugen(dienst.Auftrag(thema="Physik", tiefe=1), llm=llm, frist_ende=ende,
                          dokument=_dokument(), ganz_moderiert=True)
    assert llm.aufrufe[0]["auftrag"]["dokument"]["text"] == _MD


# ── Moderation (E2) ──────────────────────────────────────────────────────────────────────────────

class Moderation:
    def __init__(self, urteil=lambda n, text: {"flagged": False}, pause: float = 0.0) -> None:
        self.urteil, self.pause = urteil, pause
        self.texte: list[str] = []
        self.zugleich = self.hoechstens = 0

    async def __call__(self, text: str) -> dict:
        self.texte.append(text)
        self.zugleich += 1
        self.hoechstens = max(self.hoechstens, self.zugleich)
        try:
            await asyncio.sleep(self.pause)
            return self.urteil(len(self.texte), text)
        finally:
            self.zugleich -= 1


@pytest.fixture
def gerufen(monkeypatch):
    aufrufe: list[Any] = []

    async def erzeugen(auftrag, **k):
        aufrufe.append(k)   # drittes Review A, MINOR 7: alle Argumente (``ganz_moderiert``)
        return dienst.Erzeugt(None, "test")

    monkeypatch.setattr(dienst, "erzeugen", erzeugen)
    return aufrufe


def _rufe(monkeypatch, dokument, moderation: Moderation):
    monkeypatch.setattr(modul_dienst, "_moderation", lambda *_: moderation)

    async def lader():
        return dokument

    return asyncio.run(modul_dienst.aufruf(katalog.katalog()["ui_strukturentwurf"],
                                           {"thema": "Optik", "aus_dokument": True},
                                           Umgebung(dokument=lader)))


def test_der_ganze_text_wird_in_stuecken_moderiert(monkeypatch, gerufen):
    md = _lang(2 * dienst_ganztext.STUECK_ZEICHEN + 500)
    moderation = Moderation()
    erg = _rufe(monkeypatch, _dokument(md), moderation)
    assert erg.outcome.error == "test" and len(gerufen) == 1      # geprüft, dann erzeugt
    assert gerufen[0]["ganz_moderiert"] is True
    assert callable(gerufen[0]["llm_vorwaermen"])                 # Kontroll-Durchgang, MINOR 2
    assert len(moderation.texte) == 3
    assert all(len(t) <= dienst_ganztext.STUECK_ZEICHEN for t in moderation.texte)
    # Review A, NIT 12: benachbarte Stücke überlappen — ein Wort auf der Grenze steht ganz in einem
    ueber = dienst_ganztext.UEBERLAPPUNG
    assert moderation.texte[0][-ueber:] == moderation.texte[1][:ueber]
    assert moderation.texte[0] + "".join(t[ueber:] for t in moderation.texte[1:]) == md


def test_ein_stueck_ist_nie_nur_teilweise_geprueft():
    """Review A, MAJOR 2: ein Stück passt in EINEN Aufruf der Moderation ohne ``teilweise``
    (``safety/moderation``: 8 Abschnitte zu 4 000 mit 200 Überlappung)."""
    from boerdi.services.safety import moderation

    teile, ganz = moderation._abschnitte("x" * dienst_ganztext.STUECK_ZEICHEN)
    assert ganz and len(teile) <= moderation._MAX_ABSCHNITTE


def test_100_000_zeichen_in_vier_aufrufen(monkeypatch, gerufen):
    moderation = Moderation()
    _rufe(monkeypatch, _dokument(_lang(100_000)), moderation)
    assert len(moderation.texte) == 4


def test_teilweise_gilt_als_kein_urteil(monkeypatch, gerufen):
    monkeypatch.setenv("MODERATION_FAILURE_MODE", "closed")
    get_settings.cache_clear()
    try:
        erg = _rufe(monkeypatch, _dokument(),
                    Moderation(lambda n, text: {"flagged": False, "teilweise": True}))
    finally:
        get_settings.cache_clear()
    assert erg.outcome.error == "pruefung_fehlt" and gerufen == []


def test_ein_abgewiesenes_stueck_verhindert_den_entwurf(monkeypatch, gerufen):
    md = _lang(2 * dienst_ganztext.STUECK_ZEICHEN + 500)
    moderation = Moderation(lambda n, text: {"flagged": "Lernfeld 30" in text})
    erg = _rufe(monkeypatch, _dokument(md), moderation)
    assert erg.block is None and erg.outcome.error == "abgewiesen" and gerufen == []


@pytest.mark.parametrize(("modus", "fehler", "erzeugt"), [
    ("closed", "pruefung_fehlt", False), ("open", "test", True)])
def test_ausfall_der_moderation_nach_dem_modus(monkeypatch, gerufen, modus, fehler, erzeugt):
    monkeypatch.setenv("MODERATION_FAILURE_MODE", modus)
    get_settings.cache_clear()
    try:
        erg = _rufe(monkeypatch, _dokument(), Moderation(lambda n, text: {}))
    finally:
        get_settings.cache_clear()
    assert erg.outcome.error == fehler and bool(gerufen) is erzeugt
    if erzeugt:   # Viertes Review A, MINOR 7: ohne Urteil nie „ganz“ ungeprüft — Weg „gliederung“
        assert gerufen[0]["ganz_moderiert"] is False


def test_ein_platz_je_entwurf(monkeypatch, gerufen):
    """Review A, MAJOR 2: die Moderation teilt ihre Plätze mit den Chat-Zügen aller Personen — ein
    Entwurf prüft nacheinander (wie die Auszüge, Review Q4, Befund 1)."""
    moderation = Moderation(pause=0.01)
    _rufe(monkeypatch, _dokument(_lang(3 * dienst_ganztext.STUECK_ZEICHEN)), moderation)
    assert len(moderation.texte) >= 3 and moderation.hoechstens == 1


def test_ueber_der_grenze_keine_ganze_moderation(monkeypatch, gerufen):
    moderation = Moderation()
    _rufe(monkeypatch, _dokument(_lang(sd.GANZTEXT_ZEICHEN + 1)), moderation)
    assert moderation.texte == [] and len(gerufen) == 1
    assert gerufen[0]["ganz_moderiert"] is False                  # MINOR 7: über der Grenze
    assert gerufen[0]["llm_vorwaermen"] is None                   # Kontroll-Durchgang, MINOR 2


def test_ein_ungepruefter_text_wird_ebenfalls_ganz_moderiert(monkeypatch, gerufen):
    moderation = Moderation()
    _rufe(monkeypatch, _dokument(ungeprueft=True), moderation)
    # erst Übersicht und Anfang (wie bisher), dann das Ganze
    assert len(moderation.texte) == 2 and moderation.texte[1] == _MD


@pytest.mark.parametrize(("urteil", "grund"), [
    (lambda n, text: {"flagged": True}, "abgewiesen"), (lambda n, text: {}, "pruefung_fehlt")])
def test_die_saetze_nennen_das_dokument_nicht_materialien(monkeypatch, gerufen, urteil, grund):
    """Review A (vorbestehend): ``abgewiesen``/``pruefung_fehlt`` sprachen von „Materialien“ — beim
    Dokument eigene Sätze."""
    monkeypatch.setenv("MODERATION_FAILURE_MODE", "closed")
    get_settings.cache_clear()
    try:
        erg = _rufe(monkeypatch, _dokument(), Moderation(urteil))
    finally:
        get_settings.cache_clear()
    assert erg.outcome.error == grund
    assert "Dokument" in erg.text and "Materialien" not in erg.text


@pytest.mark.parametrize(("modus", "fehler", "erzeugt"), [
    ("closed", "pruefung_fehlt", False), ("open", "test", True)])
def test_eine_langsame_moderation_haelt_die_frist(monkeypatch, gerufen, modus, fehler, erzeugt):
    """Zweites Review A, MINOR 4: die Ganztext-Moderation (bis 4 Aufrufe) endet vor der Frist des
    Dienstes; läuft sie ab, entscheidet ``MODERATION_FAILURE_MODE``."""
    import time

    from boerdi.services import strukturentwurf_dienst as sdienst

    monkeypatch.setenv("MODERATION_FAILURE_MODE", modus)
    get_settings.cache_clear()
    monkeypatch.setattr(modul_dienst, "_moderation", lambda *_: Moderation(pause=3.0))

    async def lader():
        return _dokument()

    async def los():
        ende = asyncio.get_running_loop().time() + modul_dienst.RESERVE_S + sdienst.MINDEST_REST_S
        return await modul_dienst.aufruf(katalog.katalog()["ui_strukturentwurf"],
                                         {"thema": "Optik", "aus_dokument": True},
                                         Umgebung(dokument=lader, frist_ende=ende + 0.3))
    t0 = time.monotonic()
    try:
        erg = asyncio.run(los())
    finally:
        get_settings.cache_clear()
    assert time.monotonic() - t0 < 2.0
    assert erg.outcome.error == fehler and bool(gerufen) is erzeugt
    if erzeugt:   # MINOR 7 / MAJOR 4: nach Ablauf der Frist der Weg „gliederung“
        assert gerufen[0]["ganz_moderiert"] is False


async def test_ohne_zusage_der_moderation_bleibt_der_weg_gliederung():
    """Zweites Review A, MINOR 5: ``erzeugen`` schickt den ganzen Text nur mit
    ``ganz_moderiert=True`` (der Aufrufer hat ihn geprüft) — ohne die Zusage Gliederung, Anfang und
    moderierte Auszüge, auch bei einem kurzen Dokument."""
    from tests.test_strukturentwurf_dienst import Attrappe, _k

    abschnitte = gliederung(_MD)[0]
    geprueft: list[str] = []

    async def moderieren(text):
        geprueft.append(text)
        return {"flagged": False}

    llm = Attrappe([_k("Mechanik", 2, abschnitte=[abschnitte[1].id])],
                   {"Mechanik": [_k("Kraft"), _k("Energie")]})
    ende = asyncio.get_running_loop().time() + 60
    erzeugt = await dienst.erzeugen(dienst.Auftrag(thema="Physik", tiefe=2), llm=llm,
                                    frist_ende=ende, dokument=_dokument(), moderieren=moderieren)
    dok = llm.aufrufe[0]["auftrag"]["dokument"]
    assert "text" not in dok and "anfang" in dok
    assert geprueft                                           # der Auszug ging durch die Moderation
    assert erzeugt.daten["gelesen"][0]["weg"] == "gliederung"


def test_der_ganze_text_hat_eine_eigene_moderationsstufe(monkeypatch, gerufen):
    """Zweites Review A, NIT 11: gezählt unter ``strukturentwurf_ganztext`` (nicht im Alarm der Züge
    und getrennt von den Auszügen)."""
    from boerdi.services.safety import moderation

    stufen: list[str] = []

    async def moderate(text, *, stufe="openai_moderation"):
        stufen.append(stufe)
        return {"flagged": False}

    monkeypatch.setattr(moderation, "moderate", moderate)

    async def lader():
        return _dokument()

    asyncio.run(modul_dienst.aufruf(katalog.katalog()["ui_strukturentwurf"],
                                    {"thema": "Optik", "aus_dokument": True},
                                    Umgebung(dokument=lader)))
    assert stufen == ["strukturentwurf_ganztext"] and len(gerufen) == 1


@pytest.mark.parametrize(("modus", "block"), [("open", True), ("closed", False)])
def test_im_modus_open_nach_ablauf_ein_entwurf_auf_dem_weg_gliederung(monkeypatch, modus, block):
    """Drittes Review A, MAJOR 4: mit ECHTEM ``erzeugen`` (Attrappe nur als LLM) — läuft die
    Moderation des ganzen Texts im Modus ``open`` ab, entsteht der Entwurf über den Weg
    „gliederung“ (Anfang statt Text), und dafür bleibt genug Zeit (``EBENE1_RESERVE_S``)."""
    from boerdi.services import strukturentwurf_dienst as sdienst
    from tests.test_strukturentwurf_dienst import Attrappe, _k

    monkeypatch.setenv("MODERATION_FAILURE_MODE", modus)
    get_settings.cache_clear()
    monkeypatch.setattr(modul_dienst, "_moderation", lambda *_: Moderation(pause=3.0))
    llm = Attrappe([_k("Mechanik"), _k("Optik")])
    monkeypatch.setattr(sdienst, "llm_json", lambda acc, *_: llm)

    async def lader():
        return _dokument()

    async def los():
        jetzt = asyncio.get_running_loop().time()
        ende = (jetzt + modul_dienst.RESERVE_S + sdienst.MINDEST_REST_S
                + dienst_ganztext.EBENE1_RESERVE_S + 0.3)
        return await modul_dienst.aufruf(katalog.katalog()["ui_strukturentwurf"],
                                         {"thema": "Optik", "aus_dokument": True, "tiefe": 1},
                                         Umgebung(dokument=lader, frist_ende=ende))
    try:
        erg = asyncio.run(los())
    finally:
        get_settings.cache_clear()
    assert (erg.block is not None) is block
    if block:
        dok = llm.aufrufe[0]["auftrag"]["dokument"]
        assert "anfang" in dok and "text" not in dok
        assert erg.block.daten["gelesen"][0]["weg"] == "gliederung"
    else:
        assert erg.outcome.error == "pruefung_fehlt" and llm.aufrufe == []


async def test_das_vorwaermen_bucht_unter_eigener_phase(monkeypatch):
    """Kontroll-Durchgang, MINOR 2: ``llm_json(…, PHASE_VORWAERMEN)`` reicht die Phase an den
    Transport (``strukturentwurf_vorwaermen``)."""
    from types import SimpleNamespace

    from boerdi.services import llm

    gesehen: dict = {}

    async def chat_completion(**k):
        gesehen.update(k)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="{}"))])

    monkeypatch.setattr(llm, "chat_completion", chat_completion)
    await dienst.llm_json({}, dienst.PHASE_VORWAERMEN)([{"role": "user", "content": "x"}], 8, 1, 1)
    assert gesehen["phase"] == "strukturentwurf_vorwaermen"
    await dienst.llm_json({})([{"role": "user", "content": "x"}], 8, 1, 1)
    assert gesehen["phase"] == dienst.PHASE == "strukturentwurf"

