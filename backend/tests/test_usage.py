"""P3-1: token-usage extraction + per-turn accumulator — port of ALT
llm_usage.py (_extract_usage / usage_accumulator_new / usage_accumulator_add).
The accumulator dict is the shape that lands in DebugInfo.token_usage.
"""

from __future__ import annotations

from types import SimpleNamespace

from boerdi.obs import usage


def _resp(prompt: int, completion: int, cached: int, model: str,
          reasoning: int = 0) -> SimpleNamespace:
    return SimpleNamespace(
        model=model,
        usage=SimpleNamespace(
            prompt_tokens=prompt,
            completion_tokens=completion,
            prompt_tokens_details=SimpleNamespace(cached_tokens=cached),
            completion_tokens_details=SimpleNamespace(reasoning_tokens=reasoning),
        ),
    )


def test_extract_usage_reads_cached_from_details() -> None:
    got = usage.extract_usage(_resp(100, 40, 64, "gpt-5.6-luna"))
    assert got == {"prompt": 100, "completion": 40, "cached": 64, "reasoning": 0,
                   "model": "gpt-5.6-luna"}


def test_extract_usage_missing_usage_is_zero() -> None:
    got = usage.extract_usage(SimpleNamespace(model="m", usage=None))
    assert got == {"prompt": 0, "completion": 0, "cached": 0, "reasoning": 0, "model": "m"}


def test_extract_usage_no_details_defaults_cached_zero() -> None:
    resp = SimpleNamespace(model="m", usage=SimpleNamespace(
        prompt_tokens=10, completion_tokens=5, prompt_tokens_details=None,
        completion_tokens_details=None))
    got = usage.extract_usage(resp)
    assert got["cached"] == 0 and got["reasoning"] == 0


# ── Die beiden „davon"-Felder gegen die echten LiteLLM-Typen ───────────
# Nicht gegen eine nachgebaute Attrappe: der P11-Probelauf hat zweimal gezeigt,
# dass eine nach dem Code gebaute Attrappe die Annahme des Codes teilt, statt
# die Wirklichkeit abzubilden. Die Attrappen oben pinnen die Verzweigungen
# (fehlende Details, fehlendes ``usage``); diese beiden pinnen die Feldnamen.

def test_reasoning_wird_aus_echten_litellm_typen_gelesen() -> None:
    from litellm.types.utils import (
        CompletionTokensDetailsWrapper,
        ModelResponse,
        Usage,
    )

    u = Usage(prompt_tokens=10, completion_tokens=20,
              completion_tokens_details=CompletionTokensDetailsWrapper(reasoning_tokens=8))
    got = usage.extract_usage(ModelResponse(model="m", usage=u))

    assert got["reasoning"] == 8
    # „davon"-Feld: Reasoning steckt INNERHALB von completion — wer addiert,
    # zahlt doppelt. Deshalb bleibt completion die Gesamtzahl.
    assert got["completion"] == 20


def test_cached_wird_aus_echten_litellm_typen_gelesen() -> None:
    """Dasselbe für ``cached`` — und hier hängt Geld dran.

    ``cached`` entscheidet, welcher der beiden Eingabepreise gilt. Benennt
    LiteLLM das Feld um, liefert ``getattr`` still 0, und jeder
    zwischengespeicherte Token wird zum VOLLEN Eingabepreis abgerechnet, ohne
    dass ein Test rot wird. Die Attrappe oben kann das nicht bemerken: sie
    trägt denselben Namen, den der Code liest.
    """
    from litellm.types.utils import (
        ModelResponse,
        PromptTokensDetailsWrapper,
        Usage,
    )

    u = Usage(prompt_tokens=100, completion_tokens=40,
              prompt_tokens_details=PromptTokensDetailsWrapper(cached_tokens=64))
    got = usage.extract_usage(ModelResponse(model="m", usage=u))

    assert got["cached"] == 64
    # Wie beim Reasoning: ``cached`` steckt INNERHALB von prompt.
    assert got["prompt"] == 100


def test_reasoning_summiert_in_gesamt_modell_und_phase() -> None:
    acc = usage.new_accumulator()
    usage.add_usage(acc, usage.extract_usage(_resp(10, 20, 0, "m1", reasoning=8)),
                    phase="response")
    usage.add_usage(acc, usage.extract_usage(_resp(10, 5, 0, "m1", reasoning=2)),
                    phase="response")

    assert acc["reasoning_tokens"] == 10
    assert acc["models"]["m1"]["reasoning"] == 10
    assert acc["per_phase"]["response"]["reasoning"] == 10


def test_accumulator_sums_totals_models_and_phases() -> None:
    acc = usage.new_accumulator()
    assert acc == {"prompt_tokens": 0, "completion_tokens": 0, "cached_tokens": 0,
                   "reasoning_tokens": 0, "calls": 0, "models": {}, "per_phase": {}}

    usage.add_usage(acc, usage.extract_usage(_resp(100, 40, 64, "m1")), phase="classify")
    usage.add_usage(acc, usage.extract_usage(_resp(200, 60, 0, "m1")), phase="response")
    usage.add_usage(acc, usage.extract_usage(_resp(50, 10, 10, "m2")), phase="response")

    assert acc["prompt_tokens"] == 350
    assert acc["completion_tokens"] == 110
    assert acc["cached_tokens"] == 74
    assert acc["calls"] == 3
    assert acc["models"]["m1"] == {"prompt": 300, "completion": 100, "cached": 64,
                                   "reasoning": 0, "calls": 2}
    assert acc["models"]["m2"] == {"prompt": 50, "completion": 10, "cached": 10,
                                   "reasoning": 0, "calls": 1}
    assert acc["per_phase"]["classify"]["calls"] == 1
    assert acc["per_phase"]["response"] == {
        "prompt": 250, "completion": 70, "cached": 10, "reasoning": 0, "calls": 2}


def test_add_usage_ignores_empty() -> None:
    acc = usage.new_accumulator()
    usage.add_usage(acc, {})
    usage.add_usage(None, {"prompt": 5})
    assert acc["calls"] == 0


def test_add_usage_without_phase_skips_per_phase() -> None:
    acc = usage.new_accumulator()
    usage.add_usage(acc, usage.extract_usage(_resp(10, 5, 0, "m")))
    assert acc["calls"] == 1 and acc["per_phase"] == {}
    assert acc["models"]["m"]["prompt"] == 10


def test_unknown_model_bucketed() -> None:
    acc = usage.new_accumulator()
    usage.add_usage(acc, {"prompt": 3, "completion": 1, "cached": 0, "model": ""})
    assert "unknown" in acc["models"]


# ── K1e: der Merkposten dieses Zuges als ContextVar ──────────────────────

def test_current_turn_usage_ist_none_ohne_zug() -> None:
    # Ausserhalb eines Zuges (Start-Vorwaermung, Werkzeug ohne Zug) darf es
    # keinen Merkposten geben — ``None`` statt eines leeren Dicts, weil ein
    # leeres Dict lautlos nichts buchen wuerde (Fehler M0).
    usage.bind_turn_usage(None)
    assert usage.current_turn_usage() is None


def test_bind_turn_usage_gibt_dasselbe_objekt_zurueck() -> None:
    # Identitaet, nicht Gleichheit: ``add_usage`` veraendert das Dict an Ort
    # und Stelle. Nur wenn es DASSELBE Objekt ist wie ``TurnContext.usage``,
    # landet eine Buchung aus der Tiefe im Zug.
    acc = usage.new_accumulator()
    usage.bind_turn_usage(acc)
    try:
        assert usage.current_turn_usage() is acc
    finally:
        usage.bind_turn_usage(None)


def test_zwei_gleichzeitige_zuege_sehen_sich_nicht() -> None:
    # Die Sicherheitszusage des ContextVar: zwei Zuege im selben Prozess
    # buchen nicht gegenseitig. Ohne echten Aufgabenwechsel waere der Test
    # wertlos, deshalb das ``sleep(0)`` zwischen Binden und Lesen.
    import asyncio

    async def zug(marke: str) -> str:
        acc = usage.new_accumulator()
        acc["marke"] = marke
        usage.bind_turn_usage(acc)
        await asyncio.sleep(0)
        usage.add_usage(usage.current_turn_usage(),
                        {"prompt": 1, "completion": 0, "model": "m"})
        return usage.current_turn_usage()["marke"]

    async def beide() -> list[str]:
        return await asyncio.gather(zug("A"), zug("B"))

    assert asyncio.run(beide()) == ["A", "B"]
