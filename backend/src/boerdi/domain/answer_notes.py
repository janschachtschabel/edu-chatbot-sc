"""Die sichtbaren Hinweise an einer Antwort: Policy-Disclaimer + Safety-Notiz.

Zwei reine Textregeln, die ALT im Rumpf von ``_produce_answer`` und NEU bis
A4c-2b im Knoten ``graph/nodes/respond.py`` standen. Sie gehören keinem der
beiden Antwort-Erzeuger: sie hängen an ``policy`` und ``safety`` — nicht daran,
WER den Text gemacht hat. Sichtbar wurde das mit dem Agent-Modus, der denselben
Text zu verantworten hat, ohne durch ``generate_response`` zu laufen.

**Ohne die Verschiebung wäre der Verlust still gewesen:** ``assess_policy`` und
das Sicherheits-Gate laufen im Agent-Modus unverändert (A4b/A4c-1), ihre
Ergebnisse wären dort aber an keine Antwort mehr gekommen — ein redaktionell
gepflegter Pflicht-Hinweis fiele weg, und eine Anfrage mit mittlerem Risiko
bekäme keine Notiz. Beides ohne Fehlermeldung.

Verhaltensgleiche Verschiebung, Zeilen unverändert.
"""

from __future__ import annotations

from boerdi.api.schemas import PolicyDecision, SafetyDecision


def append_answer_notes(
    response_text: str, *, policy: PolicyDecision, safety: SafetyDecision
) -> str:
    """Policy-Disclaimer und Medium-Risk-Notiz an die Antwort hängen.

    Beide Regeln greifen nur bei nicht-leerem ``response_text``: an eine Antwort,
    die es nicht gibt, gehört auch kein Hinweis. Gibt den (ggf. erweiterten) Text
    zurück; ``policy``/``safety`` bleiben unberührt.
    """
    # Policy-Disclaimer anhängen (falls vorhanden).
    if policy.required_disclaimers and response_text:
        disclaimers = "\n\n".join(f"_{d}_" for d in policy.required_disclaimers)
        response_text = f"{response_text}\n\n{disclaimers}"

    # ── Safety-Hinweis (Medium-Risk) ───────────────────────────────
    # Bei High-Risk übernimmt M01 die ganze Antwort; bei Medium-Risk gibt der LLM
    # normal, wir hängen aber einen sichtbaren Hinweis an (Transparenz statt
    # stilles Blockieren).
    if safety.risk_level == "medium" and response_text:
        _safety_notes: list[str] = []
        _legal_de = {
            "strafrecht": "strafrechtlich relevante",
            "jugendschutz": "jugendschutzrelevante",
            "persoenlichkeitsrechte": "persoenlichkeitsrechtliche",
            "datenschutz": "datenschutzbezogene",
        }
        if safety.legal_flags:
            _cats = ", ".join(_legal_de.get(f, f) for f in safety.legal_flags[:2])
            _safety_notes.append(
                f"Hinweis: Deine Anfrage beruehrt {_cats} Themen — ich kann dazu "
                f"keine eigenstaendige rechtliche Beratung geben."
            )
        elif safety.blocked_tools:
            _safety_notes.append(
                "Hinweis: Fuer diese Anfrage habe ich die Suche vorsichtshalber "
                "eingeschraenkt."
            )
        elif "possible_prompt_injection" in safety.reasons:
            _safety_notes.append(
                "Hinweis: Deine Nachricht enthaelt Formulierungen, die wie eine "
                "Anweisung an mich aussehen. Ich halte mich an meine Regeln."
            )
        if _safety_notes:
            response_text = (
                f"{response_text}\n\n"
                + "\n\n".join(f"_{n}_" for n in _safety_notes)
            )
    return response_text
