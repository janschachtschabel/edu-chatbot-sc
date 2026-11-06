"""06-ablaeufe/katalog — die Abläufe als ein Studio-Bereich (Paket A1, Plan 2026-11-05 §4, §9).

Ein Ablauf ist ein Zeiger durch feste Schrittarten; seine Daten liegen als Teile im Vorgang
(``services/vorgaenge``). Das Modell beschreibt nur die Form — was der lokale Treiber sicher
ausführen kann, prüft ``services/ablauf/pruefung`` beim Speichern (Ziele, Ende, Module, Werkzeuge,
Teilnamen, Schleifen).

Schrittarten (A1): ``nachricht`` (Text), ``modul`` (ein UI-Modul mit Daten, ``abfragen`` wartet auf
die Antwort), ``werkzeug`` (ein Dienst oder ein lesendes MCP-Werkzeug, Ergebnis → Teil),
``verzweigung`` (Regeln ``wenn_teil``/``wenn_gewaehlt`` → ``dann``, zuletzt ``sonst``), ``ende``;
seit A2b ``agent`` (die KI arbeitet mit der Person, nur mit den genannten Werkzeugen).
"""

from typing import Annotated, Any

from pydantic import Field

from boerdi.domain.config_models._shared import AreaModel, Choices

_ID = r"^[a-z][a-z0-9_]{0,39}$"
#: Form einer Ablauf- oder Schritt-Kennung — auch für Endpunkte, die eine Ablauf-ID annehmen (K1b).
ID_FORM = _ID


class Weiter(AreaModel):
    """Eine Regel der Verzweigung — die erste passende gilt; ``sonst`` zuletzt."""

    wenn_teil: str | None = None
    wenn_gewaehlt: str | None = None
    dann: str | None = None
    sonst: str | None = None


class AgentSchritt(AreaModel):
    """Paket A2b: was die KI in einem ``agent``-Schritt darf — Grenzen prüft ``pruefung``."""

    #: Lesende WLO-Werkzeuge und UI-Module (mit Agent-Freigabe), 1 bis 10.
    werkzeuge: list[str] = []
    #: Hinweis an die KI je Sprache (steht in der Zeile ``[ABLAUFSCHRITT — …]``).
    hinweis: dict[str, str] | None = None
    #: Der Teil, den der Schritt hervorbringen soll; fehlt er bei „Weiter“: ``bei_fehler``, sonst
    #: wartet der Lauf weiter.
    ausgabe: str | None = None
    #: Züge am Schritt, bis die KI auf „Weiter“ verweist (1 bis 20).
    zuege: int = 5


class Schritt(AreaModel):
    id: str = Field(pattern=_ID)
    typ: Annotated[str, Choices("nachricht", "modul", "werkzeug", "verzweigung", "agent",
                                "auftrag", "ende")] = Field(
        pattern=r"^(nachricht|modul|werkzeug|verzweigung|agent|auftrag|ende)$")
    #: ``nachricht``/``ende``: der Text je Sprache; bei ``modul`` der Satz über dem Modul.
    text: dict[str, str] | None = None
    modul: str | None = None
    #: Daten des Moduls bzw. Argumente des Werkzeugs; ``{"$teil": "<name>"}`` liest aus dem Vorgang.
    daten: dict[str, Any] | None = None
    werkzeug: str | None = None
    #: ``auftrag`` (Paket K1a): der Kestra-Flow hinter der b-api — nur, was der Betrieb
    #: freischaltet.
    flow: str | None = None
    argumente: dict[str, Any] | None = None
    #: Wohin das Ergebnis eines Werkzeugs geht (Teil des Vorgangs).
    schreibt: str | None = None
    #: Nächster Schritt (Vorgabe: der folgende) bzw. die Regeln einer Verzweigung.
    weiter: str | list[Weiter] | None = None
    bei_fehler: str | None = None
    #: ``agent``: Werkzeuge, Hinweis, Ausgabe-Teil und Budget des freien Abschnitts.
    agent: AgentSchritt | None = None


class Ausloeser(AreaModel):
    art: Annotated[str, Choices("knopf", "agent", "text", "modul")] = Field(
        pattern=r"^(knopf|agent|text|modul)$")
    #: ``agent``: ``vorschlagen`` (Schnellantwort) — ``direkt`` ist offen.
    modus: Annotated[str, Choices("vorschlagen")] = "vorschlagen"
    #: ``text``: Wendungen (keine regulären Ausdrücke) — kommt eine in der Nachricht vor, startet
    #: der Ablauf (``services/ablauf/ausloeser.per_text``).
    wendungen: list[str] = []
    #: ``modul``: dessen geprüfte Antwort startet den Ablauf nach dem Modul-Schritt, wenn sie den
    #: Teil ``wenn_teil`` bringt.
    modul: str | None = None
    wenn_teil: str | None = None


#: Titel, „wann“ und „nicht wann“ stehen bei jedem Agent-Zug in der Werkzeugbeschreibung —
#: begrenzt (Querschnitts-Review).
_Titel = Annotated[str, Field(max_length=120)]
_Wann = Annotated[str, Field(max_length=200)]


class AblaufArea(AreaModel):
    id: str = Field(pattern=_ID)
    titel: dict[str, _Titel]
    beschreibung: str = Field(default="", max_length=600)
    wann: list[_Wann] = Field(default_factory=list, max_length=5)
    nicht_wann: list[_Wann] = Field(default_factory=list, max_length=5)
    #: Vorgabe aus: ein neuer Ablauf wirkt erst, wenn die Redaktion ihn einschaltet.
    aktiv: bool = False
    ausloeser: list[Ausloeser] = []
    voraussetzungen: list[Annotated[str, Choices("anmeldung")]] = []
    #: 1–40 Schritte — geprüft in ``services/ablauf/pruefung`` (das Studio-Schema kennt kein
    #: ``minItems``/``maxItems``).
    schritte: list[Schritt] = []


class AblaufKatalogArea(AreaModel):
    """Alle Abläufe in einem Bereich — ein Eintrag je Ablauf, die ``id`` ist der Schlüssel."""

    ablaeufe: list[AblaufArea] = []
