"""Soft quality layer for a golden run (port of ALT ``eval_golden.py``'s
judge + aggregation block, C3).

The deterministic half of a golden run lives in ``evals/run_golden.py``: it
fires the flows, applies the hard Soll-Ist checks and computes the scorecard.
That file must stay importable without the backend package (framework-free CLI
for reference/A-B runs, see its README), so the LLM judge cannot live there.
This module is the framework-side other half:

* ``bewerte_gespraeche`` scores every answered turn and every flow via
  ``eval/judge_v2.py`` (Paket 13: scales 1–5, flow statement);
* ``kurzbericht_erstellen`` sums the judged run up in a few sentences (Paket 13, D2);
* ``kennzahlen_des_laufs`` keeps the compact figures the trends read (D5);
* ``summarize_golden_run`` composes the run summary from the three aggregators.

The headline stays deterministic. ``avg_score`` is the hard pass rate — the
same number the scorecard shows — and the judge average is reported next to it
as ``judge_avg``. Mixing the judge into the headline would make the run list
and the scorecard disagree about the same run, and would make a rerun with a
warmer judge look like a quality improvement.

Persistence is deliberately absent: ``eval_service`` owns every DB write.
"""

from __future__ import annotations

import logging
from typing import Any

from boerdi.services.config_loader import load_persona_definitions, load_pricing
from boerdi.services.eval import auswertung_v2, vergleich_v2
from boerdi.services.eval.auswertung_v2 import KEINE_ANTWORT
from boerdi.services.eval.judge import _build_persona_expectations
from boerdi.services.eval.judge_v2 import judge_ablauf, judge_zug, kurzbericht
from boerdi.services.eval.metrics import (
    _aggregate,
    _aggregate_classification_metrics,
    count_chat_error_turns,
    count_judge_failed_turns,
)
from boerdi.services.eval.run_profile import price_from_table

logger = logging.getLogger(__name__)


def _stub(entity_id: str) -> dict[str, str]:
    """Placeholder definition for an id the config does not know.

    The judge prompt renders ``label`` and ``description``; handing it ``None``
    would put "None" into the rubric.
    """
    return {"id": entity_id, "label": entity_id, "description": ""}


def _persona_erwartungen(persona_id: str) -> str:
    """Ton- und Anrede-Regeln der Zielgruppe aus der Konfiguration (Rubrik des Judge v1)."""
    return _build_persona_expectations(persona_id)


async def bewerte_gespraeche(
    conversations: list[dict[str, Any]], *, usage_acc: dict[str, Any] | None = None,
) -> dict[str, int]:
    """Judge v2 (Paket 13): jeden beantworteten Zug, dann jeden Ablauf bewerten, in place.

    Zug-Urteile stehen in ``turn["judge"]`` (flach, mit ``total`` 0–1 wie im Judge v1 — so
    lesen Laufliste und ``judge_avg`` weiter eine Note), das Ablauf-Urteil in ``conv["urteil"]``.
    Ein Ausfall wird vermerkt (``turn["judge_failed"]`` bzw. ``conv["urteil_fehler"]``) und nie
    als Note gezählt (GV4). Züge mit ``error`` sind übersprungen: die Person bekam keine Antwort.
    Ein Ablauf ganz ohne Antwort bekommt kein Urteil — der Judge sähe nichts.

    Die Zielgruppe (``zielgruppe``, sonst ``persona_id``) kommt einmal je Lauf aus der
    Konfiguration; ``usage_acc`` sammelt die Kosten aller Judge-Aufrufe.
    """
    definitionen = {p.get("id"): p for p in load_persona_definitions()}
    zielgruppen: dict[str, dict[str, Any]] = {}
    zahl = {"zuege": 0, "ablaeufe": 0}
    for conv in conversations:
        gid = str(conv.get("zielgruppe") or conv.get("persona_id") or "*")
        if gid not in zielgruppen:
            bekannt = definitionen.get(gid)
            basis = bekannt or _stub(gid)
            zielgruppen[gid] = {
                "id": gid, "label": basis.get("label") or gid,
                "description": basis.get("description") or "",
                "erwartungen": _persona_erwartungen(gid) if bekannt else "",
            }
        zielgruppe = zielgruppen[gid]
        beantwortet = 0
        for index, turn in enumerate(conv.get("turns") or []):
            if turn.get("error"):
                continue
            beantwortet += 1
            try:
                turn["judge"] = await judge_zug(conv, index, zielgruppe, usage_acc=usage_acc)
            except Exception as fehler:
                logger.warning("[golden] Zug-Urteil fehlgeschlagen: %s", fehler)
                turn["judge_failed"] = str(fehler)[:200]
                continue
            zahl["zuege"] += 1
        if not beantwortet:
            conv["urteil_fehler"] = KEINE_ANTWORT
            continue
        try:
            conv["urteil"] = await judge_ablauf(conv, zielgruppe, usage_acc=usage_acc)
        except Exception as fehler:
            logger.warning("[golden] Ablauf-Urteil fehlgeschlagen: %s", fehler)
            conv["urteil_fehler"] = str(fehler)[:200]
            continue
        zahl["ablaeufe"] += 1
    return zahl


def kennzahlen_des_laufs(conversations: list[dict[str, Any]]) -> dict[str, Any]:
    """Kompakte Kennzahlen eines Laufs für die Trends (Paket 13, D5), beim Abschluss gespeichert.

    Die Trend-Abfrage lädt keine Transkripte (Paket 4, E1) — Noten, Latenz, Kosten und die
    Prompt-Fassungen stehen deshalb im Summary. Die Kosten gelten zum Preis beim Abschluss.
    """
    g = auswertung_v2.auswerten({"conversations": conversations},
                                price_from_table(load_pricing()))["gesamt"]
    return {"gesamt_mittel": g["gesamt_mittel"], "skalen_mittel": g["skalen_mittel"],
            "zug_mittel": g["zug_mittel"], "latenz_p50_ms": g["latenz"]["p50_ms"],
            "kosten_je_zug": g["kosten_je_zug"],
            "prompts": vergleich_v2.prompt_fassungen({"conversations": conversations})}


async def kurzbericht_erstellen(
    conversations: list[dict[str, Any]], *, usage_acc: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Kurzbericht über den bewerteten Lauf (Paket 13, D2): ``{"text", "baustellen"}``.

    Der Judge sieht die Auswertung (``auswertung_v2``), nicht die Gespräche — Kennzahlen,
    Statements je Ablauf und schwache Zellen. Ein Ausfall kommt als ``{"fehler": …}`` zurück;
    der Lauf bleibt gültig, ihm fehlt nur der Bericht.
    """
    # Ohne ein einziges Urteil (Judge ganz ausgefallen) schriebe ein bezahlter Aufruf eine
    # Zusammenfassung von nichts (Review PR #18).
    if not any(c.get("urteil") or any(t.get("judge") for t in c.get("turns") or [])
               for c in conversations):
        return {"fehler": "keine Urteile"}
    auswertung = auswertung_v2.auswerten({"conversations": conversations},
                                         price_from_table(load_pricing()))
    try:
        return await kurzbericht(auswertung, usage_acc=usage_acc)
    except Exception as fehler:
        logger.warning("[golden] Kurzbericht fehlgeschlagen: %s", fehler)
        return {"fehler": str(fehler)[:200]}


def summarize_golden_run(
    conversations: list[dict[str, Any]],
    *,
    target_turns: int,
    golden_metrics: dict[str, Any],
    current_activity: str = "Fertig",
) -> dict[str, Any]:
    """Build the ``eval_runs.summary`` payload for a golden run.

    ``golden_metrics`` comes from the deterministic runner (``aggregate_golden``)
    and is enriched in place with the judge cut, so the scorecard and the
    summary cannot drift apart.
    """
    summary = _aggregate(conversations)
    summary["target_turns"] = target_turns
    summary["current_activity"] = current_activity
    # The only source GET /eval/trends reads for its five series. A golden run
    # that omits it leaves those series empty no matter how many runs exist.
    summary["classification_metrics"] = _aggregate_classification_metrics(conversations)
    summary["golden_metrics"] = golden_metrics
    if summary.get("total_judged_turns"):
        judge_avg = summary.get("avg_score")
        summary["judge_avg"] = judge_avg
        golden_metrics["judge_avg"] = judge_avg
        golden_metrics["judged_turns"] = summary["total_judged_turns"]
    # GV4: ausgefallene Judge-Aufrufe werden GEZÄHLT statt als 0 gemittelt —
    # sonst sähe ein Gutachter-Ausfall wie ein Bot-Versagen aus. (Seit Review
    # Runde 2 derselbe Zähler wie im generativen Summary — eine Definition.)
    judge_failed = count_judge_failed_turns(conversations)
    summary["judge_failed_turns"] = judge_failed
    if judge_failed:
        golden_metrics["judge_failed_turns"] = judge_failed
    # Review-Befund 4 (2026-08-22): Chat-Fehler-Züge zählen wie Judge-Ausfälle.
    # Die CLI meldet sie über Exit 1 + stderr; der GESPEICHERTE Lauf stand
    # ohne Zähler grün da, obwohl N Züge nie stattfanden.
    chat_errors = count_chat_error_turns(conversations)
    summary["chat_error_turns"] = chat_errors
    if chat_errors:
        golden_metrics["chat_error_turns"] = chat_errors
    summary["avg_score"] = golden_metrics["overall_pass_rate"]
    return summary
