"""Safety stage 3 — German legal-category classifier.

Port of ALT ``safety_service._llm_legal_classify``. Covers Persönlichkeitsrechte
and Datenschutz (which the moderation API does not), plus a second read on
Strafrecht/Jugendschutz. The system prompt and JSON parsing are 1:1 with ALT;
the transport moves to ``services.llm.chat_completion`` (provider routing,
retries and the concurrency semaphore are centralised there).

Fail-open by design: any error returns ``{}`` so the regex gate stays the floor.
"""

from __future__ import annotations

import json
import logging

from boerdi.services.llm import chat_completion

logger = logging.getLogger(__name__)

_LEGAL_SYSTEM = """Du bist ein juristischer Sicherheits-Klassifikator für einen Bildungs-Chatbot.
Prüfe die Nutzeranfrage auf Verstöße gegen deutsches Recht.
Antworte AUSSCHLIESSLICH mit gültigem JSON nach diesem Schema:
{
  "strafrecht": {"risk": 0.0..1.0, "reason": "kurz"},
  "jugendschutz": {"risk": 0.0..1.0, "reason": "kurz"},
  "persoenlichkeitsrechte": {"risk": 0.0..1.0, "reason": "kurz"},
  "datenschutz": {"risk": 0.0..1.0, "reason": "kurz"}
}

Bewerte realistisch — auch mittelstarke Verstöße sollen ein risk > 0.5 bekommen.
Risk 0 = unauffällig, 0.3 = grenzwertig, 0.6 = klar problematisch, 1 = schwerer Verstoß.

- Strafrecht: Volksverhetzung (§130), Beleidigung (§185), Bedrohung (§241),
  Anleitungen zu Straftaten, Gewaltverherrlichung
- Jugendschutz: Inhalte ungeeignet für Minderjährige, Suizidthemen, exzessive Gewalt
- Persönlichkeitsrechte: Beleidigung, Hassäußerungen (auch gegen Organisationen,
  Marken, Produkte oder Plattformen wie z.B. "ich hasse X"), Rufschädigung,
  Verleumdung, Outing, unerlaubte Personendaten, Doxing
- Datenschutz: PII (Passwörter, Adressen, IDs), Aufforderung zur Preisgabe

WICHTIG: Aussagen wie "ich hasse [Organisation/Plattform/Person]" sind
Persönlichkeitsrechte mit risk >= 0.6 — auch ohne explizite Beleidigung."""


async def classify_legal(message: str) -> dict[str, dict]:
    """GPT classifier for German legal categories.

    Returns e.g. ``{"strafrecht": {"risk": 0.1, "reason": "..."}, ...}`` (one entry
    per known category), or ``{}`` on any error.
    """
    try:
        resp = await chat_completion(
            messages=[
                {"role": "system", "content": _LEGAL_SYSTEM},
                {"role": "user", "content": message[:2000]},
            ],
            temperature=0.0,
            max_tokens=300,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content or "{}"
        data = json.loads(raw)
        out: dict[str, dict] = {}
        for cat in ("strafrecht", "jugendschutz", "persoenlichkeitsrechte", "datenschutz"):
            entry = data.get(cat, {})
            if isinstance(entry, dict):
                out[cat] = {
                    "risk": float(entry.get("risk", 0.0) or 0.0),
                    "reason": str(entry.get("reason", ""))[:200],
                }
        return out
    except Exception as e:  # noqa: BLE001 — fail-open by design (regex floor stays)
        logger.warning("LLM legal classifier failed: %s", e)
        return {}
