"""Review Paket F (Plan 2026-11-20 §6, Entscheid E-F): kein Weg bewegt einen Lauf aus einem anderen
Gespräch.

Ein Lauf, der in Gespräch A wartet, gehört A (``Vorgang.session_id``). Zeigt der Verweis eines
anderen Gesprächs B auf ihn (Stand von vor E-F), gilt:

- **zentral:** ``arbeitsstand.auffrischen`` (im Preflight vor jedem Ablauf-Weg) entfernt den
  Verweis in B — keine fremden Chips, keine Sperre, kein wartender Lauf; in A bleibt er;
- **in der Tiefe:** wer trotzdem mit dem fremden Verweis antwortet (Modul-Antwort, „Weiter im
  Ablauf“, „Stand prüfen“, Abbrechen), bewegt den Lauf nicht (``zug_basis.gehoert_hierher``).
"""

from __future__ import annotations

import asyncio
import copy

import pytest

from boerdi.api.schemas import ChatRequest
from boerdi.services import arbeitsstand, vorgaenge
from boerdi.services.ablauf import auftrag_zug, ausloeser, treiber, wahl_zug, zug, zug_basis
from boerdi.services.auftraege import client
from tests.test_ablauf_auftrag import (  # noqa: F401 — Fixtures
    _SCHRITTE,
    _roh,
    _starte,
    freigeschaltet,
    im_zug,
)
from tests.test_ablauf_zug import _S, _geprueft, _req

_A = "sitzung-0123456789"            # wie ``_req``: das Gespräch, in dem der Lauf wartet
_B = "sitzung-bbbbbbbbbb"            # ein anderes Gespräch derselben Person

_KI = {"id": "ki", "titel": {"de": "KI"}, "aktiv": True, "ausloeser": [{"art": "knopf"}],
       "schritte": [{"id": "k", "typ": "agent", "text": {"de": "Wir arbeiten gemeinsam."},
                     "agent": {"werkzeuge": ["search_wlo_all"]}},
                    {"id": "ende", "typ": "ende", "text": {"de": "Fertig."}}]}
_MODUL = {"id": "modul", "titel": {"de": "Modul"}, "aktiv": True, "ausloeser": [{"art": "knopf"}],
          "schritte": [{"id": "up", "typ": "modul", "modul": "ui_upload",
                        "daten": {"zweck": "sammlungsstruktur"}, "schreibt": "structure",
                        "bei_fehler": "ende"},
                       {"id": "ende", "typ": "ende", "text": {"de": "Erfasst."}}]}
_WAHL = {"id": "wahl", "titel": {"de": "Wahl"}, "aktiv": True, "ausloeser": [{"art": "knopf"}],
         "schritte": [{"id": "frage", "typ": "nachricht", "text": {"de": "Wie weiter?"},
                       "optionen": [{"id": "neu", "label": {"de": "Neu"}, "ziel": "ende"}]},
                      {"id": "ende", "typ": "ende", "text": {"de": "Neu."}}]}


@pytest.fixture
def katalog(im_zug, monkeypatch):  # noqa: F811
    roh = [_roh(schritte=[{**_SCHRITTE[0], "argumente": {"text": "fest"}}, *_SCHRITTE[1:]]),
           _KI, _MODUL, _WAHL]
    monkeypatch.setattr(ausloeser, "_roh_liste", lambda: roh)
    ausloeser._gepruefter = None
    yield im_zug
    ausloeser._gepruefter = None


def _in_a(ablauf_id: str) -> dict:
    """Den Ablauf in Gespräch A starten — die Sitzung A danach."""
    state: dict = {"entities": {}}
    if ablauf_id == "lesen":
        _starte(state)
    else:
        asyncio.run(zug.starten(_S(), _req(action=zug.AKTION,
                                           action_params={"ablauf": ablauf_id}), state))
    return state


def _fremd(state_a: dict) -> dict:
    """Gespräch B mit einer Kopie des Verweises aus A (Altbestand)."""
    return {"entities": {arbeitsstand.VERWEIS: copy.deepcopy(
        state_a["entities"][arbeitsstand.VERWEIS])}}


def _in_b(**mehr) -> ChatRequest:
    return _req(**mehr).model_copy(update={"session_id": _B})


def _gespeichert(im_zug):  # noqa: F811
    [v] = im_zug.speicher.v.values()
    return v


# ── zentral: der Verweis eines anderen Gesprächs fällt im ersten Zug weg ─────────────────────

@pytest.mark.parametrize("ablauf_id", ["lesen", "wahl", "ki"])
def test_altbestand_ein_fremder_verweis_faellt_beim_ersten_zug_weg(katalog, ablauf_id):
    state_a = _in_a(ablauf_id)
    b = _fremd(state_a)
    assert zug.lauf_wartet(_B, b) is True                       # vorher: der fremde Lauf
    asyncio.run(arbeitsstand.auffrischen(_S(), _B, b["entities"]))
    assert arbeitsstand.VERWEIS not in b["entities"]
    assert zug.lauf_wartet(_B, b) is False
    assert wahl_zug.aktuelle_knoepfe(_B, b, "de") == []        # keine fremden Chips
    assert auftrag_zug.gesperrt(_B, b) is None                  # keine Sperre
    asyncio.run(arbeitsstand.auffrischen(_S(), _A, state_a["entities"]))
    assert state_a["entities"][arbeitsstand.VERWEIS]["id"] == _gespeichert(katalog).id


def test_altbestand_ein_vorgang_ohne_wartenden_lauf_bleibt(katalog):
    """Nur ein **wartender** Lauf gehört seinem Gespräch — freie Arbeit bleibt erreichbar."""
    state_a = _in_a("wahl")
    _gespeichert(katalog).status = "aktiv"
    b = _fremd(state_a)
    asyncio.run(arbeitsstand.auffrischen(_S(), _B, b["entities"]))
    assert arbeitsstand.VERWEIS in b["entities"]


# ── in der Tiefe: kein Weg bewegt den fremden Lauf ───────────────────────────────────────────

def _unberuehrt(im_zug, vorher):  # noqa: F811
    v = _gespeichert(im_zug)
    assert v.session_id == _A
    assert v.akte["lauf"] == vorher["lauf"] and v.akte["teile"] == vorher["teile"]


def test_tiefe_stand_pruefen_aus_einem_anderen_gespraech(katalog):
    state_a = _in_a("lesen")
    vorher = copy.deepcopy(_gespeichert(katalog).akte)
    katalog.staende.append(client.Stand("fertig", {"markdown": "# T"}, []))
    asyncio.run(auftrag_zug.pruefen(_S(), _in_b(action=auftrag_zug.AKTION,
                                                action_params={"ablauf": "lesen"}),
                                    _fremd(state_a)))
    _unberuehrt(katalog, vorher)


def test_tiefe_auftrag_abbrechen_aus_einem_anderen_gespraech(katalog):
    state_a = _in_a("lesen")
    vorher = copy.deepcopy(_gespeichert(katalog).akte)
    asyncio.run(auftrag_zug.abbrechen(_S(), _in_b(action=auftrag_zug.AKTION_ABBRECHEN,
                                                  action_params={"ablauf": "lesen"}),
                                      _fremd(state_a)))
    _unberuehrt(katalog, vorher)
    assert katalog.ablage.auftraege[0].status == "laeuft"


def test_tiefe_weiter_im_ablauf_aus_einem_anderen_gespraech(katalog):
    state_a = _in_a("ki")
    assert _gespeichert(katalog).akte["lauf"]["status"] == treiber.WARTET_KI
    vorher = copy.deepcopy(_gespeichert(katalog).akte)
    asyncio.run(zug.weiter_nach_ki(_S(), _in_b(action=zug.AKTION_WEITER,
                                               action_params={"ablauf": "ki"}),
                                   _fremd(state_a)))
    _unberuehrt(katalog, vorher)


def test_tiefe_modul_antwort_aus_einem_anderen_gespraech(katalog):
    state_a = _in_a("modul")
    v = _gespeichert(katalog)
    block = type("B", (), {"block_id": v.akte["lauf"]["offener_block"]})
    vorher = copy.deepcopy(v.akte)
    antwort = asyncio.run(zug.fortsetzen(_S(), _in_b(), _fremd(state_a), _geprueft(block)))
    assert antwort is None                                       # der gewöhnliche Weg
    _unberuehrt(katalog, vorher)


def test_tiefe_festhalten_weist_einen_fremden_lauf_ab(katalog):
    """``festhalten`` ist die gemeinsame Stelle aller Antworten: ein Lauf, der in einem anderen
    Gespräch wartet, wird dort nicht fortgeschrieben (Konflikt — der Aufrufer rollt zurück)."""
    _in_a("wahl")
    v = _gespeichert(katalog)
    aus = treiber.Ausgabe(lauf={**v.akte["lauf"], "status": "fertig"})
    with pytest.raises(vorgaenge.VorgangKonflikt):
        asyncio.run(zug_basis.festhalten(_S(), copy.deepcopy(v), aus, session_id=_B))
    assert zug_basis.gehoert_hierher(v, _A) and not zug_basis.gehoert_hierher(v, _B)


# ── Kontrolle Paket F (MINOR 1, 3, 4; NIT 8) ─────────────────────────────────────────────────

_KI_ENTWURF = {"id": "kie", "titel": {"de": "KI-Entwurf"}, "aktiv": True,
               "ausloeser": [{"art": "knopf"}],
               "schritte": [{"id": "k", "typ": "agent", "text": {"de": "Wir entwerfen."},
                             "agent": {"werkzeuge": ["ui_strukturentwurf"], "ausgabe": "draft"}},
                            {"id": "ende", "typ": "ende", "text": {"de": "Übernommen."}}]}
_ENTWURF_ANTWORT = {"modul": "ui_strukturentwurf", "block_id": "b0000002",
                    "daten": {"titel": "Optik", "quelle": "ki", "uebernommen": True,
                              "bearbeitet": True,
                              "knoten": [{"id": "k1", "titel": "Licht", "kinder": []}]}}


@pytest.fixture
def mit_entwurf(katalog, monkeypatch):
    roh = [*ausloeser._roh_liste(), _KI_ENTWURF]
    monkeypatch.setattr(ausloeser, "_roh_liste", lambda: roh)
    ausloeser._gepruefter = None
    return katalog


def test_kontrolle_leisten_abbruch_aus_einem_anderen_gespraech(katalog):
    from boerdi.services.ablauf import abbruch_zug

    state_a = _in_a("wahl")
    v = _gespeichert(katalog)
    vorher = copy.deepcopy(v.akte)
    marke = zug.lauf_marke(v, v.akte["lauf"])
    asyncio.run(abbruch_zug.abbrechen(_S(), _in_b(action=abbruch_zug.AKTION, action_params={
        "bestaetigt": True, "marke": marke}), _fremd(state_a)))
    _unberuehrt(katalog, vorher)


def test_kontrolle_wendung_aus_einem_anderen_gespraech(katalog):
    from boerdi.services.ablauf import wendung_zug

    state_a = _in_a("wahl")
    vorher = copy.deepcopy(_gespeichert(katalog).akte)
    asyncio.run(wendung_zug.wendung_beantworten(
        _S(), _in_b().model_copy(update={"message": "KI"}), _fremd(state_a),
        ausloeser.laden("ki")))
    _unberuehrt(katalog, vorher)


def test_kontrolle_ki_entwurf_uebernehmen_aus_einem_anderen_gespraech(mit_entwurf):
    state_a = _in_a("kie")
    assert _gespeichert(mit_entwurf).akte["lauf"]["status"] == treiber.WARTET_KI
    vorher = copy.deepcopy(_gespeichert(mit_entwurf).akte)
    antwort = asyncio.run(zug.nach_uebernahme(_S(), _in_b(), _fremd(state_a),
                                              copy.deepcopy(_ENTWURF_ANTWORT)))
    assert antwort is None
    _unberuehrt(mit_entwurf, vorher)


def test_kontrolle_neues_vorhaben_aus_einem_anderen_gespraech(katalog):
    from boerdi.services import vorgang_aktion

    state_a = _in_a("wahl")
    v = _gespeichert(katalog)
    vorher = copy.deepcopy(v.akte)
    asyncio.run(vorgang_aktion.neu(_S(), _in_b(action=vorgang_aktion.AKTION_NEU),
                                   _fremd(state_a)))
    assert v.status == "wartet_person"            # nicht geschlossen
    _unberuehrt(katalog, vorher)


def test_kontrolle_schliessen_weist_einen_fremden_lauf_ab(katalog):
    _in_a("wahl")
    v = _gespeichert(katalog)
    with pytest.raises(vorgaenge.VorgangKonflikt):
        asyncio.run(zug_basis.schliessen(_S(), copy.deepcopy(v), session_id=_B))
    assert v.status == "wartet_person"


def test_kontrolle_preflight_chip_aus_einem_anderen_gespraech(katalog, monkeypatch):
    """Der ganze Preflight: B trägt den Verweis aus A (Altbestand) und drückt dessen Chip — der
    Verweis fällt in ``auffrischen`` weg, die Antwort ist „gilt nicht mehr“, der Lauf bleibt."""
    import json

    from boerdi.graph import state as state_mod
    from boerdi.graph.nodes import preflight as pf_mod
    from boerdi.i18n import bot_text
    from boerdi.services.rate_limits import RateVerdict

    async def erlaubt(*_a, **_k):
        return RateVerdict(allowed=True)

    async def nichts(*_a, **_k):
        return None

    monkeypatch.setattr(pf_mod, "check_rate_limit", erlaubt)
    monkeypatch.setattr(pf_mod, "log_safety_event", nichts)
    monkeypatch.setattr(pf_mod, "save_message", nichts)
    state_a = _in_a("wahl")
    v = _gespeichert(katalog)
    vorher = copy.deepcopy(v.akte)
    [chip] = wahl_zug.aktuelle_knoepfe(_A, state_a, "de")
    params = json.loads(chip.split("|", 3)[3])
    ctx = state_mod.TurnContext(req=_in_b(action=wahl_zug.AKTION, action_params=params))
    ctx.session_state = _fremd(state_a)
    ctx.client_ip = "1.2.3.4"
    out = asyncio.run(pf_mod.preflight(ctx, _S()))
    assert out.early_response.content == bot_text("de", "action.ablauf.wahlVeraltet")
    assert out.early_response.quick_replies == []
    assert arbeitsstand.VERWEIS not in ctx.session_state["entities"]
    _unberuehrt(katalog, vorher)


def test_kontrolle_freigabe_festhalten_beendet_den_job_nach_einem_konflikt(monkeypatch):
    """NIT 8 (vorbestehend): ein Konflikt beim Festhalten nach einem gestarteten Auftrag beendet
    ihn wieder — wie bei jedem anderen Festhalten (``nicht_festgehalten``)."""
    from boerdi.services.ablauf import freigabe_zug

    beendet: list = []

    async def konflikt(*_a, **_k):
        raise vorgaenge.VorgangKonflikt("v-1")

    async def merke(aus):
        beendet.append(aus.auftrag)

    monkeypatch.setattr(zug_basis, "festhalten", konflikt)
    monkeypatch.setattr(zug_basis, "nicht_festgehalten", merke)
    aus = treiber.Ausgabe(lauf={"status": treiber.WARTET_AUFTRAG},
                          auftrag={"flow": "wlo/volltext", "job_id": "job-9", "schritt": "lesen"})
    antwort = asyncio.run(freigabe_zug._festhalten(_S(), _req(), {"entities": {}}, object(), aus,
                                                   None, "person-a"))
    assert antwort is None and beendet == [aus.auftrag]
