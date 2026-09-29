"""Befund 3 der ST-5-Lesart (2026-09-27): bleibt ein Typwort in Agent-Sitzungen stehen?

Der Test fährt die echte Kette: ``merge`` (Material- und Medientyp-Heuristik) →
die Sitzungs-Entitäten, die ``turn_persist`` in ``debug.entities`` spiegelt und
für den nächsten Zug speichert → der Kartenfilter in
``_postprocess_response_for_widget_modes``. Unter der Agent-Schleife klassifiziert
niemand: ``assess`` liefert die Ersatz-Klassifikation (``I01``, ``initial``, keine
Entitäten), und ohne ``topic_switch`` leerte nichts die Typ-Slots der Sitzung.

Reproduziert vor dem Fix (beide Tests rot): der Folgezug verlor ALLE Karten, und
„Zusammenfassung" (Alias auf den Canvas-Typ ``infoblatt``) leerte die Liste schon
im ersten Zug — in beiden Maschinen.

Gepatcht sind nur die Grenzen: der spekulative Vorabruf (MCP), die Nachauswahl
v2, der Anzeige-Regel-Lader und die Ersatzsuche des Sicherheitsnetzes.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest

from boerdi.api.schemas import (
    ChatRequest,
    ChatResponse,
    ClassificationResult,
    DebugInfo,
    Environment,
    SafetyDecision,
)
from boerdi.graph import state as state_mod
from boerdi.graph.nodes import merge as merge_mod
from boerdi.graph.nodes.assess import _fallback_classification
from boerdi.graph.nodes.merge import merge
from boerdi.services.prefetch import SpeculativePrefetch
from boerdi.services.widget_postprocess import _postprocess_response_for_widget_modes

MOD = "boerdi.services.widget_postprocess"
DR = "boerdi.services.config_loader.load_display_rules_config"

_SAMMLUNG = {"node_id": "c1", "node_type": "collection", "title": "Bruchrechnung"}
_THEMENSEITE = {"node_id": "t1", "node_type": "collection", "title": "Brüche",
                "topic_pages": [{"variant_id": "v1", "url": "https://wlo.example/tp"}]}
_VIDEO = {"node_id": "i1", "node_type": "content", "title": "Brüche erklärt",
          "learning_resource_types": ["Video"]}
_KARTEN = [_SAMMLUNG, _THEMENSEITE, _VIDEO]


def _grenzen(monkeypatch):
    async def _kein_vorabruf(req, classification, safety):
        return SpeculativePrefetch(None, None, None, "", [], False, [])

    monkeypatch.setattr(merge_mod, "run_speculative_prefetch", _kein_vorabruf)
    monkeypatch.setattr(f"{MOD}.card_pipeline_v2_enabled", Mock(return_value=False))
    monkeypatch.setattr(f"{MOD}._fallback_inline_search", AsyncMock(return_value=[]))
    monkeypatch.setattr(DR, Mock(return_value={"quick_replies": {"max_count": 4}}))


def _sitzung() -> dict:
    return {"entities": {}, "persona_id": "", "state_id": "S1",
            "signal_history": [], "turn_count": 0}


async def _zug(sitzung: dict, nachricht: str, engine: str = "agent",
               klassifikation: ClassificationResult | None = None) -> ChatRequest:
    """Ein Zug bis einschließlich ``merge``.

    ``sitzung`` ist über die Züge hinweg dasselbe Dict — so wie ``setup`` die
    von ``turn_persist`` gespeicherten Entitäten im nächsten Zug zurückliest.
    Ohne ``klassifikation`` gilt, was ``assess`` unter der Schleife liefert.
    """
    req = ChatRequest(session_id="s-1", message=nachricht, environment=Environment())
    ctx = state_mod.TurnContext(req=req)
    ctx.session_state = sitzung
    ctx.classification = klassifikation or _fallback_classification(sitzung, "I01")
    ctx.safety = SafetyDecision()
    await merge(ctx, engine=engine)
    return req


def _muster_klassifikation(turn_type: str, **entities) -> ClassificationResult:
    return ClassificationResult(persona_id="P-LEH", intent_id="I03", next_state="S4",
                                turn_type=turn_type, entities=entities)


def _antwort(sitzung: dict, engine: str = "agent") -> ChatResponse:
    # Genau die Spiegelung aus ``turn_persist.build_debug_and_update_session``.
    entitaeten = {k: v for k, v in sitzung["entities"].items() if not k.startswith("_")}
    return ChatResponse(session_id="s-1", content="Zur Bruchrechnung gibt es einiges.",
                        cards=[dict(k) for k in _KARTEN],
                        debug=DebugInfo(entities=entitaeten, engine=engine))


def _ids(antwort: ChatResponse) -> list[str]:
    return [k.get("node_id") if isinstance(k, dict) else k.node_id for k in antwort.cards]


async def test_agent_folgezug_ohne_typwort_behaelt_alle_karten(monkeypatch):
    """Zug 1 nennt Arbeitsblätter, Zug 2 wechselt das Thema und nennt keinen Typ.

    Die Karten von Zug 2 hat der Agent selbst gesucht; kein Wort dieses Zugs
    verlangt einen Medientyp. Vor dem Fix filterte „arbeitsblatt" aus Zug 1
    weiter — auch das Video fiel heraus.
    """
    _grenzen(monkeypatch)
    sitzung = _sitzung()
    await _zug(sitzung, "Hast du Arbeitsblätter zur Photosynthese?")
    req = await _zug(sitzung, "Und was gibt es zur Bruchrechnung?")

    aus = await _postprocess_response_for_widget_modes(req, _antwort(sitzung))

    assert _ids(aus) == ["c1", "t1", "i1"]
    assert "medientyp" not in sitzung["entities"]
    assert "material_typ" not in sitzung["entities"]


async def test_agent_zug_mit_typwort_behaelt_die_karten_des_agenten(monkeypatch):
    """Bis Paket A (Agent-Runde 2, 2026-09-29) stand hier die Gegenprobe „der
    Filter selbst bleibt" (Erwartung ``["i1"]``). Das Tor E-5 hat sie widerlegt:
    der Agent legt die Materialart in den Filter seiner Suche (Master-Skill) und
    beschreibt deren Treffer; die zweite Auslegung der Nachricht nahm ihm in
    GV-LER-1#3 alle Karten („Übungen" → ``übung``, gesucht und beschrieben:
    Arbeitsblätter). Im Agent-Zug filtert die Nachbearbeitung darum gar nicht
    mehr. Die Muster-Maschine filtert weiter (Gegenprobe unten)."""
    _grenzen(monkeypatch)
    sitzung = _sitzung()
    req = await _zug(sitzung, "Hast du Videos zur Bruchrechnung?")

    aus = await _postprocess_response_for_widget_modes(req, _antwort(sitzung))

    assert _ids(aus) == ["c1", "t1", "i1"]


async def test_muster_folgezug_behaelt_den_medientyp(monkeypatch):
    """Gegenprobe Muster-Maschine: dort trägt der Klassifikator den Zugtyp, und
    ein ``follow_up`` behält den Medientyp absichtlich („nur Videos", dann
    „noch mehr davon"). Der Fix darf das nicht anfassen."""
    _grenzen(monkeypatch)
    sitzung = _sitzung()
    await _zug(sitzung, "Hast du Videos zur Bruchrechnung?", engine="pattern",
               klassifikation=_muster_klassifikation("initial", thema="Bruchrechnung"))
    req = await _zug(sitzung, "Noch mehr davon bitte", engine="pattern",
                     klassifikation=_muster_klassifikation("follow_up"))

    aus = await _postprocess_response_for_widget_modes(req, _antwort(sitzung, "pattern"))

    assert _ids(aus) == ["i1"]


@pytest.mark.parametrize("engine", ["agent", "pattern"])
async def test_aliasziel_ohne_wlo_typ_leert_die_karten_nicht(monkeypatch, engine):
    """„Zusammenfassung" ist ein Alias auf den Canvas-Typ ``infoblatt``.

    ``infoblatt`` hat kein Stichwort in ``_CONTENT_TYPE_KEYWORDS``; der
    Rohwort-Rückfall machte daraus ein Filterwort, das in keinem
    ``learning_resource_types`` steht — alle Karten fielen heraus.
    """
    _grenzen(monkeypatch)
    sitzung = _sitzung()
    klassifikation = (None if engine == "agent"
                      else _muster_klassifikation("initial", thema="Photosynthese"))
    req = await _zug(sitzung, "Hast du eine Zusammenfassung zur Photosynthese?",
                     engine=engine, klassifikation=klassifikation)

    aus = await _postprocess_response_for_widget_modes(req, _antwort(sitzung, engine))

    assert sitzung["entities"].get("material_typ") == "infoblatt"  # die Heuristik griff
    assert _ids(aus) == ["c1", "t1", "i1"]
