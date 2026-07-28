"""Tone-modifier loaders — port of ALT config_loader/tone.py.

Primary source: persona MD frontmatter (via load_persona_definitions);
fallback: 01-base/tone-modifiers.yaml. ``default`` always from the YAML.
"""

from __future__ import annotations

from typing import Any

from boerdi.services.config_loader import _store
from boerdi.services.config_loader._store import area
from boerdi.services.config_loader.personas import _persona_slug, load_persona_definitions

_MODIFIER_KEYS = ("tone", "length_bias", "formality", "card_text_mode", "override")
_FORMALITY = ("duzen", "siezen", "wie_user")
_CARD_TEXT_MODES = ("minimal", "kurz", "explanation", "ausfuehrlich")


def _coerce_tone_modifier(raw: dict[str, Any] | None) -> dict[str, Any]:
    raw = raw or {}
    try:
        bias = float(raw.get("length_bias", 0.0))
    except (TypeError, ValueError):
        bias = 0.0
    bias = max(-0.3, min(0.3, bias))
    formality = str(raw.get("formality") or "wie_user")
    if formality not in _FORMALITY:
        formality = "wie_user"
    card_mode = str(raw.get("card_text_mode") or "minimal")
    if card_mode not in _CARD_TEXT_MODES:
        card_mode = "minimal"
    return {
        "tone": str(raw.get("tone") or "locker"),
        "length_bias": bias,
        "formality": formality,
        "card_text_mode": card_mode,
        "override": bool(raw.get("override", False)),
    }


def load_tone_modifiers_config() -> dict[str, Any]:
    modifiers: dict[str, dict[str, Any]] = {}
    for persona in load_persona_definitions():
        if any(k in persona for k in _MODIFIER_KEYS):
            modifiers[persona["id"]] = _coerce_tone_modifier(persona)
    if not modifiers:  # secondary fallback: historical YAML
        raw = area("01-base/tone-modifiers").get("modifiers") or {}
        modifiers = {pid: _coerce_tone_modifier(m) for pid, m in raw.items()
                     if isinstance(m, dict)}
    default = _coerce_tone_modifier(area("01-base/tone-modifiers").get("default_modifier"))
    return {"modifiers": modifiers, "default": default}


def get_tone_modifier_for_persona(persona_id: str) -> dict[str, Any]:
    cfg = load_tone_modifiers_config()
    if persona_id and persona_id in cfg["modifiers"]:
        return cfg["modifiers"][persona_id]
    return cfg["default"]


async def update_persona_modifier_in_frontmatter(
    persona_id: str, modifier: dict[str, Any]
) -> bool:
    """Rewrite the 5 modifier fields in the persona area's frontmatter.
    Returns False when the persona area is missing (ALT contract)."""
    key = f"04-personas/{_persona_slug(persona_id)}"
    data = area(key)
    fm = data.get("frontmatter")
    if not data or not isinstance(fm, dict) or not fm:
        return False
    coerced = _coerce_tone_modifier(modifier)
    new_fm = {**fm, **coerced}
    if _store._store is None:
        raise RuntimeError("config store not bound")
    await _store._store.put(
        key, {"frontmatter": new_fm, "body": data.get("body", "")}, updated_by="studio"
    )
    return True
