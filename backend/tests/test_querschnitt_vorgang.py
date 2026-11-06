"""Querschnitts-Review 2026-11-06, Paket Q3 — der Vorgang über die Paketgrenzen.

M6 (nach Review Q3): ein beendeter Lauf lässt seinen Vorgang offen — der Entwurf bleibt erreichbar.
Erst der **nächste** Ablauf-Start schließt einen Vorgang mit beendetem oder fremdem Lauf und beginnt
einen neuen, bevor Antwort oder Treiber etwas schreiben. Freie Arbeit (Vorgang ohne Lauf) übernimmt
ein Ablauf. Dazu: Verweis je Zug aus der DB (im Preflight), ``uebernehmen`` meldet Erfolg, die
Aktionen „neues Vorhaben“ und „Arbeitsstand löschen“ (mit Rückfrage) als Knöpfe nach einem Ablauf.
"""

from __future__ import annotations

import asyncio

from boerdi.i18n import bot_text
from boerdi.services import arbeitsstand, vorgaenge, vorgang_aktion
from boerdi.services.ablauf import ausloeser, treiber, zug
from boerdi.services.auftraege import client
from boerdi.ui_module import strukturentwurf_merken
from tests.test_ablauf_auftrag import (  # noqa: F401 — Fixtures
    _pruefe,
    _starte,
    freigeschaltet,
    im_zug,
)
from tests.test_ablauf_zug import _S, _geprueft, _req, _start, umgebung  # noqa: F401

_GRUSS = {"id": "gruss", "titel": {"de": "Gruß"}, "aktiv": True, "ausloeser": [{"art": "knopf"}],
          "schritte": [{"id": "ende", "typ": "ende", "text": {"de": "Hallo."}}]}
_SID = "sitzung-0123456789"


def _mit_gruss(umgebung):  # noqa: F811
    umgebung.katalog["wert"] = {**umgebung.katalog["wert"],
                                "ablaeufe": [*umgebung.katalog["wert"]["ablaeufe"], _GRUSS]}


def _gruss(state):
    return asyncio.run(zug.starten(_S(), _req(action=zug.AKTION,
                                              action_params={"ablauf": "gruss"}), state))


def _vorgaenge(umgebung):  # noqa: F811
    return sorted(umgebung.speicher.v.values(), key=lambda v: v.id)


# ── M6 ──────────────────────────────────────────────────────────────────────────────────────

def test_m6_ein_beendeter_lauf_laesst_seinen_vorgang_offen(im_zug):  # noqa: F811
    """Review Q3, Befund 3: sonst wäre der eben gespeicherte Entwurf nicht mehr erreichbar."""
    state: dict = {"entities": {}}
    _starte(state)
    im_zug.staende.append(client.Stand("fertig", {"markdown": "# T"}, []))
    assert _pruefe(state).content == "Gelesen."
    [v] = im_zug.speicher.v.values()
    assert v.status == "aktiv" and v.akte["lauf"]["status"] == "fertig"


def test_m6_der_naechste_start_schliesst_ihn_und_beginnt_einen_neuen(umgebung):  # noqa: F811
    _mit_gruss(umgebung)
    state: dict = {"entities": {}}
    _gruss(state)
    _gruss(state)
    alt, neu = _vorgaenge(umgebung)
    assert alt.status == "fertig" and neu.status == "aktiv"
    assert state["entities"][arbeitsstand.VERWEIS]["id"] == neu.id


def test_m6_ein_fremder_wartender_lauf_bekommt_einen_neuen_vorgang(umgebung):  # noqa: F811
    _mit_gruss(umgebung)
    state: dict = {"entities": {}}
    _start(state)                                   # sammlungsstruktur wartet am ersten Modul
    _gruss(state)
    alt, neu = _vorgaenge(umgebung)
    assert alt.status == "fertig" and alt.akte["lauf"]["status"] == "abgebrochen"
    assert neu.akte["lauf"]["ablauf"] == "gruss"


def test_m6_freie_arbeit_wird_uebernommen_nicht_geschlossen(umgebung):  # noqa: F811
    """Review Q3, Befund 1."""
    _mit_gruss(umgebung)
    state: dict = {"entities": {}}
    asyncio.run(arbeitsstand.teile_speichern(_S(), _SID, state["entities"],
                                             [("draft", "t", {"a": 1}, "z")]))
    _gruss(state)
    [v] = _vorgaenge(umgebung)
    assert "draft" in v.akte["teile"] and v.status == "aktiv"


def test_m6_ein_modul_ausloeser_auf_beendetem_vorgang_schreibt_alles_in_den_neuen(umgebung):  # noqa: F811
    """Review Q3, Befund 2: Antwort und Treiber landen im selben, neuen Vorgang."""
    _mit_gruss(umgebung)
    state: dict = {"entities": {}}
    _gruss(state)
    ablauf = ausloeser.laden("sammlungsstruktur")
    block = type("B", (), {"block_id": "neu00001"})()
    asyncio.run(zug.per_modul_starten(_S(), _req(), state, _geprueft(block, "erfasst"),
                                      (ablauf, 1)))
    alt, neu = _vorgaenge(umgebung)
    assert alt.status == "fertig" and "structure" not in alt.akte["teile"]
    assert "structure" in neu.akte["teile"] and neu.akte["lauf"]["ablauf"] == "sammlungsstruktur"


def test_scheitert_das_uebernehmen_beim_modul_ausloeser_kein_lauf(umgebung, monkeypatch):  # noqa: F811
    """Review Q3, Befund 9."""
    state: dict = {"entities": {}}
    ablauf = ausloeser.laden("sammlungsstruktur")

    async def nie(*_a, **_k):
        return False

    monkeypatch.setattr(arbeitsstand, "teile_speichern", nie)
    block = type("B", (), {"block_id": "neu00001"})()
    antwort = asyncio.run(zug.per_modul_starten(_S(), _req(), state, _geprueft(block, "erfasst"),
                                                (ablauf, 1)))
    assert antwort.content == bot_text("de", "action.ablauf.konflikt")
    # Das Ziel steht vor dem Speichern fest (Nachprüfung, Befund 3) — ohne Lauf darin.
    assert all(v.akte["lauf"] is None for v in umgebung.speicher.v.values())


def test_der_modul_ausloeser_speichert_nur_ins_vorbereitete_ziel(umgebung, monkeypatch):  # noqa: F811
    """Nachprüfung, Befund 3: wird das Ziel nach ``_ziel_vorbereiten`` geschlossen, landet die
    Antwort nicht in einem anderen Vorgang."""
    ablauf = ausloeser.laden("sammlungsstruktur")
    echt = zug._ziel_vorbereiten

    async def und_dann_zu(session, req, entities, ablauf, **k):
        ok = await echt(session, req, entities, ablauf, **k)
        for v in umgebung.speicher.v.values():
            v.status = "fertig"
        return ok

    monkeypatch.setattr(zug, "_ziel_vorbereiten", und_dann_zu)
    block = type("B", (), {"block_id": "neu00001"})()
    antwort = asyncio.run(zug.per_modul_starten(_S(), _req(), {"entities": {}},
                                                _geprueft(block, "erfasst"), (ablauf, 1)))
    assert antwort.content == bot_text("de", "action.ablauf.konflikt")
    [v] = umgebung.speicher.v.values()
    assert v.akte["teile"] == {}


def test_inzwischen_abgeschlossen_ist_ein_konflikt(umgebung, monkeypatch):  # noqa: F811
    """Nachprüfung, Befund 3/7: schließt eine zweite Sitzung den Vorgang während des Treibers,
    hängt der Lauf nicht an einem frischen Vorgang ohne die Teile davor."""
    _mit_gruss(umgebung)
    state: dict = {"entities": {}}
    _start(state)                                   # Vorgang mit wartendem Lauf
    [v] = umgebung.speicher.v.values()
    v.akte["lauf"] = None                           # freie Arbeit: wird übernommen
    echt = zug.basis.rechne

    async def und_dann_zu(*a, **k):
        aus = await echt(*a, **k)
        v.status = "fertig"
        return aus

    monkeypatch.setattr(zug.basis, "rechne", und_dann_zu)
    antwort = _gruss(state)
    assert antwort.content == bot_text("de", "action.ablauf.konflikt")
    assert len(umgebung.speicher.v) == 1


def test_ein_abgeschlossener_vorgang_nimmt_keine_teile_mehr(umgebung):  # noqa: F811
    state: dict = {"entities": {}}
    asyncio.run(arbeitsstand.teile_speichern(_S(), _SID, state["entities"],
                                             [("draft", "t", {"a": 1}, "z")]))
    [alt] = _vorgaenge(umgebung)
    umgebung.speicher.v[alt.id].status = "fertig"
    asyncio.run(arbeitsstand.teile_speichern(_S(), _SID, state["entities"],
                                             [("draft", "t", {"a": 2}, "z")]))
    assert len(umgebung.speicher.v) == 2


def test_nur_dieser_vorgang_leitet_nicht_um(umgebung):  # noqa: F811
    """Review Q3, Befund 8: eine Datei nach „neues Vorhaben“ landet nicht in einem anderen."""
    state: dict = {"entities": {}}
    asyncio.run(arbeitsstand.teile_speichern(_S(), _SID, state["entities"],
                                             [("ablage", "t", {"a": 1}, "z")]))
    [alt] = _vorgaenge(umgebung)
    umgebung.speicher.v[alt.id].status = "fertig"

    async def neu():
        return [("ablage", "t", {"a": 2}, "z")]

    ok = asyncio.run(arbeitsstand.teile_speichern(_S(), _SID, state["entities"], [],
                                                  neu=neu, nur_dieser=True))
    assert ok is False and len(umgebung.speicher.v) == 1
    # Gegenprobe (Nachprüfung, Befund 2): ohne ``nur_dieser`` entsteht ein neuer Vorgang.
    ok = asyncio.run(arbeitsstand.teile_speichern(_S(), _SID, state["entities"], [], neu=neu))
    assert ok is True and len(umgebung.speicher.v) == 2


# ── Verweis je Zug ──────────────────────────────────────────────────────────────────────────

def test_der_verweis_folgt_einmal_je_zug_dem_vorgang(umgebung):  # noqa: F811
    state: dict = {"entities": {}}
    _start(state)
    [v] = umgebung.speicher.v.values()
    v.akte["lauf"] = {**v.akte["lauf"], "schritt": "bearbeiten", "status": treiber.WARTET_KI}
    asyncio.run(arbeitsstand.auffrischen(_S(), _SID, state["entities"]))
    assert state["entities"][arbeitsstand.VERWEIS]["lauf"]["schritt"] == "bearbeiten"


def test_ein_geschlossener_vorgang_faellt_aus_dem_verweis(umgebung):  # noqa: F811
    state: dict = {"entities": {}}
    _start(state)
    [v] = umgebung.speicher.v.values()
    v.status = "fertig"
    asyncio.run(arbeitsstand.auffrischen(_S(), _SID, state["entities"]))
    assert arbeitsstand.VERWEIS not in state["entities"]


# ── Aktionen ────────────────────────────────────────────────────────────────────────────────

def test_nach_einem_fertigen_ablauf_stehen_neues_vorhaben_und_loeschen_da(umgebung):  # noqa: F811
    """Review Q3, Befund 4: die Aktionen brauchen einen Einstieg — das Modell darf keine
    ``__action__``-Knöpfe schreiben, also setzt sie das Backend."""
    _mit_gruss(umgebung)
    antwort = _gruss({"entities": {}})
    aktionen = [k.split("|")[2] for k in antwort.quick_replies]
    assert aktionen == [vorgang_aktion.AKTION_NEU, vorgang_aktion.AKTION_LOESCHEN]


def test_neues_vorhaben_schliesst_den_aktiven_vorgang(umgebung):  # noqa: F811
    state: dict = {"entities": {strukturentwurf_merken.KEY: {"titel": "alt"}}}
    _start(state)
    antwort = asyncio.run(vorgang_aktion.neu(_S(), _req(action=vorgang_aktion.AKTION_NEU), state))
    [v] = umgebung.speicher.v.values()
    assert v.status == "fertig" and v.akte["lauf"]["status"] == "abgebrochen"
    assert arbeitsstand.VERWEIS not in state["entities"]
    assert strukturentwurf_merken.KEY not in state["entities"]
    assert antwort.content == bot_text("de", "action.vorgang.neu")


def test_neues_vorhaben_bei_einem_konflikt_behaelt_den_entwurf(umgebung, monkeypatch):  # noqa: F811
    """Nachprüfung, Befund 10: der gemerkte Entwurf geht erst mit dem Erfolg."""
    state: dict = {"entities": {strukturentwurf_merken.KEY: {"titel": "alt"}}}
    _start(state)

    async def konflikt(*_a, **_k):
        raise vorgaenge.VorgangKonflikt("v")

    monkeypatch.setattr(vorgaenge, "lauf_setzen", konflikt)
    antwort = asyncio.run(vorgang_aktion.neu(_S(), _req(action=vorgang_aktion.AKTION_NEU), state))
    assert antwort.content == bot_text("de", "action.ablauf.konflikt")
    assert strukturentwurf_merken.KEY in state["entities"]
    assert arbeitsstand.VERWEIS in state["entities"]


def test_loeschen_fragt_erst_nach(umgebung):  # noqa: F811
    state: dict = {"entities": {}}
    _start(state)
    antwort = asyncio.run(vorgang_aktion.loeschen(
        _S(), _req(action=vorgang_aktion.AKTION_LOESCHEN), state))
    assert antwort.content == bot_text("de", "action.vorgang.loeschenFrage")
    assert '"bestaetigt": true' in antwort.quick_replies[0]
    assert len(umgebung.speicher.v) == 1


def test_bestaetigtes_loeschen_entfernt_alle_vorgaenge_der_person(umgebung):  # noqa: F811
    """Review Q3, Befund 5: auch die schon geschlossenen, und der gemerkte Entwurf geht mit."""
    _mit_gruss(umgebung)
    state: dict = {"entities": {strukturentwurf_merken.KEY: {"titel": "alt"}}}
    _gruss(state)
    _gruss(state)                                   # der erste ist jetzt geschlossen
    antwort = asyncio.run(vorgang_aktion.loeschen(
        _S(), _req(action=vorgang_aktion.AKTION_LOESCHEN, action_params={"bestaetigt": True}),
        state))
    assert umgebung.speicher.v == {}
    assert arbeitsstand.VERWEIS not in state["entities"]
    assert strukturentwurf_merken.KEY not in state["entities"]
    assert antwort.content == bot_text("de", "action.vorgang.geloescht")


def test_ohne_vorgang_ein_hinweis(umgebung):  # noqa: F811
    antwort = asyncio.run(vorgang_aktion.neu(_S(), _req(action=vorgang_aktion.AKTION_NEU),
                                             {"entities": {}}))
    assert antwort.content == bot_text("de", "action.vorgang.keiner")
