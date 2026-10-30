"""Policy layer (T-13/14 aus Triple-Schema v2).

Org-/Regulierungsregeln — getrennt von Safety (das User-Risiko behandelt).
Policy entscheidet, was per Konfiguration *erlaubt* ist: Tool-Whitelists je
Persona, Pflicht-Disclaimer, Lizenz-Restriktionen usw.

Regeln kommen aus ``01-base/policy.yaml`` (Studio-pflegbar, Tab „Identität &
Schutz"). 1:1-Port aus ALT ``app/services/policy_service.py`` (reine Regel-
Auswertung → Domäne; ``load_policy_config`` ist eine Read-Fassade).
"""

from __future__ import annotations

import functools
import logging
import math

import regex

from boerdi.api.schemas import PolicyDecision
from boerdi.domain import regel_regex
from boerdi.i18n import DEFAULT, Locale, pick_localized
from boerdi.obs.drossel import gedrosselt
from boerdi.services.config_loader import load_policy_config

logger = logging.getLogger(__name__)


@functools.lru_cache(maxsize=256)
def _uebersetzt(muster: str) -> tuple[regex.Pattern | None, str]:
    """Ein Muster je Text einmal übersetzt (Paket 18E: bis dahin je Zug neu) — mit dem
    Fehlertext statt der Ausnahme, damit der Cache keine Tracebacks hält."""
    try:
        return regel_regex.uebersetze(muster, ignore_case=False), ""
    except regel_regex.RegexFehler as fehler:
        return None, str(fehler)


def assess_policy(
    message: str,
    persona_id: str,
    intent_id: str,
    lang: Locale = DEFAULT,
) -> PolicyDecision:
    """Policy-Regeln anwenden und eine ``PolicyDecision`` zurückgeben.

    Jede Regel in policy.yaml kann definieren:
      match: { persona?, intent?, message_regex? }
      effect: { block_tools?, disclaimer?, disclaimer_en? }

    ``lang`` wählt den Hinweis-Text (C1-g2c). ``disclaimer_en` braucht keine
    Modelländerung: ``effect`` ist im Bereichsmodell ein freies Dict, der
    Schlüssel reist als ungepinnter Wert mit.

    Hinweis: Policy erzwingt KEINE harte Blockade (Guardrail R-01 „nie
    blockieren") — sie sperrt nur einzelne Tools und hängt Pflicht-Disclaimer an.
    """
    decision = PolicyDecision()
    cfg = load_policy_config()
    rules = cfg.get("rules", []) or []
    msg = (message or "").lower()

    for rule in rules:
        rid = rule.get("id", "policy-rule")
        match = rule.get("match", {}) or {}
        if "persona" in match and match["persona"] != persona_id:
            continue
        if "intent" in match and match["intent"] != intent_id:
            continue
        muster = match.get("message_regex")
        if muster:
            # Kein Text trifft nie: die Speicherprüfung weist ihn ab, ein alter
            # Bestand bräche sonst jeden Zug mit TypeError (Review Paket 6).
            if not isinstance(muster, str):
                continue
            # Mit Zeitgrenze (Paket 6, B1); wie bisher ohne IGNORECASE, die
            # Nachricht ist schon klein geschrieben.
            uebersetzt, fehler = _uebersetzt(muster)
            if uebersetzt is None:
                # Paket 18E (C3): die Regel fiel still weg — auch ein Pflicht-Hinweis oder
                # eine Werkzeugsperre. Das Speichern weist solche Muster ab; ein alter Stand
                # meldet sich einmal je Regel und Muster, nie mit der Nachricht.
                gedrosselt(logger, logging.WARNING, f"policy:{rid}:{muster}", math.inf,
                           "Policy-Regel %s greift nicht: ungültiges Muster (%s)", rid, fehler)
                continue
            if not regel_regex.trifft(uebersetzt, msg):
                continue

        effect = rule.get("effect", {}) or {}
        decision.matched_rules.append(rid)

        for t in effect.get("block_tools", []) or []:
            if t not in decision.blocked_tools:
                decision.blocked_tools.append(t)
        # Erst wählen, dann entdoppeln: zwei Regeln können denselben englischen
        # Hinweis tragen und verschiedene deutsche. Verglichen wird der Text,
        # der wirklich in der Antwort landet.
        disc = pick_localized(
            str(effect.get("disclaimer") or ""),
            str(effect.get("disclaimer_en") or ""),
            lang,
        )
        if disc and disc not in decision.required_disclaimers:
            decision.required_disclaimers.append(disc)

    return decision
