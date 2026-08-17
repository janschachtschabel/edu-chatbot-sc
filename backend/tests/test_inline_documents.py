"""Das Ergebnis-Dokument als Werkzeug (D1).

Bis heute wird die Box aus dem Antworttext **geraten**: Muster ∈ {M09,M10,M11},
≥200 Zeichen, ein H1 im Text. Vier Bedingungen, die zufällig zusammentreffen
müssen — live gemessen 2026-08-17 stimmte nur das Muster, und ein 8.000 Zeichen
langer Verlaufsplan fiel weg.

Hier wird sie **geliefert**: das Modell ruft ``zeige_dokument`` mit Titel, Art
und Markdown. Damit ist die Box unabhängig von Länge, Überschrift, Muster und
davon, im wievielten Zug sie kommt.

Die Argumente sind Modell-Ausgabe und damit unvertraute Eingabe — jeder Test
hier prüft eine Zurückweisung mit.
"""

from __future__ import annotations

from boerdi.domain.inline_documents import (
    DOKUMENT_ARTEN,
    MAX_MARKDOWN_ZEICHEN,
    MAX_TITEL_ZEICHEN,
    ZEIGE_DOKUMENT,
    dokument_aus_argumenten,
    dokument_werkzeug,
)


def _args(**over) -> dict:
    basis = {"titel": "Unterrichtsverlaufsplan: Optik",
             "art": "stundenplanung",
             "markdown": "# Verlaufsplan\n\n| Phase | Zeit |\n|---|---|"}
    basis.update(over)
    return basis


# ── Das Werkzeug ───────────────────────────────────────────────────────────

def test_das_werkzeug_verlangt_titel_art_und_markdown() -> None:
    fn = dokument_werkzeug()["function"]
    assert fn["name"] == ZEIGE_DOKUMENT
    props = fn["parameters"]["properties"]
    assert set(fn["parameters"]["required"]) == {"titel", "art", "markdown"}
    assert set(props) == {"titel", "art", "markdown"}


def test_die_art_aufzaehlung_fuehrt_die_gepflegten_formen() -> None:
    """Nutzer-Entscheid 2026-08-17: die fünf Bestandsformen plus die fünf
    schulischen Formen, die die Skills wirklich erzeugen."""
    enum = dokument_werkzeug()["function"]["parameters"]["properties"]["art"]["enum"]
    assert enum == list(DOKUMENT_ARTEN)
    for gebraucht in ("lernpfad", "ki_material", "edit", "bericht", "remix",
                      "stundenplanung", "unterrichtsreihe", "zeugnis",
                      "dokument", "kompendialtext"):
        assert gebraucht in enum


def test_die_beschreibung_traegt_die_anweisung() -> None:
    """Die Anweisung gehört an das Werkzeug, nicht in den Fließtext eines
    Musters — nur so gilt sie unabhängig davon, wie ein Skill formuliert ist."""
    text = dokument_werkzeug()["function"]["description"]
    assert ZEIGE_DOKUMENT not in text          # kein Selbstverweis
    assert "Arbeitsergebnis" in text
    # Jede Art wird im Beschreibungstext erklärt, sonst rät das Modell.
    for art, erklaerung in DOKUMENT_ARTEN.items():
        assert erklaerung, f"{art} ohne Erklärung"


# ── Die Abnahme der Argumente ──────────────────────────────────────────────

def test_gueltige_argumente_werden_zum_dokument() -> None:
    doc = dokument_aus_argumenten(_args())
    assert doc == {"kind": "stundenplanung",
                   "title": "Unterrichtsverlaufsplan: Optik",
                   "content": "# Verlaufsplan\n\n| Phase | Zeit |\n|---|---|",
                   "meta": {"source": "tool"}}


def test_die_box_braucht_weder_ueberschrift_noch_laenge() -> None:
    """Genau die zwei Bedingungen, an denen der geratene Weg scheiterte."""
    doc = dokument_aus_argumenten(_args(markdown="Kurz. Ohne Raute."))
    assert doc is not None
    assert doc["content"] == "Kurz. Ohne Raute."


def test_leerer_titel_oder_leeres_markdown_wird_abgewiesen() -> None:
    assert dokument_aus_argumenten(_args(titel="   ")) is None
    assert dokument_aus_argumenten(_args(markdown="")) is None
    assert dokument_aus_argumenten(_args(markdown="\n  \n")) is None


def test_eine_unbekannte_art_faellt_auf_dokument_zurueck() -> None:
    """Zurückweisen wäre hier falsch: der Inhalt ist da, nur das Etikett passt
    nicht. Das Frontend zeigt ohnehin den Titel und fällt beim Icon zurück."""
    doc = dokument_aus_argumenten(_args(art="reisebericht"))
    assert doc is not None
    assert doc["kind"] == "dokument"


def test_nicht_zeichenketten_werden_abgewiesen() -> None:
    """Werkzeug-Argumente sind Modell-Ausgabe — ein Dict im Markdown-Feld darf
    nicht bis in die Antwort durchschlagen."""
    assert dokument_aus_argumenten(_args(markdown={"a": 1})) is None
    assert dokument_aus_argumenten(_args(titel=42)) is None
    assert dokument_aus_argumenten("kein dict") is None
    assert dokument_aus_argumenten(None) is None


def test_zu_langes_markdown_wird_gedeckelt_statt_verworfen() -> None:
    """Ein Deckel schützt die Antwortgröße; wegwerfen würde die Arbeit des
    ganzen Zuges vernichten."""
    doc = dokument_aus_argumenten(_args(markdown="x" * (MAX_MARKDOWN_ZEICHEN + 500)))
    assert doc is not None
    assert len(doc["content"]) <= MAX_MARKDOWN_ZEICHEN + 40   # Platz für den Hinweis
    assert doc["content"].rstrip().endswith("…")


def test_ein_zu_langer_titel_wird_glatt_geschnitten() -> None:
    """Der Titel steht in einer KOPFZEILE, nicht in einem Absatz.

    Der Kürzungs-Hinweis des Rumpfes trägt einen Leerzeilen-Umbruch und
    Markdown-Sternchen. Die Box interpoliert den Titel (``{{ doc.title }}`` in
    ``inline-documents.component.ts``) statt ihn zu rendern — beides stünde
    also wörtlich in der Überschrift.
    """
    doc = dokument_aus_argumenten(_args(titel="T" * (MAX_TITEL_ZEICHEN + 40)))
    assert doc is not None
    assert "\n" not in doc["title"]
    assert "*" not in doc["title"]
    assert doc["title"].endswith("…")
    assert len(doc["title"]) <= MAX_TITEL_ZEICHEN + 1


def test_der_rumpf_behaelt_seinen_erklaerenden_hinweis() -> None:
    """Im Markdown ist der Satz richtig: dort ist Platz, und ohne ihn sähe der
    Abbruch nach einem Fehler aus."""
    doc = dokument_aus_argumenten(_args(markdown="x" * (MAX_MARKDOWN_ZEICHEN + 10)))
    assert doc is not None
    assert "gekuerzt" in doc["content"]


# ``MAX_DOKUMENTE_JE_ZUG`` hat hier keinen eigenen Fall: die Zahl allein
# zuzusichern belegt nichts. Gepinnt ist der DECKEL, und zwar dort, wo er
# greift — in beiden Schleifen (``test_agent_loop`` und ``test_tool_loop``).
