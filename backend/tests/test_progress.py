"""C9 — ``obs/progress.TurnProgress``: die Emit-Naht für SSE-``phase``-Ereignisse.

Gepinnt wird die Form, die der Konsument liest: ``ui/stream/phase-label.ts``
(Verbatim-Port aus ALT ``chat/chat-text-utils.ts``) erwartet je Ereignis
``{kind, step, label, data}``, verwirft ``kind === "end"`` und schlägt ``step``
in einer Label-Map nach. Diese Datei prüft die Erzeuger-Seite; die Zustellung
über den Stream prüft ``test_chat_stream.py``.

Fail-Safe ist Vertrag: ein defekter Verbraucher (voller Queue, Ausnahme im Sink)
darf den Zug niemals abbrechen — ALT ``trace_service.Tracer._emit`` schluckt
Listener-Ausnahmen aus demselben Grund.
"""

from __future__ import annotations

from boerdi.obs.progress import TurnProgress


def _collect() -> tuple[TurnProgress, list[dict]]:
    seen: list[dict] = []
    return TurnProgress(seen.append), seen


def test_start_emits_the_shape_the_widget_reads():
    progress, seen = _collect()
    progress.start("wlo_search", "Durchsuche WLO-Inhalte")
    assert seen == [{
        "kind": "start",
        "step": "wlo_search",
        "label": "Durchsuche WLO-Inhalte",
        "data": {},
    }]


def test_record_carries_its_data():
    progress, seen = _collect()
    progress.record("query_meta", "MCP search queries", {"queries": 2})
    assert seen == [{
        "kind": "record",
        "step": "query_meta",
        "label": "MCP search queries",
        "data": {"queries": 2},
    }]


def test_missing_label_falls_back_to_the_step():
    """ALT ``Tracer.start``: ``self._cur_label = label or step``."""
    progress, seen = _collect()
    progress.start("policy")
    progress.record("context")
    assert [e["label"] for e in seen] == ["policy", "context"]


def test_data_is_copied_not_referenced():
    """Der Sink stellt zu; mutiert der Aufrufer sein Dict danach weiter, darf das
    bereits abgeschickte Ereignis sich nicht rückwirkend ändern."""
    progress, seen = _collect()
    payload = {"n": 1}
    progress.record("query_meta", "x", payload)
    payload["n"] = 99
    assert seen[0]["data"] == {"n": 1}


def test_without_a_sink_nothing_is_emitted_and_nothing_raises():
    """POST /api/chat baut denselben Graphen ohne Stream — die Knoten rufen
    ``progress`` unbedingt auf, also muss der sink-lose Fall stumm tragen."""
    progress = TurnProgress()
    progress.start("pattern", "Pattern selection")
    progress.record("context", "Context snapshot built", {"a": 1})


def test_a_raising_sink_never_breaks_the_turn():
    def _boom(_event):
        raise RuntimeError("consumer gone")

    progress = TurnProgress(_boom)
    progress.start("response", "LLM response generation")  # darf nicht werfen


def test_emissions_keep_their_order():
    progress, seen = _collect()
    for step in ("safety_classify", "context", "policy", "pattern"):
        progress.start(step)
    assert [e["step"] for e in seen] == [
        "safety_classify", "context", "policy", "pattern",
    ]
