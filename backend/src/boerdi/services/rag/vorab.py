"""Die Einbettung der Nachricht vorab — neben der Klassifikation (T1, Paket 7).

Nutzer-Entscheid 2026-10-09: „RAG neben der Klassifikation“. Der Muster-Weg holt
seine ``mode: always``-Bereiche erst nach der Musterwahl (``tool_loop_messages``);
die Klassifikation davor dauert Sekunden. Gemessen 2026-10-09 (OpenAI direkt,
warm): die Einbettung 0,28–1,0 s, die ganze Suche 0,9–1,2 s. ``assess`` startet
deshalb die Einbettung neben der Klassifikation, und der Abruf nimmt den Vektor,
statt selbst einzubetten.

**Nur die Einbettung, nicht die ganze Suche.** Das Nachsortieren ist CPU-Arbeit im
gedeckelten Pool (auf dem 2-Kern-Server einer zur Zeit), und die meisten Muster —
alle Suchmuster — nehmen kein RAG: vorab gerechnet liefe es dort umsonst und nähme
dem echten Abruf und dem Karten-Filter die Kerne. Eine Einbettung über das Netz
kostet dagegen einen kleinen Aufruf. Aus demselben Grund wird eine LOKALE
Einbettung (``EMBED_BACKEND=local``, auch CPU) nicht vorab gerechnet.
"""

from __future__ import annotations

import logging
from typing import Any

from boerdi.obs.zeiten import schritt
from boerdi.services.config_loader import load_rag_config
from boerdi.services.llm_parallel import LlmAusgelastet
from boerdi.services.rag.embed import embed_backend, embed_text

logger = logging.getLogger(__name__)

#: (Text, Vektor) — der Vektor gilt nur für genau diesen Text.
Einbettung = tuple[str, list[float]]


def _hat_always_bereich(rag: dict[str, Any]) -> bool:
    return any(isinstance(d, dict) and d.get("mode") == "always" for d in rag.values())


async def rag_einbettung_vorab(text: str) -> Einbettung | None:
    """Die Einbettung von ``text`` — oder ``None``, wenn sich Vorarbeit nicht lohnt
    (kein ``always``-Bereich, lokale Einbettung) oder sie scheitert. Wirft nicht:
    Vorarbeit darf den Zug nicht kosten, der Abruf bettet dann selbst ein."""
    try:
        if embed_backend() == "local" or not _hat_always_bereich(load_rag_config()):
            return None
        with schritt("assess.rag_einbettung"):
            return text, await embed_text(text, kind="query")
    except LlmAusgelastet:
        # Review 2026-10-30: Last — die Frist meldet ``llm_platz_frist`` schon gedrosselt.
        logger.info("Einbettung vorab: kein LLM-Platz frei")
        return None
    except Exception as e:  # noqa: BLE001 — siehe Docstring
        # Ohne Traceback (Review B-1): fällt der Dienst aus, stünde er sonst in
        # jedem Muster-Zug im Protokoll; den Fehler meldet der Abruf ohnehin.
        logger.warning("Einbettung vorab gescheitert (%s) — der Abruf bettet selbst ein",
                       type(e).__name__)
        logger.debug("Einbettung vorab: Einzelheiten", exc_info=True)
        return None


def vektor_fuer(einbettung: Einbettung | None, text: str) -> list[float] | None:
    """Der Vektor, wenn er für genau ``text`` gerechnet wurde — sonst ``None``."""
    if einbettung is None or einbettung[0] != text:
        return None
    return einbettung[1]
