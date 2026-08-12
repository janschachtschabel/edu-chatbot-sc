"""Typed config-area editors (P2-5) — privacy, tone-modifiers, welcome,
context-actions, canvas/material-types.

Port of ALT config_areas.py. The DATA and VALIDATION are preserved 1:1;
storage is jsonb via the loader facade (write_area) instead of YAML text,
so ALT's custom yaml-dumper machinery is intentionally not carried over.
Mounted under /api/config by config.py; Studio auth is applied there.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Security
from pydantic import BaseModel

from boerdi.api.deps import Lang, require_studio_key
from boerdi.i18n import msg
from boerdi.services import config_loader as cl

router = APIRouter(
    prefix="/api/config", tags=["config"],
    dependencies=[Security(require_studio_key)],
)


# ── Privacy (safety forced true on write — audit trail can't be silenced) ──
class PrivacyConfig(BaseModel):
    messages: bool = True
    memory: bool = True
    quality: bool = True
    safety: bool = True  # read-only; PUT ignores the sent value


@router.get("/privacy", response_model=PrivacyConfig)
async def get_privacy_config() -> PrivacyConfig:
    return PrivacyConfig(**cl.load_privacy_config())


@router.put("/privacy", response_model=PrivacyConfig)
async def update_privacy_config(cfg: PrivacyConfig) -> PrivacyConfig:
    await cl.write_area("01-base/privacy-config", {"logging": {
        "messages": bool(cfg.messages),
        "memory": bool(cfg.memory),
        "quality": bool(cfg.quality),
        "safety": True,  # hardcoded on
    }})
    return PrivacyConfig(**cl.load_privacy_config())


# ── Tone modifiers (persona frontmatter + default fallback) ────────────────
class ToneModifier(BaseModel):
    tone: str = "locker"
    length_bias: float = 0.0  # [-0.3 .. +0.3]
    formality: str = "wie_user"  # duzen | siezen | wie_user
    card_text_mode: str = "minimal"  # minimal | kurz | explanation | ausfuehrlich
    override: bool = False


class ToneModifiersPayload(BaseModel):
    modifiers: dict[str, ToneModifier]
    default_modifier: ToneModifier


@router.get("/tone-modifiers", response_model=ToneModifiersPayload)
async def get_tone_modifiers() -> ToneModifiersPayload:
    cfg = cl.load_tone_modifiers_config()
    return ToneModifiersPayload(
        modifiers={k: ToneModifier(**v) for k, v in cfg["modifiers"].items()},
        default_modifier=ToneModifier(**cfg["default"]),
    )


@router.put("/tone-modifiers", response_model=ToneModifiersPayload)
async def update_tone_modifiers(payload: ToneModifiersPayload, lang: Lang) -> ToneModifiersPayload:
    """Persona modifiers go into each persona area's frontmatter; the
    default stays in 01-base/tone-modifiers (fallback for unknown personas)."""
    failed: list[str] = []
    for pid, mod in payload.modifiers.items():
        if not await cl.update_persona_modifier_in_frontmatter(pid, mod.model_dump()):
            failed.append(pid)
    if failed:
        # ALT: partial writes stay (each persona is independent); surface the
        # failed subset so the Studio shows its error state instead of a false OK.
        raise HTTPException(
            500, msg(lang, "tone.partial", failed=", ".join(sorted(failed))),
        )
    await cl.write_area("01-base/tone-modifiers",
                        {"default_modifier": payload.default_modifier.model_dump()})
    cfg = cl.load_tone_modifiers_config()
    return ToneModifiersPayload(
        modifiers={k: ToneModifier(**v) for k, v in cfg["modifiers"].items()},
        default_modifier=ToneModifier(**cfg["default"]),
    )


# ── Welcome ────────────────────────────────────────────────────────────────
class WelcomeConfig(BaseModel):
    greeting: str
    quick_replies: list[str]
    tour_reply: str = ""
    # C1-g2b-Nachtrag: ohne diese Felder löschte jeder Schreibzugriff über
    # diese Route die englische Fassung (das YAML wird hier feldweise neu
    # gebaut). Optional mit leerer Vorgabe — ein Aufrufer, der sie nicht kennt,
    # bekommt keinen Fehler.
    greeting_en: str = ""
    quick_replies_en: list[str] = []
    tour_reply_en: str = ""


@router.get("/welcome", response_model=WelcomeConfig)
async def get_welcome_config() -> WelcomeConfig:
    return WelcomeConfig(**cl.load_welcome_config())


@router.put("/welcome", response_model=WelcomeConfig)
async def update_welcome_config(cfg: WelcomeConfig, lang: Lang) -> WelcomeConfig:
    greeting = (cfg.greeting or "").strip()
    if not greeting:
        raise HTTPException(400, msg(lang, "field.empty", field="greeting"))
    replies = [r.strip() for r in (cfg.quick_replies or []) if r and r.strip()]
    if not replies:
        raise HTTPException(400, msg(lang, "welcome.noReplies"))
    tour_reply = (cfg.tour_reply or "").strip()
    if tour_reply and tour_reply not in replies:
        raise HTTPException(400, msg(lang, "welcome.tourReplyUnknown"))
    # Die englische Fassung wird NICHT geprüft (kein Pflichtfeld, kein
    # Tour-Chip-Abgleich): leer heißt „nicht gepflegt", und wer nur Deutsch
    # pflegt, soll nicht an einer Prüfung scheitern, die er nicht kennt.
    replies_en = [r.strip() for r in (cfg.quick_replies_en or []) if r and r.strip()]
    await cl.write_area("01-base/welcome-config", {"welcome": {
        "greeting": greeting, "quick_replies": replies, "tour_reply": tour_reply,
        "greeting_en": (cfg.greeting_en or "").strip(),
        "quick_replies_en": replies_en,
        "tour_reply_en": (cfg.tour_reply_en or "").strip(),
    }})
    return WelcomeConfig(**cl.load_welcome_config())


# ── Context actions ────────────────────────────────────────────────────────
class ContextPill(BaseModel):
    label: str
    label_en: str = ""
    kind: str  # action | text | report
    action: str = ""


class ContextGreetings(BaseModel):
    collection: str
    content: str
    topic: str


class ContextPills(BaseModel):
    collection: list[ContextPill]
    content: list[ContextPill]
    topic: list[ContextPill]


class ContextGreetingsEn(BaseModel):
    """Wie ``ContextGreetings``, aber jedes Feld optional: eine nicht gepflegte
    Sprache ist kein Fehler (C1-g2b)."""

    collection: str = ""
    content: str = ""
    topic: str = ""


class ContextActionsConfig(BaseModel):
    enabled: bool = True
    report_url: str
    greetings: ContextGreetings
    greetings_en: ContextGreetingsEn = ContextGreetingsEn()
    pills: ContextPills
    curate_prompt: str


_PILL_KINDS = {"action", "text", "report"}


def _clean_pills(
    pills: list[ContextPill], kind_name: str, lang: Lang,
) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for p in pills:
        label = (p.label or "").strip()
        kind = (p.kind or "").strip().lower()
        if not label:
            raise HTTPException(400, msg(lang, "pills.labelEmpty", field=f"pills.{kind_name}"))
        if kind not in _PILL_KINDS:
            raise HTTPException(400, msg(lang, "pills.badKind", field=f"pills.{kind_name}"))
        # `label_en` wird nicht auf Leere geprüft: leer heißt „nicht gepflegt".
        entry: dict[str, str] = {
            "label": label, "label_en": (p.label_en or "").strip(), "kind": kind,
        }
        if kind == "action":
            action = (p.action or "").strip()
            if not action:
                raise HTTPException(
                    400, msg(lang, "pills.actionMissing", field=f"pills.{kind_name}"),
                )
            entry["action"] = action
        out.append(entry)
    if not out:
        raise HTTPException(400, msg(lang, "pills.none", field=f"pills.{kind_name}"))
    return out


@router.get("/context-actions", response_model=ContextActionsConfig)
async def get_context_actions_config() -> ContextActionsConfig:
    return ContextActionsConfig(**cl.load_context_actions())


@router.put("/context-actions", response_model=ContextActionsConfig)
async def update_context_actions_config(
    cfg: ContextActionsConfig, lang: Lang,
) -> ContextActionsConfig:
    report_url = (cfg.report_url or "").strip()
    if not report_url:
        raise HTTPException(400, msg(lang, "field.empty", field="report_url"))
    greetings = {
        "collection": (cfg.greetings.collection or "").strip(),
        "content": (cfg.greetings.content or "").strip(),
        "topic": (cfg.greetings.topic or "").strip(),
    }
    for kind, text in greetings.items():
        if not text:
            raise HTTPException(400, msg(lang, "field.empty", field=f"greetings.{kind}"))
    pills = {
        "collection": _clean_pills(cfg.pills.collection, "collection", lang),
        "content": _clean_pills(cfg.pills.content, "content", lang),
        "topic": _clean_pills(cfg.pills.topic, "topic", lang),
    }
    curate_prompt = (cfg.curate_prompt or "").strip()
    if not curate_prompt:
        raise HTTPException(400, msg(lang, "field.empty", field="curate_prompt"))
    greetings_en = {
        "collection": (cfg.greetings_en.collection or "").strip(),
        "content": (cfg.greetings_en.content or "").strip(),
        "topic": (cfg.greetings_en.topic or "").strip(),
    }
    await cl.write_area("01-base/context-actions", {"context_actions": {
        "enabled": bool(cfg.enabled), "report_url": report_url,
        "greetings": greetings, "greetings_en": greetings_en,
        "pills": pills, "curate_prompt": curate_prompt,
    }})
    return ContextActionsConfig(**cl.load_context_actions())


# ── Canvas material types ──────────────────────────────────────────────────
class CanvasMaterialType(BaseModel):
    id: str
    label: str
    # Additiv am eingefrorenen Vertrag, wie beim C1-g2b-Nachtrag: ohne dieses
    # Feld würde ein PUT über diese schmale Route die englischen
    # Beschriftungen still löschen. Der Studio-Editor schreibt zwar über
    # `/config/data/{area}`, die Route hier bleibt aber offen (C1-g2e).
    label_en: str = ""
    emoji: str = ""
    category: str  # didaktisch | analytisch
    structure: str = ""


class CanvasMaterialTypesPayload(BaseModel):
    material_types: list[CanvasMaterialType]


@router.get("/canvas/material-types", response_model=CanvasMaterialTypesPayload)
async def get_canvas_material_types() -> CanvasMaterialTypesPayload:
    items = cl.load_canvas_material_types() or []
    return CanvasMaterialTypesPayload(material_types=[CanvasMaterialType(**i) for i in items])


@router.put("/canvas/material-types", response_model=CanvasMaterialTypesPayload)
async def update_canvas_material_types(
    payload: CanvasMaterialTypesPayload,
) -> CanvasMaterialTypesPayload:
    seen: set[str] = set()
    valid_categories = {"didaktisch", "analytisch"}
    for mt in payload.material_types:
        if mt.id in seen:
            raise HTTPException(400, f"Duplicate id: {mt.id}")
        seen.add(mt.id)
        if mt.category not in valid_categories:
            raise HTTPException(
                400, f"Invalid category '{mt.category}' for id '{mt.id}' "
                f"(must be one of {sorted(valid_categories)})",
            )
    await cl.write_area(
        "05-canvas/material-types",
        {"material_types": [mt.model_dump() for mt in payload.material_types]},
    )
    items = cl.load_canvas_material_types() or []
    return CanvasMaterialTypesPayload(material_types=[CanvasMaterialType(**i) for i in items])
