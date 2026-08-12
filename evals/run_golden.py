#!/usr/bin/env python
"""Golden-flow runner (P0-8) — the deterministic acceptance instrument (spec §5.7).

Ported 1:1 from ALT ``eval_golden.py`` / ``eval_metrics.py`` / ``eval_text_utils.py``
/ ``eval_service._post_chat`` — runner part only: no eval_runs DB row, no LLM
judge (both live in the backend eval API, P7). Framework-free (httpx + pyyaml),
so it can run against ANY chat backend:

    cd backend && uv run python ../evals/run_golden.py --only GS-1
    EVAL_CHAT_URL=http://localhost:8100/api/chat uv run python ../evals/run_golden.py

``EVAL_CHAT_HEADERS`` (A5) carries a JSON object of request headers into every
turn — the way to drive ONE suite against BOTH engines, since the switch is a
header (``X-Boerdi-Engine``, A4a):

    EVAL_CHAT_HEADERS='{"X-Boerdi-Engine":"agent"}' \
        uv run python ../evals/run_golden.py --label agent

Exit code 0 == all asserted hard checks passed (persona/intent/register/
structure/qr); host is reported but soft, like ALT. Exit code 2 == the run never
started (no matching flow, unreadable headers).

ONE file on purpose (documented exception to the ~300-line rule, §0 rule 7):
both ``eval_service._load_golden_runner`` and the tests load it by PATH via
``importlib.util.spec_from_file_location``, which is what keeps it runnable
against any backend without installing this project. Splitting it into a package
would break that and reintroduce the dependency it exists to avoid. The soft
half that DOES need config and an LLM lives in ``services/eval/golden.py``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import re
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
import yaml

HERE = Path(__file__).resolve().parent

GOLDEN_CATS = ["persona", "intent", "register", "structure", "qr", "host"]
GOLDEN_HARD = ["persona", "intent", "register", "structure", "qr"]

_SIE_RE = re.compile(r"\b(?:Sie|Ihnen|Ihr|Ihre[nmrs]?|Ihrem)\b")
_DU_RE = re.compile(r"\b(?:[Dd]u|[Dd]ich|[Dd]ir|[Dd]eine?[nmrs]?|[Dd]ein)\b")


def strip_id(decorated: str) -> str:
    """Extracts the bare ID from "M03 (Schritt-für-Schritt)" -> "M03"."""
    if not decorated:
        return ""
    s = str(decorated).strip()
    return s.split(" ", 1)[0] if " " in s else s


def detect_register(text: str) -> tuple[str, int, int]:
    """Sie/du heuristic: count formal vs informal markers. Label = sie|du|neutral."""
    s = len(_SIE_RE.findall(text or ""))
    d = len(_DU_RE.findall(text or ""))
    label = "sie" if s > d else ("du" if d > s else "neutral")
    return label, s, d


def chat_headers(raw: str | None) -> dict[str, str]:
    """``EVAL_CHAT_HEADERS`` (a JSON object) as request headers (A5).

    Empty means empty. Unreadable means **abort**, never "carry on without
    headers": the whole point of this setting is the engine switch
    (``X-Boerdi-Engine``), and a silent fallback would run the suite against the
    pattern engine while the report claims ``agent`` — the A/B comparison would
    then compare a run with itself, and nothing would turn red anywhere.
    """
    s = (raw or "").strip()
    if not s:
        return {}
    try:
        data = json.loads(s)
    except ValueError as e:
        raise ValueError(f"EVAL_CHAT_HEADERS is not valid JSON: {e}") from e
    if not isinstance(data, dict):
        raise ValueError("EVAL_CHAT_HEADERS must be a JSON OBJECT of name → value")
    bad = sorted(k for k, v in data.items() if not isinstance(v, str))
    if bad:
        raise ValueError(f"EVAL_CHAT_HEADERS: values must be strings ({bad})")
    return data


def repo_host() -> str:
    """Host of REPO_BASE_URL — same default as the backend (config_loader)."""
    base = (os.getenv("REPO_BASE_URL") or "").strip().rstrip("/") or (
        "https://redaktion.openeduhub.net"
    )
    return urlparse(base).netloc or base


def check_golden_turn(
    expect: dict[str, Any], bot_resp: dict[str, Any], debug: dict[str, Any],
) -> dict[str, Any]:
    """Programmatic, deterministic per-turn checks against the gold-standard
    expectations. Returns {expected, observed, checks}. A check value of
    None means "not asserted for this turn" (excluded from rates)."""
    exp_persona = str(expect.get("persona") or "*").strip()
    exp_intent = str(expect.get("intent") or "").strip()
    exp_register = str(expect.get("register") or "any").strip().lower()
    exp_structure = str(expect.get("structure") or "").strip().lower()

    obs_persona = strip_id(debug.get("persona", ""))
    obs_intent = strip_id(debug.get("intent", ""))
    obs_pattern = strip_id(debug.get("pattern", ""))
    content = bot_resp.get("content") or ""
    cards = bot_resp.get("cards") or []
    idocs = bot_resp.get("inline_documents") or []
    qr = bot_resp.get("quick_replies") or []
    reg_label, sie_n, du_n = detect_register(content)

    # B1 (ALT 2026-07-10): wildcard persona ("*") / empty intent are NOT
    # asserted -> None (neutral, excluded from overall_pass_rate), not True.
    persona_ok: bool | None = None if exp_persona == "*" else (obs_persona == exp_persona)
    intent_ok: bool | None = None if not exp_intent else (obs_intent == exp_intent)
    if exp_register == "sie":
        register_ok: bool | None = reg_label != "du"
    elif exp_register == "du":
        register_ok = reg_label != "sie"
    else:
        register_ok = None  # "any" -> not asserted
    if exp_structure == "idoc":
        structure_ok: bool | None = len(idocs) >= 1
    elif exp_structure == "cards":
        structure_ok = len(cards) >= 1
    else:
        structure_ok = None
    qr_ok = len(qr) >= 1
    host = repo_host()
    urls = [(c.get("wlo_url") or c.get("url") or "") for c in cards if isinstance(c, dict)]
    urls = [u for u in urls if u]
    host_ok: bool | None = (all(host in u for u in urls) if urls else None)

    return {
        "expected": {
            "persona": exp_persona, "intent": exp_intent,
            "register": exp_register,
            "structure": exp_structure or None,
            "must_offer": expect.get("must_offer") or "",
        },
        "observed": {
            "persona": obs_persona, "intent": obs_intent, "pattern": obs_pattern,
            "register": reg_label, "sie": sie_n, "du": du_n,
            "cards": len(cards), "idocs": len(idocs), "qr": len(qr),
            "content_len": len(content),
        },
        "checks": {
            "persona": persona_ok, "intent": intent_ok, "register": register_ok,
            "structure": structure_ok, "qr": qr_ok, "host": host_ok,
        },
    }


def flatten_debug(debug: dict[str, Any]) -> dict[str, Any]:
    """The debug fields the judge and the run aggregators read (1:1 ALT
    ``eval_golden._flatten_debug``).

    Twin of ``boerdi.services.eval.runner._flat_debug`` for the same reason
    ``augment_bot_text`` is one: this module must stay importable without the
    backend package, so it cannot reach into ``boerdi.*``. ALT keeps the same
    twin (``eval_golden`` vs. the inline copy in ``execute_run``).

    Deliberately a SUBSET: ``trace``/``context``/``entities`` would add
    kilobytes per turn to every report and every persisted transcript, and
    nothing downstream reads them.
    """
    return {
        "pattern": debug.get("pattern"),
        "persona": debug.get("persona"),
        "intent": debug.get("intent"),
        "safety": debug.get("safety"),
        "tools_called": debug.get("tools_called", []),
        "pattern_id_hint": debug.get("pattern_id_hint"),
        "pattern_reasoning": debug.get("pattern_reasoning"),
        "llm_engine_match": debug.get("llm_engine_match"),
        "token_usage": debug.get("token_usage"),
        "phase3_modulations": debug.get("phase3_modulations"),
    }


def augment_bot_text(bot_resp: dict[str, Any]) -> str:
    """Append inline-document / card / query-meta content to the bot text so
    the report reader sees what the user actually got (1:1 ALT)."""
    bot_text = bot_resp.get("content", "") or ""
    idocs = bot_resp.get("inline_documents") or []
    if idocs:
        md_parts: list[str] = []
        for doc in idocs:
            if not isinstance(doc, dict):
                continue
            content = (doc.get("content") or "").strip()
            if content:
                title = (doc.get("title") or doc.get("kind") or "").strip()
                md_parts.append(
                    "---\n[Inline-Document — vom Nutzer sichtbar"
                    + (f": {title}" if title else "") + "]\n\n" + content
                )
        if md_parts:
            bot_text = (bot_text or "").rstrip() + "\n\n" + "\n\n".join(md_parts)
    cards = bot_resp.get("cards") or []
    if cards:
        card_lines: list[str] = []
        for card in cards[:8]:
            if not isinstance(card, dict):
                continue
            ct = (card.get("title") or "").strip()
            cu = (card.get("url") or card.get("wlo_url") or "").strip()
            cd = (card.get("description") or card.get("abstract") or "").strip()[:200]
            if ct or cu:
                line = f"  - **{ct or '(ohne Titel)'}**"
                if cu:
                    line += f" — {cu}"
                if cd:
                    line += f"\n    {cd}"
                card_lines.append(line)
        if card_lines:
            bot_text = (
                (bot_text or "").rstrip()
                + f"\n\n---\n[Material-Cards — vom Nutzer sichtbar, {len(card_lines)} Treffer]\n"
                + "\n".join(card_lines)
            )
    qmetas = bot_resp.get("query_metas") or []
    if qmetas:
        qm_lines: list[str] = []
        for qm in qmetas[:5]:
            if not isinstance(qm, dict):
                continue
            qt = (qm.get("title") or qm.get("type") or "").strip()
            qu = (qm.get("url") or "").strip()
            if qt or qu:
                qm_lines.append(f"  - {qt}" + (f" — {qu}" if qu else ""))
        if qm_lines:
            bot_text = (
                (bot_text or "").rstrip()
                + "\n\n---\n[Query-Metas — vom Nutzer sichtbar]\n"
                + "\n".join(qm_lines)
            )
    return bot_text


def _quantile(ordered: list[int], q: float) -> int:
    """Nearest-rank quantile, no interpolation: these are measured milliseconds,
    and an interpolated value never actually occurred in the run."""
    idx = max(0, min(len(ordered) - 1, math.ceil(q * len(ordered)) - 1))
    return ordered[idx]


def latency_summary(values: list[int]) -> dict[str, Any]:
    """Per-turn latency distribution (A5).

    Distribution rather than an average: the MCP search was measured between 1.2
    and 23.3 seconds in the same run, and a mean would smear away exactly the
    difference the A/B comparison exists to see. Turns without a measurement are
    simply not counted — an older report must not crash the scorecard.
    """
    if not values:
        return {"turns": 0, "p50_ms": None, "p95_ms": None,
                "max_ms": None, "total_ms": 0}
    ordered = sorted(values)
    return {
        "turns": len(ordered),
        "p50_ms": _quantile(ordered, 0.5),
        "p95_ms": _quantile(ordered, 0.95),
        "max_ms": ordered[-1],
        "total_ms": sum(ordered),
    }


def aggregate_golden(conversations: list[dict]) -> dict[str, Any]:
    """Deterministic scorecard over all golden-flow turns (1:1 ALT + A5 latency)."""
    tot = {c: 0 for c in GOLDEN_CATS}
    ok = {c: 0 for c in GOLDEN_CATS}
    per_turn: list[dict[str, Any]] = []
    per_flow: dict[str, dict[str, Any]] = {}
    latencies: list[int] = []

    for conv in conversations:
        fid = conv.get("flow_id") or conv.get("persona_id") or "?"
        title = conv.get("title", "")
        pf = per_flow.setdefault(
            fid, {"title": title, "persona": conv.get("persona_id", ""),
                  **{c: {"ok": 0, "total": 0} for c in GOLDEN_CATS}},
        )
        for ti, turn in enumerate(conv.get("turns", []), start=1):
            g = turn.get("golden") or {}
            checks = g.get("checks") or {}
            latency = turn.get("latency_ms")
            if isinstance(latency, int):
                latencies.append(latency)
            per_turn.append({
                "flow": fid, "title": title, "turn": ti,
                "message": turn.get("user", ""),
                "expected": g.get("expected") or {},
                "observed": g.get("observed") or {},
                "checks": checks,
                "latency_ms": latency,
            })
            for c in GOLDEN_CATS:
                v = checks.get(c)
                if v is None:
                    continue
                tot[c] += 1
                pf[c]["total"] += 1
                if v:
                    ok[c] += 1
                    pf[c]["ok"] += 1

    rates = {c: (round(ok[c] / tot[c], 3) if tot[c] else None) for c in GOLDEN_CATS}
    hard_ok = sum(ok[c] for c in GOLDEN_HARD)
    hard_tot = sum(tot[c] for c in GOLDEN_HARD)
    return {
        "categories": GOLDEN_CATS,
        "totals": tot,
        "passed": ok,
        "rates": rates,
        "overall_pass_rate": round(hard_ok / hard_tot, 3) if hard_tot else 0.0,
        "hard_passed": hard_ok,
        "hard_total": hard_tot,
        "flows": len(conversations),
        "turns": len(per_turn),
        "latency": latency_summary(latencies),
        "per_turn": per_turn,
        "per_flow": per_flow,
    }


async def post_chat(
    chat_url: str, message: str, session_id: str,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Fire one user message at /api/chat, return raw response JSON (1:1 ALT)."""
    async with httpx.AsyncClient(timeout=60.0) as c:
        r = await c.post(chat_url, json={"session_id": session_id, "message": message},
                         headers=headers or None)
        r.raise_for_status()
        return r.json()


def _ms_since(t0: float) -> int:
    return int(round((time.perf_counter() - t0) * 1000))


async def run_flows(
    chat_url: str, flows: list[dict[str, Any]], *,
    headers: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Each flow in its own fresh session; turns sequential (context preserved).

    ``headers`` (A5) go with every turn — keyword-only and defaulted, because the
    backend eval service calls this positionally with two arguments. Each turn
    records its own ``latency_ms``: the run total mixes 24-second searches with
    instant replies and cannot answer "is the agent faster".
    """
    conversations: list[dict[str, Any]] = []
    for fi, flow in enumerate(flows, start=1):
        flow_id = str(flow.get("id") or f"flow-{fi}")
        turns_spec = flow.get("turns") or []
        session_id = f"eval-{uuid.uuid4().hex[:12]}"
        turn_records: list[dict[str, Any]] = []
        for ti, tspec in enumerate(turns_spec, start=1):
            msg = str(tspec.get("message") or "").strip()
            expect = tspec.get("expect") or {}
            print(f"  {flow_id} turn {ti}/{len(turns_spec)} …", flush=True)
            t_turn = time.perf_counter()
            try:
                bot_resp = await post_chat(chat_url, msg, session_id, headers=headers)
            except Exception as e:  # record + continue, like ALT
                print(f"  {flow_id} turn {ti} FAILED: {e}", file=sys.stderr)
                # Auch der Fehl-Zug trägt seine Zeit: eine Zeitüberschreitung ist
                # der teuerste Zug des Laufs, ausgerechnet den nicht zu messen
                # wäre die falsche Auslassung.
                turn_records.append({"user": msg, "bot": f"(chat error: {e})",
                                     "debug": {}, "error": str(e),
                                     "expected_persona": expect.get("persona"),
                                     "expected_intent": expect.get("intent"),
                                     "latency_ms": _ms_since(t_turn)})
                continue
            latency_ms = _ms_since(t_turn)
            debug = bot_resp.get("debug", {}) or {}
            turn_records.append({
                "user": msg,
                "bot": augment_bot_text(bot_resp),
                "debug": flatten_debug(debug),
                "golden": check_golden_turn(expect, bot_resp, debug),
                "expected_persona": expect.get("persona"),
                "expected_intent": expect.get("intent"),
                "cards_count": len(bot_resp.get("cards") or []),
                "response_length": len(bot_resp.get("content") or ""),
                "latency_ms": latency_ms,
            })
        # Primary intent = what turn 1 was set up to trigger. ``_aggregate`` and
        # the classification metrics key the persona×intent matrix on it.
        primary_intent = ""
        if turns_spec:
            primary_intent = str((turns_spec[0].get("expect") or {}).get("intent") or "")
        conversations.append({
            "kind": "golden",
            "flow_id": flow_id,
            "title": str(flow.get("title") or ""),
            "persona_id": str(flow.get("persona") or "*"),
            "intent_id": primary_intent,
            "session_id": session_id,
            "turns": turn_records,
        })
    return conversations


def render_console(metrics: dict[str, Any]) -> str:
    lines = ["", "Kategorie      pass/total   Rate"]
    for c in GOLDEN_CATS:
        rate = metrics["rates"][c]
        soft = "" if c in GOLDEN_HARD else "  (soft)"
        lines.append(
            f"  {c:<12} {metrics['passed'][c]:>3}/{metrics['totals'][c]:<6}"
            f"   {'—' if rate is None else f'{rate:.1%}'}{soft}"
        )
    lines.append(
        f"\nGesamt (hart): {metrics['hard_passed']}/{metrics['hard_total']}"
        f" = {metrics['overall_pass_rate']:.1%}"
        f"  |  {metrics['flows']} Flows / {metrics['turns']} Turns"
    )
    lat = metrics.get("latency") or {}
    if lat.get("turns"):
        lines.append(
            f"Latenz je Zug: p50 {lat['p50_ms'] / 1000:.1f} s"
            f" · p95 {lat['p95_ms'] / 1000:.1f} s"
            f" · max {lat['max_ms'] / 1000:.1f} s"
            f"  ({lat['turns']} gemessene Turns)"
        )
    fails = [t for t in metrics["per_turn"]
             if any(v is False for v in t["checks"].values())]
    if fails:
        lines.append("\nFehlgeschlagene Checks:")
        for t in fails:
            bad = [c for c, v in t["checks"].items() if v is False]
            lines.append(f"  {t['flow']} turn {t['turn']}: {', '.join(bad)}"
                         f"  ({t['message'][:60]}…)")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass  # non-reconfigurable stream (e.g. under some test runners)
    p = argparse.ArgumentParser(description="Golden-flow runner (spec §5.7)")
    p.add_argument("--flows", default=str(HERE / "gold-flows.yaml"))
    p.add_argument("--url", default=os.getenv("EVAL_CHAT_URL")
                   or "http://localhost:8000/api/chat")
    p.add_argument("--only", default="", help="comma-separated flow ids (e.g. GS-1,GS-3)")
    p.add_argument("--label", default="", help="report filename label")
    p.add_argument("--out", default=str(HERE / "reports"))
    args = p.parse_args(argv)

    try:
        headers = chat_headers(os.getenv("EVAL_CHAT_HEADERS"))
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2

    flows = yaml.safe_load(Path(args.flows).read_text(encoding="utf-8"))["flows"]
    if args.only:
        wanted = {x.strip() for x in args.only.split(",") if x.strip()}
        flows = [f for f in flows if str(f.get("id")) in wanted]
        if not flows:
            print(f"no flows match --only {args.only}", file=sys.stderr)
            return 2

    kopf = f" mit Kopfzeilen {', '.join(sorted(headers))}" if headers else ""
    print(f"Golden-Runner: {len(flows)} Flow(s) gegen {args.url}{kopf}")
    t0 = time.perf_counter()
    conversations = asyncio.run(run_flows(args.url, flows, headers=headers))
    metrics = aggregate_golden(conversations)

    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    label = f"-{args.label}" if args.label else ""
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / f"golden-{stamp}{label}.json"
    report_path.write_text(json.dumps({
        "chat_url": args.url,
        # Nur die NAMEN: der Report soll sagen, WOMIT gemessen wurde, aber eine
        # Kopfzeile kann ein Geheimnis tragen (``WLO-Access-Block`` führt die
        # Zugangs-Kennung).
        "chat_headers": sorted(headers),
        "started_utc": stamp,
        "duration_s": round(time.perf_counter() - t0, 1),
        "golden_metrics": metrics,
        "conversations": conversations,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(render_console(metrics))
    print(f"\nReport: {report_path}")
    errors = sum(1 for c in conversations for t in c["turns"] if t.get("error"))
    if errors:
        print(f"{errors} Turn(s) mit Chat-Fehlern", file=sys.stderr)
        return 1
    return 0 if metrics["hard_passed"] == metrics["hard_total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
