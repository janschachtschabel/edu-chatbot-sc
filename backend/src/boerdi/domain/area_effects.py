"""Wo ein Config-Bereich wirkt — je Maschine (ST-5).

Das Studio zeigt daraus „Wirkt in: Muster-Maschine · Agent-Schleife" an jedem
Abschnitt und ein Banner auf Seiten, die die Vorgabe-Maschine nicht nutzt
(``GET /api/config/effects``). Nach Code-Lesart vom 2026-09-27, je Bereich
vom Lader bis zu seinen Aufrufern verfolgt; der Stand von §2.2 im Plan
2026-09-26 ist damit überholt (E-4 brachte Leitplanken und Personas in den
Agent-Kopf, SF-1 die Krisen-Züge, ST-9 die toten Einstellungen).

Die Stufen:

* ``voll`` — die Maschine liest den Bereich, seine Einstellungen wirken.
  Einzelne tote Felder senken die Stufe nicht, solange der Großteil wirkt;
  ihre Hilfetexte im Studio sagen es.
* ``teilweise`` — nur ein Teil wirkt (oder der Großteil ist tot).
* ``krise`` — nur bei Krisen- und Drohungs-Zügen: erzwingt das Gate M01/M02,
  antwortet der Muster-Weg, auch unter der Agent-Schleife (SF-1,
  ``engine_choice.zug_laeuft_ueber_die_schleife``).
* ``keine`` — die Maschine liest den Bereich nie, oder nichts davon wirkt.

Ein neuer Bereich ohne Eintrag lässt ``tests/test_area_effects.py`` scheitern.
"""

from typing import Final, Literal

Engine = Literal["pattern", "agent"]
Effect = Literal["voll", "teilweise", "krise", "keine"]

ENGINES: Final[tuple[Engine, ...]] = ("pattern", "agent")
EFFECTS: Final[tuple[Effect, ...]] = ("voll", "teilweise", "krise", "keine")


def _e(pattern: Effect, agent: Effect) -> dict[str, Effect]:
    return {"pattern": pattern, "agent": agent}


AREA_EFFECTS: Final[dict[str, dict[str, Effect]]] = {
    # Nur der Muster-Prompt liest sie (response_prompt_builder); unter der
    # Agent-Schleife allein auf Krisen-Zügen.
    "01-base/base-persona": _e("voll", "krise"),
    "02-domain/domain-rules": _e("voll", "krise"),
    "02-domain/wlo-plattform-wissen": _e("voll", "krise"),
    "03-patterns": _e("voll", "krise"),
    "01-base/tone-modifiers": _e("voll", "krise"),
    # E-4: der Agent-Kopf bekommt die Schutzregeln R-05/08/13/15 samt „Zu R-NN".
    "01-base/guardrails": _e("voll", "teilweise"),
    # Nur `repo_base_url`/`known_repo_hosts` wirken immer; die Nachauswahl nur
    # mit CARD_PIPELINE_V2, drei Felder ohne Leser — in beiden Maschinen gleich.
    "01-base/card-pipeline": _e("teilweise", "teilweise"),
    # Nur im Klassifikator-Prompt; die Agent-Schleife klassifiziert nicht.
    "01-base/classify-overrides": _e("voll", "keine"),
    "04-entities/entities": _e("voll", "keine"),
    "04-intents/intents": _e("voll", "keine"),
    "04-signals/signal-modulations": _e("voll", "keine"),
    "01-base/placeholder-topics": _e("voll", "keine"),
    # Läuft vor der Maschinenwahl (Kontext-Begrüßung, Direktaktionen).
    "01-base/context-actions": _e("voll", "voll"),
    # Agent: nur `persona_formality` als Rückfall der Anrede im Agent-Kopf.
    "01-base/device-config": _e("voll", "teilweise"),
    # Agent: Gruppen, Einzelbox, Chip-Deckel, Dokumentbox; nicht die
    # Konsistenz-Prüfung der Werkzeug-Schleife und die Muster-Einträge.
    "01-base/display-rules": _e("voll", "teilweise"),
    # Muster: `mode`, `muster_skills`; Agent: `mode`, `agent.*`, `agent_rolle`.
    "01-base/engine": _e("teilweise", "teilweise"),
    # Alle gelesenen Felder wirken in beiden (`default_enabled` ist tot).
    "01-base/guide-mode": _e("voll", "voll"),
    "01-base/header-nav": _e("voll", "voll"),
    # Agent: nur Regeln auf Regex, P-AND oder I01 — die Schleife klassifiziert nicht.
    "01-base/policy": _e("voll", "teilweise"),
    "01-base/pricing": _e("voll", "voll"),
    # `memory` steuert nur Gedächtnis-Einträge, die allein der Muster-Prompt nutzt.
    "01-base/privacy-config": _e("voll", "teilweise"),
    # Nur `logging.enabled` wird gelesen — in beiden Maschinen.
    "01-base/quality-log-config": _e("teilweise", "teilweise"),
    # Gate, Protokoll und Drosselung laufen vor der Maschinenwahl; den
    # Krisentext liest nur das Gate von `/api/agent`.
    "01-base/safety-config": _e("teilweise", "voll"),
    "01-base/website-tour": _e("voll", "voll"),
    "01-base/welcome-config": _e("voll", "voll"),
    # Der einzige Leser steckt in einem Zweig, der nie läuft (ST-9).
    "01-base/widget-modes": _e("keine", "keine"),
    # `message_rules` wirken ohne Neustart (2026-10-01; ein ungültiges Muster weist
    # das Speichern ab, Paket 4 D6); `rag_area_rules` ohne Leser.
    "02-domain/guide-rules": _e("teilweise", "teilweise"),
    # E-4: `formality` und `label` jeder Persona im Anrede-Block des Agent-Kopfs.
    "04-personas": _e("voll", "teilweise"),
    # Agent: die Zustands-Direktive im Chip-Generator; der Zustand bleibt meist S1.
    "04-states/states": _e("voll", "teilweise"),
    # Ihre einzigen Leser ruft kein Produktionscode (`domain/canvas/intent.py`).
    "05-canvas/create-triggers": _e("keine", "keine"),
    "05-canvas/edit-triggers": _e("keine", "keine"),
    # Nur der Canvas-Schnellweg; Schnellwege sind unter der Agent-Schleife aus.
    "05-canvas/material-types": _e("voll", "keine"),
    # Agent: nur `analytical_personas` in den Chip-Hinweisen.
    "05-canvas/persona-priorities": _e("voll", "teilweise"),
    # `merge` läuft für jede Maschine; im Muster-Weg filtert sein Materialtyp
    # die Karten. Agent: der Typ gilt nur für den Zug, der Nachfilter ist aus
    # (Runde 2) — er erreicht allein die Nachauswahl mit CARD_PIPELINE_V2.
    "05-canvas/type-aliases": _e("voll", "teilweise"),
    "05-knowledge/mcp-servers": _e("voll", "voll"),
    # Muster: `mode` und `description`; Agent: der Schalter `agent` und `description`.
    "05-knowledge/rag-config": _e("teilweise", "teilweise"),
    "eval/gold-flows": _e("voll", "voll"),
}
