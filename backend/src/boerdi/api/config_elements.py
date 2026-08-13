"""Element browser + structured dimension editors (P2-5).

Port of ALT config_elements.py. Personas/patterns are stored one area per
file ({frontmatter, body}); intents/states/entities as a single list area.
Validation status codes match ALT (422 per-entry, 400 business rules).
"""

from __future__ import annotations

import logging
import re
from typing import Any

from fastapi import APIRouter, HTTPException, Security
from pydantic import BaseModel, ValidationError

from boerdi.api.config_element_models import (
    EntitiesPayload,
    EntityEntry,
    IntentEntry,
    IntentsPayload,
    PatternEntry,
    PatternsPayload,
    PersonaEntry,
    PersonasPayload,
    StateEntry,
    StatesPayload,
)
from boerdi.api.deps import Lang, require_studio_key
from boerdi.i18n import Locale, msg
from boerdi.services import config_loader as cl

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/config", tags=["config-elements"],
    dependencies=[Security(require_studio_key)],
)


def _validate_entries(
    model: type[BaseModel], raw: list, label: str, lang: Locale
) -> list:
    """Validate a list against ``model`` -> generic 422 (no field details leaked)."""
    try:
        return [model.model_validate(item) for item in raw]
    except ValidationError as e:
        logger.warning("%s: ungültige Eintragsdaten: %s", label, e)
        raise HTTPException(422, msg(lang, "entries.invalid", label=label)) from None


def _strip_empty(obj: Any) -> Any:
    """Recursively drop None/""/[]/{} (keeps stored areas clean, ALT semantics)."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            cleaned = _strip_empty(v)
            if cleaned not in (None, "", [], {}):
                out[k] = cleaned
        return out
    if isinstance(obj, list):
        return [_strip_empty(x) for x in obj if _strip_empty(x) not in (None, "", [], {})]
    return obj


def _require_unique_ids(entries: list, label: str) -> None:
    if len({e.id for e in entries}) != len(entries):
        raise HTTPException(400, f"{label} IDs must be unique.")


def _md_body(entry_id: str, label: str, text: str | None) -> str:
    """Body prose with a standard H1 when the text has none (ALT parity;
    the loader strips the H1 again on read)."""
    body = (text or "").strip()
    if body and not re.match(r"^\s*#\s", body):
        body = f"# {entry_id} — {label}\n\n{body}"
    return body


# ── element browser ────────────────────────────────────────────────────────
def _with_source(entries: list[dict], file: str) -> list[dict]:
    """Jedem Eintrag seine Quelldatei anhängen — auf einer KOPIE.

    Die Lade-Fassade reicht die Listen aus dem Prozess-Cache heraus
    (``load_intents`` = ``area(...)["intents"]``, kein Klon). Wer in diese
    Objekte schreibt, ändert den Bereich selbst: das Studio-Formular meldete
    ``intents[0].file`` … als unbekannten Schlüssel, und ein Speichern hätte
    die Anzeige-Angabe als Konfigurationswert festgeschrieben (Nutzer-Befund
    2026-08-13). ``file`` ist Herkunft für den Browser, kein Config-Wert.
    """
    return [{**entry, "file": file} for entry in entries]


@router.get("/elements")
async def get_elements() -> dict:
    """All editable elements + their source paths for the Studio browser."""
    patterns = [
        {"id": p.get("id"), "label": p.get("label", p.get("id")),
         "personas": [], "intents": [], "states": [], "signals_boost": [],
         "file": p.get("_source_file", "")}
        for p in cl.load_pattern_definitions()
    ]

    personas = []
    for p in cl.load_persona_definitions():
        entry = dict(p)
        entry["file"] = f"04-personas/{cl._persona_slug(p['id'])}.md"
        entry.pop("_source_file", None)
        personas.append(entry)

    intents = _with_source(cl.load_intents(), "04-intents/intents.yaml")
    states = _with_source(cl.load_states(), "04-states/states.yaml")

    mods, _reduce = cl.load_signal_modulations()
    signals = [
        {"id": sig, "modulations": mod, "file": "04-signals/signal-modulations.yaml"}
        for sig, mod in mods.items()
    ]

    entities = _with_source(cl.load_entities(), "04-entities/entities.yaml")

    return {
        "patterns": patterns, "personas": personas, "intents": intents,
        "states": states, "signals": signals, "entities": entities,
        "device": cl.load_device_config(),
        "base_files": [
            {"label": "Base-Persona (Identität)", "file": "01-base/base-persona.md"},
            {"label": "Guardrails (R-01 bis R-10)", "file": "01-base/guardrails.md"},
            {"label": "Device & Formality", "file": "01-base/device-config.yaml"},
            {"label": "Domain-Rules", "file": "02-domain/domain-rules.md"},
        ],
    }


# ── intents ──
@router.get("/intents")
async def get_intents_route() -> dict:
    return {"intents": cl.load_intents()}


@router.put("/intents")
async def put_intents_route(payload: IntentsPayload, lang: Lang) -> dict:
    entries = _validate_entries(IntentEntry, payload.intents, "Intent", lang)
    _require_unique_ids(entries, "Intent")
    cleaned = [_strip_empty(e.model_dump()) for e in entries]
    await cl.write_area("04-intents/intents", {"intents": cleaned})
    return {"status": "saved", "count": len(entries)}


# ── states ──
@router.get("/states")
async def get_states_route() -> dict:
    return {"states": cl.load_states()}


@router.put("/states")
async def put_states_route(payload: StatesPayload, lang: Lang) -> dict:
    entries = _validate_entries(StateEntry, payload.states, "State", lang)
    _require_unique_ids(entries, "State")
    cleaned = [_strip_empty(e.model_dump()) for e in entries]
    await cl.write_area("04-states/states", {"states": cleaned})
    return {"status": "saved", "count": len(entries)}


# ── entities (accumulation_rules block preserved) ──
@router.get("/entities")
async def get_entities_route() -> dict:
    return {
        "entities": cl.load_entities(),
        "accumulation_rules": cl.area("04-entities/entities").get("accumulation_rules", {}),
    }


@router.put("/entities")
async def put_entities_route(payload: EntitiesPayload, lang: Lang) -> dict:
    entries = _validate_entries(EntityEntry, payload.entities, "Entity", lang)
    _require_unique_ids(entries, "Entity")
    cleaned = [_strip_empty(e.model_dump()) for e in entries]
    existing = cl.area("04-entities/entities")
    data: dict[str, Any] = {"entities": cleaned}
    if existing.get("accumulation_rules"):
        data["accumulation_rules"] = existing["accumulation_rules"]  # untouched
    await cl.write_area("04-entities/entities", data)
    return {"status": "saved", "count": len(entries)}


# ── personas (one area per persona: frontmatter + body) ──
@router.get("/personas")
async def get_personas_route() -> dict:
    return {"personas": cl.load_persona_definitions()}


@router.put("/personas")
async def put_personas_route(payload: PersonasPayload, lang: Lang) -> dict:
    entries = _validate_entries(PersonaEntry, payload.personas, "Persona", lang)
    _require_unique_ids(entries, "Persona")
    for e in entries:
        fm: dict[str, Any] = {"element": "persona", "id": e.id, "label": e.label}
        if e.description:
            fm["description"] = e.description
        for k in ("tone", "length_bias", "formality", "card_text_mode", "override"):
            v = getattr(e, k)
            if v is not None:
                fm[k] = v
        if e.positive_markers:
            fm["positive_markers"] = list(e.positive_markers)
        if e.anti_markers:
            fm["anti_markers"] = [_strip_empty(am.model_dump()) for am in e.anti_markers]
        if e.discriminators:
            fm["discriminators"] = [_strip_empty(d.model_dump()) for d in e.discriminators]
        if e.goals:
            fm["goals"] = list(e.goals)
        if e.rules:
            fm["rules"] = list(e.rules)
        if e.typical_intents:
            fm["typical_intents"] = list(e.typical_intents)
        body = _md_body(e.id, e.label, e.personality_text)
        await cl.write_area(f"04-personas/{cl._persona_slug(e.id)}",
                            {"frontmatter": fm, "body": body})
    return {"status": "saved", "count": len(entries)}


# ── patterns (one area per pattern: frontmatter + body) ──
_QR_MODES = ("exact", "speculative", "none")


@router.get("/patterns")
async def get_patterns_route() -> dict:
    return {"patterns": [
        {k: v for k, v in p.items() if k != "_source_file"}
        for p in cl.load_pattern_definitions()
    ]}


@router.put("/patterns")
async def put_patterns_route(payload: PatternsPayload, lang: Lang) -> dict:
    entries = _validate_entries(PatternEntry, payload.patterns, "Pattern", lang)
    _require_unique_ids(entries, "Pattern")
    # validate ALL before writing any (no partial writes)
    for e in entries:
        if e.quick_replies_mode and e.quick_replies_mode not in _QR_MODES:
            raise HTTPException(
                400,
                msg(lang, "patterns.qrModeInvalid", value=repr(e.quick_replies_mode)),
            )

    existing_key_by_id = {
        p["id"]: cl._strip_ext(p.get("_source_file", ""))
        for p in cl.load_pattern_definitions()
    }
    for e in entries:
        area_key = existing_key_by_id.get(e.id) or _new_pattern_key(e)
        fm = _pattern_frontmatter(e)
        body = _md_body(e.id, e.label, e.body_md)
        await cl.write_area(area_key, {"frontmatter": fm, "body": body})
    return {"status": "saved", "count": len(entries)}


def _new_pattern_key(e: PatternEntry) -> str:
    slug = re.sub(r"[^a-z0-9-]+", "-", (e.label or e.id).lower()).strip("-")
    return f"03-patterns/{e.id.lower()}-{slug}"


def _pattern_frontmatter(e: PatternEntry) -> dict[str, Any]:
    fm: dict[str, Any] = {"id": e.id, "label": e.label}
    if e.short_purpose:
        fm["short_purpose"] = e.short_purpose
    if e.priority is not None:
        fm["priority"] = e.priority
    for k in ("default_tone", "default_length", "response_type", "output_mode"):
        v = getattr(e, k)
        if v:
            fm[k] = v
    for k in ("sources", "rag_areas", "tools", "precondition_slots"):
        v = getattr(e, k)
        if v:
            fm[k] = list(v)
    if e.card_text_link_required:
        fm["card_text_link_required"] = True
    if e.quick_replies_mode and e.quick_replies_mode != "exact":
        fm["quick_replies_mode"] = e.quick_replies_mode
    if e.quick_replies_max is not None:
        fm["quick_replies_max"] = max(1, min(6, int(e.quick_replies_max)))
    if e.core_rule:
        fm["core_rule"] = e.core_rule.strip()
    if e.forbidden_phrases:
        fm["forbidden_phrases"] = list(e.forbidden_phrases)
    if e.anti_patterns:
        fm["anti_patterns"] = list(e.anti_patterns)
    for k in ("when_to_use", "when_not_to_use", "trigger_phrases"):
        v = getattr(e, k)
        if v:
            fm[k] = list(v)
    if e.discriminators:
        fm["discriminators"] = [
            {"vs": str(d.get("vs", "")).strip(),
             "rule": str(d.get("rule", "")).strip(),
             "example": str(d.get("example", "")).strip()}
            for d in e.discriminators if d.get("vs") and d.get("rule")
        ]
    return fm
