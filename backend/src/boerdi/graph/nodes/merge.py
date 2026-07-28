"""Merge node — P5-9 entity-side merge (R4d), runs ``assess → MERGE → route``.

Port of the entity half of ALT ``chat_turn_setup._classify_and_merge`` that neither
``assess`` nor ``route`` covers. ``assess`` produced safety/classify/memory; this
node applies the placeholder-topic filter, folds the classifier's entities into
``session_state`` per turn_type (topic_switch carry-over v3 / correction /
default), runs the material_typ + type-focus heuristics, launches the speculative
MCP prefetch, and enriches the I05 material slot — THEN ``route`` selects the
pattern against the MERGED entities (``route.select_pattern`` reads
``session_state['entities']``, so the merge must run first).

What ALT ``_classify_and_merge`` also did but this node deliberately does NOT:

* the config-gated safety-log → the ``persist`` node (R4a), where all turn logging
  lands (the plan: logging call+gate = R4);
* persona/signal/state merge, ``validate_transition``, ``build_context`` and
  ``assess_policy`` → already in the ``route`` node.

NEU deviations over ALT: ``session_state``/``classification`` come off ``ctx`` and
are mutated in place (ALT parity — no rebinding is observed downstream); the
prefetch launcher returns a ``SpeculativePrefetch`` NamedTuple (ALT's bare 7-tuple)
whose fields land on ``ctx``. Tests patch the four boundaries (prefetch launch, the
two material-type helpers, the placeholder-config load) on THIS module; the pure
merge logic runs for real.
"""

from __future__ import annotations

import logging

from boerdi.domain.canvas.intent import extract_material_type_from_message
from boerdi.domain.content_types import _resolve_wanted_content_types
from boerdi.graph.state import TurnContext
from boerdi.services.config_loader import load_placeholder_topics_config
from boerdi.services.prefetch import run_speculative_prefetch

logger = logging.getLogger(__name__)


async def merge(ctx: TurnContext) -> TurnContext:
    """Fold the classifier's entities into ``session_state`` (per turn_type), run
    the material heuristics, launch the speculative prefetch, and enrich the I05
    slot. Mutates ``ctx`` in place and returns it."""
    req = ctx.req
    classification = ctx.classification
    session_state = ctx.session_state

    # ── Placeholder-Topic-Filter ────────────────────────────────────
    # "Thema"/"etwas"/"Material" u.ä. sind Meta-Wörter aus der Frage, kein echtes
    # Thema — sie dürfen keine MCP-Suche auslösen (die Engine soll dann nach dem
    # konkreten Thema fragen). Wortliste + min_length aus placeholder-topics.yaml.
    try:
        _ph_cfg = load_placeholder_topics_config()
        _PLACEHOLDER_TOPICS = _ph_cfg["topics"]
        _PLACEHOLDER_MIN_LEN = _ph_cfg["min_length"]
    except Exception as _ph_err:
        logger.debug("placeholder-topics config load failed: %s", _ph_err)
        _PLACEHOLDER_TOPICS = {
            "thema", "themen", "ein thema", "einem thema", "irgendwas",
            "etwas", "was", "irgendetwas", "irgendein thema", "sonstiges",
            "material", "materialien", "ein material", "ein paar materialien",
            "sachen", "dinge", "stuff", "topic", "etwas thema",
            "inhalt", "inhalte", "content",
        }
        _PLACEHOLDER_MIN_LEN = 3

    def _is_placeholder_topic(value: str | None) -> bool:
        s = (value or "").strip().lower()
        if not s:
            return False
        # Zu kurze Themen sind quasi immer Rest/Tippfehler; "OER"/"DSGVO" (3-4)
        # bleiben gültig.
        if _PLACEHOLDER_MIN_LEN > 0 and len(s) < _PLACEHOLDER_MIN_LEN:
            return True
        return s in _PLACEHOLDER_TOPICS

    if classification.entities and _is_placeholder_topic(
        classification.entities.get("thema")
    ):
        logger.info(
            "thema='%s' ist Platzhalter — auf leer gesetzt, damit Engine nachfragt",
            classification.entities.get("thema"),
        )
        classification.entities["thema"] = ""

    # Auch stale Platzhalter aus vorherigem Turn aus session_state entfernen.
    _ss_ents = session_state.get("entities") or {}
    if _is_placeholder_topic(_ss_ents.get("thema")):
        logger.info("stale session_state.thema (Platzhalter) entfernt")
        _ss_ents["thema"] = ""

    # ── turn_type entity merge ──────────────────────────────────────
    turn_type = classification.turn_type
    new_entities = classification.entities

    if turn_type == "topic_switch":
        # Carry-over-Filter v3: Slots, die der Classifier UNVERÄNDERT aus dem
        # Vorturn zurückgibt, sind höchstwahrscheinlich Carry-over (kein echter
        # neuer Wert) → verwerfen. Private ``_``-Marker (Canvas/LP-State) bleiben.
        _prev_slots_pre = {
            k: v for k, v in (session_state.get("entities") or {}).items()
            if not str(k).startswith("_") and v
        }
        if classification.entities:
            _dropped_carry = []
            for k in list(classification.entities.keys()):
                if str(k).startswith("_"):
                    continue
                v = classification.entities.get(k)
                if v and _prev_slots_pre.get(k) == v:
                    classification.entities.pop(k)
                    _dropped_carry.append(k)
            if _dropped_carry:
                logger.info(
                    "topic_switch carry-over filter: popped %s (matched prev=%s)",
                    _dropped_carry, _prev_slots_pre,
                )
            new_entities = classification.entities
        _prev_slots = {
            k: v for k, v in (session_state.get("entities") or {}).items()
            if not str(k).startswith("_") and v
        }
        _preserved = {
            k: v for k, v in (session_state.get("entities") or {}).items()
            if str(k).startswith("_")
        }
        session_state["entities"] = _preserved
        for k, v in (new_entities or {}).items():
            if not v:
                continue
            # Carry-over: Classifier liefert exakt den alten Wert bei einem
            # topic_switch — verwerfen.
            if _prev_slots.get(k) == v:
                continue
            session_state["entities"][k] = v
    elif turn_type == "correction":
        for k, v in new_entities.items():
            if v:
                session_state["entities"][k] = v
    else:  # initial, follow_up, clarification
        for k, v in new_entities.items():
            if v:
                session_state["entities"][k] = v

    # ── Heuristik-Anreicherung (material_typ + type-focus medientyp) ──
    # Der Classifier extrahiert ``material_typ`` nicht immer; die Alias-Heuristik
    # fängt mehr Fälle (Plurale, Synonyme). In classification.entities heben,
    # damit R-5 (soft-create) matcht.
    _heuristic_mt = extract_material_type_from_message(req.message)
    if _heuristic_mt and not (classification.entities or {}).get("material_typ"):
        if classification.entities is None:
            classification.entities = {}
        classification.entities["material_typ"] = _heuristic_mt
        session_state.setdefault("entities", {})["material_typ"] = _heuristic_mt

    # Type-Focus: "nur videos" / "hast du Arbeitsblätter?" → medientyp aus der
    # ``_resolve_wanted_content_types``-Regex, damit LLM-Tool-Strip + Typ-Filter
    # + Search-CTA greifen.
    if not (classification.entities or {}).get("medientyp"):
        _wanted_for_inject = _resolve_wanted_content_types(
            req.message or "",
            session_entities=session_state.get("entities") or {},
            classification_entities=classification.entities or {},
        )
        if _wanted_for_inject:
            _injected_mt = sorted(_wanted_for_inject)[0]
            if classification.entities is None:
                classification.entities = {}
            classification.entities["medientyp"] = _injected_mt
            session_state.setdefault("entities", {})["medientyp"] = _injected_mt
            logger.info(
                "type-focus heuristic injected medientyp=%r (from %r)",
                _injected_mt, req.message,
            )

    # ── Speculative MCP prefetch (post-Classification) ──────────────
    # Für Such-Style-Intents die MCP-Suche im Hintergrund starten, während
    # Pattern/Policy/Context laufen; der ``respond``-Node konsumiert das Ergebnis.
    sp = await run_speculative_prefetch(req, classification, ctx.safety)
    ctx.spec_task = sp.spec_task
    ctx.spec_tool_name = sp.spec_tool_name
    ctx.spec_tool_args = sp.spec_tool_args
    ctx.spec_query = sp.spec_query
    ctx.extra_spec_tasks = sp.extra_spec_tasks
    ctx.spec_is_search_all = sp.spec_is_search_all
    ctx.search_all_extras = sp.search_all_extras

    # ── I05: Material-Typ-Slot-Anreicherung ─────────────────────────
    # Priorität: (1) Typ AUS DIESEM Turn, (2) Classifier-Entity, (3) sticky
    # Session-Wert. Nennt der User JETZT einen Typ, gewinnt er über den Vorturn.
    _detected_mt = extract_material_type_from_message(req.message)
    if classification.intent_id == "I05":
        _mt_session = session_state.get("entities", {}).get("material_typ")
        _mt_class = (classification.entities or {}).get("material_typ")
        _chosen = _detected_mt or _mt_class or _mt_session
        if _chosen and session_state["entities"].get("material_typ") != _chosen:
            session_state["entities"]["material_typ"] = _chosen
        # Auch in classification.entities heben, damit der Canvas-Flow den
        # frischen Wert liest, ohne Session neu abzufragen.
        if _chosen:
            if classification.entities is None:
                classification.entities = {}
            classification.entities["material_typ"] = _chosen

    return ctx
