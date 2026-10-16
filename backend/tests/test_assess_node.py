"""graph.nodes.assess — Safety ∥ Classify ∥ Memory Parallel-Gruppe (P4-3).

Port von ALT ``chat_pipeline_phases._assess_safety_classify_memory``. Getestet
mit Fakes (kein echtes LLM/DB): ``memory_fetch`` wird als Parameter injiziert
(Regel 3 — kein globaler Engine; der Graph-Bau P4-6 bindet das echte
``get_memory`` an die App-Engine), ``assess_safety``/``classify_input`` werden am
Node-Modul gemonkeypatcht. ``regex_gate`` läuft echt (rein) — die harte Krise
wird über eine echte Krisen-Nachricht ausgelöst.
"""

from __future__ import annotations

import asyncio

from boerdi.api.schemas import ChatRequest, ClassificationResult, SafetyDecision
from boerdi.graph import state as state_mod
from boerdi.graph.nodes import assess as assess_mod
from boerdi.graph.nodes.assess import assess
from boerdi.obs.progress import TurnProgress


def _ctx(message: str, session_state: dict | None = None) -> state_mod.TurnContext:
    ctx = state_mod.TurnContext(req=ChatRequest(session_id="s1", message=message))
    ctx.session_state = session_state if session_state is not None else {}
    return ctx


async def _memory_ok(session_id: str) -> list[dict]:
    return [{"key": "fach", "value": "Mathe", "memory_type": "short"}]


async def _memory_boom(session_id: str) -> list[dict]:
    raise RuntimeError("db down")


def test_crisis_short_circuits_without_llm(monkeypatch):
    called = {"safety": 0, "classify": 0, "memory": 0}

    async def _spy_safety(*a, **k):
        called["safety"] += 1
        return SafetyDecision(risk_level="low")

    async def _spy_classify(*a, **k):
        called["classify"] += 1
        return ClassificationResult()

    async def _spy_memory(session_id):
        called["memory"] += 1
        return []

    monkeypatch.setattr(assess_mod, "assess_safety", _spy_safety)
    monkeypatch.setattr(assess_mod, "classify_input", _spy_classify)

    ctx = _ctx("ich will mich umbringen", {"persona_id": "P-RED", "state_id": "S2"})
    out = asyncio.run(assess(ctx, _spy_memory))

    assert out.safety.risk_level == "high"
    assert out.safety.enforced_pattern == "M01"
    assert out.classification.intent_id == "I07"
    assert out.classification.intent_confidence == 0.0
    assert out.classification.persona_id == "P-RED"   # aus session_state
    assert out.classification.next_state == "S2"       # aus session_state
    assert out.classification.turn_type == "initial"
    assert out.memories == []
    # Kurzschluss VOR der Parallel-Gruppe → kein LLM/Memory-Aufruf.
    assert called == {"safety": 0, "classify": 0, "memory": 0}


def test_parallel_success_merges_all_three(monkeypatch):
    async def _safety(msg, signals):
        return SafetyDecision(risk_level="low", stages_run=["regex"])

    async def _classify(*a, **k):
        return ClassificationResult(persona_id="P-ENT", intent_id="I05", intent_confidence=0.9)

    monkeypatch.setattr(assess_mod, "assess_safety", _safety)
    monkeypatch.setattr(assess_mod, "classify_input", _classify)

    out = asyncio.run(assess(_ctx("wie erkläre ich bruchrechnung?"), _memory_ok))

    assert out.safety.risk_level == "low"
    assert out.classification.intent_id == "I05"
    assert out.memories == [{"key": "fach", "value": "Mathe", "memory_type": "short"}]


def test_safety_failure_falls_back_to_regex_gate(monkeypatch):
    async def _boom_safety(*a, **k):
        raise RuntimeError("moderation upstream 500")

    async def _classify(*a, **k):
        return ClassificationResult(intent_id="I05")

    monkeypatch.setattr(assess_mod, "assess_safety", _boom_safety)
    monkeypatch.setattr(assess_mod, "classify_input", _classify)

    out = asyncio.run(assess(_ctx("wie erkläre ich bruchrechnung?"), _memory_ok))
    # Fallback = regex_gate über dieselbe (benigne) Nachricht → low, nur Regex-Stufe.
    assert out.safety.risk_level == "low"
    assert out.safety.stages_run == ["regex"]
    assert out.classification.intent_id == "I05"   # classify lief normal durch


def test_classify_failure_falls_back_to_default(monkeypatch):
    async def _safety(*a, **k):
        return SafetyDecision(risk_level="low")

    async def _boom_classify(*a, **k):
        raise RuntimeError("instructor blew up")

    monkeypatch.setattr(assess_mod, "assess_safety", _safety)
    monkeypatch.setattr(assess_mod, "classify_input", _boom_classify)

    ctx = _ctx("wie erkläre ich bruchrechnung?", {"persona_id": "P-AND", "state_id": "S3"})
    out = asyncio.run(assess(ctx, _memory_ok))
    assert out.classification.intent_id == "I01"          # Default-Fallback (nicht I07)
    assert out.classification.intent_confidence == 0.0
    assert out.classification.persona_id == "P-AND"
    assert out.classification.next_state == "S3"


def test_memory_failure_falls_back_to_empty(monkeypatch):
    async def _safety(*a, **k):
        return SafetyDecision(risk_level="low")

    async def _classify(*a, **k):
        return ClassificationResult(intent_id="I05")

    monkeypatch.setattr(assess_mod, "assess_safety", _safety)
    monkeypatch.setattr(assess_mod, "classify_input", _classify)

    out = asyncio.run(assess(_ctx("wie erkläre ich bruchrechnung?"), _memory_boom))
    assert out.memories == []
    assert out.classification.intent_id == "I05"          # andere Zweige unberührt
    assert out.safety.risk_level == "low"


# ── C9: Fortschritts-Meldung ────────────────────────────────────────

def test_assess_reports_the_safety_classify_step(monkeypatch):
    """Der längste Abschnitt des Zuges (Safety+Classify, ~2,5 s) muss sich melden,
    bevor er anfängt — sonst zeigt das Widget hier nur den Spinner.

    ALT feuerte hier ``parallel_group("safety_classify_memory")``, das ausschließlich
    ein ``end`` emittiert; ``formatPhaseLabel`` verwirft ``end`` UND kennt nur
    ``safety_classify`` — in ALT blieb das Label deshalb dauerhaft tot. NEU sendet
    ``start`` unter dem Namen, den der Konsument (und ALTs eigenes
    ``trace_service``-Docstring-Beispiel) nennt.
    """
    async def _safety(*a, **k):
        return SafetyDecision(risk_level="low", stages_run=["regex"])

    async def _classify(*a, **k):
        return ClassificationResult(persona_id="P-ENT", intent_id="I05")

    monkeypatch.setattr(assess_mod, "assess_safety", _safety)
    monkeypatch.setattr(assess_mod, "classify_input", _classify)

    seen: list[dict] = []
    asyncio.run(assess(_ctx("wie erkläre ich bruchrechnung?"), _memory_ok,
                       progress=TurnProgress(seen.append)))
    assert seen[0]["step"] == "safety_classify"
    assert seen[0]["kind"] == "start"


def test_assess_reports_even_on_the_crisis_short_circuit():
    """Der Regex-Kurzschluss überspringt die LLMs — die Meldung darf er nicht
    überspringen, sonst hängt das Widget im vorherigen Label fest."""
    seen: list[dict] = []
    asyncio.run(assess(_ctx("ich will mich umbringen"), _memory_ok,
                       progress=TurnProgress(seen.append)))
    assert [e["step"] for e in seen] == ["safety_classify"]


# ── K1d: die Sicherheitsprüfung bucht auf den Zug-Merkposten ──────────────

def test_assess_reicht_den_merkposten_an_die_sicherheitspruefung(monkeypatch):
    seen: dict = {}

    async def _safety(message, signals=None, usage_acc=None):
        seen["usage_acc"] = usage_acc
        return SafetyDecision(risk_level="low")

    async def _classify(*a, **k):
        return ClassificationResult(intent_id="I05")

    monkeypatch.setattr(assess_mod, "assess_safety", _safety)
    monkeypatch.setattr(assess_mod, "classify_input", _classify)

    ctx = _ctx("wie erkläre ich bruchrechnung?")
    asyncio.run(assess(ctx, _memory_ok))

    assert seen["usage_acc"] is ctx.usage


def test_die_sicherheitspruefung_bucht_ihre_dauer(monkeypatch):
    """Plan 2026-09-30 (T8): Regex und Moderation laufen ohne eigenen
    LLM-Aufruf und fehlten deshalb im Debug-Block. Die Klassifikation braucht
    keinen Schritt — sie steht mit ihrer Dauer in ``per_phase.classify``."""
    async def _safety(msg, signals, **kwargs):
        return SafetyDecision(risk_level="low", stages_run=["regex"])

    async def _classify(*a, **k):
        return ClassificationResult(persona_id="P-LER", intent_id="I02", intent_confidence=0.9)

    monkeypatch.setattr(assess_mod, "assess_safety", _safety)
    monkeypatch.setattr(assess_mod, "classify_input", _classify)

    out = asyncio.run(assess(_ctx("wie erkläre ich bruchrechnung?"), _memory_ok))

    assert out.usage["zeiten_ms"]["assess.safety"] >= 0


# ── T1 (Paket 7): die Einbettung der Nachricht neben der Klassifikation ────
def test_die_einbettung_laeuft_neben_der_klassifikation(monkeypatch):
    """Nebenläufig, nicht danach: die Klassifikation wartet hier auf ein Zeichen,
    das erst die Einbettung gibt. Liefe sie danach, stünde der Zug (Frist)."""
    gestartet = asyncio.Event()

    async def _einbettung(text):
        gestartet.set()
        return text, [0.5]

    async def _safety(msg, signals, **k):
        return SafetyDecision(risk_level="low")

    async def _classify(*a, **k):
        await asyncio.wait_for(gestartet.wait(), timeout=2)
        return ClassificationResult(intent_id="I02")

    monkeypatch.setattr(assess_mod, "assess_safety", _safety)
    monkeypatch.setattr(assess_mod, "classify_input", _classify)
    monkeypatch.setattr(assess_mod, "rag_einbettung_vorab", _einbettung)
    out = asyncio.run(assess(_ctx("Was ist WLO?"), _memory_ok))
    assert out.classification.intent_id == "I02"
    assert out.rag_einbettung == ("Was ist WLO?", [0.5])


def test_im_agent_modus_wird_nicht_vorab_eingebettet(monkeypatch):
    """Die Schleife holt Wissen nur auf Zuruf, mit der Suchanfrage des Modells."""
    aufrufe: list[str] = []

    async def _einbettung(text):
        aufrufe.append(text)
        return text, [0.5]

    async def _safety(msg, signals, **k):
        return SafetyDecision(risk_level="low")

    monkeypatch.setattr(assess_mod, "assess_safety", _safety)
    monkeypatch.setattr(assess_mod, "rag_einbettung_vorab", _einbettung)
    out = asyncio.run(assess(_ctx("Was ist WLO?"), _memory_ok, engine="agent"))
    assert aufrufe == [] and out.rag_einbettung is None


def test_eine_gescheiterte_einbettung_kostet_den_zug_nicht(monkeypatch):
    async def _kaputt(text):
        raise RuntimeError("Einbettung weg")

    async def _safety(msg, signals, **k):
        return SafetyDecision(risk_level="low")

    async def _classify(*a, **k):
        return ClassificationResult(intent_id="I02")

    monkeypatch.setattr(assess_mod, "assess_safety", _safety)
    monkeypatch.setattr(assess_mod, "classify_input", _classify)
    monkeypatch.setattr(assess_mod, "rag_einbettung_vorab", _kaputt)
    out = asyncio.run(assess(_ctx("Was ist WLO?"), _memory_ok))
    assert out.classification.intent_id == "I02"
    assert out.rag_einbettung is None


def test_eine_langsame_einbettung_haelt_den_zug_nicht_auf(monkeypatch):
    """Review Paket 7 (B-1): die Vorarbeit war gegen Fehler geschützt, nicht gegen
    Zeit — ein langsamer Einbettungsdienst hielt JEDEN Muster-Zug auf, auch
    Suchzüge ohne RAG. Jetzt wartet ``assess`` nach der Klassifikation nur kurz
    nach und verwirft die Einbettung dann; der Abruf bettet selbst ein."""
    import time

    abgebrochen = asyncio.Event()

    async def _langsam(text):
        try:
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            abgebrochen.set()
            raise
        return text, [0.5]

    async def _safety(msg, signals, **k):
        return SafetyDecision(risk_level="low")

    async def _classify(*a, **k):
        return ClassificationResult(intent_id="I02")

    monkeypatch.setattr(assess_mod, "assess_safety", _safety)
    monkeypatch.setattr(assess_mod, "classify_input", _classify)
    monkeypatch.setattr(assess_mod, "rag_einbettung_vorab", _langsam)

    async def _lauf():
        t0 = time.perf_counter()
        out = await assess(_ctx("Was ist WLO?"), _memory_ok)
        return out, time.perf_counter() - t0, abgebrochen.is_set()

    out, dauer, weg = asyncio.run(_lauf())
    assert out.classification.intent_id == "I02"
    assert out.rag_einbettung is None
    assert dauer < 2, dauer          # Nachfrist, nicht die 5 s der Einbettung
    assert weg                       # keine Aufgabe bleibt liegen
