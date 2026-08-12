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
import re
from typing import Any

from boerdi.domain.route_tail import _thema_plausible

logger = logging.getLogger(__name__)

# Shared LP-intent keyword vocabulary: substrings whose presence in a message
# signals a learning-path / lesson-prep request. Module-level so both the gate
# (here) and the LP fast-path body (topic extraction, services/lp_fast_path.py)
# read one source of truth — ALT had it inline in ``_route_pattern`` (Z. 197).
#
# **C1-f2c-b — dieses Set hat einen zweiten Auftrag.** Es ist nicht nur das
# Erkennungs-Vokabular: ``strip_lp_command_words`` unten streicht dieselben
# Wörter aus der Nachricht, um das Thema freizulegen. Ein neuer Eintrag wirkt
# also an zwei Stellen — er erkennt die Absicht UND verschwindet aus dem
# Suchbegriff. Für die englischen Einträge ist beides gewollt; wer hier etwas
# ergänzt, muss die zweite Wirkung mitdenken.
#
# Bis hierher blieb auf Englisch allein der Klassifikator-Pfad
# (``intent_id == "I04"``) — das deterministische Gate griff nie.
_lp_keywords = {
    "lernpfad", "unterrichtsvorbereitung", "unterrichtsstunde", "unterrichtsplanung",
    "unterricht vorbereiten", "unterrichtseinheit", "stundenentwurf",
    "learning path", "lesson plan", "lesson preparation", "lesson prep",
    "teaching unit", "unit plan", "prepare a lesson", "plan a lesson",
}


# Befehls- und Füllwörter, die um die Stichwörter herum stehen. Zusammen mit
# ``_lp_keywords`` legen sie das Thema frei, wenn der Klassifikator keines
# geliefert hat. Bis C1-f2c-b lag diese Liste als Schleife in
# ``services/lp_fast_path`` — mit dem zweisprachigen Stichwortsatz bekam sie
# einen zweiten Grund sich zu ändern und wohnt jetzt bei ihrem Vokabular.
#
# Die deutschen Einträge sind ALT-verbatim, inklusive ihrer Eigenart: gestrichen
# wird auf Teilzeichenketten, nicht auf Wörtern, also frisst ``"zu"`` auch das
# ``Zu`` in „Zucker". Die englischen Einträge tragen deshalb Leerzeichen —
# ohne sie ginge ``a`` in „maths" mit. Neue Einträge nach diesem Muster.
_LP_PHRASES = ["aus der sammlung", "erstelle mir", "erstelle bitte",
               "bitte einen", "bitte ein"]
_LP_FILLER = ["erstelle", "erstell", "daraus", "einen", "ein", "bitte", "mir",
              "wie sieht", "aus", "zum thema", "zur", "zu", "für", "fuer",
              # C1-f2c-b, englisch — mit Leerzeichen, s. Kommentar oben.
              "create ", "make ", "prepare ", "please", "i need ",
              "help me with ", " a ", " an ", " on ", " for ", " me ",
              " about ", " to "]


def strip_lp_command_words(message: str) -> str:
    """Die Nachricht ohne LP-Stichwörter und Befehlswörter — der Rest ist das
    Thema.

    Rückfall für ``services/lp_fast_path``, wenn die Klassifikation kein
    ``thema`` geliefert hat. Verhaltenserhaltend aus der dortigen Schleife
    gezogen; für deutsche Eingaben Zeichen für Zeichen dasselbe Ergebnis wie
    vorher, gepinnt in ``tests/test_lp_intent.py``.
    """
    out = message.lower()
    for phrase in _LP_PHRASES:
        out = out.replace(phrase, "")
    for kw in list(_lp_keywords) + _LP_FILLER:
        out = out.replace(kw, " ")
    return re.sub(r"\s+", " ", out).strip()


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
    # K1 (2026-08-11): I09/I10/I11 kamen mit M18/M19/M20 dazu und gehören aus
    # demselben Grund hierher wie I06 — es sind Aufträge AM BESTAND (anlegen,
    # prüfen, erschliessen), nicht der Wunsch nach einem neuen Lernpfad.
    # Warum das nötig ist, wurde gemessen: der Schnellweg feuert schon bei EINEM
    # Stichwort irgendwo im Satz, und „Unterrichtseinheit" steht in
    # ``_lp_keywords``. „Prüf, ob die Sammlung für meine Unterrichtseinheit
    # Optik reicht" löste ihn aus — und er läuft VOR der Musterwahl, M19 kam
    # also nie zum Zug. Im Nebensatz steht der Zweck, nicht die Aufgabe.
    _lp_blocking_intents = {
        "I07", "I08", "I02", "I06", "I09", "I10", "I11",
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
