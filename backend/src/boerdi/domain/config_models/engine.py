"""01-base/engine — welche Maschine einen Zug beantwortet.

Drei Wege stehen zur Wahl. Die **Muster-Engine** ist der Bestand: Klassifikator,
Musterwahl, gebundene Werkzeugliste. Die **Agent-Schleife** überlässt dem Modell
alles — Systemprompt plus der volle Werkzeugkatalog, keine Muster, kein
Klassifikator. Sie ist für Einbettungen gedacht, in denen der Chat-Rahmen fehlt
(Browser-Plugin, edu-sharing), und zugleich der Versuchsaufbau für die Frage, ob
sie im Chat schneller und besser ist.

Der **Hybrid** ist die Antwort auf genau diese Frage: dieselbe Schleife, aber mit
dem Musterkatalog als Werkzeug. Er spart den Klassifikator wie die Agent-Schleife
und behält die redaktionell gepflegten Muster wie der Bestand — nur wählt sie das
Modell selbst, und erst wenn es die Trefferlage kennt.

**Die Vorgabe ist ``pattern``, und das ist eine Zusage**: ohne Pflege ändert sich
am ausgelieferten Chatbot nichts. Der Bereich ist rein additiv — schaltet ihn
niemand um, wird die Agent-Schleife nie betreten.

Ein eigener Bereich statt eines Feldes in ``01-base/policy``: „welche Maschine
antwortet" ist ein neuer Begriff, er trägt die Deckel der Schleife mit, und in
``policy`` versteckt machte er jenen Bereich zweideutig. Kein ALT-Gegenstück —
ALT kannte nur einen Weg.

**Warum ``Literal`` und kein freier String.** Der Studio-Editor rendert selbst,
aus einer gemessenen JSON-Schema-Teilmenge (``schema-form/json-schema.ts``); sein
Mapper schaltet auf ``type`` und fällt sonst auf ein rohes JSON-Feld zurück. Ein
``Literal`` aus Strings behält ``type: string``, bleibt also ein bedienbares
Feld, und schreibt die erlaubten Werte zusätzlich ins Schema. Genau die Falle,
die ``01-base/pricing`` schon einmal bezahlt hat. Ein weiterer Wert ändert daran
nichts — die Zahl der Alternativen ist dem Mapper gleichgültig, ihr ``type`` nicht.
"""

from typing import Literal

from pydantic import Field

from boerdi.domain.config_models._shared import AreaModel


class AgentLimits(AreaModel):
    """Die Deckel der Agent-Schleife.

    Alle vier sind nötig, weil ein MCP-Aufruf gemessen bis 23 s steht: ohne Frist
    könnte ein Lauf mit 20 Iterationen zehn Minuten dauern, ohne Budget beliebig
    viel kosten. ``ge``/``le`` sind kein Zierrat — das Studio schreibt über
    ``PUT /config/data/{area}`` direkt gegen dieses Modell, und eine Frist von 0 s
    beendete jeden Lauf vor dem ersten Werkzeug.

    **Am 2026-08-18 angehoben (Nutzer-Entscheid): 12/90/60k → 20/300/400k.** Die
    drei mussten GEMEINSAM steigen, sonst wäre die Anhebung eine Zusage ohne
    Deckung: gemessen kostete ein Hybrid-Zug ~15 300 Token je Runde (die Kette
    wächst, der Prompt wird jede Runde neu berechnet) und ein Werkzeug-Aufruf bis
    23 s. Mit 20 Runden, aber alter Frist wäre nach ~5 Runden Schluss gewesen, mit
    altem Budget nach ~4 — der neue Wert stünde in der Konfiguration und käme nie
    zum Tragen. Genau diese Falle hatte das Budget am 2026-08-17 schon einmal
    gestellt.

    **Der Preis steht hier, nicht nur im Log:** der Kosten-Deckel je Zug steigt
    damit auf das Sechsfache des ursprünglichen Wertes. Wer ihn kleiner braucht,
    stellt ihn im Studio je Anlage ein — dieser Wert ist die Vorgabe, keine
    Obergrenze der Vernunft.
    """

    max_iterations: int = Field(default=20, ge=1, le=50)
    deadline_s: int = Field(default=300, ge=5, le=600)
    token_budget: int = Field(default=400_000, ge=1_000)

    # ``propose`` heißt: die Schleife darf kuratierende Werkzeuge rufen, aber nur
    # bis zur Vorschau — die Bestätigung bleibt beim Menschen (E1-Wall). Nichts,
    # was schreibt, darf standardmäßig schreiben; ``execute`` ist die bewusste
    # Entscheidung eines Gastgebers, der eine angemeldete Person vor sich hat.
    write_mode: Literal["propose", "execute"] = "propose"

    # Das Sicherheits-Gate hängt NICHT am Klassifikator: ``assess_safety`` nimmt
    # nur Nachricht und Signale (``graph/nodes/assess.py``). Es im Agent-Modus zu
    # behalten kostet also nichts, was der Modus einspart.
    safety: bool = True


class EngineArea(AreaModel):
    """Der Umschalter plus die Deckel der Agent-Schleife."""

    mode: Literal["pattern", "agent", "hybrid"] = "pattern"
    agent: AgentLimits = Field(default_factory=AgentLimits)
