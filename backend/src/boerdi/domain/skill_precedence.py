"""Haben die freigegebenen Anleitungen dieser Seite Vorrang vor den Mustern?

Nutzer-Regel 2026-08-16: „skills stehen dabei über den mustern die der chatbot
von haus aus mitbringt. wenn es ein muster für die gleiche ausgabe aus dem skill
und eines aus dem bot gibt - sollte er den skill nutzen".

**Wofür der Entscheid gebraucht wird.** Die mitgelieferten Schnellwege (Lernpfad,
Canvas) kürzen die Muster-Engine ab und betreten die Werkzeugschleife nie — sie
können bauartbedingt kein ``get_skill`` rufen (``grep -c skill
services/lp_fast_path.py`` → 0). Genau daran scheiterte der Befund vom 2026-08-16:
„stundenentwurf" ist ein Auslöser des Lernpfad-Schnellwegs (``lp_intent.py:43``)
UND das Aktivierungs-Stichwort des freigegebenen Skills „Stunde planen". Der
Schnellweg gewann, weil er zuerst dran war.

Greift der Vorrang, treten die Schnellwege zurück und der Zug läuft den
gewöhnlichen Weg über Muster-Engine und Werkzeugschleife. **Dort** entscheidet
das Modell — es sieht im Antwort-Prompt den Katalog samt Vorrang-Regel
(``page_context._bestands_zeilen``, eingesetzt in
``response_prompt_builder.py:119`` mit der Vorgabe ``include_stock=True``) und
hat ``get_skill_registry``/``get_skill`` in der Werkzeugliste. Dieses Modul
entscheidet also **nicht**, ob ein Skill passt — nur, ob das Modell überhaupt
gefragt wird.

**Warum die Entscheidung nicht im Klassifikator sitzt** (geprüft 2026-08-16,
ursprünglicher Entwurf verworfen): Der Klassifikator sieht den Katalog gar nicht
— ``classify_prompt.py:249`` ruft ``render_for_prompt(…, include_stock=False)``,
gemessene 2 232 Zeichen je Zug gespart. Und nennen könnte er eine Anleitung auch
nicht: die Fakten führen Titel, aber **keine** ``nodeId`` — Nutzer-Vorgabe
2026-08-14 („nur die Übersicht … höchstens eine A4 Seite", Rechnung in
``context_facts._skill_fakten``). Ihn zu fragen hieße, ihn zum Erfinden
aufzufordern.

Kennt weder MCP noch den Metadaten-Zwischenspeicher: der Aufrufer reicht die
Bestandsfakten als Dict herein. Einzige Abhängigkeit ausserhalb der stdlib ist
der Kartenfeld-Leser aus ``domain/cards/build`` — dieselbe Ebene, und der dort
bereits ausgewiesene ``domain->schema``-Import (siehe dessen Modul-Docstring).
"""

from __future__ import annotations

from dataclasses import dataclass

# Karten kommen als ``WloCard``-Modell (Muster-Pfad) ODER als Dict
# (Agent-Pfad); ``_feld`` liest beide. Bewusst wiederverwendet statt neu
# geschrieben — eine zweite Kopie derselben Regel driftet.
from boerdi.domain.cards.build import _feld

#: Wohin die Gesprächs-Notiz reist. Die ``_``-Konvention ist der etablierte
#: Platz für zugübergreifenden Nicht-Slot-Zustand (``_canvas_topic``,
#: ``_lp_used_node_ids``, ``_last_pattern`` …); ``turn_persist`` schreibt
#: ``entities`` ohnehin als JSONB, deshalb braucht es weder Spalte noch
#: Migration (dieselbe Begründung wie in ``domain/turn_frame``).
BESTAND_KEY = "_skill_bestand"

#: Wie viele Sammlungen die Notiz höchstens führt.
#:
#: **Warum überhaupt mehrere** (MCP-Entwickler + Nutzer-Entscheid 2026-08-16):
#: jede Sammlung führt ihr EIGENES Registry-Dokument. Gemessen am echten Server
#: tragen „Optik" (9e7ae956) und „Geometrische Optik" (f35c17d1) verschiedene
#: Kataloge — ``registryTitle`` „Skillkatalog Physik Optik" gegen „Skill
#: Registry", verschiedene ``registryNodeId`` —, deren Einträge sich heute
#: vollständig decken. Das ist Überschneidung, nicht Vererbung: derselbe Skill
#: darf in beiden stehen, und morgen führt einer einen, den der andere nicht
#: hat. Nur die reichste zu merken hiesse, den zweiten Katalog wegzuwerfen.
#:
#: Der Deckel, weil der Block jede Sammlung mit Titel und ID nennt: drei sind
#: die Hausgrösse (``display-rules.groups`` deckelt jede Box bei 3), und wer
#: mehr braucht, hat ein anderes Problem als einen fehlenden Eintrag.
MAX_BESTAND_SAMMLUNGEN = 3

QUELLE_SEITE = "seite"
QUELLE_GESPRAECH = "gespraech"

#: Die Anleitung, die gerade abgearbeitet wird — eigener Schlüssel neben
#: :data:`BESTAND_KEY`: jener sagt „hier GIBT es Anleitungen", dieser „DIESE
#: ist in Arbeit". Zwei Fragen, zwei Notizen.
LAUF_KEY = "_skill_lauf"

#: Wie viele Züge die Notiz gilt. Eine Rückfrage wird im nächsten Zug
#: beantwortet; zwei lassen Raum für eine zweite. Ruft das Modell die Anleitung
#: erneut, frischt sich die Notiz selbst auf — die Frist trifft also nur den
#: Fall, in dem sie nicht mehr genutzt wird. Ohne Frist bekäme jeder spätere
#: Zug denselben Hinweis, auch bei ganz anderem Thema. (Dieselbe Abwägung wie
#: bei ``CLARIFICATION_ATTEMPT_LIMIT`` in ``domain/turn_frame``.)
LAUF_GUELTIG_ZUEGE = 2

#: Wie viel Platz der Sammlungstitel im Hinweis höchstens bekommt.
#:
#: Er stammt aus einem Suchtreffer, ist also von fremder Hand. Gerahmt wird er
#: nicht — die Hausregel rahmt Langform-Prosa, ausdrücklich nicht kurze
#: Metadatenfelder (Modul-Docstring ``domain/untrusted_text``), und der
#: Seitenblock hält es mit ``meta["title"]`` genauso. Einzeilig und gedeckelt
#: muss er trotzdem sein: sonst schriebe ein Titel mit Zeilenumbrüchen eigene
#: Überschriften in den Block, in dem er steht.
MAX_TITEL_ZEICHEN = 120


@dataclass(frozen=True)
class SkillEntscheid:
    """Das Ergebnis: greift der Vorrang, wie viele Anleitungen, und warum nicht.

    :param greift: Es sind freigegebene Anleitungen im Spiel ⇒ die mitgelieferten
        Schnellwege treten zurück.
    :param anzahl: Wie viele Anleitungen; ``0``, wenn keine.
    :param grund: Warum der Vorrang NICHT greift — für Debug-Block und
        Quality-Event, nie für den Nutzer. Leer, wenn er greift.
    :param quelle: Woher die Auskunft stammt — :data:`QUELLE_SEITE` (der Nutzer
        steht auf der Sammlung) oder :data:`QUELLE_GESPRAECH` (sie kam als
        Treffer). Steht im Protokoll, damit der Weg ablesbar bleibt; leer, wenn
        der Vorrang nicht greift.
    """

    greift: bool
    anzahl: int
    grund: str
    quelle: str = ""


def _einzeilig(wert: object) -> str:
    """Fremdtext auf eine gedeckelte Zeile — sonst ``""``.

    Sammlungstitel, Skill-Titel und Sammlungs-ID kommen alle aus fremder Feder
    (Suchtreffer bzw. ``get_skill``-Ergebnis) und stehen alle in einer Zeile
    eines Prompt- oder Chat-Blocks. Ein Zeilenumbruch darin schriebe eigene
    Zeilen; deshalb EINE Regel für alle drei statt drei Handkopien.

    Gerahmt wird nicht — die Hausregel rahmt Langform-Prosa, ausdrücklich nicht
    kurze Metadatenfelder (Modul-Docstring ``domain/untrusted_text``).
    """
    if not isinstance(wert, str):
        return ""
    return " ".join(wert.split())[:MAX_TITEL_ZEICHEN]


def _anzahl(wert: object) -> int:
    """Eine brauchbare Anzahl aus Fremdinhalt — sonst ``0``.

    ``bool`` ist in Python eine ``int``-Unterart; ohne die zweite Prüfung wäre
    ein durchgerutschtes ``true`` aus dem JSON „eine Anleitung".
    """
    if isinstance(wert, int) and not isinstance(wert, bool) and wert > 0:
        return wert
    return 0


def merke_skill_sammlung(entities: object, karten: object) -> None:
    """Zeigte dieser Zug eine Sammlung mit freigegebenen Anleitungen? Merken.

    Schreibt in-place nach ``entities[BESTAND_KEY]``. Aufzurufen, sobald die
    Karten eines Zuges feststehen und BEVOR der Zustand geschrieben wird
    (``graph/nodes/assemble``).

    **Warum es die Notiz braucht.** Der Vorrang hing bis 2026-08-16 allein am
    Seitenkontext. Wer über die Suche kommt, hat keinen — der Lernpfad-Schnellweg
    griff dort wie vor allen Änderungen, gemessen an „erst zu Optik suchen, dann
    Stunde planen". Die Zahl war längst da: Suchtreffer tragen ``skill_count``
    (Paket #194). Sie wurde nur nie über den Zug hinaus behalten.

    **Gemerkt wird die reichste Sammlung** des Zuges. Mehrere Sammlungen sind der
    Normalfall einer Suche; die schmalste zu nehmen wäre eine willkürliche
    Verschlechterung, und alle zu führen brächte nichts — der Vorrang fragt nur,
    OB es Anleitungen gibt.

    **Die Notiz bleibt** (``simplify:`` — kein Verfall gebaut). Wechselt das
    Gespräch das Thema, treten die Schnellwege weiter zurück, bis eine neue
    Sammlung die Notiz überschreibt. Der Preis ist ein Zug über die
    Werkzeugschleife statt über den Schnellweg — langsamer, nicht falsch. Ein
    Verfall nach N Zügen hätte hier nichts zu reparieren (dieselbe Abwägung wie
    bei der Frist in ``domain/turn_frame``).
    """
    if not isinstance(entities, dict) or not isinstance(karten, list | tuple):
        return
    gefunden = [
        {"anzahl": anzahl,
         "titel": _einzeilig(_feld(karte, "title")),
         "node_id": _einzeilig(_feld(karte, "node_id"))}
        for karte in karten
        if (anzahl := _anzahl(_feld(karte, "skill_count")))
    ]
    if not gefunden:
        return
    # Reihenfolge ist Rang: der Block nennt sie so, und der Deckel wirft die
    # schmalste zuerst weg. ``sorted`` ist stabil — bei Gleichstand bleibt die
    # Fundreihenfolge, und die ist die Relevanz-Reihenfolge des MCP.
    gefunden.sort(key=lambda b: b["anzahl"], reverse=True)
    entities[BESTAND_KEY] = gefunden[:MAX_BESTAND_SAMMLUNGEN]


def _bestand_liste(entities: object) -> list[dict]:
    """Die gemerkten Sammlungen als Liste — aus jeder Form, die ankommt.

    Die Notiz reist als ``jsonb`` durch die Sitzung. Ein Zug, der vor der
    Umstellung auf mehrere Sammlungen geschrieben wurde, trägt dort noch ein
    einzelnes Dict; er soll deshalb nicht seinen Vorrang verlieren.
    """
    if not isinstance(entities, dict):
        return []
    notiz = entities.get(BESTAND_KEY)
    if isinstance(notiz, dict):
        return [notiz]
    if not isinstance(notiz, list):
        return []
    return [b for b in notiz if isinstance(b, dict)]


def merke_laufende_anleitung(
    entities: object, node_id: object, zug: object, titel: object = "",
) -> None:
    """Diese Anleitung wurde gerade geholt — für die Folgezüge merken (in-place).

    Aufzurufen, wenn ``get_skill`` gelaufen ist (``services/tool_loop``).

    :param titel: der Titel der Anleitung, für die Chat-Ansage
        (:func:`mit_ladehinweis`). Fehlt er, entfällt nur die Ansage — die
        Notiz selbst trägt den Faden über ``node_id``.

    **Warum es die Notiz braucht** — Nutzer-Test 2026-08-16: Der Skill „Stunde
    planen" stellte seine Rückfrage („45 oder 90 Minuten?"). Die Antwort
    „45 min physik sek 1" ging beim Klassifikator nach *Qualitätssicherung*, das
    Modell holte daraufhin eine ANDERE Anleitung und lieferte einen
    Material-Fund statt des Verlaufsplans. Ein Skill, der nachfragt, hinterliess
    keine Spur; der nächste Zug entschied neu.

    Für Rückfragen des SYSTEMS gibt es die Übergabe längst (``domain/turn_frame``
    zählt Versuche, der Klassifikator kennt ``turn_type=clarification``). Für
    Rückfragen aus einem SKILL gab es nichts.
    """
    if not isinstance(entities, dict):
        return
    if not isinstance(node_id, str) or not node_id.strip():
        return
    if not isinstance(zug, int) or isinstance(zug, bool):
        return
    entities[LAUF_KEY] = {
        "node_id": node_id.strip(),
        "zug": zug,
        "titel": _einzeilig(titel),
    }


def mit_ladehinweis(text: str, entities: object, zug: object) -> str:
    """Die Ansage „<Titel> wird geladen" vor die Antwort setzen — oder nicht.

    Nutzer-Vorgabe 2026-08-16: eine **hartcodierte** Zeile, sobald ``get_skill``
    eine Anleitung in den Prompt geholt hat.

    **Warum hartcodiert.** Bis hierher kam die Ansage aus dem Ergebnis selbst:
    der MCP-Server schreibt dort einen Abschnitt „## Aktivierung" mit der Bitte,
    eine Zeile WÖRTLICH auszugeben. Gemessen hielt sich das Modell nicht daran —
    einmal „▸ stunde-planen aktiv — Verlaufsplan für 45 oder 90 Minuten", einmal
    „[ edu-sharing Skill ] Stunde planen - aktiv". Eine Ansage, die das Modell
    umformuliert, ist eine Behauptung. Diese hier entsteht nur, wenn der Aufruf
    wirklich lief — sie ist ein Beleg.

    **Nur im ladenden Zug.** Die Notiz gilt :data:`LAUF_GUELTIG_ZUEGE` Züge,
    damit die Rückfrage einer Anleitung fortgeführt wird; die Ansage gilt einen.
    Geladen wurde einmal, und zweimal „wird geladen" wäre schlicht unwahr.

    **Vorangestellt, nicht angehängt** — sie sagt an, was gleich kommt. An eine
    leere Antwort kommt sie nicht (dieselbe Regel wie in
    ``domain/answer_notes.append_answer_notes``).
    """
    if not text or not isinstance(entities, dict):
        return text
    if not isinstance(zug, int) or isinstance(zug, bool):
        return text
    notiz = entities.get(LAUF_KEY)
    if not isinstance(notiz, dict) or notiz.get("zug") != zug:
        return text
    titel = _einzeilig(notiz.get("titel"))
    if not titel:
        return text
    return f"[ edu-sharing Skill ] {titel} - wird geladen\n\n{text}"


def laufende_anleitung(entities: object, zug: object) -> str:
    """Die ``nodeId`` der Anleitung, die noch in Arbeit ist — sonst ``""``.

    Der Aufrufer setzt daraus die Zeile für den Antwort-Prompt. Sie **informiert**
    und zwingt nicht: es bleibt bei der Nutzer-Regel „das Modell entscheidet, was
    es nutzt" — der Hinweis sorgt nur dafür, dass es die laufende Anleitung
    überhaupt kennt.
    """
    if not isinstance(entities, dict) or not isinstance(zug, int):
        return ""
    notiz = entities.get(LAUF_KEY)
    if not isinstance(notiz, dict):
        return ""
    node_id = notiz.get("node_id")
    notiert = notiz.get("zug")
    if not isinstance(node_id, str) or not node_id:
        return ""
    if not isinstance(notiert, int) or isinstance(notiert, bool):
        return ""
    return node_id if 0 <= zug - notiert <= LAUF_GUELTIG_ZUEGE else ""


def skill_vorrang(fakten: object, entities: object = None) -> SkillEntscheid:
    """Der Vorrang-Entscheid aus **zwei** Quellen: Seite und Gespräch.

    :param fakten: ``meta["context_facts"]`` aus dem Metadaten-Zwischenspeicher,
        den der ``page_context_enrich``-Knoten füllt — oder irgendetwas anderes.
        Der Wert kommt als ``jsonb`` aus ``session_state['entities']`` zurück und
        ist damit fremdbeschrieben; jede Form ist möglich und keine ist ein
        Fehler, sondern schlicht „keine Anleitungen bekannt".
    :param entities: ``session_state['entities']`` — trägt unter
        :data:`BESTAND_KEY` die Notiz, die :func:`merke_skill_sammlung` in einem
        früheren Zug hinterlassen hat. Gleiche Härte: fremdbeschrieben.
    :returns: Der :class:`SkillEntscheid`.

    **Die Seite hat Vorfahrt.** Steht der Nutzer auf einer Sammlung, ist deren
    Zahl die aktuellere Auskunft als eine Notiz von vorhin. Die Notiz ist der
    Rückfall für den Sucheinstieg — und der ist der häufigere Weg.

    Maßgeblich ist ``skills`` (die Anzahl), nicht ``skill_titles``: die Titel
    sind auf ``MAX_SKILL_ENTRIES`` gedeckelt und können fehlen, während die Zahl
    Anleitungen meldet. Eine Prüfung auf die Titelliste verlöre den Vorrang
    ausgerechnet bei den größten Sammlungen.

    Kein Schwellwert: **eine** freigegebene Anleitung ist bereits eine
    redaktionelle Aussage.
    """
    if isinstance(fakten, dict) and fakten:
        von_der_seite = _anzahl(fakten.get("skills"))
        if von_der_seite:
            return SkillEntscheid(True, von_der_seite, "", QUELLE_SEITE)
        grund = "keine-skills"
    else:
        grund = "keine-fakten"

    # Die grösste Zahl gewinnt: der Vorrang fragt nur, OB Skills im Spiel sind,
    # und die stärkste Auskunft ist die belastbarste.
    aus_dem_gespraech = max(
        (_anzahl(b.get("anzahl")) for b in _bestand_liste(entities)), default=0)
    if aus_dem_gespraech:
        return SkillEntscheid(True, aus_dem_gespraech, "", QUELLE_GESPRAECH)

    return SkillEntscheid(greift=False, anzahl=0, grund=grund)


def anleitungs_hinweis(fakten: object, entities: object) -> str:
    """Der Prompt-Block für Anleitungen, die nur aus dem GESPRÄCH bekannt sind.

    Gleiche Eingaben wie :func:`skill_vorrang` — dieselbe Frage, nur für den
    anderen Leser: das Routing fragt „darf der Schnellweg noch", der Prompt
    fragt „weiß das Modell davon".

    **Warum es den Block braucht** (live gemessen 2026-08-16 mit dem Payload,
    den das Widget wirklich schickt). Auf der Sammlungsseite trägt der Weg
    komplett: ``Bestandsfakten geladen: 36 Materialien, 28 Skills`` →
    ``page_context._bestands_zeilen`` schreibt Katalog und Vorrang-Regel in den
    Prompt → das Modell ruft ``get_skill 5b29f470`` → der Stundenentwurf steht
    in der Kachel.

    Über die SUCHE trug er nichts: ohne Seiten-Metadaten liefert
    ``render_for_prompt`` einen leeren Block. Der Vorrang griff zwar (die Notiz
    aus :func:`merke_skill_sammlung` nahm die Schnellwege aus dem Weg), aber
    danach stand das Modell vor einer Aufgabe ohne Hinweis: es wusste weder,
    dass Anleitungen freigegeben sind, noch mit welcher ``collectionId`` es
    ``get_skill_registry`` aufrufen soll — die Stufe, die M08/M09/M10/M18/M19
    ausdrücklich verlangen. Die Notiz führt beides längst mit.

    **Nicht auf der Seite** (:data:`QUELLE_SEITE`): dort steht der volle Katalog
    schon im Seitenblock. Zwei Hinweise auf dieselbe Sache wären zwei Stimmen im
    selben Prompt, und die schwächere gewönne manchmal.

    **Ohne ``node_id`` gar nichts.** Der Block ist ein Weg in zwei Stufen; ohne
    die Sammlungs-ID fehlt der ersten ihr Argument. Ein Weg, dessen erster
    Schritt nicht geht, ist schlechter als kein Weg.

    **Jede Sammlung mit ihrer eigenen ID** (MCP-Entwickler + Nutzer-Entscheid
    2026-08-16). Jede führt ihr eigenes Registry-Dokument; siehe die Messung bei
    :data:`MAX_BESTAND_SAMMLUNGEN`. Nur die reichste zu nennen hiesse, dem
    Modell den zweiten Katalog vorzuenthalten — und bei Gleichstand entschiede
    die Fundreihenfolge, welchen es nie zu sehen bekommt.

    Er **informiert und zwingt nicht** — es bleibt bei der Nutzer-Regel „das
    Modell entscheidet, was es nutzt"; der Block sorgt nur dafür, dass es die
    Wahl überhaupt hat. Wortlaut bewusst wie im Seitenblock
    (``page_context._bestands_zeilen``): eine Sache, eine Stimme.

    :returns: Der fertige Markdown-Block, oder ``""`` — dann ist nichts zu sagen.
    """
    entscheid = skill_vorrang(fakten, entities)
    if entscheid.quelle != QUELLE_GESPRAECH or not isinstance(entities, dict):
        return ""
    # Titel und ID stammen aus derselben fremden Karte, also beide einzeilig.
    # Ohne ID fällt der Eintrag weg: Stufe 1 hätte für ihn kein Argument.
    zeilen = [
        f"- {_einzeilig(b.get('titel')) or 'ohne Titel'} — "
        f"`collectionId=\"{nid}\"` ({_anzahl(b.get('anzahl'))} Skills)"
        for b in _bestand_liste(entities)
        if (nid := _einzeilig(b.get("node_id"))) and _anzahl(b.get("anzahl"))
    ]
    if not zeilen:
        return ""
    return (
        "## Freigegebene Skills\n"
        "In diesem Gespräch kamen Sammlungen vor, über die freigegebene Skills "
        "erreichbar sind:\n"
        + "\n".join(zeilen) + "\n"
        "Jede Sammlung führt ihren EIGENEN Katalog; derselbe Skill kann in "
        "mehreren stehen. Sie gehen deinen mitgelieferten Vorlagen VOR: Deckt "
        "einer von ihnen die Frage ab, arbeite nach ihm — auch dann, wenn du "
        "für dieselbe Ausgabe eine eigene Vorlage hättest.\n"
        "Der Weg, zwei Stufen: `get_skill_registry` mit einer `collectionId` von "
        "oben nennt zu jedem Titel die `nodeId` samt Verwendungshinweis der "
        "Redaktion, dann liefert `get_skill(\"<nodeId>\")` den Wortlaut — und "
        "arbeite danach, statt den Ablauf selbst zu erfinden."
    )
