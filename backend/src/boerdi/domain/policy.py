"""Policy layer (T-13/14 aus Triple-Schema v2).

Org-/Regulierungsregeln — getrennt von Safety (das User-Risiko behandelt).
Policy entscheidet, was per Konfiguration *erlaubt* ist: Tool-Whitelists je
Persona, Pflicht-Disclaimer, Lizenz-Restriktionen usw.

Regeln kommen aus ``01-base/policy.yaml`` (Studio-pflegbar, Tab „Identität &
Schutz"). 1:1-Port aus ALT ``app/services/policy_service.py`` (reine Regel-
Auswertung → Domäne; ``load_policy_config`` ist eine Read-Fassade).
"""

from __future__ import annotations

import re

from boerdi.api.schemas import PolicyDecision
from boerdi.i18n import DEFAULT, Locale, pick_localized
from boerdi.services.config_loader import load_policy_config


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
        match = rule.get("match", {}) or {}
        if "persona" in match and match["persona"] != persona_id:
            continue
        if "intent" in match and match["intent"] != intent_id:
            continue
        regex = match.get("message_regex")
        if regex:
            try:
                if not re.search(regex, msg):
                    continue
            except re.error:
                continue

        effect = rule.get("effect", {}) or {}
        rid = rule.get("id", "policy-rule")
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
