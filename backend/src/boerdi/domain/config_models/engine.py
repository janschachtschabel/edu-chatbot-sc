"""01-base/engine — welche Maschine einen Zug beantwortet.

Zwei Wege stehen zur Wahl. Die **Muster-Engine** ist der Bestand: Klassifikator,
Musterwahl, gebundene Werkzeugliste. Die **Agent-Schleife** überlässt dem Modell
alles — Systemprompt plus der volle Werkzeugkatalog, keine Muster, kein
Klassifikator. Sie ist für Einbettungen gedacht, in denen der Chat-Rahmen fehlt
(Browser-Plugin, edu-sharing), und zugleich der Versuchsaufbau für die Frage, ob
sie im Chat schneller und besser ist.

Einen dritten Weg, den **Hybrid** (dieselbe Schleife mit dem Musterkatalog als
Werkzeug), gibt es seit K1-1 (2026-09-27) nicht mehr: die K0-Messung zeigte ihn
zwischen den beiden anderen, ohne eigenen Mehrwert. Ein gespeichertes ``hybrid``
wird als ``agent`` gelesen (``EngineArea``).

**Die Modell-Vorgabe ist ``pattern``** — der Rückfall, wenn der Bereich fehlt oder
unlesbar ist (``load_engine``). Der ausgelieferte Seed setzt seit Paket 7 (K6,
Nutzer-Entscheid 2026-10-09, folgt D-15) ``agent``.

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

import functools
import logging
from typing import Annotated, Literal

from pydantic import Field, field_validator

from boerdi.domain.config_models._shared import AreaModel, Textarea

logger = logging.getLogger(__name__)


@functools.cache
def warne_hybrid_einmal(herkunft: str) -> None:
    """K1-1 (2026-09-27): ``hybrid`` ist entfernt, es gilt ``agent``.

    Einmal je Herkunft und Prozess: eine Einbettung, die ihn noch anfordert,
    schriebe sonst eine Warnung je Zug.
    """
    logger.warning("%s: 'hybrid' ist entfernt (K1-1, 2026-09-27) — es gilt 'agent'.",
                   herkunft)


#: Die Vorgaben der Schleifen-Deckel — eine Stelle für die normalen und die
#: anonymen Deckel, damit die Vorbelegung nicht still auseinanderläuft.
MAX_ITERATIONS_VORGABE = 30
DEADLINE_S_VORGABE = 900
TOKEN_BUDGET_VORGABE = 900_000


class AnonymousLimits(AreaModel):
    """Engere Deckel für Züge ohne angemeldete Person (AG-6, Entscheid D-9).

    Jeder Client wählt die Maschine über die Kopfzeile ``X-Boerdi-Engine``; ohne
    diese Deckel gelten für einen anonymen Zug dieselben wie für eine angemeldete
    Einbettung. **Vorbelegt mit den aktuellen Werten** (Nutzer, 2026-09-27: nicht
    hart deckeln, aber im Studio anbieten) — die Vorgabe ändert also nichts.
    Angewandt als Minimum (``services/agent_deckel``): ein Wert über dem normalen
    Deckel hebt nichts an, ein geleertes Feld heißt „wie angemeldet". Grenzen wie
    dort, aus demselben Grund (das Studio schreibt direkt gegen dieses Modell).
    """

    max_iterations: int | None = Field(default=MAX_ITERATIONS_VORGABE, ge=1, le=50)
    deadline_s: int | None = Field(default=DEADLINE_S_VORGABE, ge=5, le=1800)
    token_budget: int | None = Field(default=TOKEN_BUDGET_VORGABE, ge=1_000)


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

    max_iterations: int = Field(default=MAX_ITERATIONS_VORGABE, ge=1, le=50)
    # Obergrenze mitgehoben: 30 Runden x (Modellzeit + bis 23 s Werkzeug)
    # sprengen 600 s im Zweifel. Der Deckel ist ein Sicherheitsnetz, keine
    # Erwartung — der typische Zug lag gemessen weit darunter.
    deadline_s: int = Field(default=DEADLINE_S_VORGABE, ge=5, le=1800)
    token_budget: int = Field(default=TOKEN_BUDGET_VORGABE, ge=1_000)

    # ``propose`` heißt: die Schleife darf kuratierende Werkzeuge rufen, aber nur
    # bis zur Vorschau — die Bestätigung bleibt beim Menschen (E1-Wall). Nichts,
    # was schreibt, darf standardmäßig schreiben; ``execute`` ist die bewusste
    # Entscheidung eines Gastgebers, der eine angemeldete Person vor sich hat.
    write_mode: Literal["propose", "execute"] = "propose"

    # ``safety`` gestrichen (Paket 7, P4): das Sicherheits-Gate läuft immer — in
    # beiden Maschinen und am Endpunkt; der Schalter hatte keinen Leser.

    # AG-6: gilt im Chat, wenn keine angemeldete Person hinter dem Zug steht.
    anonymous: AnonymousLimits = Field(default_factory=AnonymousLimits)


#: AG-3: die Rolle des Agenten, wie sie im Studio vorbelegt ist. Die ersten zwei
#: Absätze sind der bisherige Rollenblock aus ``respond_agent``. Die Antwortform
#: antwortet auf zwei Fehlerbilder der K0-Messung: kein Dokument, wo eines
#: verlangt war, und eine Rückfrage statt einer Suche, wo Material verlangt war
#: (Plan 2026-09-26 §13, „K0-Ergebnis"). D1 (Plan 2026-09-28): sie zählte
#: „Arbeitsblatt, Quiz" zu dem, was der Agent „auch ohne Fertiges im Bestand"
#: selbst baut — „hast du Übungen?" wurde so ein eigenes Blatt, und der Kopf geht
#: dem Master-Skill vor. Selbst gebaut wird jetzt nur auf Wunsch oder wenn nichts
#: passt; zusammengestellt (Lernpfad, Stunde) weiterhin aus den Treffern.
ROLLE_VORGABE = (
    "Du bist Boerdi, der Assistent von WirLernenOnline (WLO). Du sprichst mit "
    "einem Menschen im Chat — kurz, freundlich und ohne Floskeln.\n\n"
    "Arbeitsweise: Hole dir die Tatsachen mit den Werkzeugen, statt sie aus dem "
    "Gedächtnis zu behaupten. Steht in einer Sammlung ein Skill zu deiner "
    "Aufgabe, halte dich daran. Nenne, worauf du dich stützt, und sage "
    "ausdrücklich, was du NICHT prüfen konntest.\n\n"
    "Antwortform: Fragt jemand nach Material, suche zuerst mit dem, was du "
    "weißt (Thema, Fach, Klassenstufe, Anlass) — die Treffer erscheinen als "
    "Karten; eine Rückfrage höchstens danach. Ein eigenes Material erstellst du "
    "nur, wenn es verlangt ist oder im Bestand nichts passt — dann sag, dass es "
    "selbst erstellt ist. Wird ein fertiges Ergebnis verlangt (ein erstelltes "
    "Material, eine Stunden- oder Lernpfad-Planung, der Volltext eines "
    "Materials), liefere es mit zeige_dokument als Box; fehlt ein fertiger "
    "Lernpfad oder Stundenablauf, stelle ihn aus den Treffern zusammen."
)

#: D-5 (2026-09-27, „wie empfohlen"): die Leitplanken, die in jedem Modus gelten.
SCHUTZREGELN_VORGABE = ("R-05", "R-08", "R-13", "R-15")


class AgentRolle(AreaModel):
    """Rolle und Grenzen des Agenten (AG-3): was der Betreiber im Studio setzt.

    Die Arbeitsweise im Einzelnen setzt die Redaktion im Repositorium (der
    Master-Skill); der Kopf aus diesen Feldern steht davor und geht ihm vor
    (``services/agent_kopf``). ``schutzregeln`` sind Kennungen aus
    ``01-base/guardrails``: nur diese gelten für den Agenten. Die übrigen sind
    Arbeitsregeln der Muster-Maschine (etwa „max. 5 Treffer"), die die Schleife
    eher bremsen.
    """

    rolle: Annotated[str, Textarea()] = ROLLE_VORGABE
    schutzregeln: list[str] = Field(default_factory=lambda: list(SCHUTZREGELN_VORGABE))


class Betrieb(AreaModel):
    """Schalter des laufenden Betriebs (Paket 7, S1–S3, Nutzer-Entscheid 2026-10-09).

    Bis Paket 7 reine Umgebungsvariablen; hier wirken sie ohne Neustart. Ist die
    Umgebungsvariable gesetzt, gilt sie (``services/betriebsschalter``).
    """

    # S1 (``LLM_SERVICE_TIER``): OpenAI-Stufe „fast“ — 4- bis 5-facher
    # Tokenpreis, keine EU-Datenhaltung. Nur OpenAI direkt, gpt-5/gpt-6.
    fast_modus: bool = False
    # S2 (``CHAT_TOKEN_STREAMING``): Vorgabe an. Live-Proben 2026-10-03: Drift 0/6.
    token_streaming: bool = True
    # S3 (``AGENT_INLINE_QUICK_REPLIES``): aus, bis der Master-Skill-Abschnitt
    # „Schnellantworten“ angepasst ist (Text: Plan 2026-09-30-muster-kette-zeit).
    agent_schnellantworten: bool = False
    # S4 (P5-9): ohne persönliche Anmeldung mit dem Dienst-Block der Anlage
    # (``MCP_AUTH_TOKEN``) schreiben — in beiden Modi. Vorgabe aus; ohne
    # Umgebungsvariable als Gegenstück: ein Gastkonto schreiben zu lassen ist
    # eine ausdrückliche Entscheidung im Studio (``services/schreibrecht``).
    gastkonto_schreibt: bool = False


class EngineArea(AreaModel):
    """Der Umschalter, die Deckel der Agent-Schleife und ihre Rolle (AG-3),
    dazu die Skill-Brücke der Muster-Maschine (E-6) und die Betriebsschalter
    (Paket 7)."""

    mode: Literal["pattern", "agent"] = "pattern"
    agent: AgentLimits = Field(default_factory=AgentLimits)
    agent_rolle: AgentRolle = Field(default_factory=AgentRolle)
    betrieb: Betrieb = Field(default_factory=Betrieb)
    # E-6 (Nutzer-Entscheid 2026-09-27): im Muster-Modus bekommt jedes
    # Werkzeug-Muster ``get_skill_registry`` und ``get_skill`` dazu, sobald
    # freigegebene Skills im Spiel sind — von Haus aus führen sie nur sechs von
    # zwanzig Mustern. Vorgabe aus: ohne Pflege ändert sich nichts. Mechanik und
    # Grenzen in ``domain/skill_bruecke``.
    muster_skills: bool = False

    @field_validator("mode", mode="before")
    @classmethod
    def _hybrid_gilt_als_agent(cls, wert: object) -> object:
        """Ein gespeichertes ``hybrid`` (K1-1) wird als ``agent`` gelesen.

        Ohne diese Umdeutung schlüge die Prüfung fehl, ``load_engine`` fiele
        auf die Vorgabe zurück, und die Anlage liefe still als Muster-Maschine —
        samt zurückgesetzter Deckel und Rolle.
        """
        if isinstance(wert, str) and wert.strip().lower() == "hybrid":
            warne_hybrid_einmal("01-base/engine")
            return "agent"
        return wert
