"""Was das MODELL von einem Werkzeug-Ergebnis zu sehen bekommt.

Herausgelöst aus ``inline_grouping`` (2026-08-16), weil dort vier
Änderungsgründe nebeneinander wohnten und die Redaktion der größte davon
geworden war. Sie hat ihren eigenen: die Antwortformen des MCP-Servers. Was
der NUTZER sieht — die Kasten-Zuordnung, der Wahrheits-Fußtext, der
Auswahl-Deckel — bleibt drüben.

Der Schnitt ist ein reiner Umzug: kein Verhalten geändert, nur der Wohnort.
``_is_einzelinhalt_card`` kommt weiterhin aus ``inline_grouping`` — die
Kasten-Zuordnung ist dessen Sache, hier wird sie nur gefragt.

Framework-frei zur Importzeit (stdlib + Logger). Einzige Ausnahme:
:func:`_redigiere_kombi_suche` holt den toleranten Envelope-Leser LAZY, im
Rumpf — Begründung dort.

**Warum das trotz MCP-Wissen in ``domain/`` liegt** (Entscheid 2026-08-16). Es
ist das einzige der 55 ``domain/``-Module, das in ``services.mcp`` greift; die
übrigen ``domain → services``-Kanten gehen sämtlich auf ``config_loader``, die
Konfig-Fassade. Der Grenzübertritt ist also real und keine Hausordnung. Er wird
in Kauf genommen, weil das Modul ZWEI Dinge trägt:

* **Politik** — was das Modell sehen darf, damit es nichts behauptet, was der
  Nutzer nicht sieht (:data:`_EINZELINHALT_LEAK_TOOLS`, :func:`_einzelinhalt_satz`,
  die Drei-Wege-Weiche). Das ist eine Produktregel, keine Transportfrage.
* **Drahtform-Wissen** — die drei Töpfe und ihre Feldnamen
  (:data:`_KOMBI_FELDER`, :func:`_kurzfassung`).

Ein Umzug nach ``services/mcp/`` verschöbe die Politik in die Adapterschicht —
die schlechtere der beiden Verletzungen. Ein dritter Schnitt entlang dieser Naht
wäre bei dieser Dateigröße Überbau.

**Ausstieg, falls es doch stört:** die Kopplung hängt an genau einem Aufruf. Wer
``_redact_search_content_for_llm`` neben dem Rohtext den bereits gelesenen
Umschlag hereinreicht, dreht die Kante um, ohne dass das Modul umzieht. Nicht
gratis: die drei Aufrufstellen (``tool_loop`` einmal, ``tool_loop_messages``
zweimal) halten heute nur den Rohtext — das Lesen wandert also mit, es
verschwindet nicht.
"""

from __future__ import annotations

import json
import logging as _log

from boerdi.domain.inline_grouping import _is_einzelinhalt_card

_logger = _log.getLogger(__name__)

# Tools deren Ergebnis im inline_result_grouping-Modus Einzelinhalt-
# Details enthalten könnte und damit Quellen für "Arbeitsblatt"-/
# "Video"-/"Inhalt"-Leakage in den Bot-Text sind. Nicht enthalten:
# search_wlo_collections / _topic_pages / browse_collection_tree /
# get_subject_portals — deren Treffer SIND als Boxen sichtbar, der
# User sieht also was beschrieben wird.
_EINZELINHALT_LEAK_TOOLS = {
    "search_wlo_content",      # primärer Treffer-Pool für Einzelmaterialien
    "get_collection_contents",  # Sammlung-Inhalte = i.d.R. Einzelmaterialien
    "get_node_details",        # Detail-View eines konkreten (oft Einzel-)Knotens
}


def _einzelinhalt_satz(name: str, einzel: list[dict]) -> str:
    """Die Ansage über zurückgehaltene Einzelinhalte — samt Typ-Aufschlüsselung.

    Zwei Aufrufer: die Leak-Werkzeuge ersetzen ihren ganzen Text damit, die
    Kombi-Suche hängt ihn hinter ihre beiden sichtbaren Töpfe.
    """
    n = len(einzel)
    types: dict[str, int] = {}
    for c in einzel:
        lrt = (c.get("lrt_label")
               or c.get("learning_resource_type")
               or "Inhalt")
        types[lrt] = types.get(lrt, 0) + 1
    type_summary = ", ".join(
        f"{k}x {t}" for t, k in sorted(
            types.items(), key=lambda x: -x[1],
        )[:5]
    ) or "verschiedene Typen"
    _logger.info(
        "redaction: redacted %s (n=%d einzelinhalte, types=%s)",
        name, n, type_summary,
    )
    return (
        f"OK - {name} lieferte {n} Einzelinhalte "
        f"({type_summary}). Diese sind im Backend gespeichert "
        "und werden NICHT als sichtbare Items angezeigt - der "
        "User erreicht sie nur ueber die Such-CTA. WICHTIG: "
        "Du darfst diese Einzelinhalte NICHT im Antwort-Text "
        "erwaehnen, zaehlen oder typisieren (kein 'ein Video', "
        "'ein Arbeitsblatt', 'zwei Materialien', 'eine Aufgabe'). "
        "Sprich im Text NUR ueber Themenseiten und Sammlungen."
    )


#: Das Kombi-Suchwerkzeug — seit W5-2a das Standard-Suchwerkzeug des Modells.
#: Antwortet in DREI Töpfen statt mit einer Trefferliste und braucht deshalb
#: eine eigene Redaktion.
_KOMBI_WERKZEUG = "search_wlo_all"

#: Der Skill-Katalog — eigene Antwortform, eigene Kürzung. Siehe
#: :func:`_redigiere_skill_registry`.
_KATALOG_WERKZEUG = "get_skill_registry"

#: Deckel je Katalog-Beschreibung. Sie soll das Modell WÄHLEN lassen, nicht
#: arbeiten — den Wortlaut liefert danach ``get_skill``. An der echten Registry
#: gemessen sind die Beschreibungen 45–250 Zeichen lang.
_KATALOG_BESCHREIBUNG = 200

#: Die Felder, aus denen das Modell einen Treffer beurteilen und auswählen kann.
#: ``compendiumText`` fehlt bewusst: er macht die Antwort erst groß (68 der 87 KB
#: im gemessenen Optik-Zug) und wird bei Bedarf einzeln über
#: ``get_compendium_text`` nachgeladen — dass es einen gibt, sagt
#: :data:`_MERKER_KOMPENDIUM`. Vorschaubild, MIME-Typ und Dateigröße tragen zur
#: Auswahl nichts bei. ``learningResourceTypes`` steht dabei, seit auch der
#: Flachkarten-Modus Einzelinhalte durchreicht: ob etwas ein Video oder ein
#: Arbeitsblatt ist, entscheidet dort über die Auswahl. Bei Sammlungen ist das
#: Feld leer und fällt von selbst weg.
_KOMBI_FELDER = ("nodeId", "title", "description", "keywords",
                 "disciplines", "educationalContexts", "learningResourceTypes")

#: Sagt „hier liegt redaktionelle Übersichts-Prosa", ohne sie mitzuschicken.
#: Ohne diesen Merker hätte ``get_compendium_text`` seit der Kürzung gar keinen
#: Anlass mehr — der gekürzte Auszug, auf den seine Beschreibung zeigte, ist ja
#: genau das, was hier wegfällt.
_MERKER_KOMPENDIUM = "hasCompendium"


#: Der alte, blinde Deckel: so viele Zeichen Rohtext bekommt das Modell, wo es
#: nichts Strukturiertes zu kürzen gibt (Fehlertexte, Markdown-Antworten, Tools
#: ohne eigene Redaktion). Bewusst als Rückfallebene stehengeblieben — für einen
#: unbekannten Text ist ein Deckel besser als keiner. Wo die Antwortform bekannt
#: ist, wird sie strukturell gekürzt statt abgeschnitten.
_ROH_DECKEL = 4000

#: Deckel für die Beschreibung eines Treffers — das einzige Feld ohne natürliche
#: Länge. Gemessen am echten Optik-Zug gehen die Sammlungs-Beschreibungen (441 /
#: 422 Zeichen, Median 376) vollständig durch; der Deckel greift erst bei
#: Ausreißern (bis 1802 Zeichen). Er ersetzt die Obergrenze, die der alte
#: ``raw_text[:4000]`` nebenbei mitbrachte: ``maxCollections`` ist dem Modell als
#: freier Integer angeboten (Server-Maximum 20), es können also 40 Treffer sein.
_MAX_BESCHREIBUNG = 600


def _kurzfassung(eintrag: dict) -> dict:
    """Ein Treffer auf :data:`_KOMBI_FELDER`; leere Felder fallen weg.

    Die Beschreibung wird bei :data:`_MAX_BESCHREIBUNG` gekappt, sichtbar mit
    Auslassungszeichen. Die ``nodeId`` überlebt jede Kürzung — ohne sie wäre der
    Treffer nicht wählbar, und genau das war der Befund.
    """
    kurz = {f: eintrag[f] for f in _KOMBI_FELDER if eintrag.get(f)}
    text = kurz.get("description")
    if isinstance(text, str) and len(text) > _MAX_BESCHREIBUNG:
        kurz["description"] = text[:_MAX_BESCHREIBUNG] + "…"
    if str(eintrag.get("compendiumText") or "").strip():
        kurz[_MERKER_KOMPENDIUM] = True
    return kurz


def _redigiere_kombi_suche(raw_text: str, *, mit_einzelinhalten: bool = False) -> str | None:
    """``search_wlo_all`` aufs Wählbare gekürzt — jeder Treffer, kein Ballast.

    :param mit_einzelinhalten: auch den ``content``-Topf mitschicken. Im
        Kasten-Modus ``False``: dort sind Einzelinhalte für den Nutzer nicht
        sichtbar, das Modell darf sie nicht nennen, und an ihre Stelle tritt
        :func:`_einzelinhalt_satz`. Im Flachkarten-Modus ``True``: dort **sieht**
        der Nutzer sie, sie zurückzuhalten wäre also falsch — gekürzt werden sie
        trotzdem, denn blind war der alte Deckel in BEIDEN Modi.

    ``None``, wenn der Text kein Kombi-Envelope ist — dann bleibt es beim alten
    Zeichen-Deckel.

    **Warum es diese Funktion gibt** (Befund 2026-08-16, Nutzer: „er findet die
    Optik-Sammlung weiterhin nicht"): das Kombi-Werkzeug antwortet in drei
    Töpfen, und der EINZIGE unsichtbare — ``content`` — steht vorn. Gemessen an
    der echten Antwort zu „Optik": 86.933 Zeichen, ``collections`` ab Zeichen
    12.023, ``topicPages`` ab 17.410. Der Deckel ``raw_text[:4000]`` ließ dem
    Modell 4 von 41 Node-IDs, allesamt Einzelinhalte. Es konnte „Optik" nicht in
    ``select_top_cards`` nennen, weil es die ID nie sah — und das Fenster ging
    vollständig an den Topf, den der Kasten-Modus dem Nutzer gerade vorenthält.

    Der tolerante Leser statt ``json.loads``, weil der MCP die Freigabeliste als
    ZWEITEN content-Block anhängt und unser Client beide zu einem Text fügt; ein
    blankes ``json.loads`` scheiterte an genau den Antworten, um die es hier geht.
    Lazy importiert, damit dieses Modul zur Importzeit abhängigkeitsfrei bleibt
    (Kopfkommentar). Die Technik ist dieselbe wie bei den MCP-Importen in
    ``card_pipeline`` — die Rechtfertigung aber NICHT: ``card_pipeline`` liegt in
    ``services`` und überschreitet dabei keine Schichtgrenze, dieser Aufruf hier
    schon. Warum das in Kauf genommen wird und wie man es wieder loswird, steht
    im Modulkopf; ein Lazy-Import verschiebt nur den Zeitpunkt, nicht die
    Abhängigkeit.
    """
    from boerdi.services.mcp.parsers.json_scan import load_envelope

    env = load_envelope(raw_text)
    if not isinstance(env, dict):
        return None
    if not any(isinstance(env.get(t), dict)
               for t in ("content", "collections", "topicPages")):
        return None
    gezeigt: dict = {}
    if env.get("query"):
        gezeigt["query"] = env["query"]
    toepfe = ("collections", "topicPages")
    if mit_einzelinhalten:
        toepfe = ("content", *toepfe)
    for topf_name in toepfe:
        topf = env.get(topf_name)
        if not isinstance(topf, dict):
            continue
        gezeigt[topf_name] = {
            **{k: topf[k] for k in ("total", "count") if isinstance(topf.get(k), int)},
            "results": [_kurzfassung(r) for r in (topf.get("results") or [])
                        if isinstance(r, dict)],
        }
    return json.dumps(gezeigt, ensure_ascii=False)


def _katalog_aus_markdown(raw_text: str) -> list[dict]:
    """Die Katalog-Einträge aus der Markdown-Form; leere Liste, wenn keine.

    Die Vorgabe des Werkzeugs ist ``markdown`` und das ist eine Entscheidung
    (``SkillRegistryArgs``: der Agent-Vorabruf legt den Registry-Text mit den
    Verwendungshinweisen dem Modell vor). Also muss die Kürzung diese Form
    lesen können — nicht die Form der Kürzung weichen.

    Gekoppelt wird an die **Feldmarken** ``### `` und ``nodeId:``, nicht an
    deutschen Fließtext. Das ist dieselbe Grenze, die
    ``parsers/skill_registry`` beim Anstoß gezogen hat: Vertragsfläche ja,
    Wortlaut nein. Ohne diese Marken kommt eine leere Liste zurück, und der
    Aufrufer fällt auf den blinden Deckel — schlechter als eine Liste, besser
    als eine falsche.
    """
    eintraege: list[dict] = []
    for block in raw_text.split("\n### ")[1:]:
        zeilen = block.splitlines()
        titel = zeilen[0].strip() if zeilen else ""
        node_id = ""
        zweck: list[str] = []
        for z in zeilen[1:]:
            if z.startswith("nodeId:"):
                node_id = z[len("nodeId:"):].strip()
            elif z.startswith("Keywords:") or z.startswith("#"):
                break
            elif z.strip():
                zweck.append(z.strip())
        if node_id:
            eintraege.append(
                {"nodeId": node_id, "title": titel, "description": " ".join(zweck)})
    return eintraege


def _redigiere_skill_registry(raw_text: str) -> str | None:
    """Der Skill-Katalog als reine Auswahlliste; ``None``, wenn unlesbar.

    **Der Befund, der das nötig machte** (live gemessen 2026-08-16). Die Antwort
    von ``get_skill_registry`` ist für die Sammlung „Optik" 32 855 Zeichen lang.
    :data:`_ROH_DECKEL` schnitt sie bei 4 000 ab — das Modell sah 12 %. Der
    gesuchte Eintrag „Stunde planen" beginnt bei Zeichen 13 091, seine ``nodeId``
    ebenso; beide waren unerreichbar. Das Modell rief ``get_skill`` daraufhin mit
    erfundenen IDs (gemessen: ``e6bcb2e0…``, ``7f2c8b94…``, einmal wörtlich
    ``'???'``) und bekam je 67–100 Zeichen Fehlertext zurück. Es hat nicht
    geschludert — es hatte keine einzige gültige ID vor sich.

    **Warum die Antwort so groß ist:** sie trägt dieselben 28 Skills ZWEIMAL —
    einmal als ``markdown``-Fließtext (16 717 Zeichen) und einmal als
    ``entries``-Liste (17 379). Für die Auswahl braucht das Modell die Liste;
    der Fließtext ist ihre Prosafassung. Also fällt er weg, und die Liste bleibt
    **vollständig**: die Wahl trifft das Modell, eine Teilliste nähme sie ihm
    vorweg.

    Damit löst diese Funktion ein, was der Deckel-Kommentar schon vorsah — „wo
    die Antwortform bekannt ist, wird sie strukturell gekürzt statt
    abgeschnitten". Für diese Form war sie bekannt und wurde trotzdem
    abgeschnitten.

    Kein Rahmen und keine Kürzung der Titel: ``skill_registry_note`` macht das
    für ihren eigenen Block; hier steht der Werkzeugtext, den ``frame_untrusted``
    am Aufrufer ohnehin umschließt.
    """
    from boerdi.services.mcp.parsers.json_scan import load_envelope

    daten = load_envelope(raw_text)
    registry = daten.get("registry") if isinstance(daten, dict) else None
    eintraege = registry.get("entries") if isinstance(registry, dict) else None
    if not isinstance(eintraege, list) or not eintraege:
        eintraege = _katalog_aus_markdown(raw_text)
    if not eintraege:
        return None

    zeilen = [
        f"Freigegebene Skills dieser Sammlung: {len(eintraege)}.",
        "Je Eintrag: nodeId — Titel — wofür sie da ist. Den Wortlaut liefert "
        "get_skill(nodeId).",
        "",
    ]
    for e in eintraege:
        if not isinstance(e, dict) or not e.get("nodeId"):
            continue
        titel = " ".join(str(e.get("title") or "").split())
        zweck = " ".join(str(e.get("description") or "").split())
        if len(zweck) > _KATALOG_BESCHREIBUNG:
            zweck = zweck[:_KATALOG_BESCHREIBUNG] + "…"
        zeilen.append(f"- {e['nodeId']} — {titel} — {zweck}")
    return "\n".join(zeilen)


def _redact_search_content_for_llm(
    name: str, raw_text: str, parsed_cards: list[dict],
    _inline_grouping_mode: bool,
) -> str:
    """Den LLM-sichtbaren Tool-Result-Text auf das kürzen, was das Modell zum
    Auswählen braucht — im inline_result_grouping-Modus zusätzlich ohne die
    Einzelinhalte, die der Nutzer dort nicht sieht.

    Die Cards selbst bleiben in ``all_cards`` / Prefetch-Akkumulatoren erhalten,
    sodass Such-CTA-Count und Lernpfad-Generator (separater Flow) weiter Zugriff
    haben.

    Drei Wege, in dieser Reihenfolge:

    1. **Die Kombi-Suche** liefert Sichtbares UND Unsichtbares in EINER Antwort,
       ist also weder „ganz durchlassen" noch „ganz ersetzen": sie wird
       strukturell redigiert, unabhängig davon, ob Einzelinhalte dabei sind —
       siehe :func:`_redigiere_kombi_suche`.
    2. **Die Einzelinhalt-Quellen** (:data:`_EINZELINHALT_LEAK_TOOLS`) werden
       ganz durch die Ansage ersetzt, sobald mindestens ein Einzelinhalt dabei
       ist; kamen nur Sammlungen zurück, bleibt der Text stehen.
    3. **Alles andere** — Tools mit ausschließlich Sammlungen/Themenseiten
       (search_wlo_collections, search_wlo_topic_pages, browse_collection_tree,
       get_subject_portals) — bleibt unangetastet: der User SIEHT diese Treffer.

    Weg 1 gilt in BEIDEN Modi — der Zeichen-Deckel war überall blind; nur was
    zurückgehalten werden darf, hängt am Modus. Wege 2 und 3 greifen nur im
    inline_result_grouping-Modus.
    """
    if name == _KATALOG_WERKZEUG:
        # Vor der Kombi-Suche geprüft, weil der Rückfall derselbe ist: gelingt
        # die strukturelle Kürzung nicht, bleibt der blinde Deckel.
        katalog = _redigiere_skill_registry(raw_text)
        return katalog if katalog is not None else raw_text[:_ROH_DECKEL]
    if name == _KOMBI_WERKZEUG:
        kurz = _redigiere_kombi_suche(
            raw_text, mit_einzelinhalten=not _inline_grouping_mode)
        if kurz is None:
            # Fehlertext statt Nutzlast — lieber der alte Deckel als nichts.
            return raw_text[:_ROH_DECKEL]
        if not _inline_grouping_mode:
            return kurz
        einzel = [c for c in parsed_cards if _is_einzelinhalt_card(c)]
        return kurz + ("\n\n" + _einzelinhalt_satz(name, einzel) if einzel else "")
    if not (_inline_grouping_mode and parsed_cards):
        return raw_text[:_ROH_DECKEL]
    einzel = [c for c in parsed_cards if _is_einzelinhalt_card(c)]
    if name not in _EINZELINHALT_LEAK_TOOLS:
        return raw_text[:_ROH_DECKEL]
    if not einzel:
        # Tool steht zwar auf der Leak-Liste, aber konkret nur Sammlungen
        # zurückgekommen → keine Redaction nötig (z.B. get_collection_contents
        # einer Meta-Sammlung).
        return raw_text[:_ROH_DECKEL]
    return _einzelinhalt_satz(name, einzel)
