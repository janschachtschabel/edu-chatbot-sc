"""01-base/engine — welche Maschine einen Zug beantwortet.

Zwei Wege stehen zur Wahl. Die **Muster-Engine** ist der Bestand: Klassifikator,
Musterwahl, gebundene Werkzeugliste. Die **Agent-Schleife** überlässt dem Modell
alles — Systemprompt plus der volle Werkzeugkatalog, keine Muster, kein
Klassifikator. Sie ist für Einbettungen gedacht, in denen der Chat-Rahmen fehlt
(Browser-Plugin, edu-sharing), und zugleich der Versuchsaufbau für die Frage, ob
sie im Chat schneller und besser ist.

**Die Vorgabe ist ``pattern``, und das ist eine Zusage**: ohne Pflege ändert sich
am ausgelieferten Chatbot nichts. Der Bereich ist rein additiv — schaltet ihn
niemand um, wird die Agent-Schleife nie betreten.

Ein eigener Bereich statt eines Feldes in ``01-base/policy``: „welche Maschine
antwortet" ist ein neuer Begriff, er trägt die Deckel der Schleife mit, und in
``policy`` versteckt machte er jenen Bereich zweideutig. Kein ALT-Gegenstück —
ALT kannte nur einen Weg.

**Warum ``Literal`` und kein freier String.** Der Studio-Editor rendert selbst,
aus einer gemessenen JSON-Schema-Teilmenge (``schema-form/json-schema.ts``); sein
Mapper schaltet auf ``type`` und fällt sonst auf ein rohes JSON-Feld zurück.
``Literal`` zweier Strings behält ``type: string``, bleibt also ein bedienbares
Feld, und schreibt die erlaubten Werte zusätzlich ins Schema. Genau die Falle,
die ``01-base/pricing`` schon einmal bezahlt hat.
"""

from typing import Literal

from pydantic import Field

from boerdi.domain.config_models._shared import AreaModel


class AgentLimits(AreaModel):
    """Die Deckel der Agent-Schleife.

    Alle vier sind nötig, weil ein MCP-Aufruf gemessen bis 23 s steht: ohne Frist
    könnte ein Lauf mit 12 Iterationen acht Minuten dauern, ohne Budget beliebig
    viel kosten. ``ge``/``le`` sind kein Zierrat — das Studio schreibt über
    ``PUT /config/data/{area}`` direkt gegen dieses Modell, und eine Frist von 0 s
    beendete jeden Lauf vor dem ersten Werkzeug.
    """

    max_iterations: int = Field(default=12, ge=1, le=50)
    deadline_s: int = Field(default=90, ge=5, le=600)
    token_budget: int = Field(default=60_000, ge=1_000)

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

    mode: Literal["pattern", "agent"] = "pattern"
    agent: AgentLimits = Field(default_factory=AgentLimits)
