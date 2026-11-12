"""Wächter für die Vorlage des Master-Skills (``docs/skills/vorgehen.md``).

Die Vorlage ist die Quelle des Textes, den die Redaktion in den Knoten des
Master-Skills überträgt (``services/master_skill``). Die Regeln hier stammen aus
dem Tor der Agent-Schleife (E-5, drei Läufe, 23 harte Fehler; Plan
``docs/plans/2026-09-28-agent-runde-2.md``): 13 davon löst der Text, nicht der
Code. Gepinnt sind die tragenden Sätze, nicht nur ihre Überschriften — eine
Überschrift ohne Regel darunter hält kein Modell auf. Die älteren Wächter
(Werkzeugnamen, Kernbegriff, Ansage-Regel) stehen in ``test_mcp_tool_defs.py``.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_VORLAGE = Path(__file__).parents[2] / "docs" / "skills" / "vorgehen.md"

#: Zitate MIT Anrede, die gewollt sind: Nutzersätze, der zitierte Satz aus dem
#: Gastgeber-Block und das „du" der Anleitung selbst. Ein neues Zitat mit
#: du/Sie gehört nur nach bewusster Prüfung hierher — Sätze des Bots an die
#: Person stehen unpersönlich.
_ERLAUBTE_ANREDE_ZITATE = frozenset({
    "du", "Hast du Übungen dazu?", "hast du was zu X?", "du kannst nichts ändern",
})
_ANREDE = re.compile(r"\b(?:du|dir|dich|dein\w*|Sie|Ihnen|Ihr\w*)\b")
_ZITAT = re.compile(r"„([^“\"]+)[“\"]")


#: So schreibt der md-editor des Repositoriums die Muster-Kennungen, wenn die
#: Redaktion die Vorlage in den Knoten überträgt (gemessen 2026-09-29):
#: „### Neues Material (M10)“ wird „### Neues Material **M10**“. Die Wächter
#: tragen beide Schreibweisen — sonst prüften sie nur die Vorlage und nicht den
#: Text, den der Chat bekommt (``scripts/check_master_skill.py``).
_KENNUNG_IN_KLAMMERN = re.compile(r"^(### .*) [(](M[0-9]{2})[)]$", re.MULTILINE)


def _wie_im_editor(text: str) -> str:
    return _KENNUNG_IN_KLAMMERN.sub(lambda m: f"{m.group(1)} **{m.group(2)}**", text)


#: Gemessen 2026-10-17 an der übertragenen Kurzfassung: der Editor setzt jede
#: Überschrift fett — „## **Entscheiden**“, auch geteilt um Code
#: („### **Internes Wissen zuerst (**`wissen_suchen`**)**“). Die Wächter suchen
#: Überschriften deshalb ohne Fettdruck.
_UEBERSCHRIFT = re.compile(r"^(#{1,6} )(.+)$", re.MULTILINE)


def _fett_wie_im_editor(text: str) -> str:
    return _UEBERSCHRIFT.sub(lambda m: f"{m.group(1)}**{m.group(2)}**", text)


def _ohne_fett_in_ueberschriften(text: str) -> str:
    return _UEBERSCHRIFT.sub(lambda m: m.group(1) + m.group(2).replace("**", ""), text)


#: Die Kurzfassung (2026-10-17: Stichpunkte statt Prosa, weniger Token) muss dieselben tragenden
#: Sätze halten — sonst kehren die gemessenen Fehler zurück, sobald sie im Knoten steht.
_KURZFASSUNG = _VORLAGE.with_name("vorgehen-knapp.md")
_FASSUNGEN = {"": lambda t: t, "-editor": _wie_im_editor, "-fett": _fett_wie_im_editor}


@pytest.fixture(scope="module", params=[
    f"{datei}{art}" for datei in ("vorlage", "knapp") for art in _FASSUNGEN])
def text(request: pytest.FixtureRequest) -> str:
    datei, _, art = request.param.partition("-")
    vorlage = (_KURZFASSUNG if datei == "knapp" else _VORLAGE).read_text(encoding="utf-8")
    return _FASSUNGEN[f"-{art}" if art else ""](vorlage)


def test_die_editor_fassung_schreibt_die_kennungen_um() -> None:
    """Ohne Umschrift prüfte der Parameter ``editor`` nur die Vorlage ein zweites Mal."""
    umgeschrieben = _wie_im_editor(_VORLAGE.read_text(encoding="utf-8"))
    assert "### Neues Material **M10**" in umgeschrieben
    assert "(M10)" not in umgeschrieben


def test_die_fett_fassung_setzt_jede_ueberschrift_fett() -> None:
    """Dasselbe für den Parameter ``fett`` — und der Rückweg trifft wieder die Vorlage."""
    vorlage = _KURZFASSUNG.read_text(encoding="utf-8")
    fett = _fett_wie_im_editor(vorlage)
    assert "\n## **Entscheiden**\n" in fett
    assert "\n## Entscheiden\n" not in fett
    assert _ohne_fett_in_ueberschriften(fett) == vorlage


def _flach(text: str) -> str:
    """Umbruch und Einzug zählen nicht: ein neu umbrochener Absatz sagt dasselbe
    — und ein verbotener Satz entkommt dem Wächter nicht über einen Zeilenwechsel."""
    return " ".join(text.split())


def _abschnitt(text: str, titel: str) -> str:
    """Der Rumpf unter ``## titel`` bis zur nächsten h2-Überschrift, flach."""
    kopf = f"\n## {titel}\n"
    text = _ohne_fett_in_ueberschriften(text)
    assert kopf in text, titel
    return _flach(text.split(kopf, 1)[1].split("\n## ", 1)[0])


def _unterabschnitt(text: str, kopfzeile: str) -> str:
    """Der Rumpf unter der h3-Zeile, die ``kopfzeile`` trägt, bis zur nächsten
    Überschrift, flach. Die Muster-Kennungen (M09 …) in den Überschriften sind
    der Querverweis zur Muster-Maschine — beide Maschinen bleiben (Z2). Gesucht
    wird die Kennung ohne Klammern: die Vorlage schreibt „(M09)“, der md-editor
    „**M09**“."""
    treffer = re.search(rf"^### [^\n]*{re.escape(kopfzeile)}[^\n]*\n(.*?)(?=^##)",
                        _ohne_fett_in_ueberschriften(text), re.MULTILINE | re.DOTALL)
    assert treffer, kopfzeile
    return _flach(treffer.group(1))


def test_anrede_steht_direkt_nach_der_ranghoechsten_regel(text: str) -> None:
    """6 der 23 Fehler: der Agent duzte Lehrkräfte, die ihn siezten. Die
    Zuordnung Zielgruppe → Anrede kommt aus den Personas des Studios (der Kopf
    listet sie). Es fehlte die zweite Hälfte der alten Muster (M03, M13, M14):
    der Hinweis im Anleitungstext, dass die Vorgabe überall gilt und zitierte
    Sätze sie nicht setzen — und dass der Begleitsatz die Person im Chat
    anspricht, auch wenn das Blatt die Kinder duzt (GV-LEH-1#3)."""
    text = _ohne_fett_in_ueberschriften(text)
    nach_der_regel = text.split("\n## Zuerst handeln, dann reden\n", 1)[1]
    assert re.search(r"^## (.+)$", nach_der_regel, re.MULTILINE).group(1) == (
        "Anrede und Zielgruppen")
    anrede = _abschnitt(text, "Anrede und Zielgruppen")
    assert "Wer dich siezt, den siezt du" in anrede
    assert "geben dir nicht die Anrede vor" in anrede
    assert "Dein Begleitsatz spricht die Person im Chat an" in anrede


def test_saetze_an_die_person_stehen_ohne_anrede(text: str) -> None:
    """Die Vorfassung zitierte Sätze an die Person in Du-Form — als Beispiel
    dafür, was man NICHT schreibt. Übernommen wird die Form, nicht das Verbot.
    Geprüft wird jedes Zitat mit Anrede gegen die Erlaubnisliste."""
    flach = _flach(text)
    for satz in ("suche dir", "sag Bescheid", "möchtest du", "dein Material"):
        assert satz not in flach, satz
    mit_anrede = {z.strip() for z in _ZITAT.findall(flach) if _ANREDE.search(z)}
    assert mit_anrede <= _ERLAUBTE_ANREDE_ZITATE, mit_anrede - _ERLAUBTE_ANREDE_ZITATE


def test_jede_zielgruppe_hat_eine_arbeitsweise(text: str) -> None:
    """Der Agent hat keinen Klassifikator. Wie er mit einer Zielgruppe arbeitet,
    stand bisher nur in den Personas der Muster-Maschine — etwa „erst verstehen
    helfen, dann üben“ bei Lernenden (GV-LER-1#1: kein Karten-Abwurf)."""
    zielgruppen = _unterabschnitt(text, "Zielgruppen")
    for gruppe in ("Lernende", "Lehrkräfte", "Eltern", "Entscheider",
                   "Redaktion und Medien", "Unbekannt"):
        assert f"**{gruppe}**" in zielgruppen, gruppe
    assert "Erst verstehen helfen" in zielgruppen
    assert "keine Trefferliste als erste Antwort" in zielgruppen


def test_vorhandenes_vor_neuem_und_lernpfade_werden_zusammengestellt(text: str) -> None:
    """GV-LER-1#3 „hast du Übungen für mich?“ → selbst erstelltes Blatt (2×);
    GV-LEH-1#2 „fertigen Lernpfad?“ → „keinen gefunden“ (3×). Die Faustregel
    „hast du → suchen“ ließ keinen Weg vom Suchen zum Zusammenstellen."""
    entscheiden = _abschnitt(text, "Entscheiden")
    assert "Vorhandenes geht vor Neuem" in entscheiden
    assert "ist eine Suche" in entscheiden
    assert "Zusammenstellen ist kein Erzeugen" in entscheiden
    assert "aus den Treffern zusammen und lieferst ihn als Dokument" in entscheiden


def test_machen_ist_ein_auftrag_zum_erzeugen(text: str) -> None:
    """GV-LER-2#1 fragt „kannst du mir ein kleines quiz … machen?“ — steht
    „mach“ nicht bei den Erzeugen-Verben, macht „ohne Erzeugen-Verb ist es
    eine Suche“ aus dem Auftrag eine Suche (Review 2026-09-28)."""
    verben = re.search(r"([a-z /]+) → erzeugen", _abschnitt(text, "Entscheiden"))
    assert verben and "mach" in verben.group(1).split(" / ")


def test_verengen_ist_suche_und_kritik_ist_rueckmeldung(text: str) -> None:
    """„Bezug auf zuletzt Gezeigtes“ darf „eher für die Mittelstufe“
    (GV-AND-1#3: neue, verengte Treffer) und „das passt alles nicht“
    (GV-AND-2#2: nachfragen, was fehlt) nicht zum Überarbeiten ziehen."""
    reihenfolge = _unterabschnitt(text, "Reihenfolge der Prüfung")
    assert "ist eine neue Suche" in reihenfolge
    assert "**Rückmeldung**" in reihenfolge


def test_rueckfrage_erst_nach_der_suche(text: str) -> None:
    """GV-AND-2#1: „Pflichtangabe fehlt → genau eine Frage“ gewann gegen den
    Kopf („erst suchen“) — bei Fach, Stufe und Anlass ohne eigenes Thema."""
    assert "suchst du zuerst" in _abschnitt(text, "Nachfragen")


def test_ein_platzhalter_fragt_nach_dem_thema_auch_auf_einer_sammlung(text: str) -> None:
    """Live 2026-10-17 auf der Sammlung Optik: „Ich suche Inhalte zu einem Thema.“
    → der Agent suchte nach „Optik“ und fragte erst danach. Bis 2026-10-04 fragte
    er zuerst. Drei Stellen zogen zur Suche: „Suchen → Finden“ steht vor „kein
    Thema → Nachfragen“, „reicht das Bekannte … suchst du zuerst“ nahm die Seite
    als das Bekannte, und die Seitenregel liest „das Thema“ als Seiteninhalt."""
    reihenfolge = _unterabschnitt(text, "Reihenfolge der Prüfung")
    finden = re.search(r"→ \*\*Finden\*\*[;,][^\n]*?→ \*\*Nachfragen\*\*", reihenfolge)
    assert finden and "Platzhalter" in finden.group(0)
    nachfragen = _abschnitt(text, "Nachfragen")
    assert "auch auf einer Sammlung oder Themenseite" in nachfragen
    assert "meint nicht die Seite" in nachfragen


def test_filter_sparsam_setzen(text: str) -> None:
    """Nutzer-Vorgabe 2026-10-17: Fach, Bildungsstufe und Inhaltstyp tragen; andere
    Filter nur, wenn verlangt oder nötig. Seltene Werte (Eltern, bestimmte Lizenzen)
    sind kaum getaggt und leeren die Trefferliste — die Zielgruppe hängt meist nur als
    Lernende oder Lehrende am Inhalt."""
    finden = _abschnitt(text, "Finden")
    assert "Filter sparsam" in finden
    assert "Fach, Bildungsstufe und Inhaltstyp" in finden
    assert "nur auf ausdrücklichen Wunsch" in finden
    assert "Zielgruppe" in finden
    assert "nicht hineindeuten" in finden


def test_die_rettung_fuehrt_die_schritte_selbst_aus(text: str) -> None:
    """Probe 2026-10-17 (V14, Xylophonbau): nach zwei leeren Suchen fragte der Agent,
    statt selbst einen Oberbegriff zu versuchen oder Filter zu lockern. Eine verlangte
    Lizenz fällt nie stillschweigend (Probe V16, dritte Runde: die Folgesuche ließ „OER“
    weg, die Karte zeigte womöglich anderes Material)."""
    m12 = _unterabschnitt(text, "M12")
    assert "Führe die Schritte selbst aus" in m12
    assert "zuerst Inhaltstyp, dann Stufe" in m12
    assert "verlangte Lizenz nur mit Hinweis" in m12


def test_kernbegriff_auch_in_der_sammlung(text: str) -> None:
    """Probe 2026-10-17 (V5): ``get_collection_contents`` bekam „interaktive Übungen
    Kurzgeschichten Englisch Sekundarstufe II“ als Suchbegriff."""
    assert "auch innerhalb einer Sammlung" in _abschnitt(text, "Finden")


def test_anrede_bleibt_im_gespraech(text: str) -> None:
    """Probe 2026-10-17 (V7): bei unbekannter Zielgruppe gibt der Kopf „möglichst ohne
    direkte Anrede“ vor — der Agent schrieb erst „suchst du“, im Folgezug „wenn Sie“."""
    anrede = _abschnitt(text, "Anrede und Zielgruppen")
    assert "ohne direkte Anrede" in anrede
    assert "bleibt im ganzen Gespräch" in anrede


def test_quiz_loesungen_mit_begruendung(text: str) -> None:
    """Probe 2026-10-17 (V12): „Quiz mit Begründung“ in Klammern kam nicht an — die
    Lösungen standen als „1. A, 2. B …“ da."""
    assert "ein Satz Begründung" in _unterabschnitt(text, "M10")
    # Vierte Runde: ohne Formvorlage fehlte die Begründung in 1 von 2 Läufen („1. A) Lava“).
    assert "„1. B – weil" in _unterabschnitt(text, "M10")


def test_quiz_verteilt_die_richtige_antwort(text: str) -> None:
    """Probe 2026-10-17 (V12, zweite Runde): fünf Fragen, fünfmal „A“ richtig — ein Quiz,
    das sich ohne Wissen lösen lässt."""
    assert "über die Antwortpositionen verteilen" in _unterabschnitt(text, "M10")


def test_stufe_nur_aus_einer_angabe(text: str) -> None:
    """Probe 2026-10-17 (V18): „Bruchrechnen für Eltern“ → ``Sekundarstufe I``, ohne dass
    eine Stufe genannt war. Bruchrechnung gibt es in der Grundschule und in der Sek I —
    aus dem Thema erschlossen, schneidet die Stufe die Hälfte weg."""
    assert "nie aus dem Thema erschließen" in _abschnitt(text, "Finden")


def test_anrede_nicht_aus_anleitungen(text: str) -> None:
    """Probe 2026-10-17 (V9): auf der Sammlung Optik duzte der Agent in 4 von 5 Läufen —
    die geladene Sammlungs-Anleitung spricht das Modell mit „du“ an (3 du-, 0 Sie-Formen)."""
    assert "Anleitungen, Kompendium und Seitentext" in _abschnitt(text, "Anrede und Zielgruppen")


def test_dokumente_gehen_ueber_das_werkzeug(text: str) -> None:
    """Im Agent-Zug entsteht eine Box nur über ``ui_inhaltsrahmen``. Der Rückfall
    „Text ab der ersten Überschrift“ greift in ``turn_persist`` nur für die
    Muster M09–M11, und ein Agent-Zug heißt ``AGENT``. Die Vorfassung
    beschrieb den Rückfall: so geschriebenes Material blieb in der Blase."""
    assert "`ui_inhaltsrahmen`" in _abschnitt(text, "Oberfläche ansteuern")
    for kennung in ("M09", "M10", "M11", "M17"):
        assert "`ui_inhaltsrahmen`" in _unterabschnitt(text, kennung), kennung
    flach = _flach(text)
    for mechanik in ("Überschrift", "als Markdown direkt im Chat"):
        assert mechanik not in flach, mechanik



def test_die_aenderungs_vorschau_zeigt_der_chat_selbst(text: str) -> None:
    """Paket 2 (Runde-2-Plan, N-3): den Kasten mit der Vorschau einer Änderung
    zeigt der Chat selbst, seit 2026-10-01 auch im Agent-Zug — so sagt es die
    Muster-Datei M18 schon. Die Vorfassung ließ das Modell die Vorschau
    „wörtlich als gerahmten Kasten“ vorlegen; über `ui_inhaltsrahmen` stünden
    dann zwei Kästen da."""
    m18 = _unterabschnitt(text, "M18")
    assert "zeigt der Chat von selbst" in m18
    assert "gerahmten Kasten" not in m18


def test_platzhalter_ueberstehen_den_editor(text: str) -> None:
    """Gemessen 2026-10-17: der md-editor löscht ``<N>`` und ``<Thema>`` als
    HTML-Tags — im Knoten stand „Material für Klasse“. In Backticks bleiben sie
    stehen; außerhalb schreibt die Vorlage Platzhalter ohne spitze Klammern."""
    ohne_code = re.sub(r"`[^`\n]*`", "", text)
    assert not re.findall(r"<[^<>\n]+>", ohne_code)

# ── Seit dem Review 2026-09-29 hier statt in ``test_mcp_tool_defs.py`` ─────
# Sie lasen die Vorlage selbst ein und liefen deshalb weder gegen die
# Editor-Fassung noch im Prüfskript (``scripts/check_master_skill.py``) mit —
# darunter die Ansage-Regel gegen leere Blasen.

def test_vorgehen_md_nennt_nur_existierende_werkzeuge(text: str) -> None:
    """Wächter für den Master-Skill (docs/skills/vorgehen.md): jeder als
    Backtick-Code genannte Name mit Unterstrich muss ein Werkzeug des Katalogs
    oder ein virtuelles Werkzeug des Chat-Zuges sein. Ein Tippfehler dort ist
    ein Phantom-Werkzeug im wichtigsten Prompt-Dokument — das Modell ruft es,
    bekommt einen Fehler und rät weiter (gemessen 2026-08-16 bei den
    erfundenen get_skill-IDs)."""
    from boerdi.domain.antwort_werkzeug import RESPOND_TO_USER
    from boerdi.domain.inline_documents import INHALTSRAHMEN
    from boerdi.services.mcp.tool_defs import TOOL_DEFINITIONS
    from boerdi.services.mcp.tool_defs_curation import CURATION_TOOL_DEFINITIONS
    from boerdi.ui_module.werkzeuge import modul_werkzeug_titel

    # Auch die Aufrufform zählt: `get_skill_registry(nodeId)` nennt ein Werkzeug.
    genannt = {t for t in re.findall(r"`([a-z][a-z0-9_]+)(?=[`(])", text) if "_" in t}
    katalog = {d["function"]["name"]
               for d in (*TOOL_DEFINITIONS, *CURATION_TOOL_DEFINITIONS)}
    # ``ui_inhaltsrahmen``: im Agent-Zug der einzige Weg zur Dokument-Box
    # (Agent-Runde 2, 2026-09-28) — der Chat-Zug legt es immer dazu. Dazu das
    # Antwort-Werkzeug samt seinem Feld ``quick_replies`` und die Modul-Werkzeuge
    # aus den Manifesten (``ui_entscheidung``, ``ui_themenbaum``; Paket U1).
    virtuell = {"wissen_suchen", "liefere_ergebnis", INHALTSRAHMEN, RESPOND_TO_USER,
                "quick_replies", *modul_werkzeug_titel()}
    # ``search_skill`` nennt der Skill nur, um es zu VERNEINEN („existiert
    # nicht") — die Nennung ist gewollt, das Werkzeug bleibt draußen.
    unbekannt = genannt - katalog - virtuell - {"search_skill"}
    assert not unbekannt, unbekannt


def test_vorgehen_md_traegt_die_kernbegriff_suchregel(text: str) -> None:
    """Y1 (2026-08-20, Live-Befund Repo-Einbettung): das Modell reichte den
    ganzen Nutzersatz als ``query`` durch ("ich suche nur arbeitsblätter zu
    optik") — Ranking verwässert, und der Satz landet in den Such-Links der
    Oberfläche. Die Regel „query = Kernbegriff, Materialart/Fach/Stufe in die
    Filter" muss im Finden-Teil des Master-Skills stehen und dort bleiben."""
    finden = _ohne_fett_in_ueberschriften(text).split("## Finden", 1)[1]
    assert "Kernbegriff" in finden
    assert 'query: "Optik"' in finden
    assert 'learningResourceType: "Arbeitsblatt"' in finden
    # Z1: alle drei Filter-Dimensionen beim Namen — das Modell soll wissen,
    # WOHIN Fach und Stufe gehoeren, nicht nur, dass sie nicht in die query.
    assert "discipline" in finden
    assert "educationalContext" in finden


def test_vorgehen_md_traegt_die_ansage_regel(text: str) -> None:
    """Ansage-Echo (2026-08-21, live 4 von 12 Zuegen): der MCP-Server bittet im
    Kopf jedes Skill-Dokuments, die Aktivierungszeile woertlich auszugeben —
    das Modell antwortete in jedem dritten Zug NUR mit dieser Zeile, und nach
    dem Abzug der Modell-Kopie (``mit_master_ansage``) blieb eine leere Blase.
    Behoben redaktionell statt im Code (Nutzer-Entscheid 2026-08-21): die
    Gegen-Regel im Master-Skill uebersteuert die Bitte — gemessen danach 0 von
    15. Sie muss in der ranghoechsten Sektion stehen und dort bleiben; die
    sichtbare Ansage setzt der Server (``skill_ansagen``) und haengt nicht an
    dieser Regel."""
    handeln = _ohne_fett_in_ueberschriften(text).split(
        "## Zuerst handeln, dann reden", 1)[1].split("\n## ", 1)[0]
    assert "Aktivierungszeilen tippst du nie selbst" in handeln
    assert "gilt diese Bitte hier nicht" in handeln


# ── UI-Module (Golden-Lauf 2026-11-03): nur die Kurzfassung, die live steht ──
# Der Agent wählte das Auswahlfeld nie (GV-UI-3/4/5: „Zuerst handeln“ ohne
# Regel für eine Rückfrage nach den Ergebnissen) und tippte ein Unterthema als
# Liste ab, statt den Themenbaum mit der Sammlung zu zeigen (GV-UI-1).

@pytest.fixture(scope="module", params=list(_FASSUNGEN))
def knapp(request: pytest.FixtureRequest) -> str:
    return _FASSUNGEN[request.param](_KURZFASSUNG.read_text(encoding="utf-8"))


def test_knapp_auswahlfeld_nach_den_ergebnissen(knapp: str) -> None:
    oberflaeche = _abschnitt(knapp, "Oberfläche ansteuern")
    assert "`ui_entscheidung`" in oberflaeche
    assert "Ergebnisse dieses Zuges stehen davor" in oberflaeche
    assert "keine Schnellantworten dazu" in oberflaeche
    assert "nie als Bestätigung eines Schreibvorgangs" in oberflaeche
    assert "Rückfrage im Auswahlfeld ist kein Vertagen" in _abschnitt(
        knapp, "Zuerst handeln, dann reden")
    assert "als Auswahlfeld" in _unterabschnitt(knapp, "M03")
    assert "als Auswahlfeld" in _unterabschnitt(knapp, "M06")


def test_knapp_themenbaum_mit_der_sammlung_eines_unterthemas(knapp: str) -> None:
    tiefer = _unterabschnitt(knapp, "M08")
    assert "`ui_themenbaum`" in tiefer
    assert "erst mit `search_wlo_collections` finden" in tiefer
    assert "`browse_collection_tree` nur, wenn du die Unterthemen selbst auswertest" in tiefer
    assert "keine Themenliste" in _abschnitt(knapp, "Oberfläche ansteuern")


def test_knapp_schnellantworten_liefert_das_antwort_werkzeug(knapp: str) -> None:
    oberflaeche = _abschnitt(knapp, "Oberfläche ansteuern")
    assert "`respond_to_user`" in oberflaeche
    assert "`quick_replies`" in oberflaeche


def test_knapp_lehrkraefte_werden_gesiezt(knapp: str) -> None:
    assert "(Klasse, Unterricht, Lehrplan): Sie;" in _abschnitt(
        knapp, "Anrede und Zielgruppen")


# ── Review U1 gesamt (2026-11-03): Auswahlfeld ohne Widerspruch zu M03 ──


def test_knapp_klaerungsfragen_aus_m03_kommen_ohne_suche(knapp: str) -> None:
    """Befund 13: „Ergebnisse dieses Zuges stehen davor“ widersprach M03 (Platzhalter: eine
    Frage VOR jeder Suche; Erstellauftrag ohne Typ) und „Nicht für offene Fragen“ der Themenfrage
    mit Freitext."""
    oberflaeche = _abschnitt(knapp, "Oberfläche ansteuern")
    assert "stehen davor, wenn das Vorgehen Werkzeuge braucht" in oberflaeche
    assert "die Klärungsfragen aus M03 (nur Platzhalter, fehlender Typ) kommen ohne Suche" in (
        oberflaeche)
    assert ("Die Themenfrage aus M03 mit drei konkreten Vorschlägen und Freitext zählt nicht als "
            "offene Frage") in oberflaeche
    assert "erst die Ergebnisse dieses Zuges (falls das Vorgehen welche braucht)" in _abschnitt(
        knapp, "Zuerst handeln, dann reden")
    assert "vor jeder Suche" in _unterabschnitt(knapp, "M03")


def test_knapp_begleittext_zum_auswahlfeld_ueber_das_antwort_werkzeug(knapp: str) -> None:
    """Befund 14 (Golden-Lauf 2026-11-03): neben dem Auswahlfeld stand nur „Bitte wähle unten
    aus.“ — geduzt gegenüber einer Lehrkraft, ohne Einordnung der Ergebnisse."""
    oberflaeche = _abschnitt(knapp, "Oberfläche ansteuern")
    assert ("Den Begleittext (Ergebnisse, Einordnung, in der Anrede der Person) wie sonst über "
            "`respond_to_user` (`text`, ohne `quick_replies`) in derselben Runde") in oberflaeche


def test_knapp_lernende_auswahlfeld_oder_schnellantworten(knapp: str) -> None:
    """Befund 15: nach einer Erklärung war offen, wann Auswahlfeld und wann Schnellantworten."""
    assert ("Ändert eine offene Angabe den nächsten Schritt (Klasse, Vorwissen) → Auswahlfeld, "
            "sonst Schnellantworten mit Übungsangebot") in _unterabschnitt(knapp, "M04")


# ── Paket U2 (2026-11-04): Bestand oder Entwurf — die beiden Fälle sauber trennen ──


def test_knapp_bestand_oder_entwurf_mit_der_mehrdeutigkeits_regel(knapp: str) -> None:
    """Plan 2026-11-04 T-14: „Themenbaum für <Fachportal>“ ohne Hinweis → Bestand und die
    Schnellantwort, ausdrücklich Neues → Entwurf. Die Werkzeugbeschreibungen allein reichten bei
    U1 nicht (Golden-Lauf 2026-11-03)."""
    tiefer = _unterabschnitt(knapp, "M08")
    assert "`ui_themenbaum` zeigt nur, was es in WLO gibt" in tiefer
    assert "„Sammlung aufbauen zu Thema X“" in tiefer and "→ `ui_strukturentwurf`" in tiefer
    assert "ein Thema ohne WLO-Sammlung" in tiefer
    assert "die Schnellantwort „Neue Gliederung dazu entwerfen“" in tiefer


def test_knapp_entwurf_endet_den_zug_und_arbeitet_mit_dem_stand_der_person(knapp: str) -> None:
    oberflaeche = _abschnitt(knapp, "Oberfläche ansteuern")
    assert "`ui_strukturentwurf` entwirft eine neue Gliederung" in oberflaeche
    assert "Er beendet den Zug wie das Auswahlfeld" in oberflaeche
    # Review U2, Befund 7: die Quittung liest kein Modell mehr — der Satz kommt in derselben Runde.
    assert "den kurzen Begleitsatz in derselben Runde über `respond_to_user`" in oberflaeche
    # Drittes Review U2, Befund 2: der letzte Entwurf gilt auch Züge später.
    assert "Später steht der letzte Stand als `[DEIN LETZTER ENTWURF]` da" in oberflaeche
    assert "unverändert wieder zum Bearbeiten mit `vorlage` und erneut_zeigen" in oberflaeche
    assert "(`[ENTWURF DER PERSON]`), damit weiterarbeiten, nicht neu entwerfen" in oberflaeche
    assert "`vorlage` und `vertiefen`" in oberflaeche and "Nie für den Bestand." in oberflaeche
    assert "Fehlt der Entwurf" in oberflaeche
    assert "neue Gliederung → Entwurf" in _abschnitt(knapp, "Immer gültig")


# ── Paket U3-5 (2026-11-08): Ordner/Lehrplan → ui_upload, Abgleich → ui_strukturabgleich ──


def test_knapp_ordner_oder_lehrplan_und_abgleich(knapp: str) -> None:
    """Plan 2026-11-04 §9 U3-5 und Plan 2026-11-08 E-9: die Beschreibung allein reichte bei
    ui_entscheidung nicht (Golden-Lauf 2026-11-03) — eine Regel im Master-Skill."""
    oberflaeche = _abschnitt(knapp, "Oberfläche ansteuern")
    assert "→ `ui_upload` mit `zweck: sammlungsstruktur`" in oberflaeche
    assert "nur per Klick im Modul — nie selbst anstoßen" in oberflaeche
    # 2026-11-10: Lesen und Entwerfen gehen anonym, nur das Übertragen braucht die Anmeldung
    assert "ohne Anmeldung sagen, dass erst das Übertragen eine" in oberflaeche
    assert "→ `ui_strukturabgleich` mit der `nodeId` der Sammlung" in oberflaeche
    assert "`abdeckung: true`, wenn nach fehlendem Material" in oberflaeche
    assert "Ohne Entwurf erst `ui_strukturentwurf`." in oberflaeche
    assert "Fehlt der Abgleich: Lücken mit M19 belegen" in oberflaeche
    # Gesamt-Review, Befunde 3 und 4: M08 und M19 verweisen auf die Module
    assert "zuerst `ui_upload`" in _unterabschnitt(knapp, "M08")
    assert "zeigt es `ui_strukturabgleich`" in _unterabschnitt(knapp, "M19")



def test_knapp_dokument_weg_und_ablaeufe(knapp: str) -> None:
    """2026-11-10: Lehrplan-PDF → Lesen → Entwurf aus dem Dokument (anonym, Nutzer-Entscheid) und
    die Abläufe der Redaktion als Werkzeuge ``ablauf-…`` (Plan 2026-11-09, AS-5)."""
    oberflaeche = _abschnitt(knapp, "Oberfläche ansteuern")
    assert "`aus_dokument: true`" in oberflaeche
    assert "Lesen und Entwerfen gehen ohne Anmeldung" in oberflaeche
    assert "das Feld zeigen, nicht nur" in oberflaeche
    assert "Werkzeuge `ablauf-…`" in oberflaeche
    assert "höchstens einen je Zug" in oberflaeche
    assert "`[ABLAUFSCHRITT — …]`" in oberflaeche


def test_knapp_ablauf_geht_modul_und_platzhalter_frage_vor(knapp: str) -> None:
    """TW-3 und Rückmeldung 11.11.: „ich will einen Themenbaum zu einem Thema erstellen“ → die KI
    fragte nach M03 per Auswahlfeld nach dem Thema, statt den Ablauf zu starten. Ein passender
    Ablauf geht Modulen und der Platzhalter-Frage vor — er fragt selbst."""
    oberflaeche = _abschnitt(knapp, "Oberfläche ansteuern")
    assert "geht er einzelnen Modulen und Werkzeugen vor" in oberflaeche
    assert "**Ablauf zuerst:**" in _abschnitt(knapp, "Nachfragen")
    assert "er geht vor und fragt selbst" in _unterabschnitt(knapp, "Reihenfolge der Prüfung")
    # TW-6 (Durchtest 12.11.): auch vor dem Upload-Feld — die KI öffnete es sonst bei „aus meinem
    # Lehrplan“, „aus meinen Ordnern“ und „aus meinen Dateien“ direkt
    finden = _abschnitt(knapp, "Finden")
    assert "ansteuern“) — außer ein passender Ablauf" in finden
    assert "`zweck: sammlungsstruktur` — außer ein passender Ablauf" in oberflaeche
    assert "nie nur „lade" in oberflaeche                 # keine Sackgasse ohne Feld


def test_formeln_stehen_als_latex_in_den_begrenzern(text: str) -> None:
    r"""Plan 2026-11-10, TB-E4 (Querschnitts-Review Gruppe E, Befund 5): das Widget zeichnet
    LaTeX in ``\( … \)`` und ``\[ … \]`` als Formel — die Regel steht in jeder Fassung."""
    assert "Formeln als LaTeX" in text
    assert r"\(" in text and r"\[" in text

