"""C1 (Plan ``docs/plans/2026-11-13-mcp-nach-audit.md``): ein Ausfall ist nicht „nichts gefunden“.

Seit der Audit-Nacharbeit unterscheidet der MCP-Server Ausfall und leere Liste. Der Chatbot
verlor das — im Cache (bis zu 30 Minuten), in der Kürzung für die KI und im Text des
Themenseiten-Musters.

Die Antworten hier haben die Form, die der Server wirklich sendet (am Arbeitsstand gelesen,
Reviews C1): ``search_wlo_collections`` schreibt im JSON-Text nur ``{total, count, results}`` und
hängt den Hinweissatz als eigenen Block an; das Kennzeichen ``incomplete`` steht dort allein im
strukturierten Teil. ``search_wlo_all`` trägt es je Topf auch im Text, ``browse_collection_tree``
als ``childrenUnread`` am Knoten.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from boerdi.domain import mcp_unvollstaendig as mu
from boerdi.domain.tool_result_redaction import (
    _redact_search_content_for_llm,
    redigiere_strukturell,
)
from boerdi.services.mcp import client, tool_cache, transport
from boerdi.services.mcp.parsers import parse_topic_page_swimlanes
from tests.test_mcp_client import (  # noqa: F401 — Fixture
    _text_part,
    _wire_tool_url,
    mcp_state,
)
from tests.test_topic_pages import _run_m16, m16  # noqa: F401 — Fixture

_SATZ_LEER = ("Die Suche nach Sammlungen hat nicht (vollständig) geantwortet — 0 Treffer sind "
              "hier KEIN Befund „keine Sammlungen“. Bitte später erneut versuchen.")
_SATZ_TEIL = ("Die Suche nach Themenseiten war nur teilweise erreichbar — die Liste kann "
              "unvollständig sein.")
_SATZ_UNTERLISTE = ("Hinweis: Mindestens eine Unterliste dieser Sammlung ließ sich gerade nicht "
                    "lesen — die Inhalte darunter fehlen hier. Das ist KEIN Befund „mehr gibt es "
                    "nicht“; bitte später erneut versuchen.")
_SATZ_ZWEIG = ("  … die Unterthemen ließen sich gerade nicht lesen — das heißt NICHT, dass es "
               "keine gibt. Später erneut: browse_collection_tree mit nodeId=n2")
_SATZ_WIKI = ("Wikipedia hat gerade nicht geantwortet — ob es einen Artikel zu \"x\" gibt, ist "
              "damit offen. Das ist KEIN Befund „kein Artikel“. Bitte später erneut versuchen.")
_LEER = json.dumps({"total": 0, "count": 0, "results": []})
#: ``search_wlo_collections`` im JSON-Modus bei einem Ausfall: Umschlag OHNE Kennzeichen + Satz.
_SAMMLUNGEN_AUSFALL = _LEER + "\n" + _SATZ_LEER
_BAUM_AUSFALL = {"results": [{"nodeId": "n1", "title": "Physik", "children": [
    {"nodeId": "n2", "title": "Optik", "childrenUnread": True}]}]}
_SUCHE, _SAMMLUNGEN = "search_wlo_all", "search_wlo_collections"


# ── Erkennen ───────────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(("werkzeug", "strukturiert", "text"), [
    (_SAMMLUNGEN, {"total": 0, "count": 0, "results": [], "incomplete": True},
     _SAMMLUNGEN_AUSFALL),
    (_SUCHE, {"collections": {"count": 0, "results": [], "incomplete": True},
              "topicPages": {"count": 2, "results": [{}, {}]}}, ""),
    (_SAMMLUNGEN, None, _SAMMLUNGEN_AUSFALL),          # nur der Text, Satz hinter dem Umschlag
    (_SUCHE, None, json.dumps({"collections": {"incomplete": True, "results": []}})),
    ("get_wikipedia_summary", None,
     json.dumps({"query": "x", "found": False, "unreachable": True, "summary": None})),
    ("get_topic_page_content", None,
     json.dumps({"variantId": "", "swimlanes": [], "reason": "source_unreachable"})),
    ("browse_collection_tree", _BAUM_AUSFALL, "ok"),   # zweites Review: Zweig nicht gelesen
    ("browse_collection_tree", None, json.dumps(_BAUM_AUSFALL)),
    ("browse_collection_tree", None, "- Physik\n  - Optik\n" + _SATZ_ZWEIG),
    ("search_wlo_topic_pages", None, _SATZ_LEER),      # Markdown-Modus
    ("search_wlo_topic_pages", None, "# Treffer\n\n- A\n\n" + _SATZ_TEIL),
    ("get_collection_contents", None, "# Sammlung\n\n- A\n\n" + _SATZ_UNTERLISTE),
    ("get_wikipedia_summary", None, _SATZ_WIKI),
])
def test_eine_unvollstaendige_antwort_wird_erkannt(werkzeug, strukturiert, text):
    assert mu.ist_unvollstaendig(werkzeug, strukturiert, text)


@pytest.mark.parametrize(("werkzeug", "strukturiert", "text"), [
    (_SAMMLUNGEN, {"total": 3, "count": 3, "results": [{}, {}, {}]}, "ok"),
    (_SAMMLUNGEN, {"total": 0, "count": 0, "results": [], "incomplete": False},
     "Keine Sammlungen gefunden."),
    (_SUCHE, {"collections": {"count": 0, "results": []}}, ""),
    (_SAMMLUNGEN, None, _LEER),
    ("search_wlo_topic_pages", None, "Keine Themenseiten gefunden."),
    ("get_topic_page_content", None, json.dumps({"swimlanes": [], "reason": "empty_config"})),
    ("browse_collection_tree", {"results": [{"nodeId": "n1", "children": [
        {"nodeId": "n2", "hasMoreChildren": True}]}]}, "ok"),
    (_SAMMLUNGEN, None, ""),
    # ein Treffer, dessen TITEL den Satz des Servers wörtlich trägt, ist keine Meldung des Servers
    (_SAMMLUNGEN, None, json.dumps({"total": 1, "count": 1, "results": [{"title": _SATZ_LEER}]})),
])
def test_eine_vollstaendige_antwort_bleibt_es(werkzeug, strukturiert, text):
    assert not mu.ist_unvollstaendig(werkzeug, strukturiert, text)


@pytest.mark.parametrize(("werkzeug", "strukturiert", "text"), [
    # eine Anleitung oder ein Volltext, der die Wendung zitiert, ist kein Ausfall (zweites Review)
    ("get_skill", None, "# Skill\n\nSagt der Server „" + _SATZ_LEER + "“, dann frag später."),
    ("get_wlo_content_text", None, _SATZ_UNTERLISTE),
    ("get_compendium_text", {"incomplete": True}, "x"),
    # ein fremder MCP-Server: dasselbe Feld kann dort etwas anderes heißen
    ("wetter__vorhersage", {"incomplete": True, "unreachable": True}, _SATZ_WIKI),
    # die Skill-Suche meldet so auch dauerhafte Grenzen (Seitengröße, Tiefe) — bewusst nicht
    ("search_skill", None, "Die Sammlung wurde nicht vollständig gelesen (Seitengröße)."),
    (_SAMMLUNGEN, {"skills": [], "incomplete": True, "incompleteNote": "Seitengröße"}, ""),
])
def test_andere_werkzeuge_und_die_skill_suche_zaehlen_nicht(werkzeug, strukturiert, text):
    assert not mu.ist_unvollstaendig(werkzeug, strukturiert, text)
    assert mu.mit_hinweissaetzen(werkzeug, "kurz", text) == "kurz"


def test_die_saetze_des_servers_werden_nur_hinter_dem_umschlag_gelesen():
    assert mu.hinweissaetze(_SAMMLUNGEN, _SAMMLUNGEN_AUSFALL) == [_SATZ_LEER]
    assert mu.hinweissaetze(_SAMMLUNGEN, json.dumps({"results": [{"title": _SATZ_LEER}]})) == []
    assert mu.hinweissaetze("search_wlo_topic_pages", "- A\n" + _SATZ_TEIL + "\n- B") \
        == [_SATZ_TEIL]
    assert mu.hinweissaetze(_SAMMLUNGEN, "") == []


def test_hoechstens_drei_saetze_reisen_mit():
    baum = "\n".join(f"- Zweig {i}\n{_SATZ_ZWEIG}" for i in range(9))
    assert len(mu.hinweissaetze("browse_collection_tree", baum)) == 3


@pytest.mark.parametrize("text", ["[" * 5000, "[Titel](https://wlo.example) — kein JSON",
                                  "﻿" + _SAMMLUNGEN_AUSFALL, "{kaputt"])
def test_ein_seltsamer_textanfang_wirft_nicht(text):
    """Zweites Review: tief verschachteltes ``[[[[…`` warf ``RecursionError``."""
    mu.ist_unvollstaendig(_SAMMLUNGEN, None, text)
    mu.hinweissaetze(_SAMMLUNGEN, text)


# ── Cache ──────────────────────────────────────────────────────────────────────────────────────

def _ergebnis(text: str, strukturiert: dict | None = None) -> dict:
    return {"result": {"content": [_text_part(text)],
                       **({"structuredContent": strukturiert} if strukturiert else {})}}


def _dreimal(monkeypatch, tool: str, args: dict, antworten: list[dict],
             spaeter_s: float) -> tuple[int, int, str]:
    """Zwei Aufrufe direkt hintereinander, ein dritter ``spaeter_s`` Sekunden danach — wie viele
    davon den Server erreichten (nach dem zweiten, nach dem dritten) und der letzte Text.
    Gezählt werden nur Aufrufe DIESES Werkzeugs (der Baum löst vorher die Fachportale auf)."""
    _wire_tool_url(monkeypatch)
    aufrufe: list[str] = []
    skript = list(antworten)

    async def rufe(tool_name, arguments=None, *, url=None, **_kw):
        if tool_name != tool:
            return {"result": {"content": []}}
        aufrufe.append(tool_name)
        return skript.pop(0) if skript else {"result": {"content": []}}

    monkeypatch.setattr(transport, "call_tool", rufe)
    jetzt = [1_000_000.0]
    monkeypatch.setattr(tool_cache._time, "time", lambda: jetzt[0])
    asyncio.run(client.call_mcp_tool(tool, dict(args)))
    asyncio.run(client.call_mcp_tool(tool, dict(args)))
    nach_zwei = len(aufrufe)
    jetzt[0] += spaeter_s
    text = asyncio.run(client.call_mcp_tool(tool, dict(args)))
    return nach_zwei, len(aufrufe), text


_VOLL = json.dumps({"total": 1, "count": 1, "results": [{"title": "Optik", "nodeId": "n1"}]})


def test_eine_unvollstaendige_liste_steht_nur_sekunden_im_cache(mcp_state, monkeypatch):  # noqa: F811
    """Vorher blieb die Liste aus einem Ausfall 300 s stehen. Jetzt 30 s: kurz genug für „noch
    einmal versuchen“, lang genug, dass eine Überlast nicht mit jedem Zug neu angefragt wird."""
    aus = _ergebnis(_SAMMLUNGEN_AUSFALL, {"total": 0, "count": 0, "results": [],
                                          "incomplete": True})
    nach_zwei, am_ende, text = _dreimal(
        monkeypatch, _SAMMLUNGEN, {"query": "Optik"}, [aus, _ergebnis(_VOLL)], spaeter_s=31)
    assert (nach_zwei, am_ende) == (1, 2) and "Optik" in text


def test_ein_ungelesener_zweig_steht_nicht_30_minuten_im_cache(mcp_state, monkeypatch):  # noqa: F811
    """Zweites Review (schwer): ``browse_collection_tree`` hat die längste Frist (1800 s) — ein
    Ausfall stand so lange als „Zweig ohne Unterthemen“ da, auch für den Strukturabgleich."""
    aus = _ergebnis(json.dumps(_BAUM_AUSFALL), _BAUM_AUSFALL)
    gut = {"results": [{"nodeId": "n1", "children": [
        {"nodeId": "n2", "title": "Optik", "children": [{"nodeId": "n3", "title": "Linsen"}]}]}]}
    nach_zwei, am_ende, text = _dreimal(
        monkeypatch, "browse_collection_tree", {"nodeId": "n1", "depth": 2},
        [aus, _ergebnis(json.dumps(gut), gut)], spaeter_s=31)
    assert (nach_zwei, am_ende) == (1, 2) and "Linsen" in text


def test_ein_grund_source_unreachable_steht_nur_sekunden_im_cache(mcp_state, monkeypatch):  # noqa: F811
    """Review C1 (schwer): ``get_topic_page_content`` trägt weder ``incomplete`` noch einen Satz,
    nur den Grund."""
    aus = json.dumps({"variantId": "", "collectionId": None, "swimlanes": [],
                      "reason": "source_unreachable"})
    gut = json.dumps({"variantId": "v1", "swimlanes": [{"heading": "Videos", "cards": []}]})
    nach_zwei, am_ende, text = _dreimal(
        monkeypatch, "get_topic_page_content", {"query": "Klima"},
        [_ergebnis(aus), _ergebnis(gut)], spaeter_s=31)
    assert (nach_zwei, am_ende) == (1, 2) and "Videos" in text


def test_eine_vollstaendige_liste_behaelt_die_frist_ihres_werkzeugs(mcp_state, monkeypatch):  # noqa: F811
    nach_zwei, am_ende, _text = _dreimal(
        monkeypatch, _SAMMLUNGEN, {"query": "Optik"}, [_ergebnis(_VOLL), _ergebnis(_VOLL)],
        spaeter_s=200)
    assert (nach_zwei, am_ende) == (1, 1)


def test_teilantwort_und_fehltreffer_bleiben_ganz_draussen():
    assert not client._cachebar("count_wlo_content_matches", "ok", {"missing": [{"part": "k"}]})
    assert not client._cachebar("get_skill", "Skill x ist nicht abrufbar (404).", None)
    assert client._cachebar(_SAMMLUNGEN, _LEER, {"total": 0, "results": []})


# ── Was die KI sieht ───────────────────────────────────────────────────────────────────────────

def test_die_kuerzung_der_sammlungssuche_behaelt_den_satz_des_servers():
    """Review C1 (schwer): der Umschlag trägt hier kein Kennzeichen, der Satz steht dahinter —
    die Kurzfassung warf ihn weg, in beiden Wegen."""
    for kurz in (redigiere_strukturell(_SAMMLUNGEN, _SAMMLUNGEN_AUSFALL),
                 _redact_search_content_for_llm(_SAMMLUNGEN, _SAMMLUNGEN_AUSFALL, [], False)):
        umschlag, _, rest = kurz.partition("\n\n")
        assert json.loads(umschlag)["results"] == [] and rest == _SATZ_LEER


def test_die_kuerzung_der_kombi_suche_behaelt_kennzeichen_und_saetze():
    roh = json.dumps({"query": "Optik",
                      "content": {"total": 1, "count": 1,
                                  "results": [{"title": "A", "nodeId": "1"}]},
                      "collections": {"total": 0, "count": 0, "results": [], "incomplete": True},
                      "topicPages": {"total": 2, "count": 2, "incomplete": True,
                                     "results": [{"title": "T", "nodeId": "2"}]}}) \
        + "\n" + _SATZ_LEER + "\n" + _SATZ_TEIL
    kurz = redigiere_strukturell(_SUCHE, roh)
    umschlag = json.loads(kurz.partition("\n\n")[0])
    assert umschlag["collections"]["incomplete"] is True
    assert umschlag["topicPages"]["incomplete"] is True and "incomplete" not in umschlag["content"]
    assert _SATZ_LEER in kurz and _SATZ_TEIL in kurz


def test_ohne_ausfall_aendert_sich_die_kuerzung_nicht():
    """Wächter für den Normalfall — er war nie betroffen und soll es nicht werden."""
    roh = json.dumps({"total": 1, "count": 1, "results": [{"title": "A", "nodeId": "1"}]})
    kurz = redigiere_strukturell(_SAMMLUNGEN, roh)
    assert set(json.loads(kurz)) == {"total", "count", "results"}
    assert _redact_search_content_for_llm("search_wlo_topic_pages", "x" * 9000, [], False) \
        == "x" * 4000


def test_eine_anleitung_die_den_satz_zitiert_bleibt_wie_sie_ist():
    anleitung = "# Skill\n\n" + "Text. " * 2000 + "\n" + _SATZ_LEER + "\n\nWeiter im Text."
    assert _redact_search_content_for_llm("get_skill", anleitung, [], False) == anleitung
    assert redigiere_strukturell("get_skill", anleitung) == anleitung


def test_der_satz_ueberlebt_den_zeichen_deckel():
    """Themenseiten mit Teilausfall: lange Liste, der Satz steht am Ende — hinter dem Deckel."""
    lang = json.dumps({"total": 40, "results": [{"title": "T" * 200, "nodeId": str(i)}
                                               for i in range(40)]}) + "\n" + _SATZ_TEIL
    assert len(lang) > 4000
    kurz = _redact_search_content_for_llm("search_wlo_topic_pages", lang, [], False)
    assert kurz.endswith(_SATZ_TEIL) and len(kurz) < 4000 + len(_SATZ_TEIL) + 10


def test_der_satz_ueberlebt_den_ersatz_durch_die_ansage():
    """Im Gruppiermodus ersetzt eine Ansage die Einzelinhalte von ``get_collection_contents`` —
    der Hinweis „eine Unterliste ließ sich nicht lesen“ ging mit verloren."""
    roh = json.dumps({"total": 1, "count": 1, "results": [{"title": "A", "nodeId": "1"}]}) \
        + "\n" + _SATZ_UNTERLISTE
    karte = {"node_id": "1", "title": "A", "node_type": "content"}
    kurz = _redact_search_content_for_llm("get_collection_contents", roh, [karte], True)
    assert kurz.endswith(_SATZ_UNTERLISTE)


# ── Das Themenseiten-Muster ohne KI ────────────────────────────────────────────────────────────

def test_der_grund_des_servers_wird_vom_draht_gelesen():
    roh = json.dumps({"variantId": "", "collectionId": None, "variantTitle": "",
                      "topicPageUrl": None, "swimlanes": [], "reason": "source_unreachable"})
    assert parse_topic_page_swimlanes(roh)["reason"] == mu.GRUND_AUSFALL


def test_m16_ein_ausfall_ist_keine_leere_themenseite(m16):  # noqa: F811
    """Vorher: „sie ist eventuell noch leer oder nicht vollständig freigegeben“ — über eine
    Quelle, die nur nicht geantwortet hat."""
    m16["swimlanes"] = {"swimlanes": [], "reason": "source_unreachable"}
    view, cards, text = _run_m16("M16", entities={"thema": "Klimawandel"})
    assert view is None and cards == []
    assert "nicht geantwortet" in text and "Klimawandel" in text
    assert "noch leer" not in text and "keine Themenseite gefunden" not in text


def _m16_text(m16, art: str) -> str:  # noqa: F811
    m16["art"] = art
    m16["swimlanes"] = {"swimlanes": [], "reason": ""}
    return _run_m16("M16", entities={"thema": "Klimawandel"})[2]


@pytest.mark.parametrize("art", ["transport", "timeout", "busy"])
def test_m16_keine_antwort_ist_ein_ausfall(m16, art):  # noqa: F811
    text = _m16_text(m16, art)
    assert "nicht geantwortet" in text and "noch leer" not in text


@pytest.mark.parametrize("art", ["tool", "auth"])
def test_m16_eine_ablehnung_ist_kein_ausfall(m16, art):  # noqa: F811
    """Reviews C1: ungültige Eingabe, unbekanntes Werkzeug, fehlende Anmeldung — „noch einmal
    versuchen“ hülfe nicht. Geprüft wird die ART des Fehlers, nicht eine Liste von Codes."""
    assert "nicht geantwortet" not in _m16_text(m16, art)


def test_m16_ein_fehler_des_repositoriums_ist_ein_ausfall(m16, monkeypatch):  # noqa: F811
    import boerdi.services.topic_pages as topic_pages

    async def antworte(_tool, _args):
        return "MCP error [upstream_error]: Das Repositorium antwortet mit 502.", "tool"

    monkeypatch.setattr(topic_pages, "call_mcp_tool_status", antworte)
    m16["swimlanes"] = {"swimlanes": [], "reason": ""}
    assert "nicht geantwortet" in _run_m16("M16", entities={"thema": "Klimawandel"})[2]


def test_m16_ein_leerer_grund_bleibt_bei_der_vorsichtigen_aussage(m16):  # noqa: F811
    m16["swimlanes"] = {"swimlanes": [], "reason": "empty_config"}
    _view, _cards, text = _run_m16("M16", entities={"thema": "Klimawandel"})
    assert "noch leer" in text and "nicht geantwortet" not in text
