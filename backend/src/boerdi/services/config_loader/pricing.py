"""Preistafel-Loader (K3/K4) — Gegenstück zu ``gold_flows.py``.

Kein ALT-Vorbild: ALT rechnete nicht ab. Die Toleranz ist trotzdem dieselbe
wie dort — eine kaputte oder von Hand verunglückte Tafel darf die
Kostenschau nicht mit einem 500 beenden. ``seed_io.import_tree`` schreibt
ungeprüfte Dicts in den Store, dieser Fall ist also erreichbar.

``None`` heißt „unlesbar", eine leere Tafel heißt „nichts gepflegt". Beide
enden ohne Preis, aber aus verschiedenen Gründen, und die Auswertung sagt
welcher: sähen sie gleich aus, zeigte ein YAML-Tippfehler denselben
Bildschirm wie eine frische Installation, und der Grund stünde nur im Log.
"""

from __future__ import annotations

import logging

from boerdi.domain.config_models.pricing import PricingArea
from boerdi.services.config_loader._store import area

logger = logging.getLogger(__name__)


def load_pricing() -> PricingArea | None:
    """Die gepflegte Preistafel, oder ``None``, wenn der Bereich unlesbar ist.

    Ein fehlender Bereich ist kein Fehler: er kommt als leeres Dict und
    validiert zur leeren Tafel („nichts gepflegt"). ``None`` bekommt nur, wer
    einen Bereich vorfindet, der nicht zum Modell passt.
    """
    try:
        return PricingArea.model_validate(area("01-base/pricing"))
    except Exception:
        logger.warning(
            "pricing: 01-base/pricing ist unlesbar — es wird kein Preis "
            "angesetzt", exc_info=True,
        )
        return None
