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


@pytest.fixture(scope="module", params=["vorlage", "editor"])
def text(request: pytest.FixtureRequest) -> str:
    vorlage = _VORLAGE.read_text(encoding="utf-8")
    return vorlage if request.param == "vorlage" else _wie_im_editor(vorlage)


def test_die_editor_fassung_schreibt_die_kennungen_um() -> None:
    """Ohne Umschrift prüfte der Parameter ``editor`` nur die Vorlage ein zweites Mal."""
    umgeschrieben = _wie_im_editor(_VORLAGE.read_text(encoding="utf-8"))
    assert "### Neues Material **M10**" in umgeschrieben
    assert "(M10)" not in umgeschrieben


def _flach(text: str) -> str:
    """Umbruch und Einzug zählen nicht: ein neu umbrochener Absatz sagt dasselbe
    — und ein verbotener Satz entkommt dem Wächter nicht über einen Zeilenwechsel."""
    return " ".join(text.split())


def _abschnitt(text: str, titel: str) -> str:
    """Der Rumpf unter ``## titel`` bis zur nächsten h2-Überschrift, flach."""
    kopf = f"\n## {titel}\n"
    assert kopf in text, titel
    return _flach(text.split(kopf, 1)[1].split("\n## ", 1)[0])


def _unterabschnitt(text: str, kopfzeile: str) -> str:
    """Der Rumpf unter der h3-Zeile, die ``kopfzeile`` trägt, bis zur nächsten
    Überschrift, flach. Die Muster-Kennungen (M09 …) in den Überschriften sind
    der Querverweis zur Muster-Maschine — beide Maschinen bleiben (Z2). Gesucht
    wird die Kennung ohne Klammern: die Vorlage schreibt „(M09)“, der md-editor
    „**M09**“."""
    treffer = re.search(rf"^### [^\n]*{re.escape(kopfzeile)}[^\n]*\n(.*?)(?=^##)", text,
                        re.MULTILINE | re.DOTALL)
    assert treffer, kopfzeile
    return _flach(treffer.group(1))


def test_anrede_steht_direkt_nach_der_ranghoechsten_regel(text: str) -> None:
    """6 der 23 Fehler: der Agent duzte Lehrkräfte, die ihn siezten. Die
    Zuordnung Zielgruppe → Anrede kommt aus den Personas des Studios (der Kopf
    listet sie). Es fehlte die zweite Hälfte der alten Muster (M03, M13, M14):
    der Hinweis im Anleitungstext, dass die Vorgabe überall gilt und zitierte
    Sätze sie nicht setzen — und dass der Begleitsatz die Person im Chat
    anspricht, auch wenn das Blatt die Kinder duzt (GV-LEH-1#3)."""
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


def test_dokumente_gehen_ueber_das_werkzeug(text: str) -> None:
    """Im Agent-Zug entsteht eine Box nur über ``zeige_dokument``. Der Rückfall
    „Text ab der ersten Überschrift“ greift in ``turn_persist`` nur für die
    Muster M09–M11, und ein Agent-Zug heißt ``AGENT``. Die Vorfassung
    beschrieb den Rückfall: so geschriebenes Material blieb in der Blase."""
    assert "`zeige_dokument`" in _abschnitt(text, "Oberfläche ansteuern")
    for kennung in ("M09", "M10", "M11", "M17"):
        assert "`zeige_dokument`" in _unterabschnitt(text, kennung), kennung
    flach = _flach(text)
    for mechanik in ("Überschrift", "als Markdown direkt im Chat"):
        assert mechanik not in flach, mechanik



def test_die_aenderungs_vorschau_zeigt_der_chat_selbst(text: str) -> None:
    """Paket 2 (Runde-2-Plan, N-3): den Kasten mit der Vorschau einer Änderung
    zeigt der Chat selbst, seit 2026-10-01 auch im Agent-Zug — so sagt es die
    Muster-Datei M18 schon. Die Vorfassung ließ das Modell die Vorschau
    „wörtlich als gerahmten Kasten“ vorlegen; über `zeige_dokument` stünden
    dann zwei Kästen da."""
    m18 = _unterabschnitt(text, "M18")
    assert "zeigt der Chat von selbst" in m18
    assert "gerahmten Kasten" not in m18

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
    from boerdi.domain.inline_documents import ZEIGE_DOKUMENT
    from boerdi.services.mcp.tool_defs import TOOL_DEFINITIONS
    from boerdi.services.mcp.tool_defs_curation import CURATION_TOOL_DEFINITIONS

    # Auch die Aufrufform zählt: `get_skill_registry(nodeId)` nennt ein Werkzeug.
    genannt = {t for t in re.findall(r"`([a-z][a-z0-9_]+)(?=[`(])", text) if "_" in t}
    katalog = {d["function"]["name"]
               for d in (*TOOL_DEFINITIONS, *CURATION_TOOL_DEFINITIONS)}
    # ``zeige_dokument``: im Agent-Zug der einzige Weg zur Dokument-Box
    # (Agent-Runde 2, 2026-09-28) — der Chat-Zug legt es immer dazu.
    virtuell = {"wissen_suchen", "liefere_ergebnis", ZEIGE_DOKUMENT}
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
    finden = text.split("## Finden", 1)[1]
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
    handeln = text.split("## Zuerst handeln, dann reden", 1)[1].split("\n## ", 1)[0]
    assert "Aktivierungszeilen tippst du nie selbst" in handeln
    assert "gilt diese Bitte hier nicht" in handeln
