"""Das Safety-Gate des Agent-Endpunkts (AG-4 Teil B, Plan 2026-09-26 §8).

``/api/agent`` lief bis hier ohne Gate (§2.3 Punkt 3): ein Auftrag mit Krise
oder Drohung ging ungeprüft in die Schleife. Jetzt prüft ihn derselbe Weg wie
den Chat (``assess_safety``; fällt eine LLM-Stufe aus, bleibt das Regex-Gate —
dieselbe Rückfallebene wie in ``preflight``), BEVOR etwas geholt oder gerufen
wird:

* Krise (Selbstgefährdung, belegt durch Grund oder Kategorie) → der
  Krisentext aus dem Studio (``01-base/safety-config``, D-14);
* sonst hohes Risiko (Drohung, Rechtsverstoß) → die Abweisung;
* mittleres Risiko → die Schleife läuft, ohne die gesperrten Werkzeuge.

Die beiden ersten enden ohne Schleife mit ``stop_reason: "safety"``. Geloggt
werden Risiko und Muster, nie der Auftrag.
"""

from __future__ import annotations

import logging
from typing import Any

from boerdi.api.schemas import SafetyDecision
from boerdi.domain.config_models.base_governance import (
    KRISENTEXT_VORGABE,
    KRISENTEXT_VORGABE_EN,
)
from boerdi.i18n.bot_text import bot_text
from boerdi.i18n.locale import Locale, pick_localized
from boerdi.services.config_loader import load_safety_config
from boerdi.services.safety.service import (
    assess_safety,
    regex_rueckfall,
    sperrt_ohne_moderation,
)

logger = logging.getLogger(__name__)

#: Woran eine KRISE zu erkennen ist — am Beleg, nicht an der Muster-Kennung
#: (Review-Befund 2026-09-27). Die Kennung taugt nicht: das Regex-Gate setzt M01
#: fest, gleich was im Studio als ``crisis_pattern`` steht, und die Moderation
#: vergibt die Krisen-Kennung auch für andere harte Kategorien („Rest → M01",
#: ``services/safety/service.py``) — eine Waffenanfrage bekam so den Trost.
_KRISEN_GRUND = "crisis_signal_detected"
_KRISEN_KATEGORIEN = frozenset({"self_harm", "self_harm/intent"})


def _ist_krise(entscheid: SafetyDecision) -> bool:
    return (_KRISEN_GRUND in entscheid.reasons
            or bool(_KRISEN_KATEGORIEN & set(entscheid.flagged_categories)))


async def pruefe(auftrag: str, usage_acc: dict[str, Any] | None) -> SafetyDecision:
    """Die Safety-Entscheidung zum Auftrag; bei Ausfall das reine Regex-Gate."""
    try:
        return await assess_safety(auftrag, [], usage_acc=usage_acc)
    except Exception as err:
        logger.warning("agent: Safety-Prüfung fehlgeschlagen (%s) — es bleibt das "
                       "Regex-Gate", type(err).__name__)
        return regex_rueckfall(auftrag, [])


def _krisentext(cfg: dict[str, Any], sprache: Locale) -> str:
    """Der gepflegte Text; ein leeres Feld heißt „nicht gepflegt"."""
    de = str(cfg.get("crisis_message") or "").strip() or KRISENTEXT_VORGABE
    en = str(cfg.get("crisis_message_en") or "").strip() or KRISENTEXT_VORGABE_EN
    return pick_localized(de, en, sprache)


def stopp_text(entscheid: SafetyDecision, sprache: Locale) -> str | None:
    """Der Text, mit dem der Lauf gar nicht erst beginnt — oder ``None``."""
    if entscheid.risk_level == "high" and _ist_krise(entscheid):
        logger.info("agent: Sicherheits-Gate — Krise, Krisentext statt Lauf")
        return _krisentext(load_safety_config(), sprache)
    if entscheid.risk_level == "high" or entscheid.enforced_pattern:
        logger.info("agent: Sicherheits-Gate — Risiko %s, Muster %s, Abweisung statt Lauf",
                    entscheid.risk_level, entscheid.enforced_pattern or "-")
        return bot_text(sprache, "error.safetyBlocked")
    if sperrt_ohne_moderation(entscheid):
        # Paket 18A, Review 18: derselbe Schalter wie im Chat.
        logger.info("agent: Sicherheits-Gate — ohne Moderation, Absage statt Lauf")
        return bot_text(sprache, "error.moderationUnavailable")
    return None
