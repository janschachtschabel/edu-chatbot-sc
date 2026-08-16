"""Der Freigabe-Katalog, den ein Werkzeugergebnis nebenbei mitbringt (P1).

Teil der Fassade ``boerdi.services.mcp.parsers``. Eigenes Modul, eigener
Aenderungsgrund: die anderen Parser bauen Karten fuer die Oberflaeche, dieser
baut einen Block fuer den Prompt.

**Was gemessen wurde.** Der MCP haengt an einen Sammlungs-Knoten, der ein
Registry-Dokument fuehrt, das Feld ``skillRegistry`` mit
``{nodeId, title, entries[{nodeId, title}]}``. Es sitzt am **Knoten**, nicht an
der Huelle, und nur dann, wenn dieser Knoten selbst als Trefferzeile auftaucht.

Deshalb sucht dieses Modul nicht bei bestimmten Werkzeugen, sondern in jedem
Ergebnis, das Knoten auflistet — Suche, Auflistung, Baum, Knotendetails. Es
laeuft ueber jedes Werkzeugergebnis; ohne Feld kostet es einen fehlgeschlagenen
``json.loads`` und gibt "" zurueck.

**Zweite Messung (2026-08-15, echter Server, „Geometrische Optik" f35c17d1) —
sie korrigiert die erste.** Gemessen am DEPLOYTEN Stand; der neue Servercode
liegt vor und aendert zwei dieser vier Zeilen — welche und wodurch, steht bei
:data:`_SAMMLUNGS_WERKZEUGE`. Wer die Karte dort pruefen will, liest also besser
zuerst sie: die Liste hier ist das Vorher, sie ist das Nachher. Der Auszug reist
NUR auf dem Suchpfad mit:

* ``search_wlo_collections("Geometrische Optik")`` → 28 Eintraege an JEDEM der
  beiden Treffer.
* ``get_node_details(f35c17d1)`` → kein Feld. Man fragt die Sammlung selbst ab
  und erfaehrt nichts von ihren 28 Anleitungen.
* ``get_collection_contents(f35c17d1)`` → kein Feld, weder mit ``files`` noch
  mit ``folders``.
* ``browse_collection_tree(f35c17d1)`` → kein Feld, an keiner der sechs
  Unter-Sammlungen.

Die erste Messung (2026-08-13) hatte fuer ``contentFilter=folders`` noch eine
Ausnahme notiert; sie gilt so nicht mehr. Praktische Folge und der Grund fuer
:func:`_anstoss`: sobald das Modell in eine Sammlung HINEINnavigiert, steht im
Ergebnis nichts mehr von Anleitungen — und bis 2026-08-15 stiess auch nichts
mehr an. Die Sammlung ist trotzdem bekannt: ihre nodeId steht in den
Argumenten, mit denen wir gerufen haben.

**Warum ueberhaupt.** Der Befund vom selben Tag (B-1): M09 deklariert alle drei
Skill-Werkzeuge und ruft keines. Der Katalog kommt hier ohne Extra-Aufruf mit —
das Modell muss nichts wissen, um ihn zu sehen. Er traegt nur Titel und nodeId;
Beschreibung und Verwendungshinweis der Redaktion liefert ``get_skill_registry``
(gemessen ~20 KB gegen ~2 KB hier), die Anleitung selbst ``get_skill``.

**Vertrauensgrenze.** Die Titel sind Repository-Metadaten, also fremd
beschrieben. Kein Rahmen (``untrusted_text``): dessen Regel zieht die Linie bei
Langform-Prosa, kurze strukturierte Felder — Kartentitel, Trefferzeilen —
laufen ungerahmt, und ein Skill-Titel ist genau das. Die Massnahme hier ist
billiger und passt zur Form: jeder Titel wird auf **eine Zeile** gezwungen und
gedeckelt. Ein einzeiliger Titel kann keinen eigenen Abschnitt aufmachen und
sich nicht als Anweisungsblock tarnen.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from boerdi.services.mcp.parsers.json_scan import load_envelope

#: Deckel gegen Prompt-Flutung. Eine Registry sind ~28 Eintraege ≈ 2 KB;
#: ``contentFilter=folders`` auf einer grossen Sammlung kann viele
#: Unter-Sammlungen liefern, jede mit eigener Registry. Was wegfaellt, wird
#: gesagt — eine stille Kuerzung laese den Katalog vollstaendig aussehen.
_MAX_REGISTRIES = 3
_MAX_ENTRIES = 40
_MAX_TITLE = 80

#: Schutz vor entarteten Strukturen (Selbstbezug im JSON gibt es nicht, tiefe
#: Verschachtelung schon: ``browse_collection_tree`` reicht mehrere Ebenen).
_MAX_DEPTH = 12

_MARKER = (
    "[SKILL-REGISTRY — freigegebene Skills der Redaktion, "
    "mitgeliefert von diesem Werkzeug]"
)
_AUFFORDERUNG = "Passt eine zur Aufgabe, hole sie mit get_skill(nodeId) und folge ihr."
_FUSS = (
    "Beschreibungen und Verwendungshinweise der Redaktion: "
    "get_skill_registry(collectionId)."
)

#: Werkzeuge, bei denen der Server ueber die ANGEFRAGTE Sammlung nichts sagt —
#: samt des Arguments, das ihre nodeId traegt.
#:
#: Genau zwei, und die Auswahl ist am Quelltext des MCP-Servers geprueft
#: (2026-08-15, am NEUEN Stand — er liegt vor, ist aber noch nicht deployt; die
#: Messliste im Modul-Docstring zeigt den deployten und weicht deshalb bei
#: ``get_node_details`` und ``get_collection_contents`` ab).
#: ``browse_collection_tree`` haengt Registries nur an die KINDER
#: (``cachedRegistriesFor``), nie an die Sammlung, nach der gefragt wurde;
#: ``get_collection_stats`` ruehrt die Registry ueberhaupt nicht an. Wer eines
#: davon ruft, steht in einer Sammlung und erfaehrt sonst nichts von ihren
#: Anleitungen.
#:
#: **Alle anderen fielen am 2026-08-15 heraus, und das ist der Kern.** Fuer
#: ``get_collection_contents``, ``search_wlo_within_collection``,
#: ``get_topic_page_content`` und ``get_related_content`` antwortet der Server
#: selbst (``tools/shared.ts::subjectRegistryText``); fuer ``get_node_details``
#: und ``search_wlo_collections`` haengt er die Registry an den Knoten
#: (``ensureRegistries``). Dort ist unser Anstoss nicht nur ueberfluessig,
#: sondern schaedlich: ``subjectRegistryText`` schweigt ABSICHTLICH, wenn es
#: nachgesehen und nichts gefunden hat (shared.ts:58) — und in dieses Schweigen
#: hinein schickte unser Anstoss das Modell fuer nichts los.
#:
#: Damit entfaellt die Kopplung an den WORTLAUT des Servers. Bis zu dieser
#: Fassung erkannten wir seine Antwort an vier deutschen Satzanfaengen; das
#: liess Fremdinhalt mitentscheiden (eine Beschreibung „Skill-Registry: siehe
#: Handbuch" brachte uns zum Schweigen) und waere bei jeder Umformulierung
#: gebrochen. Jetzt haengt es an Werkzeugnamen — Vertragsflaeche statt Prosa.
#:
#: **Nicht dabei und mit Absicht:** ``get_node_breadcrumb`` beantwortet, WO eine
#: Sammlung sitzt, nicht was in ihr zu tun ist — ein Anstoss dort waere Rauschen
#: auf einer reinen Orientierungsfrage. ``get_subject_portals`` ebenso: es ist
#: ein Waehler ueber dreissig Portale, kein Arbeiten in einem davon.
_SAMMLUNGS_WERKZEUGE = {
    "browse_collection_tree": "nodeId",
    "get_collection_stats": "nodeId",
}

#: Sagt „fuer DIESE Sammlung", nicht „in diesem Ergebnis": seit der Anstoss auch
#: neben einem Katalog stehen kann (der der Kinder), waere „dieses Ergebnis
#: bringt keine mit" direkt unter einer Freigabeliste schlicht falsch.
_ANSTOSS_MARKER = "[SKILL-REGISTRY — fuer die angefragte Sammlung nicht dabei]"

#: Sagt, was schon geschehen ist und was noch fehlt — der Katalog liegt vor,
#: die Anleitung nicht. Siehe :func:`_nachfassen`.
_NACHFASS_MARKER = "[SKILL-REGISTRY — Katalog gelesen, Skill noch nicht]"


@dataclass(frozen=True)
class SkillEntry:
    """Ein freigegebener Skill: so viel, wie der Auszug traegt."""

    node_id: str
    title: str


@dataclass(frozen=True)
class SkillRegistry:
    """Die Freigabeliste einer Sammlung, wie sie am Knoten mitkommt."""

    collection_id: str
    collection_title: str
    registry_id: str
    entries: tuple[SkillEntry, ...]


def _einzeilig(wert: object, deckel: int) -> str:
    """Fremdtext auf eine gedeckelte Zeile bringen (siehe Modul-Docstring)."""
    text = " ".join(str(wert or "").split())
    return text[:deckel] if len(text) > deckel else text


def skill_titel(raw_text: object) -> str:
    """Der Titel einer geholten Anleitung — aus der H1 der ersten Zeile.

    ``get_skill`` antwortet mit MARKDOWN, nicht mit JSON (gemessen 2026-08-16
    gegen den echten Server)::

        # Stunde planen
        nodeId: 5b29f470-…

    **Nur die erste Zeile.** Ein ``#`` weiter unten gehoert zur Gliederung des
    Dokuments; ihn als Titel zu nehmen hiesse, dem Nutzer einen Abschnittsnamen
    als Namen der Anleitung anzusagen. Lieber kein Titel als ein geratener — der
    Aufrufer laesst die Ansage dann weg
    (``domain/skill_precedence.mit_ladehinweis``).

    Einzeilig und auf :data:`_MAX_TITLE` gedeckelt wie jeder Fremdtitel hier.
    """
    if not isinstance(raw_text, str):
        return ""
    erste = raw_text.lstrip().split("\n", 1)[0].strip()
    treffer = re.match(r"#\s+(\S.*)$", erste)
    return _einzeilig(treffer.group(1), _MAX_TITLE) if treffer else ""


def _gueltige_eintraege(roh: object) -> list[dict]:
    """Die abrufbaren Eintraege einer Registry — ohne ``nodeId`` kein Skill.

    Eine Regel, zwei Verbraucher: der Prompt-Block unten und der Zaehler fuer
    die Karte (:func:`skill_count_of`). Zwei Zaehlweisen fuer dasselbe Feld
    waeren eine Gelegenheit zum Auseinanderlaufen — die Kachel wuerde eine Zahl
    zeigen, die der Block darunter nicht belegt.
    """
    if not isinstance(roh, dict):
        return []
    eintraege = roh.get("entries")
    if not isinstance(eintraege, list):
        return []
    return [e for e in eintraege if isinstance(e, dict) and e.get("nodeId")]


def skill_count_of(node: object) -> int:
    """Wie viele Skills an DIESEM Knoten freigegeben sind; 0 ohne Registry.

    Fuer die Karte gedacht (Nutzer-Vorgabe 2026-08-14): dass Skills an einer
    Sammlung haengen, soll auch bei einer *Suche* sichtbar sein, nicht nur
    wenn man im Seitenkontext auf ihr steht. Der MCP liefert ``skillRegistry``
    dabei ungefragt mit (gemessen an ``search_wlo_collections`` und
    ``search_wlo_all``) — es kostet also keinen zusaetzlichen Abruf.

    Nur die Zahl, nicht die Titel: die Kachel zeigt einen Hinweis, kein
    Verzeichnis. Den Katalog traegt der Prompt-Block, die Volltexte
    ``get_skill_registry`` / ``get_skill``.
    """
    if not isinstance(node, dict):
        return 0
    return len(_gueltige_eintraege(node.get("skillRegistry")))


def _als_registry(besitzer: dict, roh: dict) -> SkillRegistry | None:
    eintraege = tuple(
        SkillEntry(node_id=str(e.get("nodeId") or ""), title=_einzeilig(e.get("title"), _MAX_TITLE))
        for e in _gueltige_eintraege(roh)
    )
    if not eintraege:
        return None
    collection_id = str(besitzer.get("nodeId") or "")
    return SkillRegistry(
        collection_id=collection_id,
        collection_title=_einzeilig(besitzer.get("title"), _MAX_TITLE),
        registry_id=str(roh.get("nodeId") or collection_id),
        entries=eintraege,
    )


def _sammle(knoten: object, treffer: list[SkillRegistry], tiefe: int = 0) -> None:
    if tiefe > _MAX_DEPTH:
        return
    if isinstance(knoten, list):
        for kind in knoten:
            _sammle(kind, treffer, tiefe + 1)
        return
    if not isinstance(knoten, dict):
        return
    roh = knoten.get("skillRegistry")
    if isinstance(roh, dict):
        gelesen = _als_registry(knoten, roh)
        if gelesen is not None:
            treffer.append(gelesen)
    for wert in knoten.values():
        if isinstance(wert, list | dict):
            _sammle(wert, treffer, tiefe + 1)


def parse_skill_registries(raw_text: str) -> list[SkillRegistry]:
    """Alle Freigabelisten aus einem Werkzeugergebnis, entdoppelt.

    Entdoppelt ueber die nodeId des Registry-Dokuments: mehrere Unter-Sammlungen
    koennen dieselbe Liste fuehren (gemessen: das Lehrtoolkit haengt an mehreren
    Knoten), und zweimal dasselbe im Prompt ist zweimal bezahlt.

    Unlesbarer Text gibt ``[]`` und wirft nicht — siehe :func:`_lade`.
    """
    daten = load_envelope(raw_text)
    if daten is None:
        return []

    treffer: list[SkillRegistry] = []
    _sammle(daten, treffer)

    gesehen: set[str] = set()
    entdoppelt: list[SkillRegistry] = []
    for r in treffer:
        if r.registry_id in gesehen:
            continue
        gesehen.add(r.registry_id)
        entdoppelt.append(r)
    return entdoppelt


def _registry_block(r: SkillRegistry) -> list[str]:
    anzahl = len(r.entries)
    wort = "Skill" if anzahl == 1 else "Skills"
    zeilen = [
        f'Skill-Registry: „{r.collection_title}" ({r.collection_id}) '
        f"gibt {anzahl} {wort} frei.",
    ]
    for e in r.entries[:_MAX_ENTRIES]:
        zeilen.append(f"- {e.title} — {e.node_id}")
    if anzahl > _MAX_ENTRIES:
        zeilen.append(f"- … und {anzahl - _MAX_ENTRIES} weitere, siehe get_skill_registry.")
    return zeilen


def _anstoss(
    tool_name: str, args: dict | None, *, beantwortet: frozenset[str] = frozenset(),
) -> str:
    """Der Hinweis auf eine Sammlung, ueber deren Anleitungen niemand etwas sagt.

    Die ID kommt aus den Argumenten, mit denen WIR gerufen haben — kein
    Zusatzabruf, keine Rateraterei am Fremdtext. **Der Ergebnistext geht hier
    gar nicht mehr ein**, und das ist der Punkt: ob der Server die Frage schon
    beantwortet hat, entscheidet :data:`_SAMMLUNGS_WERKZEUGE`, nicht sein
    Wortlaut.

    **Mit Bedingung**, und das ist der zweite Kern: ohne sie riefe das Modell
    ``get_skill_registry`` bei jedem Navigationsschritt: ein Abruf je Drilldown
    fuer eine Frage, die niemand gestellt hat.

    :param beantwortet: Sammlungen, deren Katalog in DIESER Nachricht schon
        steht — dort waere der Anstoss eine Doppelung. Nur die tatsaechlich
        gezeigten zaehlen, nicht die weggekuerzten: beantwortet ist, was das
        Modell sieht. Heute kann der Fall nur eintreten, wenn der Server die
        Registry der angefragten Sammlung selbst anhaengt; genau das ist die
        Aenderung, die dem MCP-Team vorgeschlagen ist, und dann verstummt der
        Anstoss von allein, ohne dass jemand die Karte pflegen muss.
    """
    feld = _SAMMLUNGS_WERKZEUGE.get(tool_name)
    if feld is None:
        return ""
    node_id = _einzeilig((args or {}).get(feld), _MAX_TITLE)
    if not node_id or node_id in beantwortet:
        return ""
    return "\n".join([
        "",
        "",
        _ANSTOSS_MARKER,
        f"Diese Sammlung ({node_id}) kann Skills der Redaktion freigeben; "
        f'ob und welche, sagt get_skill_registry(collectionId="{node_id}").',
        "Geht es um eine Aufgabe IN dieser Sammlung — etwas erstellen, planen, "
        "erschliessen, pruefen —, hole sie VOR der eigenen Loesung. Geht es nur "
        "ums Stoebern oder Auflisten, lass es.",
    ])


def _nachfassen(tool_name: str, raw_text: str) -> str:
    """Der Anstoss zum ZWEITEN Schritt, direkt am Katalog-Ergebnis (2026-08-16).

    **Der Befund.** Live in der Sammlung „Optik": das Modell ruft
    ``get_skill_registry``, bekommt 32 855 Zeichen — und ruft ``get_skill``
    nicht. Drei Erklaerungen sind ausgeschlossen und gemessen: das Werkzeug
    fehlt nicht (``seeds/03-patterns/m09-lernpfad-erstellung.md:20``), die
    ``nodeId`` fehlt nicht (die Antwort traegt sie), und die Anweisung fehlt
    nicht — sie steht DREIFACH: im Seitenblock (``page_context.
    _bestands_zeilen``) und in beiden Werkzeugbeschreibungen.

    **Was bleibt.** Der Katalog liefert je Eintrag eine Beschreibung, die wie
    ein fertiger Auftrag liest — fuer „Stunde planen" etwa „tabellarischer
    Verlaufsplan mit Phasen, Minuten, Sozialform und Material je Phase". Nach
    32 855 Zeichen hat das Modell etwas in der Hand, das sich vollstaendig
    anfuehlt; der Wortlaut der Anleitung ist mit 14 290 Zeichen sogar 2,3× so
    klein. Der Grenznutzen eines weiteren Abrufs sieht klein aus — er ist es
    nicht: die Beschreibung sagt, WAS herauskommt, die Anleitung WIE.

    **Warum hier und nicht im Prompt.** Eine vierte Formulierung im
    Systemprompt waere der vierte Versuch derselben Art nach drei
    erfolglosen. Diese Zeile steht stattdessen an der Entscheidungsstelle:
    unmittelbar unter dem Ergebnis, im selben Zug, in dem das Modell waehlt.

    **Die Luecke war strukturell.** :func:`parse_skill_registries` sucht
    ``skillRegistry`` an aufgelisteten Knoten; eine ``get_skill_registry``-
    Antwort traegt aber ``{"registry": …}`` — eine andere Form. Und
    :data:`_SAMMLUNGS_WERKZEUGE` kennt das Werkzeug nicht. Nach dem Abruf des
    Katalogs wurde also gar nichts angehaengt.

    **Nur bei einem Katalog MIT Eintraegen.** Eine Sammlung ohne freigegebene
    Anleitungen liefert ``{"registry": {"entries": []}}`` — dort waere „waehle
    einen Eintrag" eine Aufforderung ins Leere. Gepinnt von
    ``test_die_registry_selbst_stoesst_sich_nicht_an``, das genau diese
    Nutzlast fuehrt; die erste Fassung dieser Funktion hing allein am
    Werkzeugnamen und ist daran gescheitert.

    **Mit Ausstieg**, aus demselben Grund wie bei :func:`_anstoss`: passt
    kein Eintrag, soll das Modell weiterarbeiten statt einen unpassenden Skill
    zu holen. Dieselbe Absicherung traegt die Beschreibung von
    ``search_skill`` seit jeher.
    """
    if tool_name != "get_skill_registry":
        return ""
    daten = load_envelope(raw_text)
    # Dieselbe Gueltigkeitsregel wie ueberall im Modul: ohne ``nodeId`` ist ein
    # Eintrag nicht abrufbar, also kein Grund, zum Abruf aufzufordern.
    if not isinstance(daten, dict) or not _gueltige_eintraege(daten.get("registry")):
        return ""
    return "\n".join([
        "",
        "",
        _NACHFASS_MARKER,
        "Diese Liste nennt Titel, nodeIds und Kurzbeschreibungen — NICHT den "
        "Skill selbst.",
        "Passt ein Eintrag zur Anfrage: jetzt get_skill(nodeId) mit DESSEN "
        "nodeId aufrufen und danach arbeiten. Die Kurzbeschreibung sagt, WAS "
        "herauskommt; der Skill sagt, WIE — sie ist kein Ersatz.",
        "Passt keiner, arbeite ohne Skill weiter und erwaehne ihn nicht.",
    ])


def skill_registry_note(
    raw_text: str, *, tool_name: str = "", args: dict | None = None,
) -> str:
    """Der Block fuers Modell, oder "" wenn dieses Ergebnis keine Registry traegt.

    Wird an die ``role=tool``-Nachricht **angehaengt**, nicht eingemischt:
    ``_redact_search_content_for_llm`` schreibt den Ergebnistext um, bevor das
    Modell ihn sieht. Bei den Einzelinhalt-Werkzeugen ersetzt es ihn ganz durch
    eine Zusammenfassung; bei der Kombi-Suche baut es ihn aus dem Envelope NEU
    auf — und das in beiden Anzeige-Modi. Wer den Block vorher einbaut, verliert
    ihn in beiden Faellen; beim Neuaufbau erst recht, denn dort ueberlebt nur,
    was im Envelope steht — still.

    **Mit eigenem Trenner davor.** Angehaengt wird mit ``+``, und das Ergebnis
    davor endet auf keiner bestimmten Zeile — ohne die Leerzeile klebte der
    Marker an der letzten Zeile des Fremdtextes (``…}]}[SKILL-REGISTRY …``).
    Ein Titel, der auf eine Zeile gezwungen wird, gewinnt nichts, wenn die
    Ueberschrift darueber selbst mitten im Fremdtext steht. ``_ui_box_state_
    footer`` beginnt aus demselben Grund mit ``\\n\\n``.

    ``tool_name``/``args`` (2026-08-15) sind der Aufruf, aus dem dieses Ergebnis
    stammt. Bringt es keine Registry mit, war der Aufruf aber sammlungsbezogen,
    tritt der **Anstoss** an die Stelle des Katalogs (:func:`_anstoss`) — live
    gemessen kommt der Auszug nur auf dem Suchpfad mit, und beim Hineinnavigieren
    in eine Sammlung schwieg bis dahin alles. Ohne die beiden Angaben verhaelt
    sich die Funktion wie zuvor; die vier Nahtstellen reichen sie durch.

    **Der Katalog schlaegt den Anstoss nur fuer DIESELBE Sammlung.** Wo beide
    dieselbe meinen, stuenden sonst 2 kB Katalog und die Bitte, ihn abzurufen,
    in derselben Nachricht. Wo sie verschiedene meinen, ist es keine Doppelung,
    sondern zwei Auskuenfte — und bis 2026-08-15 fiel dabei die wichtigere aus:
    ``browse_collection_tree`` haengt Registries an die KINDER, sobald der Cache
    sie kennt, also entschied dessen Waerme darueber, ob die Sammlung, IN der
    das Modell steht, ueberhaupt erwaehnt wurde. Kalt ja, warm nein — derselbe
    Aufruf, zwei Prompts. Warm war zugleich der schaedlichere Fall: Kataloge der
    Unter-Sammlungen und kein Wort ueber die eigene liest sich, als fuehre
    gerade sie keine.
    """
    registries = parse_skill_registries(raw_text)
    if not registries:
        # Die beiden Anstoesse schliessen einander aus, nicht der Reihenfolge
        # wegen, sondern weil ihre Werkzeugmengen disjunkt sind: _nachfassen
        # greift bei ``get_skill_registry``, _anstoss bei den zwei Werkzeugen
        # aus _SAMMLUNGS_WERKZEUGE. Das ``or`` sagt genau das.
        return _nachfassen(tool_name, raw_text) or _anstoss(tool_name, args)
    gezeigt = registries[:_MAX_REGISTRIES]
    zeilen = ["", "", _MARKER, _AUFFORDERUNG]
    for r in gezeigt:
        zeilen.extend(_registry_block(r))
    if len(registries) > _MAX_REGISTRIES:
        zeilen.append(
            f"(Dieses Ergebnis nennt {len(registries) - _MAX_REGISTRIES} weitere "
            "Sammlungen mit eigener Freigabeliste.)"
        )
    zeilen.append(_FUSS)
    return "\n".join(zeilen) + _anstoss(
        tool_name, args, beantwortet=frozenset(r.collection_id for r in gezeigt),
    )
