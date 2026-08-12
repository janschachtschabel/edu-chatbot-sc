"""01-base/engine — welche Maschine antwortet, als gepflegte Vorgabe.

**Ein unlesbarer Bereich liefert die Vorgabe, nicht ``None``.** Das ist der
Unterschied zum Nachbarn ``pricing``: dort heißt „unlesbar" *kein Preis
angesetzt*, und der Aufrufer muss das wissen. Hier gibt es keinen dritten
Zustand — irgendeine Maschine muss den Zug beantworten. Und welche das im
Zweifel ist, ist eine Sicherheitsfrage: ein Tippfehler im YAML darf den
ausgelieferten Chatbot nicht auf einen anderen Antwortweg schalten. Also fällt
jeder Fehler auf ``EngineArea()`` zurück, und das ist die Muster-Engine.
"""

from __future__ import annotations

import logging

from boerdi.domain.config_models.engine import EngineArea
from boerdi.services.config_loader._store import area

logger = logging.getLogger(__name__)


def load_engine() -> EngineArea:
    """Der gepflegte Umschalter — bei jedem Fehler die Vorgabe (Muster-Engine)."""
    try:
        return EngineArea.model_validate(area("01-base/engine"))
    except Exception:
        logger.warning(
            "engine: 01-base/engine ist unlesbar — der Zug läuft mit der "
            "Muster-Engine weiter", exc_info=True,
        )
        return EngineArea()
