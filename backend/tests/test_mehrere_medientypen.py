"""Paket 18B — mehrere Medientypen in einer Anfrage („Arbeitsblatt oder interaktives Material“).

Externes Audit 2026-10 und Prüfung 2026-10-28. Bisher:
- ``learningResourceType`` als Liste → -32602, gerettet nur vom Retry des Modells;
- der Typ-Fokus wählte ``sorted(wanted)[0]``: Label und Such-URL kannten einen Typ;
- der Anti-Halluzinations-Wächter stürzte auf ``list.strip``;
- Stichwörter als Teilzeichenkette: „Protest“ war ein Quiz, „Beispiel“ ein Spiel.
"""

from __future__ import annotations

import json
import logging

import pytest

from boerdi.domain.content_types import (
    _extract_wanted_content_types,
    _resolve_wanted_content_types,
    als_liste,
    als_text,
    normalisiere_entitaeten,
)
from boerdi.services.mcp import listen_argumente as la
from boerdi.services.mcp.tool_args import validate_tool_args

# ── Stichwörter ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("nachricht", [
    "Material zum Protest der Bauern",
    "Gib mir ein Beispiel für Reibung",
    "Ein Exkurs zur Geschichte",
    "Kannst du das testen?",
    "Schick mir eine Testnachricht",
    "Ein Gegenbeispiel zur Regel",
    "Rechenbeispiele zur Prozentrechnung",
    "Der Diskurs über Medien",
])
def test_ein_wortteil_ist_kein_medientyp(nachricht):
    assert _extract_wanted_content_types(nachricht) == set()


@pytest.mark.parametrize(("nachricht", "erwartet"), [
    ("Hast du einen Test zur Bruchrechnung?", {"quiz"}),
    ("Lernvideos zur Optik", {"video"}),
    ("Übungsblätter zu Brüchen", {"übung"}),
    ("Ein Lernspiel zum Einmaleins", {"spiel"}),
    # Review 18: Komposita, die den Typ meinen, zählen weiter.
    ("Ein Klassentest zu Brüchen", {"quiz"}),
    ("Gibt es einen Onlinekurs zu Python?", {"kurs"}),
    ("Ein Rollenspiel zur Demokratie", {"spiel"}),
    ("Spiele zum Einmaleins", {"spiel"}),
    ("Show me the latest videos on optics", {"video"}),
    ("Arbeitsblatt oder interaktives Material zum Klimawandel", {"arbeitsblatt", "interaktiv"}),
])
def test_ganze_woerter_und_komposita_bleiben_erkannt(nachricht, erwartet):
    assert _extract_wanted_content_types(nachricht) == erwartet


@pytest.mark.parametrize(("wert", "erwartet"), [
    ("Onlinekurs", {"kurs"}), ("Vokabeltest", {"quiz"}), ("Rollenspiel", {"spiel"}),
])
def test_ein_klassifikatorwert_als_kompositum_trifft_seinen_typ(wert, erwartet):
    # Review 18: der Wert IST ein Typwort. Mit der Ganzwort-Regel fiel „Onlinekurs“
    # auf das rohe Wort zurück, und der Kartenfilter warf jede Karte weg.
    assert _resolve_wanted_content_types("", classification_entities={"medientyp": wert}) \
        == erwartet


def test_ein_medientyp_als_liste_ergibt_alle_typen():
    wanted = _resolve_wanted_content_types(
        "", classification_entities={"medientyp": ["Arbeitsblatt", "Interaktives Medium"]})
    assert wanted == {"arbeitsblatt", "interaktiv"}


# ── Werte, die als Liste ankommen ────────────────────────────────────────

@pytest.mark.parametrize(("wert", "text", "liste"), [
    ("Video", "Video", ["Video"]),
    ("  ", "", []),
    (["Arbeitsblatt", "", "Video", "Arbeitsblatt"], "Arbeitsblatt", ["Arbeitsblatt", "Video"]),
    ([], "", []),
    (None, "", []),
    (42, "", []),
])
def test_als_text_und_als_liste(wert, text, liste):
    assert als_text(wert) == text
    assert als_liste(wert) == liste


def test_normalisierung_der_entitaeten():
    roh = {"medientyp": ["Arbeitsblatt", "Interaktives Medium"], "fach": ["Physik", "Chemie"],
           "thema": "Optik", "stufe": []}
    assert normalisiere_entitaeten(roh) == {
        "medientyp": "Arbeitsblatt",
        "medientypen": ["Arbeitsblatt", "Interaktives Medium"],
        "fach": "Physik",
        "thema": "Optik",
    }


def test_ein_einzelner_medientyp_bekommt_keine_liste():
    assert normalisiere_entitaeten({"medientyp": ["Video"]}) == {"medientyp": "Video"}


# ── MCP: Listen auffächern ───────────────────────────────────────────────

def _umschlag(*ids: str, total: int | None = None) -> str:
    return json.dumps({"total": total if total is not None else len(ids), "count": len(ids),
                       "results": [{"nodeId": i, "title": i} for i in ids]})


class _Rufe:
    """Attrappe des einzelnen MCP-Aufrufs: Antwort je Wert von ``learningResourceType``."""

    def __init__(self, antworten: dict[str, tuple[str, str]]):
        self.antworten = antworten
        self.aufrufe: list[dict] = []

    async def __call__(self, tool_name, arguments, **kwargs):
        self.aufrufe.append(dict(arguments))
        return self.antworten[arguments["learningResourceType"]]


async def test_eine_liste_wird_aufgefaechert_und_zusammengefuehrt():
    rufe = _Rufe({"Arbeitsblatt": (_umschlag("a", "b", total=7), ""),
                  "Interaktives Medium": (_umschlag("b", "c", total=3), "")})
    text, art = await la.mit_listen(
        "search_wlo_content",
        {"query": "Klima", "learningResourceType": ["Arbeitsblatt", "Interaktives Medium"]},
        rufe)
    assert art == ""
    assert [a["learningResourceType"] for a in rufe.aufrufe] == ["Arbeitsblatt",
                                                                 "Interaktives Medium"]
    obj = json.loads(text)
    assert [r["nodeId"] for r in obj["results"]] == ["a", "b", "c"]   # entdoppelt
    assert obj["total"] == 10 and obj["count"] == 3


async def test_eine_liste_mit_einem_wert_wird_ausgepackt():
    rufe = _Rufe({"Video": (_umschlag("v"), "")})
    await la.mit_listen("search_wlo_content",
                        {"query": "x", "learningResourceType": ["Video"]}, rufe)
    assert rufe.aufrufe == [{"query": "x", "learningResourceType": "Video"}]


async def test_eine_leere_liste_faellt_weg():
    class _Einmal:
        aufrufe: list = []

        async def __call__(self, tool_name, arguments, **kwargs):
            self.aufrufe.append(dict(arguments))
            return _umschlag("x"), ""

    rufe = _Einmal()
    await la.mit_listen("search_wlo_content",
                        {"query": "x", "learningResourceType": [], "discipline": "Physik"}, rufe)
    assert rufe.aufrufe == [{"query": "x", "discipline": "Physik"}]


async def test_teilweise_fehler_liefern_die_treffer_der_uebrigen():
    rufe = _Rufe({"Arbeitsblatt": ("MCP error: kaputt", "tool"),
                  "Video": (_umschlag("v"), "")})
    text, art = await la.mit_listen(
        "search_wlo_content", {"query": "x", "learningResourceType": ["Arbeitsblatt", "Video"]},
        rufe)
    # Der Umschlag plus Hinweis auf die gescheiterte Teilsuche — gelesen wie vom Parser.
    assert art == "" and la.load_envelope(text)["results"][0]["nodeId"] == "v"


async def test_scheitern_alle_kommt_der_erste_fehler_zurueck():
    rufe = _Rufe({"Arbeitsblatt": ("MCP error: a", "tool"), "Video": ("MCP error: b", "tool")})
    text, art = await la.mit_listen(
        "search_wlo_content", {"query": "x", "learningResourceType": ["Arbeitsblatt", "Video"]},
        rufe)
    assert (text, art) == ("MCP error: a", "tool")


async def test_hoechstens_drei_werte_werden_abgefragt():
    rufe = _Rufe({t: (_umschlag(t), "") for t in "abcde"})
    await la.mit_listen("search_wlo_content",
                        {"query": "x", "learningResourceType": list("abcde")}, rufe)
    assert len(rufe.aufrufe) == 3


async def test_der_begleittext_des_servers_bleibt_erhalten():
    # Review 18: der Server hängt Hinweise als eigenen Block an (nicht aufgelöster
    # Filter, Lizenz, Skill-Liste) — beim Zusammenführen gingen sie verloren.
    rufe = _Rufe({"Arbeitsblatt": (_umschlag("a") + "\n\nHinweis: Lizenz beachten.", ""),
                  "Video": (_umschlag("v") + "\n\nHinweis: Lizenz beachten.", "")})
    text, _art = await la.mit_listen(
        "search_wlo_content", {"query": "x", "learningResourceType": ["Arbeitsblatt", "Video"]},
        rufe)
    assert text.count("Hinweis: Lizenz beachten.") == 1
    assert [r["nodeId"] for r in la.load_envelope(text)["results"]] == ["a", "v"]


async def test_ein_teilfehler_wird_dem_modell_genannt(caplog):
    rufe = _Rufe({"Arbeitsblatt": ("MCP error: kaputt", "tool"),
                  "Video": (_umschlag("v"), "")})
    with caplog.at_level(logging.INFO, logger=la.__name__):
        text, _art = await la.mit_listen(
            "search_wlo_content",
            {"query": "x", "learningResourceType": ["Arbeitsblatt", "Video"]}, rufe)
    assert "Arbeitsblatt" in text and "fehlgeschlagen" in text
    assert "1 of 2" in caplog.text


async def test_eine_ausnahme_eines_teilaufrufs_laesst_die_anderen_zaehlen():
    class _Wirft(_Rufe):
        async def __call__(self, tool_name, arguments, **kwargs):
            if arguments["learningResourceType"] == "Arbeitsblatt":
                raise RuntimeError("weg")
            return await super().__call__(tool_name, arguments, **kwargs)

    rufe = _Wirft({"Video": (_umschlag("v"), "")})
    text, art = await la.mit_listen(
        "search_wlo_content", {"query": "x", "learningResourceType": ["Arbeitsblatt", "Video"]},
        rufe)
    assert art == "" and la.load_envelope(text)["results"][0]["nodeId"] == "v"


def test_total_summiert_nur_die_inhaltssuche():
    # ``search_wlo_all``: Sammlungen und Themenseiten hängen nicht am Typ — beide
    # Teilsuchen fanden dieselben, ihr ``total`` ist keine Summe.
    def _alle(inhalt: str) -> str:
        return json.dumps({
            "content": {"total": 5, "count": 1, "results": [{"nodeId": inhalt}]},
            "collections": {"total": 2, "count": 2,
                            "results": [{"nodeId": "c1"}, {"nodeId": "c2"}]}})

    obj = la.load_envelope(la.vereinige_umschlaege([_alle("a"), _alle("v")]))
    assert obj["content"]["total"] == 10 and obj["content"]["count"] == 2
    assert obj["collections"]["total"] == 2 and obj["collections"]["count"] == 2


async def test_der_mcp_client_reicht_listen_an_das_auffaechern(monkeypatch):
    from boerdi.services.mcp import client

    gerufen = []

    async def _spy(tool_name, arguments, rufe, **kwargs):
        gerufen.append((tool_name, rufe, kwargs))
        return "OK", ""

    monkeypatch.setattr(client, "mit_listen", _spy)
    assert await client.call_mcp_tool_status(
        "search_wlo_content", {"query": "x", "learningResourceType": ["a", "b"]}) == ("OK", "")
    assert gerufen == [("search_wlo_content", client.call_mcp_tool_status,
                        {"use_cache": True})]


def test_die_werkzeugschleife_reicht_mehrere_typen_als_liste(monkeypatch):
    from tests.test_tool_loop import _OutcomeFake, _resp_text, _resp_tools, _run_loop

    out = _OutcomeFake()
    _run_loop(monkeypatch, [
        _resp_tools([("tc1", "search_wlo_content", json.dumps({"query": "klima"}))]),
        _resp_text("fertig"),
    ], outcome=out, classification={"entities": {
        "medientyp": "Arbeitsblatt", "medientypen": ["Arbeitsblatt", "Interaktives Medium"]}})
    assert out.calls[0][1]["learningResourceType"] == ["Arbeitsblatt", "Interaktives Medium"]


def test_nur_suchwerkzeuge_werden_umgeformt():
    assert la.braucht_umformung("search_wlo_content", {"learningResourceType": ["a", "b"]})
    assert not la.braucht_umformung("wlo_create_content", {"keywords": ["a", "b"]})
    assert not la.braucht_umformung("search_wlo_content", {"learningResourceType": "a"})


# ── tool_args: der zweite Fehler bleibt nicht stumm ──────────────────────

def test_ein_fehler_nach_dem_klemmen_wird_geloggt(caplog):
    with caplog.at_level(logging.WARNING, logger="boerdi.services.mcp.tool_args"):
        validate_tool_args("search_wlo_content",
                           {"query": "x", "maxResults": 999, "license": ["OER", "CC"]})
    assert "after clamping" in caplog.text
