"""Paket S (Plan 2026-11-08), S2/S3: der Freigabe-Schritt im Zug.

- Der Schritt legt vor (ohne Schlüssel), merkt die Abnahme wie im Chat (mit Aufrufer und Marke) und
  zeigt Satz, Vorschau-Box und Chip; der Lauf wartet (``wartet_freigabe``).
- „ja“ löst der Vorlauf ein; danach geht der Lauf weiter (Erfolg → Teil, abgelehnt → ``bei_fehler``,
  Ausgang offen → Ende mit Fehler, ausgelastet → er wartet).
- Nein → „Vorschau erneut zeigen“; „Ablauf abbrechen“ endet ohne Schreiben.
"""

from __future__ import annotations

import asyncio
import copy
from types import SimpleNamespace

import pytest

from boerdi.api.schemas import ChatRequest, ChatResponse, Environment
from boerdi.domain.host_capabilities import LESEND
from boerdi.i18n.bot_text import bot_text
from boerdi.services import arbeitsstand, vorgaenge
from boerdi.services import write_approval as wa_mod
from boerdi.services.ablauf import ausloeser, freigabe_zug, treiber, zug, zug_basis
from boerdi.services.mcp.client import McpAntwort
from tests.test_ablauf_zug import _S, _Speicher
from tests.test_paket_s import _FREIGABE, W1

_SCHRITTE = [
    {"id": "anhaengen", "typ": "werkzeug", "werkzeug": W1, "freigabe": _FREIGABE,
     "argumente": {"nodeId": "n-1", "markdown": "# Optik", "source": "manual"},
     "schreibt": "angehaengt", "bei_fehler": "schade"},
    {"id": "fertig", "typ": "ende", "text": {"de": "Angehängt."}},
    {"id": "schade", "typ": "ende", "text": {"de": "Nicht angehängt."}},
]
_SCHLUESSEL = "Schluessel-0123456789abcd"
_SITZUNG = "sitzung-0123456789"


def _req(**mehr):
    return ChatRequest(session_id=_SITZUNG, **{"message": "", **mehr},
                       environment=Environment(locale="de"))


@pytest.fixture
def im_zug(monkeypatch):
    sp = _Speicher()
    for name in ("lesen", "juengster", "anlegen", "teil_setzen", "lauf_setzen", "teil_wert",
                 "beruehren", "alle_loeschen", "anonyme_der_sitzung_loeschen", "sitzung_setzen"):
        monkeypatch.setattr(vorgaenge, name, getattr(sp, name))
    for modul in (arbeitsstand, ausloeser):
        monkeypatch.setattr(modul, "has_personal_auth", lambda: True)
    for modul in (arbeitsstand, freigabe_zug, wa_mod):
        monkeypatch.setattr(modul, "aufrufer_kennung", lambda: "person-a")
    for modul in (freigabe_zug, wa_mod):
        monkeypatch.setattr(modul, "schreiben_erlaubt", lambda: True)

    async def nichts(*_a, **_k):
        return None

    for modul in (zug_basis, wa_mod):
        monkeypatch.setattr(modul, "save_message", nichts)
        monkeypatch.setattr(modul, "update_session", nichts)
    monkeypatch.setattr(freigabe_zug, "update_session", nichts)
    monkeypatch.setattr(freigabe_zug, "save_message", nichts)
    katalog = {"ablaeufe": [{"id": "anhaengen", "titel": {"de": "Anhängen"}, "aktiv": True,
                             "ausloeser": [{"art": "knopf"}], "voraussetzungen": ["anmeldung"],
                             "schritte": copy.deepcopy(_SCHRITTE)}]}
    monkeypatch.setattr(ausloeser, "area", lambda key: katalog if key == ausloeser.BEREICH else {})
    vorgelegt: list = []
    vorlagen: list = []

    async def vorlegen(name, args, *_rest):
        vorgelegt.append((name, args))
        return vorlagen.pop(0) if vorlagen else treiber.Vorlage("Vorschau: Volltext an n-1",
                                                                _SCHLUESSEL)

    monkeypatch.setattr(freigabe_zug, "_vorlegen", vorlegen)
    gerufen: list = []
    antworten: list = []

    async def mcp(tool, args, **_k):
        gerufen.append((tool, dict(args)))
        return antworten.pop(0)

    monkeypatch.setattr(wa_mod, "call_mcp_tool_antwort", mcp)
    return SimpleNamespace(speicher=sp, vorgelegt=vorgelegt, vorlagen=vorlagen, gerufen=gerufen,
                           antworten=antworten)


def _starte(state):
    return asyncio.run(zug.starten(_S(), _req(action=zug.AKTION,
                                              action_params={"ablauf": "anhaengen"}), state))


def _ja(state, nachricht="Ja, so ausführen"):
    async def lauf():
        vorher = state["entities"].get("_pending_write")
        anfrage = _req(message=nachricht)
        antwort = await wa_mod.redeem_write_approval(_S(), anfrage, state)
        assert antwort is not None
        return await freigabe_zug.nach_einloesen(_S(), anfrage, state, vorher, antwort)

    return asyncio.run(lauf())


def _lauf(state):
    return state["entities"][arbeitsstand.VERWEIS]["lauf"]


def _teile(im_zug):
    [v] = im_zug.speicher.v.values()
    return v.akte.get("teile") or {}


def test_s2_der_schritt_legt_vor_und_wartet(im_zug):
    state: dict = {"entities": {}}
    antwort = _starte(state)
    assert im_zug.vorgelegt == [(W1, {"nodeId": "n-1", "markdown": "# Optik",
                                      "source": "manual"})]
    assert _FREIGABE["de"] in antwort.content
    [box] = antwort.ui.ui_bloecke
    assert "Vorschau: Volltext an n-1" in str(box.model_dump())
    assert _SCHLUESSEL not in antwort.content and _SCHLUESSEL not in str(box.model_dump())
    assert antwort.quick_replies[0] == bot_text("de", "action.write.confirmChip")
    assert antwort.quick_replies[1].split("|")[2] == freigabe_zug.AKTION_ABBRECHEN
    offen = state["entities"]["_pending_write"]
    assert offen["tool"] == W1 and offen["token"] == _SCHLUESSEL and offen["caller"] == "person-a"
    marke = offen[freigabe_zug.MARKE]
    assert marke["ablauf"] == "anhaengen" and marke["schritt"] == "anhaengen" and marke["id"]
    assert _lauf(state)["status"] == treiber.WARTET_FREIGABE
    [v] = im_zug.speicher.v.values()
    assert v.akte["lauf"]["freigabe_id"] == marke["id"]


def test_s3_ja_loest_ein_und_der_lauf_geht_weiter(im_zug):
    state: dict = {"entities": {}}
    _starte(state)
    im_zug.antworten.append(McpAntwort("Volltext angehängt.",
                                       strukturiert={"nodeId": "n-1", "ok": True}))
    antwort = _ja(state)
    [(tool, args)] = im_zug.gerufen
    assert tool == W1 and args["confirmToken"] == _SCHLUESSEL and args["nodeId"] == "n-1"
    assert "Volltext angehängt." in antwort.content and "Angehängt." in antwort.content
    assert _lauf(state)["status"] == "fertig"
    assert _teile(im_zug)["angehaengt"]["wert"] == {"nodeId": "n-1", "ok": True}
    assert freigabe_zug.ERGEBNIS not in state


def test_s3_abgelehnt_geht_zu_bei_fehler(im_zug):
    state: dict = {"entities": {}}
    _starte(state)
    im_zug.antworten.append(McpAntwort("MCP error [refused]: nein", "tool", "refused",
                                       {"code": "refused", "message": "nein"}))
    antwort = _ja(state)
    assert "Nicht angehängt." in antwort.content and _lauf(state)["status"] == "fertig"
    assert "angehaengt" not in _teile(im_zug)


def test_s3_ausgang_offen_beendet_den_lauf(im_zug):
    state: dict = {"entities": {}}
    _starte(state)
    im_zug.antworten.append(McpAntwort("MCP error: keine Antwort", "timeout"))
    antwort = _ja(state)
    assert _lauf(state)["status"] == "fehler"
    assert "Nicht angehängt." not in antwort.content
    assert bot_text("de", "action.ablauf.fehler") in antwort.content


def test_s3_ausgelastet_laesst_den_lauf_warten(im_zug):
    state: dict = {"entities": {}}
    _starte(state)
    im_zug.antworten.append(McpAntwort("MCP error: voll", "busy"))
    _ja(state)
    assert _lauf(state)["status"] == treiber.WARTET_FREIGABE
    assert freigabe_zug.MARKE in state["entities"]["_pending_write"]


def test_s2_nein_dann_vorschau_erneut_zeigen(im_zug):
    state: dict = {"entities": {}}
    _starte(state)
    state["entities"].pop("_pending_write")              # ein Nein verwirft die Abnahme
    knopf = freigabe_zug.weiter_knopf(_SITZUNG, state, "de")
    assert knopf and knopf.split("|")[2] == freigabe_zug.AKTION_ERNEUT
    antwort = asyncio.run(freigabe_zug.erneut(_S(), _req(
        action=freigabe_zug.AKTION_ERNEUT, action_params={"ablauf": "anhaengen"}), state))
    assert len(im_zug.vorgelegt) == 2 and antwort.ui.ui_bloecke
    assert state["entities"]["_pending_write"]["token"] == _SCHLUESSEL
    assert freigabe_zug.weiter_knopf(_SITZUNG, state, "de") is None


def test_s2_ablauf_abbrechen(im_zug):
    state: dict = {"entities": {}}
    _starte(state)
    antwort = asyncio.run(freigabe_zug.abbrechen(_S(), _req(
        action=freigabe_zug.AKTION_ABBRECHEN, action_params={"ablauf": "anhaengen"}), state))
    assert antwort.content == bot_text("de", "action.ablauf.freigabeAbgebrochen")
    assert _lauf(state)["status"] == "abgebrochen" and im_zug.gerufen == []


def test_s2_nichts_zu_aendern_geht_gleich_weiter(im_zug):
    im_zug.vorlagen.append(treiber.Vorlage("Steht schon so da.", None))
    state: dict = {"entities": {}}
    antwort = _starte(state)
    assert "Angehängt." in antwort.content and _lauf(state)["status"] == "fertig"
    assert "_pending_write" not in state["entities"]
    assert _teile(im_zug)["angehaengt"]["wert"] == {"unveraendert": True}


def test_s2_ohne_vorschau_geht_es_zu_bei_fehler(im_zug, monkeypatch):
    async def keine(name, args, *_rest):
        return None

    monkeypatch.setattr(freigabe_zug, "_vorlegen", keine)
    state: dict = {"entities": {}}
    antwort = _starte(state)
    assert "Nicht angehängt." in antwort.content and "_pending_write" not in state["entities"]


def test_s3_neu_vorgelegt_traegt_die_marke_weiter(im_zug):
    state: dict = {"entities": {}}
    _starte(state)
    abgelaufen = McpAntwort("MCP error [confirm_expired]: alt", "tool", "confirm_expired",
                            {"code": "confirm_expired", "message": "alt"})
    neu = McpAntwort("Vorschau neu … confirmToken: Schluessel-neu-0123456789ab")
    im_zug.antworten.extend([abgelaufen, neu])
    _ja(state)
    offen = state["entities"]["_pending_write"]
    assert offen["token"] == "Schluessel-neu-0123456789ab"
    assert offen[freigabe_zug.MARKE]["schritt"] == "anhaengen"
    assert _lauf(state)["status"] == treiber.WARTET_FREIGABE


def test_s3_ohne_marke_aendert_sich_nichts():
    antwort = asyncio.run(freigabe_zug.nach_einloesen(
        _S(), _req(), {"entities": {}}, {"tool": W1},
        ChatResponse(session_id="s", content="x")))
    assert antwort.content == "x"



# ── Review S2/S3 ──────────────────────────────────────────────────────────────────────────────

def test_review_der_schluessel_steht_nicht_im_debug(im_zug, monkeypatch):
    gespeichert: list = []

    async def merke(*a, **k):
        gespeichert.append(k.get("debug"))

    monkeypatch.setattr(zug_basis, "save_message", merke)
    state: dict = {"entities": {}}
    antwort = _starte(state)
    assert _SCHLUESSEL not in str(antwort.debug.model_dump())
    assert _SCHLUESSEL not in str(gespeichert)
    assert "_pending_write" not in antwort.debug.entities


def _echt(monkeypatch, antwort, *, verborgen=False, tool_mode=None):
    """Das echte ``_vorlegen`` mit einer Attrappe des MCP-Aufrufs."""
    from boerdi.services import write_approval
    from boerdi.services.mcp import client

    aufrufe: list = []

    async def mcp(tool, args, **_k):
        aufrufe.append((tool, args))
        return antwort

    monkeypatch.setattr(client, "call_mcp_tool_antwort", mcp)
    monkeypatch.setattr(write_approval, "verborgene_werkzeuge",
                        lambda: {W1} if verborgen else set())
    env = Environment(locale="de", **({"tool_mode": tool_mode} if tool_mode else {}))
    anfrage = ChatRequest(session_id=_SITZUNG, message="", environment=env)
    vorlegen = freigabe_zug.vorleger(anfrage)
    args = {"nodeId": "n-1", "markdown": "# T", "source": "manual"}
    return asyncio.run(vorlegen(W1, args)) if vorlegen else None, aufrufe


@pytest.mark.parametrize("fall", ["verborgen", "lesend"])
def test_review_gesperrt_wird_nicht_vorgelegt(monkeypatch, fall):
    from boerdi.services import write_approval

    monkeypatch.setattr(freigabe_zug, "schreiben_erlaubt", lambda: True)
    monkeypatch.setattr(write_approval, "schreiben_erlaubt", lambda: True)
    vorlage, aufrufe = _echt(monkeypatch, McpAntwort("x"), verborgen=fall == "verborgen",
                             tool_mode=LESEND if fall == "lesend" else None)
    assert vorlage is None and aufrufe == []


def test_review_echtes_vorlegen(monkeypatch):
    from boerdi.services import write_approval

    for modul in (freigabe_zug, write_approval):
        monkeypatch.setattr(modul, "schreiben_erlaubt", lambda: True)
    # Schlüssel aus dem Text (kein strukturierter Teil), redigiert
    vorlage, _ = _echt(monkeypatch, McpAntwort("Vorschau … confirmToken: " + _SCHLUESSEL))
    assert vorlage.schluessel == _SCHLUESSEL and _SCHLUESSEL not in vorlage.text
    # vorübergehend und abgelehnt
    for art in ("busy", "transport", "timeout", "auth"):
        vorlage, _ = _echt(monkeypatch, McpAntwort("MCP error: x", art))
        assert vorlage.ausfall == "voruebergehend", art
    vorlage, _ = _echt(monkeypatch, McpAntwort(
        "MCP error [would_replace_file]: Datei da", "tool", "would_replace_file",
        {"code": "would_replace_file", "message": "Der Datensatz trägt eine Datei"}))
    assert vorlage.ausfall == "abgelehnt" and "Datei" in vorlage.text
    # zu große Angaben: nicht vorgelegt, nichts gerufen, mit Grund (Review S4, Befund 8)
    monkeypatch.setattr(freigabe_zug, "MAX_REMEMBERED_ARGS_BYTES", 10)
    vorlage, aufrufe = _echt(monkeypatch, McpAntwort("x"))
    assert vorlage.ausfall == "abgelehnt" and aufrufe == []
    assert vorlage.text == bot_text("de", "write.planTooLarge")


def test_review_voruebergehend_beim_vorlegen_wartet(im_zug):
    im_zug.vorlagen.append(treiber.Vorlage("Später bitte.", None, ausfall="voruebergehend"))
    state: dict = {"entities": {}}
    antwort = _starte(state)
    assert "Später bitte." in antwort.content and _lauf(state)["status"] == treiber.WARTET_FREIGABE
    assert antwort.quick_replies[0].split("|")[2] == freigabe_zug.AKTION_ERNEUT
    assert "_pending_write" not in state["entities"]


def test_review_abgelehnte_vorschau_nennt_den_grund_und_geht_zu_bei_fehler(im_zug):
    im_zug.vorlagen.append(treiber.Vorlage("Abgelehnt: trägt eine Datei.", None,
                                           ausfall="abgelehnt"))
    state: dict = {"entities": {}}
    antwort = _starte(state)
    assert "trägt eine Datei" in antwort.content and "Nicht angehängt." in antwort.content


def test_review_abgelaufen_und_ja(im_zug):
    state: dict = {"entities": {}}
    _starte(state)
    state["entities"]["_pending_write"]["minted_at"] = 0.0
    antwort = asyncio.run(freigabe_zug.vor_einloesen(_S(), _req(message="ja"), state))
    assert antwort.content == bot_text("de", "action.ablauf.freigabeAbgelaufen")
    assert antwort.quick_replies[0].split("|")[2] == freigabe_zug.AKTION_ERNEUT
    assert "_pending_write" not in state["entities"] and im_zug.gerufen == []
    # ohne Ja: still weg, der gewöhnliche Zug zeigt den Knopf
    _starte(state)
    state["entities"]["_pending_write"]["minted_at"] = 0.0
    assert freigabe_zug.weiter_knopf(_SITZUNG, state, "de") is not None
    assert asyncio.run(freigabe_zug.vor_einloesen(_S(), _req(message="was heißt das?"),
                                               state)) is None


def test_review_eine_alte_vorschau_setzt_keinen_neuen_lauf_fort(im_zug):
    state: dict = {"entities": {}}
    _starte(state)
    alt = copy.deepcopy(state["entities"]["_pending_write"])
    _starte(state)                                        # neu gestartet, eigene Vorlage
    state["entities"]["_pending_write"] = alt
    im_zug.antworten.append(McpAntwort("Volltext angehängt."))
    antwort = _ja(state)
    assert antwort.content == "Volltext angehängt."       # geschrieben, was die Person sah …
    assert _lauf(state)["status"] == treiber.WARTET_FREIGABE   # … der neue Lauf wartet weiter


def test_review_konflikt_nach_dem_schreiben_beendet_den_lauf(im_zug, monkeypatch):
    state: dict = {"entities": {}}
    _starte(state)
    echt = zug_basis.festhalten

    async def konflikt(*_a, **_k):
        raise vorgaenge.VorgangKonflikt()

    monkeypatch.setattr(zug_basis, "festhalten", konflikt)
    im_zug.antworten.append(McpAntwort("Volltext angehängt."))
    antwort = _ja(state)
    monkeypatch.setattr(zug_basis, "festhalten", echt)
    assert bot_text("de", "action.ablauf.freigabeKonflikt") in antwort.content
    [v] = im_zug.speicher.v.values()
    assert v.akte["lauf"]["status"] == "fehler"


def test_review_ohne_wirkung_verbraucht_bietet_die_vorschau_neu(im_zug):
    state: dict = {"entities": {}}
    _starte(state)
    im_zug.antworten.append(McpAntwort("MCP error [timeout]: zu langsam", "tool", "timeout",
                                       {"code": "timeout", "message": "zu langsam",
                                        "outcomeOpen": False}))
    antwort = _ja(state)
    assert antwort.quick_replies[0].split("|")[2] == freigabe_zug.AKTION_ERNEUT
    assert _lauf(state)["status"] == treiber.WARTET_FREIGABE


def test_review_das_ergebnis_ohne_schluesselfelder(im_zug):
    state: dict = {"entities": {}}
    _starte(state)
    im_zug.antworten.append(McpAntwort("ok", strukturiert={
        "nodeId": "n-1", "confirm": {"token": "x"}, "items": [{"confirmToken": "y", "a": 1}]}))
    _ja(state)
    assert _teile(im_zug)["angehaengt"]["wert"] == {"nodeId": "n-1", "items": [{"a": 1}]}



# ── Gesamt-Review Paket S ─────────────────────────────────────────────────────────────────────

def test_gesamt_ein_ja_nach_dem_abbruch_schreibt_nicht(im_zug):
    state: dict = {"entities": {}}
    _starte(state)
    offen = copy.deepcopy(state["entities"]["_pending_write"])
    asyncio.run(freigabe_zug.abbrechen(_S(), _req(
        action=freigabe_zug.AKTION_ABBRECHEN, action_params={"ablauf": "anhaengen"}), state))
    state["entities"]["_pending_write"] = offen          # die Abnahme aus einem anderen Gespräch
    antwort = asyncio.run(freigabe_zug.vor_einloesen(_S(), _req(message="ja"), state))
    assert antwort.content == bot_text("de", "action.ablauf.freigabeNichtMehrOffen")
    assert "_pending_write" not in state["entities"] and im_zug.gerufen == []


def test_gesamt_eine_passende_abnahme_laesst_den_vorlauf_einloesen(im_zug):
    state: dict = {"entities": {}}
    _starte(state)
    assert asyncio.run(freigabe_zug.vor_einloesen(_S(), _req(message="ja"), state)) is None
    assert "_pending_write" in state["entities"]


def test_gesamt_konflikt_nach_ablehnung_sagt_nicht_gespeichert(im_zug, monkeypatch):
    state: dict = {"entities": {}}
    _starte(state)

    async def konflikt(*_a, **_k):
        raise vorgaenge.VorgangKonflikt()

    monkeypatch.setattr(zug_basis, "festhalten", konflikt)
    im_zug.antworten.append(McpAntwort("MCP error [refused]: nein", "tool", "refused",
                                       {"code": "refused", "message": "nein"}))
    antwort = _ja(state)
    assert bot_text("de", "action.ablauf.freigabeKonflikt") not in antwort.content
    assert bot_text("de", "action.ablauf.konflikt") in antwort.content


def test_gesamt_nur_vorbereitet_beendet_den_lauf(im_zug, monkeypatch):
    state: dict = {"entities": {}}
    _starte(state)
    monkeypatch.setattr(freigabe_zug, "_nur_vorbereitet", lambda einloesung: True)
    im_zug.antworten.append(McpAntwort("Vorbereitet."))
    antwort = _ja(state)
    assert bot_text("de", "action.ablauf.freigabeVorbereitet") in antwort.content
    assert "Angehängt." not in antwort.content
    [v] = im_zug.speicher.v.values()
    assert v.akte["lauf"]["status"] == "fehler" and "angehaengt" not in (v.akte.get("teile") or {})
