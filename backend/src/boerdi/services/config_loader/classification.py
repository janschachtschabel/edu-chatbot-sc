"""Classification loaders (intents/states/entities/signals/patterns/
overrides) — port of ALT config_loader/classification.py.

simplify: the MD-section fallback parser for patterns WITHOUT frontmatter
(legacy files) is deferred to the P4 pattern-engine port — all 16 real
pattern files carry full frontmatter (inventory 2026-07-11).
"""

from __future__ import annotations

from typing import Any

from boerdi.services.config_loader._store import area, cached_keys

_SIGNAL_KNOWN_KEYS = (
    "tone", "length", "skip_intro", "one_option", "add_sources",
    "show_more", "show_overview",
)


def load_signal_modulations() -> tuple[dict[str, Any], list[str]]:
    """(modulations, reduce_items_signals); per-signal only KNOWN keys survive."""
    data = area("04-signals/signal-modulations")
    raw = data.get("signals") or {}
    modulations: dict[str, Any] = {}
    for sig, cfg in raw.items():
        if not isinstance(cfg, dict):
            continue
        modulations[sig] = {k: cfg[k] for k in _SIGNAL_KNOWN_KEYS if k in cfg}
    return modulations, list(data.get("reduce_items_signals") or [])


def load_intents() -> list[dict[str, Any]]:
    return area("04-intents/intents").get("intents") or []


def load_states() -> list[dict[str, Any]]:
    return area("04-states/states").get("states") or []


def get_state_directive(state_id: str) -> dict[str, Any]:
    for state in load_states():
        if state.get("id") == state_id:
            return {
                "id": state.get("id"),
                "label": state.get("label", ""),
                "role": state.get("role", ""),
                "bot_directive": str(state.get("bot_directive") or "").strip(),
                "next_likely": state.get("next_likely") or [],
            }
    return {}


def load_entities() -> list[dict[str, Any]]:
    return area("04-entities/entities").get("entities") or []


def load_tie_breaker_config() -> dict[str, Any]:
    """No file — hardcoded no-op shim (ALT contract)."""
    return {
        "enabled": False,
        "max_score_gap": 0.05,
        "top_n_window": 2,
        "allow_patterns_winner": [],
    }


def load_classify_overrides_config() -> dict[str, Any]:
    data = area("01-base/classify-overrides")
    return {
        "persona_overrides": data.get("persona_overrides") or [],
        "intent_overrides": data.get("intent_overrides") or [],
        "intent_conflict_rule": data.get("intent_conflict_rule") or "",
        "topic_overrides": data.get("topic_overrides") or {},
        "pattern_disambiguators": data.get("pattern_disambiguators") or [],
        "few_shot_examples": data.get("few_shot_examples") or [],
    }


def _normalize_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value if str(v or "").strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _strip_h1(body: str) -> str:
    lines = body.lstrip("\n").splitlines(keepends=True)
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    return "".join(lines).lstrip("\n")


def load_pattern_definitions() -> list[dict[str, Any]]:
    """All 03-patterns/* areas: frontmatter meta (skip no-id) + normalized
    list fields + discriminator filter + body_md + _source_file."""
    out: list[dict[str, Any]] = []
    for key in cached_keys("03-patterns/"):
        data = area(key)
        meta = dict(data.get("frontmatter") or {})
        if not meta.get("id"):
            continue
        for field in ("when_to_use", "when_not_to_use", "trigger_phrases"):
            meta[field] = _normalize_list(meta.get(field))
        discs = []
        for d in meta.get("discriminators") or []:
            if isinstance(d, dict) and d.get("vs") and d.get("rule"):
                discs.append({
                    "vs": d["vs"], "rule": d["rule"], "example": d.get("example", ""),
                })
        meta["discriminators"] = discs
        meta["body_md"] = _strip_h1(str(data.get("body") or ""))
        meta["_source_file"] = f"{key}.md"
        out.append(meta)
    return out
