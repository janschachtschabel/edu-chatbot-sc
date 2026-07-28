"""Persona/prompt-layer loaders — port of ALT config_loader/personas.py.

simplify: the MD-section fallback for personas WITHOUT frontmatter is
deferred to P4 (all 6 real files carry full frontmatter, inventory
2026-07-11); ``personality_text`` = body without the leading H1.
"""

from __future__ import annotations

from typing import Any

from boerdi.services.config_loader._store import area, cached_keys
from boerdi.services.config_loader.classification import _strip_h1

_SLUGS = {"P-AND": "and", "P-ELT": "elt", "P-ENT": "ent",
          "P-LEH": "leh", "P-LER": "ler", "P-RED": "red"}
_MODIFIER_KEYS = ("tone", "length_bias", "formality", "card_text_mode", "override")


def _persona_slug(persona_id: str) -> str:
    pid = str(persona_id or "").strip()
    if pid in _SLUGS:
        return _SLUGS[pid]
    return pid.lower().removeprefix("p-")


def load_persona_definitions() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for key in cached_keys("04-personas/"):
        data = area(key)
        fm = data.get("frontmatter") or {}
        if not fm.get("id"):
            continue
        markers = fm.get("positive_markers") or []
        persona: dict[str, Any] = {
            "id": fm["id"],
            "label": fm.get("label", ""),
            "description": fm.get("description", ""),
            "positive_markers": markers,
            "hints": markers,  # ALT alias
            "anti_markers": fm.get("anti_markers") or [],
            "discriminators": fm.get("discriminators") or [],
            "goals": fm.get("goals") or [],
            "rules": fm.get("rules") or [],
            "typical_intents": fm.get("typical_intents") or [],
            "personality_text": _strip_h1(str(data.get("body") or "")).strip(),
            "_source_file": f"{key}.md",
        }
        for extra in _MODIFIER_KEYS:
            if extra in fm:
                persona[extra] = fm[extra]
        out.append(persona)
    return out


def load_persona_prompt(persona_id: str) -> str:
    """Compact prompt block from frontmatter + body prose (H1 stripped)."""
    data = area(f"04-personas/{_persona_slug(persona_id)}")
    fm = data.get("frontmatter") or {}
    if not fm:
        return f"Persona: {persona_id} (Standard-Persona)"
    parts: list[str] = [f"Persona: {fm.get('label') or persona_id}"]
    if fm.get("description"):
        parts.append(str(fm["description"]).strip())
    for field, prefix in (("tone", "Ton"), ("formality", "Anrede"),
                          ("length_bias", "Längen-Bias")):
        if fm.get(field) is not None:
            parts.append(f"{prefix}: {fm[field]}")
    for field, heading in (("goals", "Ziele"), ("rules", "Regeln")):
        values = fm.get(field) or []
        if values:
            parts.append(heading + ":\n" + "\n".join(f"- {v}" for v in values))
    body = _strip_h1(str(data.get("body") or "")).strip()
    if body:
        parts.append(body)
    return "\n\n".join(parts)


def load_base_persona() -> str:
    return str(area("01-base/base-persona").get("body") or "")


def load_guardrails() -> str:
    return str(area("01-base/guardrails").get("body") or "")


def load_domain_rules() -> str:
    """Concatenate the 02-domain MD docs as full file text (frontmatter incl.,
    like ALT reading raw files), '\\n\\n'-joined, sorted by key."""
    from boerdi.services import seed_io

    parts: list[str] = []
    for key in cached_keys("02-domain/"):
        data = area(key)
        if seed_io.is_md_area(data):
            parts.append(seed_io.join_frontmatter(data["frontmatter"], data["body"]))
    return "\n\n".join(parts)
