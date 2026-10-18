"""Judge v2 (Paket 13, C2–C4): ein Urteil je Ablauf, knapp je Zug.

Wie der Judge v1 (``judge.py``): ein Aufruf über ``llm.chat_completion`` im Hintergrund-Kanal,
Temperatur 0, JSON-Antwort, das Modell aus ``scenario_gen.judge_model()`` (leer = Chat-Modell).
Ein unbrauchbares Urteil **wirft** ``JudgeError`` — die Aufrufer vermerken es, statt eine stille
Note einzurechnen. Noten werden auf 1–5 geklemmt; eine fehlende Skala ist kein Urteil.

Der Merkposten ``usage_acc`` (Phasen ``judge_ablauf``/``judge_zug``) sammelt die Judge-Kosten
eines Laufs getrennt von den Chat-Zügen.
"""

from __future__ import annotations

import json
from typing import Any

from boerdi.services.eval import prompts_v2
from boerdi.services.eval.judge import JudgeError
from boerdi.services.eval.scenario_gen import judge_model
from boerdi.services.llm import chat_completion

_STATEMENT_ZEICHEN = 800
_GRUND_ZEICHEN = 300
_AUFFAELLIGKEITEN = 8
_BERICHT_ZEICHEN = 2000


async def _urteil(prompt: str, phase: str, usage_acc: dict[str, Any] | None) -> dict[str, Any]:
    try:
        resp = await chat_completion(
            messages=[{"role": "user", "content": prompt}],
            model=judge_model(), temperature=0.0,
            response_format={"type": "json_object"}, background=True,
            usage_acc=usage_acc, phase=phase,
        )
        roh = (resp.choices[0].message.content or "").strip()
        daten = json.loads(roh) if roh else None
    except Exception as fehler:
        raise JudgeError(f"Judge-Aufruf fehlgeschlagen: {fehler}") from fehler
    if not isinstance(daten, dict):
        raise JudgeError(f"Judge-Antwort ist kein JSON-Objekt (content={roh[:80]!r})")
    return daten


def _note(wert: Any) -> int:
    """Eine Note 1–5, gerundet — `int()` schnitt 4,6 auf 4 und nahm `True` als 1."""
    if isinstance(wert, bool):
        raise JudgeError(f"Note unlesbar: {wert!r}")
    try:
        return max(1, min(5, round(float(wert))))
    except (TypeError, ValueError) as fehler:
        raise JudgeError(f"Note unlesbar: {wert!r}") from fehler


def _skalen(daten: dict[str, Any], schluessel: dict[str, str]) -> dict[str, dict[str, Any]]:
    roh = daten.get("skalen")
    if not isinstance(roh, dict):
        raise JudgeError("Judge-Antwort ohne Skalen")
    fehlend = [k for k in schluessel if k not in roh]
    if fehlend:
        raise JudgeError(f"Skalen fehlen: {', '.join(fehlend)}")
    skalen: dict[str, dict[str, Any]] = {}
    for k in schluessel:
        eintrag = roh[k] if isinstance(roh[k], dict) else {"note": roh[k]}
        skalen[k] = {"note": _note(eintrag.get("note")),
                     "grund": str(eintrag.get("grund") or "")[:_GRUND_ZEICHEN]}
    return skalen


def _auffaelligkeiten(roh: Any) -> list[dict[str, Any]]:
    aus: list[dict[str, Any]] = []
    for eintrag in roh if isinstance(roh, list) else []:
        if not isinstance(eintrag, dict) or not str(eintrag.get("text") or "").strip():
            continue
        zug = eintrag.get("zug")
        art = str(eintrag.get("art") or "")
        aus.append({
            "zug": zug if isinstance(zug, int) and not isinstance(zug, bool) else None,
            "art": art if art in prompts_v2.AUFFAELLIGKEIT_ARTEN else "sonstiges",
            "text": str(eintrag["text"])[:_GRUND_ZEICHEN],
        })
    return aus[:_AUFFAELLIGKEITEN]


async def judge_ablauf(
    gespraech: dict[str, Any], zielgruppe: dict[str, Any],
    *, usage_acc: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Das Urteil über den ganzen Verlauf: Skalen, Gesamt, Statement, Auffälligkeiten."""
    daten = await _urteil(prompts_v2.ablauf_prompt(gespraech, zielgruppe), "judge_ablauf",
                          usage_acc)
    return {
        "skalen": _skalen(daten, prompts_v2.ABLAUF_SKALEN),
        "gesamt": _note(daten.get("gesamt")),
        "statement": str(daten.get("statement") or "")[:_STATEMENT_ZEICHEN],
        "auffaelligkeiten": _auffaelligkeiten(daten.get("auffaelligkeiten")),
        "fassung": prompts_v2.JUDGE_V2_FASSUNG,
    }


async def judge_zug(
    gespraech: dict[str, Any], index: int, zielgruppe: dict[str, Any],
    *, usage_acc: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Das Urteil über ``turns[index]`` mit dem Verlauf davor.

    Flach wie der Judge v1 (``turn["judge"]``): die Skalen als Zahlen, dazu ``total``
    (= (gesamt − 1) / 4, 0–1) und ``notes`` — so lesen Laufliste und Lauf-Detail von heute
    weiter eine Note, bis sie die neuen Felder zeigen.
    """
    daten = await _urteil(prompts_v2.zug_prompt(gespraech, index, zielgruppe), "judge_zug",
                          usage_acc)
    skalen = _skalen(daten, prompts_v2.ZUG_SKALEN)
    gesamt = _note(daten.get("gesamt"))
    notiz = str(daten.get("notiz") or "")[:_GRUND_ZEICHEN]
    return {
        **{k: v["note"] for k, v in skalen.items()},
        "gruende": {k: v["grund"] for k, v in skalen.items()},
        "gesamt": gesamt, "notiz": notiz,
        "total": round((gesamt - 1) / 4, 3), "notes": notiz,
        "fassung": prompts_v2.JUDGE_V2_FASSUNG,
    }


async def kurzbericht(
    auswertung: dict[str, Any], *, usage_acc: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Einschätzung des ganzen Laufs (5–8 Sätze) und höchstens drei Baustellen."""
    daten = await _urteil(prompts_v2.bericht_prompt(auswertung), "judge_bericht", usage_acc)
    text = str(daten.get("text") or "").strip()
    if not text:
        raise JudgeError("Kurzbericht ohne Text")
    baustellen = []
    for b in daten.get("baustellen") if isinstance(daten.get("baustellen"), list) else []:
        if isinstance(b, dict) and str(b.get("text") or "").strip():
            ablauf = b.get("ablauf")
            baustellen.append({"ablauf": ablauf if isinstance(ablauf, str) and ablauf else None,
                               "text": str(b["text"])[:_GRUND_ZEICHEN]})
    return {"text": text[:_BERICHT_ZEICHEN], "baustellen": baustellen[:3],
            "fassung": prompts_v2.JUDGE_V2_FASSUNG}
