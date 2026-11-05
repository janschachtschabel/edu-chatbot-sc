"""Paket U2-d (Plan 2026-11-04, T-13): die Brücke „Als Entwurf bearbeiten“.

Im Bestandsbaum (``ui_themenbaum``) wählt die Person „Als Entwurf bearbeiten“; die Direktaktion
``edit_collection_as_draft`` holt die Sammlung über das Baum-Werkzeug — ohne LLM —, formt einen
Strukturentwurf (Titel, Beschreibung, Schlagworte, ``wlo_id``) und zeigt ihn als offene Frage.
Bestandsknoten erreichen die KI erst, wenn die Person den Entwurf übernimmt oder dazu schreibt.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest

from boerdi.api.schemas import ChatRequest, ChatResponse, Environment
from boerdi.domain.ui_bloecke import DEBUG_KEY
from boerdi.services import strukturentwurf_aktion as aktion
from boerdi.ui_module import datenquelle, katalog, schalter
from boerdi.ui_module import strukturentwurf as se
from boerdi.ui_module.antwort import OFFENE_FRAGE
from boerdi.ui_module.namen import STRUKTURENTWURF, THEMENBAUM
from boerdi.ui_module.strukturentwurf_bestand import aus_bestand
from tests.test_preflight_node import _SESSION

WURZEL = "aaaa1111-0000-4000-8000-000000000000"


def _uuid(n: int) -> str:
    return f"bbbb2222-0000-4000-8000-{n:012d}"


def _knoten(n: int, titel: str, **mehr: Any) -> dict:
    return {"nodeId": _uuid(n), "title": titel, "description": f"Über {titel}. " * 40,
            "keywords": [titel, "WLO"], "url": "https://wirlernenonline.de/x", **mehr}


def _payload(**mehr: Any) -> dict:
    return {"parent": WURZEL, "depth": 2, "total": 2, "results": [
        _knoten(1, "Algebra", hasMoreChildren=True, children=[_knoten(2, "Gleichungen"),
                                                              _knoten(3, "Terme")]),
        _knoten(4, "Geometrie")], **mehr}


# ── Umformung ─────────────────────────────────────────────────────────────

def test_aus_dem_bestand_wird_ein_gueltiger_entwurf():
    daten = aus_bestand(_payload(), "Mathematik")
    assert daten["quelle"] == "wlo" and daten["titel"] == "Mathematik"
    assert daten["wurzel_wlo_id"] == WURZEL and daten["gekuerzt"] is True   # hasMoreChildren
    algebra, geometrie = daten["knoten"]
    assert algebra["id"] == "k1" and algebra["wlo_id"] == _uuid(1)
    assert len(algebra["beschreibung"]) == se.BESCHREIBUNG_ZEICHEN
    assert algebra["keywords"] == ["Algebra", "WLO"]
    assert [k["id"] for k in algebra["kinder"]] == ["k1-1", "k1-2"]
    assert geometrie["id"] == "k2" and "kinder" not in geometrie
    manifest = katalog.katalog()[STRUKTURENTWURF]
    assert katalog.daten_fehler(manifest, daten) == [] and se.fehler(daten) == []


def test_ohne_titel_nimmt_der_entwurf_einen_festen():
    assert aus_bestand(_payload(), "")["titel"] == "Gliederung aus WLO"


def _viele(oben: int, kinder: int) -> dict:
    return {"parent": WURZEL, "results": [
        _knoten(i, f"T{i}", children=[_knoten(1000 + i * 20 + j, f"U{j}") for j in range(kinder)])
        for i in range(oben)]}


def test_mehr_als_der_deckel_oben_wird_gekappt_und_gekuerzt_gemeldet():
    daten = aus_bestand(_viele(31, 5), "Viel")
    assert len(daten["knoten"]) == se.HOECHSTENS_OBEN and daten["gekuerzt"] is True


def test_der_gesamtdeckel_gilt_auch_fuer_den_bestand():
    daten = aus_bestand(_viele(31, 12), "Viel")
    assert se.anzahl(daten["knoten"]) == se.HOECHSTENS_KNOTEN and daten["gekuerzt"] is True
    assert se.fehler(daten) == []


@pytest.mark.parametrize("payload", [None, {}, {"results": []}, {"results": [{"title": " "}]}])
def test_ohne_brauchbare_knoten_gibt_es_keinen_entwurf(payload):
    assert aus_bestand(payload, "x") is None


def test_unbrauchbare_kennungen_werden_kein_wlo_verweis():
    p = {"parent": "-userhome-", "results": [{"nodeId": "Mathematik", "title": "Algebra"}]}
    daten = aus_bestand(p, "x")
    assert "wurzel_wlo_id" not in daten and "wlo_id" not in daten["knoten"][0]


# ── Direktaktion ──────────────────────────────────────────────────────────

class _Spion:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def __call__(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append({"args": args, **kwargs})


class _Rufer:
    def __init__(self, text: str | None = None, art: str = "") -> None:
        self.calls: list[tuple[str, dict]] = []
        self.text, self.art = (json.dumps(_payload()) if text is None else text), art

    async def __call__(self, werkzeug: str, args: dict) -> tuple[str, str]:
        self.calls.append((werkzeug, dict(args)))
        return self.text, self.art


@pytest.fixture
def db(monkeypatch):
    save, update = _Spion(), _Spion()
    monkeypatch.setattr(aktion, "save_message", save)
    monkeypatch.setattr(aktion, "update_session", update)
    return save, update


def _req(module=(STRUKTURENTWURF, THEMENBAUM), **params: Any) -> ChatRequest:
    return ChatRequest(session_id="bb-1", message="Gliederung als Entwurf bearbeiten",
                       action="edit_collection_as_draft", action_params=params,
                       environment=Environment(ui_module=list(module)))


def _laufen(req: ChatRequest, state: dict | None = None) -> tuple[ChatResponse, dict]:
    state = {} if state is None else state
    return asyncio.run(aktion.handle_edit_collection_as_draft(
        _SESSION, req, state, blocked_tools=[])), state


def test_die_aktion_zeigt_den_entwurf_als_offene_frage(monkeypatch, db):
    rufer = _Rufer()
    monkeypatch.setattr(datenquelle, "_rufen", rufer)
    resp, state = _laufen(_req(collection_id=WURZEL, title="Mathematik"))
    assert rufer.calls == [("browse_collection_tree",
                            {"nodeId": WURZEL, "depth": 2, "maxResults": 31})]
    [block] = resp.ui.ui_bloecke
    assert block.modul == STRUKTURENTWURF and block.art == "abfragen" and block.status == "offen"
    assert block.daten["quelle"] == "wlo" and resp.quick_replies == []
    assert state["entities"][OFFENE_FRAGE]["block_id"] == block.block_id
    save, update = db
    assert update.calls[0]["entities"][OFFENE_FRAGE]["modul"] == STRUKTURENTWURF
    [gespeichert] = save.calls
    assert gespeichert["args"][2] == "assistant" and DEBUG_KEY in gespeichert["debug"]
    # Ohne LLM: kein Knotentitel im Text der Blase (der Verlauf geht als Text an die KI).
    assert "Algebra" not in resp.content and "Mathematik" in resp.content
    assert resp.debug.tools_called == [STRUKTURENTWURF]


@pytest.mark.parametrize("params", [{"collection_id": "Mathematik", "title": "x"},
                                    {"collection_id": "-userhome-"}, {}])
def test_eine_falsche_kennung_ruft_nichts(monkeypatch, db, params):
    rufer = _Rufer()
    monkeypatch.setattr(datenquelle, "_rufen", rufer)
    resp, _ = _laufen(_req(**params))
    assert rufer.calls == [] and not resp.ui.ui_bloecke


def test_ohne_gemeldetes_oder_aktives_modul_kein_aufruf(monkeypatch, db):
    rufer = _Rufer()
    monkeypatch.setattr(datenquelle, "_rufen", rufer)
    resp, _ = _laufen(_req(module=(THEMENBAUM,), collection_id=WURZEL))
    assert rufer.calls == [] and not resp.ui.ui_bloecke
    monkeypatch.setattr(schalter, "aktiv", lambda name: name != STRUKTURENTWURF)
    resp, _ = _laufen(_req(collection_id=WURZEL))
    assert rufer.calls == [] and "abgeschaltet" in resp.content


def test_ohne_angebotenes_baum_werkzeug_kein_aufruf(monkeypatch, db):
    rufer = _Rufer()
    monkeypatch.setattr(datenquelle, "_rufen", rufer)
    monkeypatch.setattr(aktion, "angebotene_mcp_werkzeuge", lambda **_kw: ["search_wlo_all"])
    resp, _ = _laufen(_req(collection_id=WURZEL, title="Mathematik"))
    assert rufer.calls == [] and not resp.ui.ui_bloecke and resp.quick_replies == []


def test_ein_fehler_des_werkzeugs_ergibt_einen_ehrlichen_satz(monkeypatch, db):
    monkeypatch.setattr(datenquelle, "_rufen", _Rufer("weg", "transport"))
    resp, state = _laufen(_req(collection_id=WURZEL, title="Mathematik"))
    assert not resp.ui.ui_bloecke and "nicht" in resp.content
    assert OFFENE_FRAGE not in state.get("entities", {})
    assert resp.quick_replies                                    # „Nochmal versuchen“


# ── Verteiler (preflight) ─────────────────────────────────────────────────


def test_der_verteiler_kennt_die_aktion_und_prueft_sie_wie_die_anderen(monkeypatch):
    from boerdi.api.schemas import SafetyDecision
    from boerdi.graph.nodes import preflight as pf_mod
    from boerdi.graph.nodes.preflight import preflight
    from tests.test_preflight_node import _ctx, _patch_db, _patch_handlers, _patch_safety, _Spy

    _patch_handlers(monkeypatch)
    entwurf = _Spy(ChatResponse(session_id="bb-1", content="ENTWURF-OK"))
    monkeypatch.setattr(pf_mod, "handle_edit_collection_as_draft", entwurf)
    _patch_db(monkeypatch)
    safety = _patch_safety(monkeypatch, SafetyDecision(risk_level="low", blocked_tools=["x"]))
    out = asyncio.run(preflight(_ctx(aktion.AKTION, collection_id=WURZEL, title="Mathe"),
                                _SESSION))
    assert out.early_response.content == "ENTWURF-OK"
    assert len(entwurf.calls) == 1 and len(safety.calls) == 1


# ── Review U2 (Frontend, Befund 9): die Brücke nur, wenn der Entwurf aktiv ist ──


def test_der_bestandsbaum_sagt_ob_die_bruecke_geht(monkeypatch):
    from boerdi.ui_module import themenbaum

    payload = {"parent": WURZEL, "results": [_knoten(1, "Algebra")]}
    daten = themenbaum.daten_aus(payload, "Mathematik")
    assert daten["entwurf_moeglich"] is True
    assert katalog.daten_fehler(katalog.katalog()[THEMENBAUM], daten) == []
    monkeypatch.setattr(schalter, "aktiv", lambda name: name != STRUKTURENTWURF)
    assert "entwurf_moeglich" not in themenbaum.daten_aus(payload, "Mathematik")



def test_drittes_review_2_die_bruecke_merkt_keinen_entwurf(monkeypatch, db):
    """Bestandsknoten erreichen die KI erst, wenn die Person den Entwurf zurückschickt — die
    Brücke schreibt deshalb nichts in den Entwurfs-Speicher der Sitzung."""
    from boerdi.ui_module import strukturentwurf_merken as merken

    monkeypatch.setattr(datenquelle, "_rufen", _Rufer())
    _resp, state = _laufen(_req(collection_id=WURZEL, title="Mathematik"))
    assert merken.KEY not in state["entities"]


def test_drittes_review_8_ohne_titel_ein_ersatz_in_der_sprache_der_person(monkeypatch, db):
    from boerdi.i18n import bot_text

    monkeypatch.setattr(datenquelle, "_rufen", _Rufer())
    req = _req(collection_id=WURZEL)
    req.environment.locale = "en"
    resp, _ = _laufen(req)
    assert resp.ui.ui_bloecke[0].daten["titel"] == bot_text("en", "action.draft.ohneTitel")
    assert aus_bestand(_payload(), "", ersatz_titel="X")["titel"] == "X"
