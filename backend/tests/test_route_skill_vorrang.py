"""Freigegebene Anleitungen schlagen die mitgelieferten Schnellwege (route.py).

**Der Fehler, den diese Datei festhält** (live gemessen 2026-08-16, Sammlung
„Optik" mit 28 freigegebenen Anleitungen): Auf „ich will einen stundenentwurf zu
optik erstellen" baute der Bot einen Lernpfad aus der Systemvorlage, statt den
redaktionell freigegebenen Skill „Stunde planen" zu laden.

Die Ursache ist eine Wortgleichheit, die kein Zufall ist: ``"stundenentwurf"``
steht in ``lp_intent._lp_keywords`` UND ist das Aktivierungs-Stichwort jenes
Skills. Der Schnellweg gewann, weil er zuerst dran war — und er kann bauartbedingt
kein ``get_skill`` rufen, denn er betritt die Werkzeugschleife nie.

**Der wichtigste Test ist der letzte: die Gegenrichtung.** Dieselbe Nachricht auf
einer Seite OHNE Anleitungen nimmt den Schnellweg weiterhin. Die Zusage „wo es
nichts Freigegebenes gibt, ändert sich nichts" gehört in einen Test, nicht in
einen Vorsatz — das ist dieselbe Regel, nach der ``test_route_engine_mode.py``
gebaut ist.

**Und was NICHT zurücktritt:** die Musterwahl. Sie liefert die Werkzeugliste, mit
der das Modell die Anleitung überhaupt erst holen kann; sie mit den Schnellwegen
zusammen abzuschalten hieße, dem Modell den Weg zu nehmen, den es gehen soll.
"""

from __future__ import annotations

import pytest

from boerdi.api.schemas import (
    ChatRequest,
    ClassificationResult,
    PolicyDecision,
    SafetyDecision,
)
from boerdi.domain.pattern_engine import PatternDef
from boerdi.graph import state as state_mod
from boerdi.graph.nodes import route as route_mod
from boerdi.graph.nodes.route import route
from boerdi.services.canvas_fast_path import CanvasFastPathResult
from boerdi.services.lp_fast_path import LpFastPathResult

# Die Nachricht aus dem Befund, wörtlich.
BEFUND = "ich will einen stundenentwurf zu optik erstellen"


def _ctx(*, message=BEFUND, skills=None, classification=None, bestand=None):
    """Ein Zug auf einer Seite, die ``skills`` freigegebene Anleitungen trägt.

    ``skills=None`` heißt „kein Seitenkontext" — der Zustand jeder Seite, die
    nicht angereichert wurde. Der Titel muss gesetzt sein, sonst gibt
    ``page_context.get_cached`` nichts zurück (es prüft genau darauf).

    ``bestand`` ist die ZWEITE Quelle: die Notiz, die ein früherer Zug dieses
    Gesprächs hinterlassen hat, weil er eine Sammlung mit Anleitungen zeigte.
    Genau die Lage des Sucheinstiegs — Karten ja, Seitenkontext nein.
    """
    ctx = state_mod.TurnContext(req=ChatRequest(session_id="s1", message=message))
    entities: dict = {}
    if skills is not None:
        entities["_page_metadata"] = {
            "title": "Optik",
            "context_facts": {"materials": 36, "skills": skills},
        }
    if bestand is not None:
        entities["_skill_bestand"] = bestand
    ctx.session_state = {
        "persona_id": "", "signal_history": [], "entities": entities, "state_id": "",
    }
    ctx.classification = classification or ClassificationResult(intent_id="I04")
    ctx.safety = SafetyDecision(risk_level="low")
    ctx.memories = []
    return ctx


def _patch(monkeypatch, seen):
    """Die Nachbarn abfangen; ``seen`` ist die Beweislage.

    Ein NICHT eingetragener Schlüssel heißt „nie gerufen" — dieselbe Bauart wie
    in ``test_route_engine_mode.py``.
    """
    win = PatternDef(id="M09", label="Suche")

    def _sel(**k):
        seen["select_pattern"] = k
        return (win, {"tools": [], "id": "M09"}, {"M09": 1.0}, [])

    def _dli(**k):
        seen["detect_lp_intent"] = k
        return (True, "Optik")

    async def _lp(**k):
        seen["run_lp_fast_path"] = k
        return LpFastPathResult(
            routed=False, response_text=None, wlo_cards_raw=None,
            tools_called=[], new_state=k["new_state"], qr_mode=None,
            qr_max=None, qr_spec_task=k["qr_spec_task"],
        )

    async def _cv(**k):
        seen["run_canvas_create_fast_path"] = k
        return CanvasFastPathResult(
            routed=False, payload_out=None, forced_quick_replies=[],
            response_text="", tools_called=k["tools_called"], wlo_cards_raw=[],
            new_state=k["new_state"],
        )

    monkeypatch.setattr(route_mod, "select_pattern", _sel)
    monkeypatch.setattr(route_mod, "detect_lp_intent", _dli)
    monkeypatch.setattr(route_mod, "run_lp_fast_path", _lp)
    monkeypatch.setattr(route_mod, "run_canvas_create_fast_path", _cv)
    monkeypatch.setattr(route_mod, "_qr_policy", lambda pid: ("exact", 4))
    monkeypatch.setattr(route_mod, "assess_policy", lambda **k: PolicyDecision())
    monkeypatch.setattr(route_mod, "validate_transition",
                        lambda **k: {"validated_state": k["next_"], "plausible": True,
                                     "reason": "", "prev_next_likely": []})
    monkeypatch.setattr(route_mod, "load_rag_config", dict)


# ── Der Vorrang greift ─────────────────────────────────────────────
@pytest.mark.anyio
async def test_mit_anleitungen_tritt_der_lernpfad_schnellweg_zurueck(monkeypatch):
    """Die Regressionsprüfung für den gemeldeten Fehler.

    ``detect_lp_intent`` würde „stundenentwurf" bejahen — der Patch oben gibt
    ausdrücklich ``(True, "Optik")`` zurück. Es darf gar nicht erst gefragt
    werden.
    """
    seen: dict = {}
    _patch(monkeypatch, seen)
    ctx = await route(_ctx(skills=28))
    assert "detect_lp_intent" not in seen
    assert seen["run_lp_fast_path"]["has_lp_intent"] is False
    assert ctx.lp_routed is False


@pytest.mark.anyio
async def test_mit_anleitungen_tritt_auch_der_canvas_schnellweg_zurueck(monkeypatch):
    """Der zweite Schnellweg ist genauso skill-blind — er bekommt einen eigenen
    Wächter, damit sein Ausbleiben nicht bloß eine Nebenwirkung des ersten ist."""
    seen: dict = {}
    _patch(monkeypatch, seen)
    ctx = await route(_ctx(classification=ClassificationResult(intent_id="I05"),
                           skills=28))
    assert "run_canvas_create_fast_path" not in seen
    assert ctx.canvas_routed is False


@pytest.mark.anyio
async def test_eine_einzige_anleitung_genuegt(monkeypatch):
    """Kein Schwellwert — die Regel des Nutzers kennt keinen."""
    seen: dict = {}
    _patch(monkeypatch, seen)
    await route(_ctx(skills=1))
    assert "detect_lp_intent" not in seen


# ── Was NICHT zurücktritt ──────────────────────────────────────────
@pytest.mark.anyio
async def test_die_musterwahl_laeuft_trotz_vorrang_weiter(monkeypatch):
    """Ohne Muster keine Werkzeugliste — und ohne Werkzeugliste kein
    ``get_skill``. Der Vorrang nimmt den Schnellweg, nicht den Weg."""
    seen: dict = {}
    _patch(monkeypatch, seen)
    ctx = await route(_ctx(skills=28))
    assert seen["select_pattern"]["intent_id"] == "I04"
    assert ctx.winner_id == "M09"


# ── Gegenrichtung ──────────────────────────────────────────────────
@pytest.mark.anyio
async def test_gegenrichtung_ohne_anleitungen_bleibt_der_schnellweg(monkeypatch):
    """Dieselbe Nachricht, dieselbe Absicht — nur ohne freigegebene Anleitungen.
    Hier ist der Schnellweg weiterhin richtig, denn es gibt nichts, dem er
    weichen müsste."""
    seen: dict = {}
    _patch(monkeypatch, seen)
    ctx = await route(_ctx())
    assert seen["detect_lp_intent"]["message"] == BEFUND
    assert seen["run_lp_fast_path"]["has_lp_intent"] is True
    assert "run_canvas_create_fast_path" in seen
    assert ctx.winner_id == "M09"


@pytest.mark.anyio
async def test_eine_seite_mit_null_anleitungen_ist_wie_keine(monkeypatch):
    """Eine angereicherte Seite, deren Registry leer war: Fakten sind da, aber
    sie sagen „nichts freigegeben". Der Schnellweg bleibt."""
    seen: dict = {}
    _patch(monkeypatch, seen)
    await route(_ctx(skills=0))
    assert seen["run_lp_fast_path"]["has_lp_intent"] is True


# ── Der Sucheinstieg: die Sammlung kam aus dem Gespräch ─────────────
# Ihr Testlauf 2026-08-16, zwei Züge: „Was gibt es zu Optik in Physik?" →
# Sammlung gefunden. „Erstelle mir dazu einen Stundenentwurf" → Vorlage statt
# Skill. Der Vorrang hing allein am Seitenkontext, den ein Sucheinstieg nicht
# hat — und damit lief der Lernpfad-Schnellweg wie vor allen Änderungen.
@pytest.mark.anyio
async def test_ohne_seite_zaehlt_die_sammlung_aus_dem_gespraech(monkeypatch):
    seen: dict = {}
    _patch(monkeypatch, seen)
    ctx = await route(_ctx(bestand={
        "anzahl": 28, "titel": "Geometrische Optik", "node_id": "f35c17d1"}))
    # Dieselbe Beweisform wie bei der Seite mit Anleitungen: der Body wird
    # gerufen, kehrt aber mit ``has_lp_intent=False`` sofort zurück — gefragt
    # wird der Head-Gate gar nicht erst.
    assert "detect_lp_intent" not in seen
    assert seen["run_lp_fast_path"]["has_lp_intent"] is False
    assert ctx.lp_routed is False
    assert "run_canvas_create_fast_path" not in seen
    assert ctx.winner_id == "M09", "die Musterwahl laeuft weiter — sie liefert die Werkzeuge"


@pytest.mark.anyio
async def test_eine_notiz_ueber_null_anleitungen_ist_wie_keine(monkeypatch):
    """Gegenrichtung zur zweiten Quelle: eine Notiz, die nichts meldet, ändert
    nichts. Dieselbe Zusage wie bei der Seite mit null Anleitungen."""
    seen: dict = {}
    _patch(monkeypatch, seen)
    await route(_ctx(bestand={"anzahl": 0, "titel": "", "node_id": ""}))
    assert seen["run_lp_fast_path"]["has_lp_intent"] is True
