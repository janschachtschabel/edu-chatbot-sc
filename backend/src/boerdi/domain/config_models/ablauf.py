"""06-ablaeufe/katalog — die Abläufe als ein Studio-Bereich (Paket A1, Plan 2026-11-05 §4, §9).

Ein Ablauf ist ein Zeiger durch feste Schrittarten; seine Daten liegen als Teile im Vorgang
(``services/vorgaenge``). Das Modell beschreibt nur die Form — was der lokale Treiber sicher
ausführen kann, prüft ``services/ablauf/pruefung`` beim Speichern (Ziele, Ende, Module, Werkzeuge,
Teilnamen, Schleifen).

Schrittarten (A1): ``nachricht`` (Text), ``modul`` (ein UI-Modul mit Daten, ``abfragen`` wartet auf
die Antwort), ``werkzeug`` (ein Dienst oder ein lesendes MCP-Werkzeug, Ergebnis → Teil; seit
Paket S auch ein schreibendes WLO-Werkzeug mit ``freigabe``),
``verzweigung`` (Regeln ``wenn_teil``/``wenn_gewaehlt`` → ``dann``, zuletzt ``sonst``), ``ende``;
seit A2b ``agent`` (die KI arbeitet mit der Person, nur mit den genannten Werkzeugen).
"""

from typing import Annotated, Any

from pydantic import BeforeValidator, ConfigDict, Field

from boerdi.domain.config_models._shared import AreaModel, Catalog, Choices, NurBei, TeilWerte

_ID = r"^[a-z][a-z0-9_]{0,39}$"
#: Form einer Ablauf- oder Schritt-Kennung — auch für Endpunkte, die eine Ablauf-ID annehmen (K1b).
ID_FORM = _ID


def _ohne_leere_saetze(wert: Any) -> Any:
    """Paket S (Review S1, Befund 4): leere Sätze je Sprache fallen weg; bleibt keiner, ist die
    Freigabe nicht gesetzt (das Studio speichert eine leere Zeile als ``{"de": ""}``)."""
    if wert == "":
        return None
    if isinstance(wert, dict):
        wert = {k: v for k, v in wert.items() if not (isinstance(v, str) and not v.strip())}
        return wert or None
    return wert


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
    # K2c-1: ``NurBei`` sagt dem Studio, bei welchem ``typ`` ein Feld gilt (aus ``treiber`` und
    # ``pruefung`` gelesen; Wächter ``tests/test_ablauf_studio_k2c1.py``). Nur Schema — die Fassung
    # eines Ablaufs hängt an den Daten, nicht an der Auszeichnung.
    #: ``nachricht``/``ende``: der Text je Sprache; bei ``modul`` der Satz über dem Modul.
    text: Annotated[dict[str, str] | None,
                    NurBei("typ", "nachricht", "modul", "agent", "auftrag", "ende")] = None
    modul: Annotated[str | None, NurBei("typ", "modul")] = None
    #: Daten des Moduls (ein Werkzeug nimmt ``argumente``); ``{"$teil": "<name>"}`` liest aus dem
    #: Vorgang, mit ``"pfad": "a.b"`` eine Stelle darin (K2d-1).
    daten: Annotated[Annotated[dict[str, Any], TeilWerte()] | None, NurBei("typ", "modul")] = None
    werkzeug: Annotated[str | None, NurBei("typ", "werkzeug")] = None
    #: ``auftrag`` (Paket K1a): der Kestra-Flow hinter der b-api — nur, was der Betrieb
    #: freischaltet (K2c-1: Auswahl aus ``B_API_JOBS_FLOWS``).
    flow: Annotated[Annotated[str, Catalog("ablauf_flows")] | None,
                    NurBei("typ", "auftrag")] = None
    argumente: Annotated[Annotated[dict[str, Any], TeilWerte()] | None,
                         NurBei("typ", "werkzeug", "auftrag")] = None
    #: ``auftrag`` (Paket K2b): ``gesperrt`` — solange der Auftrag läuft, nimmt das Gespräch nur
    #: „Stand prüfen“, „Abbrechen“ und die Vorgangs-Knöpfe an; ``frei`` oder leer — es geht weiter.
    #: Vorgabe ``None``, nicht ``"frei"`` (Review K2b): ``treiber.fassung`` lässt nur ``None`` weg —
    #: eine andere Vorgabe änderte die Fassung jedes Ablaufs, und jeder wartende Lauf bräche ab.
    #: Zweites Review K2b, Befund 6: das Studio speichert „— nicht gesetzt —“ als ``""`` — das ist
    #: leer, kein 422 (der Validator außen, damit Muster und Auswahl im Schema bleiben).
    warten: Annotated[Annotated[str, Choices("frei", "gesperrt"),
                                Field(pattern=r"^(frei|gesperrt)$")] | None,
                      BeforeValidator(lambda w: None if w == "" else w),
                      NurBei("typ", "auftrag")] = None
    #: Wohin das Ergebnis eines Werkzeugs geht (Teil des Vorgangs).
    schreibt: Annotated[str | None, NurBei("typ", "werkzeug", "auftrag")] = None
    #: ``werkzeug`` (Paket S): der Satz über der Vorschau eines schreibenden WLO-Werkzeugs, je
    #: Sprache. Ohne ihn ist ein schreibendes Werkzeug nicht erlaubt (``pruefung``); mit ihm legt
    #: der Schritt die Änderung vor und wartet auf die Freigabe der Person. Vorgabe ``None`` (wegen
    #: ``treiber.fassung``); leer (``""``/``{}`` aus dem Studio) ist nicht gesetzt.
    freigabe: Annotated[dict[str, str] | None, BeforeValidator(_ohne_leere_saetze),
                        NurBei("typ", "werkzeug")] = None
    #: ``auftrag`` (Paket K2d-2): die Dateien des Ergebnisses (``outputId``), die beim Abholen
    #: geholt und als Text lesbar werden — im Teil unter ``texte.<outputId>``. Höchstens drei;
    #: Kennungen ohne Punkt (sie sind ein Glied eines ``$teil``-Pfads).
    dateien_holen: Annotated[list[Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")]] | None,
                             Field(max_length=3), NurBei("typ", "auftrag")] = None
    #: Nächster Schritt (Vorgabe: der folgende) bzw. die Regeln einer Verzweigung.
    weiter: Annotated[str | list[Weiter] | None,
                      NurBei("typ", "nachricht", "modul", "werkzeug", "verzweigung", "agent",
                             "auftrag")] = None
    bei_fehler: Annotated[str | None, NurBei("typ", "modul", "werkzeug", "agent", "auftrag")] = None
    #: ``agent``: Werkzeuge, Hinweis, Ausgabe-Teil und Budget des freien Abschnitts.
    agent: Annotated[AgentSchritt | None, NurBei("typ", "agent")] = None


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
    #: Paket K2c-4: das Studio setzt unter jeden Ablauf „Prüfen“
    #: (``POST /api/config/ablauf-pruefen``) und die Schrittfolge — nur eine Auszeichnung im Schema,
    #: die Daten bleiben.
    model_config = ConfigDict(extra="allow", json_schema_extra={"x-widget": "ablauf"})

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
