"""Pure decision helpers for the route node's fast-path tail (P4-4-Tail).

Two pure helpers lifted out of ALT ``_route_pattern``'s tail that bracket the
fast-path routing: ``_thema_plausible`` gates whether the LP/Canvas fast-path may
fire for a given topic (rejects classifier garbage that a substring-misread of the
message produced), and ``reconcile_effective_pattern`` resolves which pattern
actually executed once a fast-path has (or has not) routed.

Framework-free (stdlib only) → ``domain/``. ``_thema_plausible`` is a verbatim 1:1
port of ALT's nested helper (dedented to top level); ``reconcile_effective_pattern``
is an inline→function extraction of the ALT tail (statements verbatim). Both are
consumed once the LP/Canvas fast-paths + effective-pattern wiring land in P4-5.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _thema_plausible(t: str) -> bool:
    if not t:
        return False
    import re as _rex
    _tl = t.lower().strip(" .,:;?!")
    if len(_tl) < 3:
        return False
    # Starts with pronoun/article → Satzrest
    if _rex.match(r"^(das|dieses|diese|dieser|der|die|den|dem|des|ein|eine|einen|einem|einer|eines|"
                  r"ihm|ihr|ihn|ihnen|mir|mich|dir|dich|uns|euch|es|sie|er)\b", _tl):
        return False
    # Starts with question/meta word
    if _rex.match(r"^(wie|was|wo|wann|warum|wer|wieso|wieviel|kannst|kann|könnte|könntest|"
                  r"hast|habt|gibt|gibts|ideen|vorschläge|tipps|möglichkeiten|"
                  r"eine frage|frage|ne frage|irgendwas|bitte|mal|gerne|gern|"
                  r"also|so|mal eben)\b", _tl):
        return False
    if t.rstrip().endswith("?"):
        return False
    # Query/meta verbs → existierendes Material, nicht LP-Thema
    if _rex.search(r"\b(runterladen|herunterladen|bewerten|bewertung|prüfen|"
                   r"ansehen|anschauen|kopieren|teilen|löschen|exportieren|"
                   r"ausdrucken|drucken|speichern|öffnen|schließen|abbrechen|"
                   r"bereitstellen|bereitstellung|schicken|senden|zusenden|"
                   r"weiterleiten|feedback|meinung|bewerte|review)\b", _tl):
        return False
    # Fragment-Rest nach Material-Typ-Strip: "e der aktuellen..."
    if _rex.match(r"^(e|er|es|en|em|n|s)\s", _tl):
        return False
    return True


def reconcile_effective_pattern(winner, _lp_routed, _canvas_routed, tools_called):
    """Resolve which pattern actually executed once the LP/Canvas fast-paths
    have (or have not) routed material (ALT ``_route_pattern`` tail).

    The engine may have picked e.g. M03 (slot clarification) while a fast-path
    then delivered material — quality logs, inline-document routing and
    telemetry must see the EXECUTED pattern, not the engine's original pick.
    Returns ``(effective_pattern_id, effective_pattern_label)``.
    """
    _effective_pattern_id = winner.id
    _effective_pattern_label = winner.label
    if _lp_routed:
        _effective_pattern_id = "M09"
        _effective_pattern_label = "Lernpfad-Erstellung"
        # _qr_mode/_qr_max wurden im LP-Fast-Path bereits auf die
        # M09-Policy gesetzt (inkl. evtl. laufendem Spec-Task).
    elif _canvas_routed:
        # _canvas_routed=True kann zwei Dinge bedeuten:
        # (a) Echter Canvas-Inhalt wurde generiert (tools_called enthält
        #     ``canvas_service.generate_canvas_content``) → M10.
        # (b) Slot-Klärungs-Branch („Welches Material?" / „Zu welchem
        #     Thema?") — tools_called ist leer, response_text ist eine
        #     kurze Rückfrage. Hier MUSS effective auf M03 runter, sonst
        #     packt die InlineDocument-Routing-Logik die Slot-Frage in
        #     eine gerahmte Box (eval-316d36 P-RED/I05-Befund: Slot-
        #     Klärung erschien als Inline-Box mit Topic-Title).
        if "canvas_service.generate_canvas_content" in (tools_called or []):
            _effective_pattern_id = "M10"
            _effective_pattern_label = "KI-Inhalt-Generierung"
        else:
            _effective_pattern_id = "M03"
            _effective_pattern_label = "Slot-Klärung"
    if _effective_pattern_id != winner.id:
        logger.info(
            "effective_pattern override: engine=%s → executed=%s "
            "(lp_routed=%s canvas_routed=%s)",
            winner.id, _effective_pattern_id, _lp_routed, _canvas_routed,
        )
    return _effective_pattern_id, _effective_pattern_label
