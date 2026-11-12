"""06-ablaeufe/<id> — ein Ablauf je Dokument (Paket A1, Plan 2026-11-05 §4, §9; seit AS-0 ein
Ordner wie die Muster, Plan 2026-11-09 — vorher eine Liste im Bereich ``06-ablaeufe/katalog``).

Ein Ablauf ist ein Zeiger durch feste Schrittarten; seine Daten liegen als Teile im Vorgang
(``services/vorgaenge``). Das Modell beschreibt nur die Form — was der lokale Treiber sicher
ausführen kann, prüft ``services/ablauf/pruefung`` beim Speichern (Ziele, Ende, Module, Werkzeuge,
Teilnamen, Schleifen).

Schrittarten (A1): ``nachricht`` (Text), ``modul`` (ein UI-Modul mit Daten, ``abfragen`` wartet auf
die Antwort), ``werkzeug`` (ein Dienst oder ein lesendes MCP-Werkzeug, Ergebnis → Teil; seit
Paket S auch ein schreibendes WLO-Werkzeug mit ``freigabe``),
``verzweigung`` (Regeln ``wenn_teil``/``wenn_gewaehlt`` → ``dann``, zuletzt ``sonst``), ``ende``;
seit A2b ``agent`` (die KI arbeitet mit der Person, nur mit den genannten Werkzeugen).
Seit AS-3a tragen ``nachricht`` und ``modul`` Schnellantworten (``optionen``, ``freitext``): der
Schritt wartet, die Wahl verzweigt direkt. Seit AS-4a beschreibt ``start`` die Startdaten, die ein
Ablauf mit dem Auslöser ``extern`` von der Gastseite annimmt (``services/ablauf/startdaten``).
"""

from typing import Annotated, Any, Literal

from pydantic import BeforeValidator, ConfigDict, Field

from boerdi.domain.config_models._shared import (
    AreaModel,
    Catalog,
    Choices,
    NurBei,
    SchrittZiel,
    TeilWerte,
    Textarea,
    WeiterRegeln,
)

_ID = r"^[a-z][a-z0-9_]{0,39}$"
#: Form einer Ablauf- oder Schritt-Kennung — auch für Endpunkte, die eine Ablauf-ID annehmen (K1b).
ID_FORM = _ID
#: Der Ordner der Abläufe (AS-0): ``06-ablaeufe/<id>``, die Kennung ist der Schlüssel.
ORDNER = "06-ablaeufe"
#: Vergeben: so hieß bis AS-0 der Bereich mit allen Abläufen (Migration 0021).
RESERVIERT = frozenset({"katalog"})
#: TW-3: höchstens so lang ist der Startknopf eines KI-Schritts (wie ein Chip-Label).
STARTKNOPF_ZEICHEN = 60


def _ohne_leere_saetze(wert: Any) -> Any:
    """Paket S (Review S1, Befund 4): leere Sätze je Sprache fallen weg; bleibt keiner, ist die
    Freigabe nicht gesetzt (das Studio speichert eine leere Zeile als ``{"de": ""}``)."""
    if wert == "":
        return None
    if isinstance(wert, dict):
        wert = {k: v for k, v in wert.items() if not (isinstance(v, str) and not v.strip())}
        return wert or None
    return wert


def _leer_ist_nicht_gesetzt(wert: Any) -> Any:
    """Das Studio speichert eine geleerte Liste als ``[]`` — sie zählt wie nicht gesetzt (sonst
    änderte sie die Fassung, ``treiber.fassung`` lässt nur ``None`` weg)."""
    return None if wert == [] else wert


class WennWert(AreaModel):
    """AS-3c (Plan 2026-11-09, D4): eine Stelle eines Teils mit einem Wert vergleichen
    (``services/ablauf/vergleich``)."""

    #: ``teil.<name>`` oder ``teil.<name>.<pfad>``.
    quelle: str = Field(max_length=200)
    vergleich: Annotated[str, Choices("gleich", "enthaelt", "vorhanden", "leer", "groesser",
                                      "kleiner")] = Field(
        pattern=r"^(gleich|enthaelt|vorhanden|leer|groesser|kleiner)$")
    #: Leer bei ``vorhanden`` und ``leer``; bei ``groesser``/``kleiner`` eine Zahl.
    wert: str | None = Field(default=None, max_length=200)


class Weiter(AreaModel):
    """Eine Regel der Verzweigung — die erste passende gilt; ``sonst`` zuletzt."""

    wenn_teil: str | None = None
    wenn_gewaehlt: str | None = None
    #: AS-3c: Vergleich einer Stelle eines Teils — allein, ohne ``wenn_teil``/``wenn_gewaehlt``.
    #: Vorgabe ``None`` (wegen ``treiber.fassung``).
    wenn_wert: WennWert | None = None
    #: AS-7a (F-6): Pfadmuster (``domain/seiten_muster``) auf die Seite des Zuges — allein wie
    #: ``wenn_wert``. Vorgabe ``None`` (wegen ``treiber.fassung``).
    wenn_seite: Annotated[list[Annotated[str, Field(max_length=200)]] | None,
                          BeforeValidator(_leer_ist_nicht_gesetzt)] = None
    dann: str | None = None
    sonst: str | None = None


class AgentSchritt(AreaModel):
    """Paket A2b: was die KI in einem ``agent``-Schritt darf — Grenzen prüft ``pruefung``."""

    #: Lesende WLO-Werkzeuge und UI-Module (mit Agent-Freigabe), 1 bis 10.
    werkzeuge: list[str] = []
    #: Hinweis an die KI je Sprache (steht in der Zeile ``[ABLAUFSCHRITT — …]``).
    hinweis: dict[str, Annotated[str, Textarea()]] | None = None
    #: Der Teil, den der Schritt hervorbringen soll; fehlt er bei „Weiter“: ``bei_fehler``, sonst
    #: wartet der Lauf weiter.
    ausgabe: str | None = None
    #: Züge am Schritt, bis die KI auf „Weiter“ verweist (1 bis 20).
    zuege: int = 5
    #: Plan 2026-11-11, TW-2: Vorgaben der Redaktion für die Module dieses Schritts, je Sprache
    #: (etwa „bei Lehrplänen Lernfelder als Ebene 1“). Sie gehen in den Systemteil eines Dienstes
    #: wie ``ui_strukturentwurf`` — Text der Redaktion, nie Eingabe der Person. Vorgabe ``None``
    #: (wegen ``treiber.fassung``).
    vorgaben: Annotated[dict[str, Annotated[str, Textarea(), Field(max_length=2000)]] | None,
                        BeforeValidator(_ohne_leere_saetze)] = None
    #: Plan 2026-11-11, TW-3: eine Schnellantwort beim Eintritt in den Schritt (je Sprache) — ihr
    #: Text geht als Nachricht der Person an die KI, die dann loslegt. Vorgabe ``None``.
    startknopf: Annotated[dict[str, Annotated[str, Field(max_length=STARTKNOPF_ZEICHEN)]] | None,
                          BeforeValidator(_ohne_leere_saetze)] = None


class Schnellantwort(AreaModel):
    """AS-3a (Plan 2026-11-09, D2): eine Schnellantwort — ein Chip mit Label je Sprache; die Wahl
    führt zum Schritt ``ziel``."""

    id: str = Field(pattern=_ID)
    label: dict[str, Annotated[str, Field(max_length=60)]]
    ziel: Annotated[str, SchrittZiel()] = Field(pattern=_ID)


class Freitext(AreaModel):
    """AS-3a: getippter Text an einem Schritt mit Schnellantworten wird der Teil ``schreibt``,
    dann geht es zum Schritt ``ziel``."""

    ziel: Annotated[str, SchrittZiel()] = Field(pattern=_ID)
    schreibt: str = Field(max_length=40)


class Schritt(AreaModel):
    id: str = Field(pattern=_ID)
    typ: Annotated[str, Choices("nachricht", "modul", "werkzeug", "verzweigung", "agent",
                                "auftrag", "seite", "ende")] = Field(
        pattern=r"^(nachricht|modul|werkzeug|verzweigung|agent|auftrag|seite|ende)$")
    # K2c-1: ``NurBei`` sagt dem Studio, bei welchem ``typ`` ein Feld gilt (aus ``treiber`` und
    # ``pruefung`` gelesen; Wächter ``tests/test_ablauf_studio_k2c1.py``). Nur Schema — die Fassung
    # eines Ablaufs hängt an den Daten, nicht an der Auszeichnung.
    #: ``nachricht``/``ende``: der Text je Sprache; bei ``modul`` der Satz über dem Modul.
    text: Annotated[dict[str, Annotated[str, Textarea()]] | None,
                    NurBei("typ", "nachricht", "modul", "agent", "auftrag", "seite", "ende")] = None
    modul: Annotated[str | None, NurBei("typ", "modul")] = None
    #: Daten des Moduls (ein Werkzeug nimmt ``argumente``); ``{"$teil": "<name>"}`` liest aus dem
    #: Vorgang, mit ``"pfad": "a.b"`` eine Stelle darin (K2d-1), als Auswahl (``liste``/``wo``/
    #: ``feld``, AS-Da) eine Liste — nur innerhalb von ``daten``, nie als Ganzes.
    daten: Annotated[Annotated[dict[str, Any], TeilWerte()] | None, NurBei("typ", "modul")] = None
    #: Querschnitts-Review AS-D: eine Vorschlagsliste im Studio (offen wie jeder Katalog).
    werkzeug: Annotated[Annotated[str, Catalog("ablauf_werkzeuge")] | None,
                        NurBei("typ", "werkzeug")] = None
    #: ``auftrag`` (Paket K1a): der Kestra-Flow hinter der b-api — nur, was der Betrieb
    #: freischaltet (K2c-1; seit Paket KF die Freigabe im Studio, ``01-base/kestra-flows``).
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
    #: ``auftrag`` (Plan 2026-11-10, TB-F1, Nutzer-Entscheid N15): der Flow schreibt ins
    #: Repositorium (Metadaten, Sammlungen …). Der Chatbot sieht nicht in den Flow — die Redaktion
    #: legt es hier fest. Ein Auftrag braucht ohnehin die WLO-Anmeldung; der Vermerk steht im Studio
    #: und im Handbuch. Vorgabe ``None`` (wegen ``treiber.fassung``).
    repo_schreibt: Annotated[bool | None, NurBei("typ", "auftrag")] = None
    #: ``ende`` (Plan 2026-11-11, Review TW-4, Befund 2; Nutzer N16): hier steigt die Person aus dem
    #: Ablauf aus. Einige Züge lang startet derselbe Ablauf nicht wieder von selbst (Wendung,
    #: Modul-Antwort, Werkzeug der KI, ``zug_basis.abgelehnt``); die Antwort bietet „Doch mit
    #: Ablauf“. Abgewählt (``False``) ist nicht gesetzt — sonst änderte es die Fassung.
    ausstieg: Annotated[bool | None, BeforeValidator(lambda w: None if w is False else w),
                        NurBei("typ", "ende")] = None
    #: Wohin das Ergebnis eines Werkzeugs geht (Teil des Vorgangs). An einer ``nachricht`` mit
    #: Schnellantworten (Plan 2026-11-10, TB-T1): das Label der gewählten Option als Text-Teil —
    #: so erreichen die Antworten auf die Kernfragen die Werkzeuge späterer Schritte.
    schreibt: Annotated[str | None, NurBei("typ", "werkzeug", "auftrag", "nachricht")] = None
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
                             "auftrag", "seite"), WeiterRegeln()] = None
    bei_fehler: Annotated[str | None, NurBei("typ", "modul", "werkzeug", "agent", "auftrag")] = None
    #: AS-3a: Schnellantworten (höchstens 8, ``pruefung``) — mit ihnen wartet der Schritt, und die
    #: Wahl verzweigt direkt. Vorgabe ``None`` (wegen ``treiber.fassung``).
    optionen: Annotated[Annotated[list[Schnellantwort], Field(max_length=50)] | None,
                        BeforeValidator(_leer_ist_nicht_gesetzt),
                        NurBei("typ", "nachricht", "modul")] = None
    #: AS-3a: getippter Text als Antwort (wird ein Teil) — auch ohne ``optionen``.
    freitext: Annotated[Freitext | None, NurBei("typ", "nachricht", "modul")] = None
    #: ``agent``: Werkzeuge, Hinweis, Ausgabe-Teil und Budget des freien Abschnitts.
    agent: Annotated[AgentSchritt | None, NurBei("typ", "agent")] = None
    #: AS-7a (F-1, F-2): ``seite`` — wohin der Chip führt (Pfad mit ``/`` oder ``https://``) und
    #: seine Aufschrift je Sprache; ``ankunft`` (Pfadmuster): der Lauf wartet, bis die Person dort
    #: ist. Vorgaben ``None`` (wegen ``treiber.fassung``).
    url: Annotated[Annotated[str, Field(max_length=500)] | None,
                   BeforeValidator(lambda w: w.strip() if isinstance(w, str) else w),
                   NurBei("typ", "seite")] = None
    label: Annotated[dict[str, Annotated[str, Field(max_length=60)]] | None,
                     NurBei("typ", "seite")] = None
    ankunft: Annotated[list[Annotated[str, Field(max_length=200)]] | None,
                       BeforeValidator(_leer_ist_nicht_gesetzt), NurBei("typ", "seite")] = None


class Ausloeser(AreaModel):
    #: AS-4a: ``extern`` — Start von der Gastseite (Widget-API ``startAblauf``, Attribut
    #: ``ablauf-start``) mit Startdaten; seit AS-5a bringt auch ``agent`` (Vorschlag der KI) Daten.
    art: Annotated[str, Choices("knopf", "agent", "text", "modul", "extern", "seite")] = Field(
        pattern=r"^(knopf|agent|text|modul|extern|seite)$")
    #: ``agent``: ``vorschlagen`` (die KI schlägt per Knopf vor, AS-5a) oder ``direkt`` (Plan
    #: 2026-11-10, TB-E3: der Ablauf startet nach der Antwort von selbst — derselbe Knopf, das
    #: Widget drückt ihn). ``direkt`` gilt nur für Abläufe, die nichts schreiben; sonst bleibt es
    #: ein Vorschlag (``werkzeuge.ablauf_schreibt``), und die Prüfung meldet es.
    #: Ohne ``pattern`` wie bisher: ein unbekannter Modus lädt und wird ein Prüfbefund.
    modus: Annotated[str, Choices("vorschlagen", "direkt")] = "vorschlagen"
    #: ``text``: Wendungen (keine regulären Ausdrücke) — kommt eine in der Nachricht vor, startet
    #: der Ablauf (``services/ablauf/ausloeser.per_text``).
    wendungen: list[str] = []
    #: ``modul``: dessen geprüfte Antwort startet den Ablauf nach dem Modul-Schritt, wenn sie den
    #: Teil ``wenn_teil`` bringt.
    modul: str | None = None
    wenn_teil: str | None = None
    #: AS-7a (F-7): ``seite`` — Pfadmuster; passt die Seite beim Öffnen, bietet das Widget den
    #: Ablauf unter der Begrüßung an (kein Start von selbst).
    muster: list[Annotated[str, Field(max_length=200)]] = []


class StartFeld(AreaModel):
    """AS-4a (Plan 2026-11-09 §5f, E2 A): ein Feld der Startdaten. Die Daten prüft
    ``services/ablauf/startdaten`` — sie sind Eingaben, nie Rechte."""

    #: Wie ein Teilname — ``{start.<name>}`` im Text, ``{"$teil": "start", "pfad": "<name>"}``.
    name: str = Field(pattern=r"^[a-z][a-z0-9_]{1,29}$")
    typ: Annotated[str, Choices("text", "nodeid", "zahl", "ja_nein")] = Field(
        pattern=r"^(text|nodeid|zahl|ja_nein)$")
    pflicht: bool = False
    #: Wird in AS-5 die Beschreibung des Werkzeug-Parameters.
    beschreibung: dict[str, Annotated[str, Field(max_length=200)]] = {}
    #: Nur ``text``: längere Texte werden abgewiesen. Höchstens 500 — so prüft das Safety-Gate einer
    #: Direktaktion jedes Feld ganz (Querschnitts-Review AS-4, Befund 3). Im Text zeigt
    #: ``{start.name}`` höchstens 200 Zeichen (``platzhalter.MAX_ZEICHEN``).
    max_zeichen: Annotated[int, NurBei("typ", "text")] = Field(default=200, ge=1, le=500)


#: Titel, „wann“ und „nicht wann“ stehen bei jedem Agent-Zug in der Werkzeugbeschreibung —
#: begrenzt (Querschnitts-Review).
_Titel = Annotated[str, Field(max_length=120)]
_Wann = Annotated[str, Field(max_length=200)]


#: Eine Schritt- oder Teil-Kennung in einem Testfall (gedeckelt, Review AS-1).
_Kennung = Annotated[str, Field(max_length=40)]


class TestEingabe(AreaModel):
    """AS-1: was ein Testfall an einem wartenden Schritt eingibt — je nach Wartepunkt eines
    davon."""

    #: Der Schritt, an dem der Lauf dann wartet.
    bei: str = Field(pattern=_ID)
    #: Die Antwort eines abfragenden Moduls (seine ``daten``, etwa ``{"gewaehlt": ["a"]}``).
    antwort: dict[str, Any] | None = None
    #: Das Ergebnis eines Auftrags oder einer eingelösten Freigabe.
    ergebnis: dict[str, Any] | None = None
    #: Der Auftrag ist gescheitert bzw. der Server lehnt die Freigabe ab.
    fehler: bool = False
    #: Sagt die Person ja oder nein zur Freigabe?
    freigabe: Literal["ja", "nein"] | None = None
    #: Was die KI an einem ``agent``-Schritt hinterlässt (Teilname → Wert).
    teile: dict[str, Any] = Field(default_factory=dict)
    #: AS-3a: die gewählte Schnellantwort (ihre Kennung) …
    option: _Kennung | None = None
    #: … oder der getippte Text an einem Schritt mit ``freitext``.
    text: str | None = Field(default=None, max_length=2000)
    #: AS-7a: die Seite, auf der die Person ankommt (an einem wartenden ``seite``-Schritt).
    seite: str | None = Field(default=None, max_length=500)


class TestErwartung(AreaModel):
    """AS-1: was nach den Eingaben gelten soll — nur, was gesetzt ist, wird verglichen."""

    #: Die besuchten Schritte in genau dieser Reihenfolge.
    weg: list[_Kennung] = Field(default_factory=list, max_length=200)
    #: ``nicht_gestartet``: eine Voraussetzung fehlt (ohne Anmeldung, Review AS-1, Befund 6).
    status: Literal["fertig", "fehler", "wartet_person", "wartet_ki", "wartet_auftrag",
                    "wartet_freigabe", "wartet_wahl", "wartet_seite",
                    "nicht_gestartet"] | None = None
    #: Der Schritt, an dem der Lauf zuletzt stand (Ende, Fehler oder Wartepunkt).
    ende: _Kennung | None = None
    #: Teile, die es am Ende gibt.
    teile: list[_Kennung] = Field(default_factory=list, max_length=20)


class AblaufTest(AreaModel):
    """AS-1 (Plan 2026-11-09 §5c): ein Testfall, mit dem echten Treiber simuliert — ohne LLM, MCP,
    Auftrag oder Freigabe (``services/ablauf/simulation``)."""

    name: str = Field(min_length=1, max_length=80)
    #: Teile vor dem Start (Teilname → Wert).
    teile: dict[str, Any] = Field(default_factory=dict)
    #: Ergebnis je ``werkzeug``-Schritt (Schritt-ID → Wert; ``null`` = liefert nichts). Reine
    #: Dienste ohne Netz rechnet die Simulation selbst, ein Eintrag hier überschreibt sie.
    werkzeuge: dict[str, Any] = Field(default_factory=dict)
    eingaben: list[TestEingabe] = Field(default_factory=list, max_length=30)
    erwartet: TestErwartung = Field(default_factory=TestErwartung)
    #: AS-4a: Startdaten wie von der Gastseite — sie gehen durch dieselbe Prüfung wie im Betrieb.
    start: dict[str, Any] | None = None
    #: AS-5a (Querschnitts-Review RB, Befund 2): woher die Startdaten kommen — ``gastseite``
    #: (Auslöser extern; Kennungen dürfen an lesende Werkzeuge) oder ``ki`` (Auslöser agent; ohne
    #: diese Rechte), wie im Betrieb.
    quelle: Annotated[str, Choices("gastseite", "ki")] = Field(
        default="gastseite", pattern=r"^(gastseite|ki)$")
    #: Review AS-1, Befund 6: angemeldet oder nicht — ohne Anmeldung startet ein Ablauf mit der
    #: Voraussetzung ``anmeldung`` nicht, Aufträge und Freigaben gehen zu ``bei_fehler``.
    angemeldet: bool = True
    #: Beginnen ab diesem Schritt — wie ein Modul-Auslöser nach dem beantworteten Modul; dazu die
    #: Wahl jenes Moduls (``gewaehlt``). Ohne ``ab``: ab dem ersten Schritt.
    ab: str | None = Field(default=None, pattern=_ID)
    gewaehlt: list[_Kennung] = Field(default_factory=list, max_length=20)
    #: AS-7a (F-6): die Seite der Person beim Start (für ``wenn_seite`` und die Ankunft).
    seite: str = Field(default="/", max_length=500)


class AblaufArea(AreaModel):
    #: Paket K2c-4: das Studio setzt unter jeden Ablauf „Prüfen“
    #: (``POST /api/config/ablauf-pruefen``) und die Schrittfolge — nur eine Auszeichnung im Schema,
    #: die Daten bleiben.
    model_config = ConfigDict(extra="allow", json_schema_extra={"x-widget": "ablauf"})

    id: str = Field(pattern=_ID)
    titel: dict[str, _Titel]
    #: AS-7c: Fließtext (bis 600 Zeichen) — eine Textfläche im Studio (Wächter ST-2f).
    beschreibung: Annotated[str, Textarea()] = Field(default="", max_length=600)
    wann: list[_Wann] = Field(default_factory=list, max_length=5)
    nicht_wann: list[_Wann] = Field(default_factory=list, max_length=5)
    #: Vorgabe aus: ein neuer Ablauf wirkt erst, wenn die Redaktion ihn einschaltet.
    aktiv: bool = False
    ausloeser: list[Ausloeser] = []
    voraussetzungen: list[Annotated[str, Choices("anmeldung")]] = []
    #: AS-4a: die Startdaten (höchstens 10 Felder) — Vorgabe ``None``; eine geleerte Liste zählt
    #: wie nicht gesetzt.
    start: Annotated[Annotated[list[StartFeld], Field(max_length=10)] | None,
                     BeforeValidator(_leer_ist_nicht_gesetzt)] = None
    #: 1–40 Schritte — geprüft in ``services/ablauf/pruefung`` (das Studio-Schema kennt kein
    #: ``minItems``/``maxItems``).
    schritte: list[Schritt] = []
    #: AS-1: Testfälle — „Tests ausführen“ im Studio (``POST /api/config/ablauf-testen``). Die
    #: Fassung eines Laufs hängt nur an den Schritten; Tests ändern sie nicht.
    tests: list[AblaufTest] = Field(default_factory=list, max_length=20)

