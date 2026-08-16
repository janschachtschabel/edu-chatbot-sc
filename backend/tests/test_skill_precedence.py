"""Der Vorrang freigegebener Anleitungen vor den mitgelieferten Mustern.

Die Regel des Nutzers (2026-08-16): „skills stehen dabei über den mustern die
der chatbot von haus aus mitbringt". Diese Datei hält die reine Entscheidung
fest — greift der Vorrang in diesem Zug, und wenn nicht, warum nicht.

**Warum der Grund mitgeprüft wird:** er ist kein Schmuck, sondern der Nachweis
im Debug-Block. Der gemeldete Fehler kam auf, weil die einzige verfügbare
Auskunft über die Skill-Nutzung eine *Selbstauskunft des Modells* war — die war
zufällig richtig, aber sie war kein Beleg. Ein Grund, der nur manchmal stimmt,
wäre derselbe Fehler noch einmal.

**Warum so viel Unsinn als Eingabe:** die Fakten reisen als ``jsonb`` durch
``session_state['entities']`` und sind damit fremdbeschrieben — dieselbe Lage,
die ``context_facts.retry_due`` bereits ausdrücklich behandelt. Was von dort
kommt, darf jede Form haben.
"""

from __future__ import annotations

import pytest

from boerdi.domain.skill_precedence import (
    BESTAND_KEY,
    LAUF_GUELTIG_ZUEGE,
    LAUF_KEY,
    MAX_BESTAND_SAMMLUNGEN,
    MAX_TITEL_ZEICHEN,
    anleitungs_hinweis,
    laufende_anleitung,
    merke_laufende_anleitung,
    merke_skill_sammlung,
    mit_ladehinweis,
    skill_vorrang,
)


# ── Kein Vorrang: es gibt nichts, dem etwas vorgehen könnte ────────
@pytest.mark.parametrize("fakten", [None, {}, "kaputt", 17, [], ["skills"]])
def test_ohne_brauchbare_fakten_greift_kein_vorrang(fakten):
    """Ohne Fakten bleibt alles wie bisher — der Schnellweg ist nicht der
    Fehler, er ist nur der falsche Weg WENN Anleitungen da sind."""
    e = skill_vorrang(fakten)
    assert e.greift is False
    assert e.anzahl == 0
    assert e.grund == "keine-fakten"


def test_fakten_ohne_skill_zahl_greifen_nicht():
    """Eine Sammlung ohne freigegebene Anleitungen: der Bestandsabruf lieferte
    Materialzahlen, aber die Registry war leer (``_skill_fakten`` gibt dann ein
    leeres Dict zurück, die Materialzahlen bleiben)."""
    e = skill_vorrang({"materials": 36, "sub_collections": 2})
    assert e.greift is False
    assert e.grund == "keine-skills"


@pytest.mark.parametrize("wert", [0, -3, "28", 28.0, None, True])
def test_eine_unbrauchbare_skill_zahl_greift_nicht(wert):
    """``skills`` ist als Anzahl geschrieben (``len(eintraege)``), kommt aber
    aus ``jsonb`` zurück. Alles, was keine echte positive Ganzzahl ist, zählt
    als „keine Anleitungen" — im Zweifel bleibt der Bestandsweg.

    ``True`` steht ausdrücklich in der Liste: in Python ist ``bool`` eine
    ``int``-Unterart, ``isinstance(True, int)`` ist wahr. Ohne eigene Prüfung
    wäre ein durchgerutschtes ``true`` aus dem JSON „eine Anleitung".
    """
    e = skill_vorrang({"materials": 36, "skills": wert})
    assert e.greift is False
    assert e.anzahl == 0
    assert e.grund == "keine-skills"


# ── Vorrang: die Redaktion hat etwas freigegeben ───────────────────
def test_mit_freigegebenen_anleitungen_greift_der_vorrang():
    """Der Fall aus dem Befund: die Sammlung „Optik" trug 28 Anleitungen,
    darunter „Stunde planen" — und der Bot baute trotzdem seinen Lernpfad."""
    e = skill_vorrang({"materials": 36, "skills": 28, "skill_titles": ["Stunde planen"]})
    assert e.greift is True
    assert e.anzahl == 28
    assert e.grund == ""


def test_eine_einzige_anleitung_genuegt():
    """Kein Schwellwert: eine freigegebene Anleitung ist eine redaktionelle
    Aussage über diese Seite, und die geht der Systemvorlage vor."""
    assert skill_vorrang({"skills": 1}).greift is True


# ── Zweite Quelle: die Sammlung kam aus dem GESPRÄCH ────────────────
# Live gemessen 2026-08-16: „erst zu Optik suchen, dann Stunde planen" fiel
# durch, obwohl Zug 1 die Sammlung fand. Der Vorrang hing allein am
# Seitenkontext — wer über die Suche kommt, hat keinen. Die Karte trug die
# Zahl längst mit (``skill_count = 28``, Paket #194); sie wurde nur nie
# gemerkt.

class _Karte:
    """Karten kommen als Pydantic-Modell durch den Graphen, nicht als Dict."""

    def __init__(self, node_id="", title="", skill_count=0):
        self.node_id, self.title, self.skill_count = node_id, title, skill_count


def test_eine_karte_mit_anleitungen_wird_fuers_gespraech_gemerkt():
    entities: dict = {}
    merke_skill_sammlung(entities, [
        _Karte("c1", "Ein Video", 0),
        _Karte("f35c17d1", "Geometrische Optik", 28),
    ])
    assert entities["_skill_bestand"] == [
        {"anzahl": 28, "titel": "Geometrische Optik", "node_id": "f35c17d1"}]


def test_ohne_anleitungen_wird_nichts_gemerkt():
    entities: dict = {}
    merke_skill_sammlung(entities, [_Karte("c1", "Ein Video", 0)])
    assert entities == {}


def test_die_reichste_sammlung_gewinnt_die_notiz():
    """Mehrere Sammlungen im Zug: gemerkt wird die mit den meisten Anleitungen —
    die schmalste zu nehmen wäre eine willkürliche Verschlechterung."""
    entities: dict = {}
    merke_skill_sammlung(entities, [_Karte("a", "Klein", 2), _Karte("b", "Groß", 28)])
    assert entities["_skill_bestand"][0]["node_id"] == "b"


def test_karten_als_dict_werden_genauso_gelesen():
    """Der Agent-Pfad reicht Karten als Dict herein — beide Formen zählen."""
    entities: dict = {}
    merke_skill_sammlung(entities, [{"node_id": "x", "title": "Optik", "skill_count": 5}])
    assert entities["_skill_bestand"][0]["anzahl"] == 5


@pytest.mark.parametrize("unsinn", [None, "keine liste", 42, {"a": 1}])
def test_unbrauchbare_karten_hinterlassen_keine_notiz(unsinn):
    entities: dict = {}
    merke_skill_sammlung(entities, unsinn)
    assert entities == {}


def test_ohne_seitenkontext_traegt_die_notiz_aus_dem_gespraech_den_vorrang():
    """Der eigentliche Befund: kein Seitenkontext, aber das Gespräch hat eine
    Sammlung mit Anleitungen gezeigt — der Vorrang muss greifen."""
    entscheid = skill_vorrang(None, {"_skill_bestand": {"anzahl": 28}})
    assert entscheid.greift is True
    assert entscheid.anzahl == 28
    assert entscheid.quelle == "gespraech"


def test_der_seitenkontext_hat_vorfahrt_vor_der_notiz():
    """Steht der Nutzer AUF einer Sammlung, gilt deren Zahl — sie ist die
    aktuellere Auskunft als eine Notiz von vorhin."""
    entscheid = skill_vorrang({"skills": 3}, {"_skill_bestand": {"anzahl": 28}})
    assert (entscheid.anzahl, entscheid.quelle) == (3, "seite")


@pytest.mark.parametrize("notiz", [
    None, "kein dict", {}, {"_skill_bestand": None}, {"_skill_bestand": {}},
    {"_skill_bestand": {"anzahl": 0}}, {"_skill_bestand": {"anzahl": True}},
    {"_skill_bestand": {"anzahl": "28"}},
])
def test_eine_unbrauchbare_notiz_traegt_keinen_vorrang(notiz):
    """Die Notiz reist als ``jsonb`` mit und ist damit fremdbeschrieben —
    dieselbe Härte wie bei den Bestandsfakten."""
    assert skill_vorrang(None, notiz).greift is False


# ── Die laufende Anleitung (Befund aus dem Nutzer-Test 2026-08-16) ──
# Der Skill „Stunde planen" stellte eine Rückfrage („45 oder 90 Minuten?").
# Die Antwort „45 min physik sek 1" ging beim Klassifikator nach
# *Qualitätssicherung*, das Modell holte einen ANDEREN Skill (c8936233 statt
# 5b29f470) und lieferte einen Material-Fund statt des Verlaufsplans.
# Belegt im Protokoll durch drei get_skill-Aufrufe in Folge.
#
# Für Rückfragen des SYSTEMS (M03) gibt es die Übergabe längst
# (``domain/turn_frame`` + ``turn_type=clarification``). Für Rückfragen aus
# einem SKILL gab es nichts: der nächste Zug entschied neu.

def test_die_geholte_anleitung_wird_fuers_gespraech_gemerkt():
    entities: dict = {}
    merke_laufende_anleitung(entities, "5b29f470", zug=7)
    assert laufende_anleitung(entities, zug=7) == "5b29f470"


def test_die_anleitung_gilt_auch_im_naechsten_zug():
    """Der eigentliche Zweck: die Antwort auf die Rückfrage kommt EINEN Zug
    später — genau dort war die Anleitung bisher vergessen."""
    entities: dict = {}
    merke_laufende_anleitung(entities, "5b29f470", zug=7)
    assert laufende_anleitung(entities, zug=8) == "5b29f470"


def test_die_anleitung_verfaellt_nach_der_frist():
    """Ohne Frist bekäme jeder spätere Zug denselben Hinweis, auch bei ganz
    anderem Thema. Ruft das Modell die Anleitung erneut, frischt die Notiz
    sich selbst auf — die Frist trifft also nur, wer sie nicht mehr nutzt."""
    entities: dict = {}
    merke_laufende_anleitung(entities, "5b29f470", zug=7)
    assert laufende_anleitung(entities, zug=7 + LAUF_GUELTIG_ZUEGE) == "5b29f470"
    assert laufende_anleitung(entities, zug=8 + LAUF_GUELTIG_ZUEGE) == ""


def test_eine_neue_anleitung_ersetzt_die_alte():
    entities: dict = {}
    merke_laufende_anleitung(entities, "5b29f470", zug=7)
    merke_laufende_anleitung(entities, "c8936233", zug=8)
    assert laufende_anleitung(entities, zug=8) == "c8936233"


@pytest.mark.parametrize("node_id", ["", "   ", None, 42, {"a": 1}])
def test_ohne_brauchbare_id_wird_nichts_gemerkt(node_id):
    entities: dict = {}
    merke_laufende_anleitung(entities, node_id, zug=7)
    assert entities == {}


@pytest.mark.parametrize("notiz", [
    None, "kein dict", {}, {"_skill_lauf": None}, {"_skill_lauf": {}},
    {"_skill_lauf": {"node_id": "x"}},          # ohne Zug -> unbrauchbar
    {"_skill_lauf": {"node_id": "", "zug": 7}},
    {"_skill_lauf": {"node_id": "x", "zug": "sieben"}},
])
def test_eine_unbrauchbare_notiz_nennt_keine_anleitung(notiz):
    """Die Notiz reist als ``jsonb`` mit — dieselbe Härte wie bei den
    Bestandsfakten."""
    assert laufende_anleitung(notiz, zug=7) == ""


def test_der_grund_bleibt_unterscheidbar():
    """Ohne Fakten und ohne Notiz muss weiterhin ablesbar sein, WELCHE Quelle
    fehlte — der Grund ist der Nachweis im Debug-Block, kein Schmuck."""
    assert skill_vorrang(None, None).grund == "keine-fakten"
    assert skill_vorrang({"materials": 5}, None).grund == "keine-skills"


def test_titel_sind_fuer_den_vorrang_ohne_belang():
    """Der Vorrang hängt an der ZAHL, nicht an der Titelliste: die Liste ist
    auf ``MAX_SKILL_ENTRIES`` gedeckelt und kann leer sein, während die Zahl
    Anleitungen meldet. Wer hier auf die Titel prüfte, verlöre den Vorrang
    genau bei den größten Sammlungen."""
    assert skill_vorrang({"skills": 28, "skill_titles": []}).greift is True


# ── Der Hinweis für den Sucheinstieg ───────────────────────────────
# Live gemessen 2026-08-16 mit dem Payload, den das Widget wirklich schickt:
# der SEITEN-Weg trägt alles (``Bestandsfakten geladen: 36 Materialien, 28
# Skills`` → Katalog im Prompt → ``get_skill 5b29f470`` → Stundenentwurf in
# der Kachel). Der SUCHEINSTIEG trug nichts: ohne Seiten-Metadaten liefert
# ``page_context.render_for_prompt`` einen leeren Block, und die Notiz aus
# :func:`merke_skill_sammlung` las bis dahin ausschliesslich das Routing.
#
# Das Modell wusste dort also weder, DASS Anleitungen freigegeben sind, noch
# mit welcher ``collectionId`` es ``get_skill_registry`` aufrufen soll — die
# Stufe 2, die die Muster M08/M09/M10/M18/M19 ausdrücklich verlangen. Die Notiz
# trägt beides längst mit (``{anzahl, titel, node_id}``).

_NOTIZ = {BESTAND_KEY: {
    "anzahl": 28, "titel": "Geometrische Optik", "node_id": "f35c17d1"}}


def test_der_hinweis_nennt_zahl_titel_id_und_beide_stufen():
    """Ein Hinweis ohne Sammlungs-ID wäre eine Anweisung, die niemand ausführen
    kann — deshalb ist die ID der Kern der Zusage, nicht die Prosa."""
    text = anleitungs_hinweis(None, _NOTIZ)
    assert "28" in text
    assert "Geometrische Optik" in text
    assert "f35c17d1" in text
    assert "get_skill_registry" in text
    # ``get_skill(`` statt ``get_skill``: letzteres steckt schon in
    # ``get_skill_registry`` und ginge als Treffer durch, ohne dass die zweite
    # Stufe je im Text stünde.
    assert "get_skill(" in text


def test_auf_der_seite_schweigt_der_hinweis():
    """Steht der Nutzer AUF der Sammlung, rendert ``_bestands_zeilen`` bereits
    den vollen Katalog samt Vorrang-Regel. Ein zweiter, schwächerer Hinweis
    daneben wäre eine konkurrierende Stimme im selben Prompt."""
    assert anleitungs_hinweis({"skills": 28}, _NOTIZ) == ""


def test_ohne_notiz_kein_hinweis():
    assert anleitungs_hinweis(None, {}) == ""


def test_ohne_sammlungs_id_kein_hinweis():
    """Die Notiz kann eine Karte ohne ``node_id`` gemerkt haben. Dann fehlt der
    Stufe 2 ihr Argument — und ein Weg, dessen erster Schritt nicht geht, ist
    schlechter als kein Weg."""
    assert anleitungs_hinweis(None, {BESTAND_KEY: {"anzahl": 28, "titel": "X"}}) == ""


@pytest.mark.parametrize("entities", [None, "kein dict", {}, {BESTAND_KEY: None}])
def test_unbrauchbare_notiz_ergibt_keinen_hinweis(entities):
    """Die Notiz reist als ``jsonb`` mit — dieselbe Härte wie überall hier."""
    assert anleitungs_hinweis(None, entities) == ""


def test_die_fremden_felder_bleiben_einzeilig_und_gedeckelt():
    """Titel UND Sammlungs-ID stammen aus einem Suchtreffer, also aus fremder
    Feder. Gerahmt werden sie nicht — die Hausregel rahmt Langform-Prosa, nicht
    kurze Metadatenfelder (``domain/untrusted_text``). Einzeilig und gedeckelt
    müssen sie trotzdem sein, sonst brechen sie die Blockstruktur auf, in der
    sie stehen."""
    text = anleitungs_hinweis(None, {BESTAND_KEY: {
        "anzahl": 3, "titel": "Optik\n## Neue Überschrift\n" + "x" * 300,
        "node_id": "c1\n### Auch hier"}})
    zeilen = text.splitlines()
    # Geprüft wird die Struktur, nicht die Zeichenfolge: „## …" mitten in einem
    # Satz ist harmlos, „## …" am Zeilenanfang wäre eine zweite Überschrift im
    # Prompt — und die sähe aus wie unsere eigene.
    assert zeilen[0] == "## Freigegebene Skills"
    assert not any(z.lstrip().startswith("#") for z in zeilen[1:])
    assert "x" * (MAX_TITEL_ZEICHEN + 1) not in text


# ── Die harte Ladezeile im Chat (Nutzer-Vorgabe 2026-08-16) ────────────────
# Bis hierher kam die Aktivierungs-Ansage aus dem ``get_skill``-Ergebnis: der
# MCP-Server schreibt dort einen Abschnitt „## Aktivierung" mit der Bitte, eine
# Zeile WÖRTLICH auszugeben. Live gemessen hielt sich das Modell nicht daran —
# einmal „▸ stunde-planen aktiv — Verlaufsplan für 45 oder 90 Minuten", einmal
# „[ edu-sharing Skill ] Stunde planen - aktiv". Eine Ansage, die das Modell
# umformuliert, ist eine Behauptung; die hier ist ein Beleg, weil sie nur
# entsteht, wenn ``get_skill`` wirklich lief.

def test_die_ladezeile_nennt_den_titel_im_vorgegebenen_format():
    entities: dict = {}
    merke_laufende_anleitung(entities, "5b29f470", zug=3, titel="Stunde planen")
    assert mit_ladehinweis("Antwort.", entities, zug=3) == (
        "[ edu-sharing Skill ] Stunde planen - wird geladen\n\nAntwort.")


def test_nur_der_ladende_zug_sagt_es_an():
    """Die Notiz gilt zwei Züge (damit die Rückfrage fortgeführt wird), die
    ANSAGE nur einen: geladen wurde einmal, und zweimal „wird geladen" wäre
    schlicht unwahr."""
    entities: dict = {}
    merke_laufende_anleitung(entities, "5b29f470", zug=3, titel="Stunde planen")
    assert mit_ladehinweis("Antwort.", entities, zug=4) == "Antwort."


def test_ohne_titel_keine_zeile():
    """Ohne Titel bliebe „[ edu-sharing Skill ]  - wird geladen" — eine Zeile
    mit einer Lücke, wo die Auskunft stehen sollte. Der Aufruf steht ohnehin im
    Protokoll; die Chat-Zeile ist für Menschen."""
    entities: dict = {}
    merke_laufende_anleitung(entities, "5b29f470", zug=3)
    assert mit_ladehinweis("Antwort.", entities, zug=3) == "Antwort."


def test_an_eine_leere_antwort_kommt_keine_zeile():
    """Dieselbe Regel wie bei ``append_answer_notes``: an eine Antwort, die es
    nicht gibt, gehört auch kein Hinweis."""
    entities: dict = {}
    merke_laufende_anleitung(entities, "5b29f470", zug=3, titel="Stunde planen")
    assert mit_ladehinweis("", entities, zug=3) == ""


@pytest.mark.parametrize("entities", [None, "kein dict", {}, {LAUF_KEY: None}])
def test_ohne_brauchbare_notiz_bleibt_die_antwort_wie_sie_war(entities):
    assert mit_ladehinweis("Antwort.", entities, zug=3) == "Antwort."


def test_der_fremde_skill_titel_bleibt_einzeilig_und_gedeckelt():
    entities: dict = {}
    merke_laufende_anleitung(
        entities, "n1", zug=1, titel="Stunde\nplanen " + "x" * 300)
    zeilen = mit_ladehinweis("Antwort.", entities, zug=1).splitlines()
    assert len(zeilen[0]) < MAX_TITEL_ZEICHEN + 60
    assert zeilen[0].startswith("[ edu-sharing Skill ] Stunde planen")


# ── Mehrere Sammlungen, mehrere Kataloge (MCP-Entwickler 2026-08-16) ───────
# Gemessen gegen den echten Server: „Optik" (9e7ae956) und „Geometrische Optik"
# (f35c17d1) führen ZWEI eigene Registry-Dokumente —
#   registryTitle  'Skillkatalog Physik Optik'  vs  'Skill Registry'
#   registryNodeId  d84d54c4-…                  vs  247da7a9-…
# — deren Einträge sich heute vollständig decken. Das ist Überschneidung, nicht
# Vererbung: derselbe Skill darf in beiden stehen, und morgen kann einer davon
# einen führen, den der andere nicht hat.
#
# Nutzer-Entscheid: „dann wäre es richtig das beides kommt". Bis hierher merkte
# sich der Zug nur die REICHSTE Sammlung — bei Gleichstand entschied die
# Reihenfolge, und der zweite Katalog war für das Modell unerreichbar.

def test_alle_sammlungen_mit_skills_werden_gemerkt():
    entities: dict = {}
    merke_skill_sammlung(entities, [
        _Karte("9e7ae956", "Optik", 28),
        _Karte("c1", "Ein Video", 0),
        _Karte("f35c17d1", "Geometrische Optik", 28),
    ])
    assert [b["node_id"] for b in entities[BESTAND_KEY]] == ["9e7ae956", "f35c17d1"]


def test_die_reichste_steht_vorn():
    """Reihenfolge ist Rang: der Block nennt sie so, und bei einem Deckel
    fällt die schmalste zuerst weg."""
    entities: dict = {}
    merke_skill_sammlung(entities, [_Karte("a", "Klein", 2), _Karte("b", "Groß", 28)])
    assert [b["node_id"] for b in entities[BESTAND_KEY]] == ["b", "a"]


def test_die_liste_ist_gedeckelt():
    entities: dict = {}
    merke_skill_sammlung(
        entities, [_Karte(f"c{i}", f"S{i}", 30 - i) for i in range(10)])
    assert len(entities[BESTAND_KEY]) == MAX_BESTAND_SAMMLUNGEN


def test_der_vorrang_nimmt_die_groesste_zahl():
    entities = {BESTAND_KEY: [{"anzahl": 3}, {"anzahl": 28}]}
    entscheid = skill_vorrang(None, entities)
    assert (entscheid.greift, entscheid.anzahl) == (True, 28)


def test_der_hinweis_nennt_jede_sammlung_mit_ihrer_id():
    text = anleitungs_hinweis(None, {BESTAND_KEY: [
        {"anzahl": 28, "titel": "Optik", "node_id": "9e7ae956"},
        {"anzahl": 28, "titel": "Geometrische Optik", "node_id": "f35c17d1"},
    ]})
    assert "9e7ae956" in text
    assert "f35c17d1" in text
    assert "Optik" in text
    assert "Geometrische Optik" in text


def test_eintraege_ohne_id_fallen_aus_dem_hinweis():
    """Ohne Sammlungs-ID fehlt ``get_skill_registry`` ihr Argument — der
    Eintrag ist nicht begehbar und gehört nicht in den Weg."""
    text = anleitungs_hinweis(None, {BESTAND_KEY: [
        {"anzahl": 5, "titel": "Ohne ID"},
        {"anzahl": 28, "titel": "Optik", "node_id": "9e7ae956"},
    ]})
    assert "Ohne ID" not in text
    assert "9e7ae956" in text


def test_die_alte_einzelform_wird_weiter_gelesen():
    """Die Notiz reist als ``jsonb`` durch die Sitzung: ein Zug, der vor der
    Umstellung geschrieben wurde, trägt noch ein einzelnes Dict."""
    alt = {BESTAND_KEY: {"anzahl": 28, "titel": "Optik", "node_id": "9e7ae956"}}
    assert skill_vorrang(None, alt).anzahl == 28
    assert "9e7ae956" in anleitungs_hinweis(None, alt)
