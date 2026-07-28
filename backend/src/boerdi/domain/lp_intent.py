"""LP-intent gate for the learning-path fast-path (P4-4-Tail).

``detect_lp_intent`` is the entry gate of ALT ``_route_pattern``'s LP fast-path
(the prolog, Z. 196-281): it decides whether an LP request should route to the
learning-path builder (``_has_lp_intent``) and resolves the topic (``_thema``),
rejecting a classifier substring-misread as garbage (via ``_thema_plausible``)
and forcing pattern degradation when an LP intent lacks a concrete topic.

Framework-free (stdlib + logger) → ``domain/``. Reuses ``_thema_plausible`` from
:mod:`boerdi.domain.route_tail` (shared with the Canvas fast-path). Verbatim port
of the ALT prolog decision statements; the body-init locals
(``classification_dict``, the ``_last_contents``/``_last_collections`` JSON, the
card accumulator) belong to the LP-body slice, not this gate. Consumed once the
LP fast-path lands in P4-5.
"""

from __future__ import annotations

import logging
from typing import Any

from boerdi.domain.route_tail import _thema_plausible

logger = logging.getLogger(__name__)

# Shared LP-intent keyword vocabulary: substrings whose presence in a message
# signals a learning-path / lesson-prep request. Module-level so both the gate
# (here) and the LP fast-path body (topic extraction, services/lp_fast_path.py)
# read one source of truth — ALT had it inline in ``_route_pattern`` (Z. 197).
_lp_keywords = {
    "lernpfad", "unterrichtsvorbereitung", "unterrichtsstunde", "unterrichtsplanung",
    "unterricht vorbereiten", "unterrichtseinheit", "stundenentwurf",
}


def detect_lp_intent(
    *,
    classification: Any,
    message: str,
    session_state: dict,
    pattern_output: dict,
) -> tuple[bool, str]:
    """Decide whether the LP fast-path may fire and resolve its topic.

    Returns ``(_has_lp_intent, _thema)``. Mutates in place (ALT parity): clears
    ``session_state["entities"]["thema"]`` when the classifier's topic is garbage,
    and forces ``pattern_output`` degradation (``degradation`` + ``missing_slots``)
    when an LP intent is present but no concrete topic is known.
    """
    _msg_lower = message.lower()
    # LP-Fast-Path darf NICHT feuern wenn der Classifier einen non-create
    # Intent gewählt hat. Der User will dann z.B. einen bestehenden Lernpfad
    # bearbeiten (I06), bewerten (I02) oder Feedback geben
    # (I07) — nicht einen neuen erstellen.
    # Welle C Sprint 4: I03 ist in I03 gemerged (Download =
    # Repo-Link-Output von Search-Pattern, kein Backend-File-Stream).
    _lp_blocking_intents = {
        "I07", "I08", "I02", "I06",
    }
    # Persona-Block: bestimmte Personas profitieren NICHT von einem
    # didaktisch strukturierten Lernpfad. P-RED/P-ENT erwarten
    # Recherche-Material für Artikel/Positionspapiere — nicht eine
    # Stunden-Strukturierung mit Lernzielen. Eval-Befund: für diese
    # Personas führt LP-Generierung zu unnatürlichen Antworten.
    _persona_blocks_lp = session_state.get("persona_id") in (
        "P-RED", "P-ENT",
    )
    _has_lp_intent = (
        classification.intent_id not in _lp_blocking_intents
        and not _persona_blocks_lp
        and (
            any(kw in _msg_lower for kw in _lp_keywords)
            or classification.intent_id == "I04"
        )
    )

    # Only route to LP builder if a concrete topic is known — fach alone is not enough
    _thema = session_state.get("entities", {}).get("thema", "")

    if _thema and not _thema_plausible(_thema):
        logger.info("LP fast-path: thema %r rejected as garbage, forcing degradation", _thema)
        _thema = ""
        session_state.setdefault("entities", {})["thema"] = ""

    # Force degradation when LP keywords detected but thema missing
    if _has_lp_intent and not _thema:
        _missing = [s for s in ["thema", "stufe"] if not session_state.get("entities", {}).get(s)]
        if _missing:
            pattern_output["degradation"] = True
            pattern_output["missing_slots"] = list(set(
                pattern_output.get("missing_slots", []) + _missing
            ))

    return _has_lp_intent, _thema
