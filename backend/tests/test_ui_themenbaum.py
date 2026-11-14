"""Paket U1-e: der Themenbaum (`ui_themenbaum`) mit Datenquelle `browse_collection_tree`.

Die KI nennt nur Fach oder Sammlung; das Backend ruft das Werkzeug selbst, formt schlanke Knoten
und legt den Block in die Antwort. An die KI geht eine Quittung OHNE Knoten — der Nachweis von
U1-e (Plan §15, E-1): der Baum kostet keine Modell-Tokens für die Knoten.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from boerdi.domain.werkzeug_angebot import NICHT_ANGEBOTEN
from boerdi.services.mcp.tool_defs import TOOL_DEFINITIONS
from boerdi.ui_module import datenquelle, katalog, themenbaum
from boerdi.ui_module.werkzeuge import modul_werkzeuge
from tests.test_agent_loop import _lauf, _OutcomeFake, _resp_text, _resp_tools, _tool_call
from tests.test_ui_modul_katalog import _manifest, _schreibe

THEMENBAUM = "ui_themenbaum"
WERKZEUG = "browse_collection_tree"


def _knoten(node_id: str, title: str, **mehr) -> dict:
    """Ein Knoten, wie der Server ihn schickt (`FormattedNode` + Baum-Felder)."""
    n = {"nodeId": node_id, "title": title, "description": f"GEHEIM-BESCHREIBUNG {title}",
         "keywords": ["k"], "disciplines": [], "educationalContexts": [], "userRoles": [],
         "learningResourceTypes": [], "url": f"https://wirlernenonline.de/sammlung/{node_id}",
         "downloadUrl": "", "contentUrl": "", "previewUrl": "", "previewIsIcon": False,
         "mimeType": "", "fileSize": 0, "license": "", "publisher": "", "nodeType": "collection",
         "topicPageUrl": ""}
    n.update(mehr)
    return n


def _payload(**mehr) -> dict:
    p = {"parent": "aaaa-1111", "depth": 2, "total": 2, "truncated": True, "results": [
        _knoten("bbbb-2222", "Algebra", hasMoreChildren=True, children=[
            _knoten("cccc-3333", "Gleichungen", fileCount=12),
            _knoten("dddd-4444", "Terme"),
        ]),
        _knoten("eeee-5555", "Geometrie", topicPageUrl="https://wirlernenonline.de/geometrie/",
                contentsCount=7),
    ]}
    p.update(mehr)
    return p


ALLE_KNOTEN = ("Algebra", "Gleichungen", "Terme", "Geometrie",
               "bbbb-2222", "cccc-3333", "dddd-4444", "eeee-5555")


def _manifest_baum() -> dict:
    return katalog.katalog()[THEMENBAUM]


# ── e-1 Vertrag: datenquelle.vorgaben ─────────────────────────────────────


def test_eine_datenquelle_darf_feste_vorgaben_tragen(tmp_path):
    m = _manifest(datenquelle={"werkzeug": WERKZEUG, "argumente": ["subject"],
                               "vorgaben": {"depth": 2}})
    assert katalog.lade(_schreibe(tmp_path, m))["ui_probe"]["datenquelle"]["vorgaben"] == {
        "depth": 2}


def test_vorgaben_muessen_ein_objekt_sein(tmp_path):
    m = _manifest(datenquelle={"werkzeug": WERKZEUG, "argumente": ["subject"], "vorgaben": [2]})
    with pytest.raises(katalog.KatalogFehler, match="vorgaben"):
        katalog.lade(_schreibe(tmp_path, m))


# ── e-2 Manifest ──────────────────────────────────────────────────────────


def test_der_themenbaum_steht_im_katalog_mit_seiner_datenquelle():
    m = _manifest_baum()
    assert (m["art"], m["agent"]) == ("anzeigen", True)
    assert m["datenquelle"]["werkzeug"] == WERKZEUG
    # N3 (2026-11-14): dazu der Titel einer Sammlung und ihr Fach — angeboten nur, wenn der
    # MCP-Server sie kennt (``tests/test_mcp_sammlung_per_name.py``).
    assert m["datenquelle"]["argumente"] == ["subject", "discipline", "collection", "nodeId"]
    assert m["datenquelle"]["vorgaben"] == {"depth": 2, "maxResults": 31}
    assert "oeffnen" in m["faehigkeiten"]


def test_argumente_und_vorgaben_gibt_es_im_werkzeug_wirklich():
    """Drift-Wächter: die KI bekommt die Beschreibung des MCP-Werkzeugs — fehlt ein Argument dort,
    stünde ein Parameter ohne Beschreibung im Angebot."""
    from boerdi.api.schemas_mcp import CollectionTreeArgs
    from boerdi.services.mcp import faehigkeiten, sammlung_per_name

    m = _manifest_baum()
    [werkzeug] = [t for t in TOOL_DEFINITIONS if t["function"]["name"] == WERKZEUG]
    # N3: ``collection`` und ``discipline`` stehen in der Definition, sobald der Server sie kennt.
    faehigkeiten.uebernehmen([{"name": WERKZEUG,
                               "input_schema": {"properties": {"collection": {}}}}])
    props = sammlung_per_name.erweitert(werkzeug)["function"]["parameters"]["properties"]
    assert set(m["datenquelle"]["argumente"]) <= set(props)
    # … und der Client lässt sie durch (er filtert, was sein Argument-Modell nicht kennt).
    assert set(m["datenquelle"]["argumente"]) <= set(CollectionTreeArgs.model_fields)
    assert set(m["datenquelle"]["vorgaben"]) <= set(props)
    CollectionTreeArgs(**m["datenquelle"]["vorgaben"])        # gültig nach dem Argument-Modell


def test_drei_ebenen_passen_nicht_zur_eingabe():
    enkel = {"id": "x1", "titel": "Enkel"}
    daten = {"knoten": [{"id": "a1", "titel": "A", "kinder": [
        {"id": "b1", "titel": "B", "kinder": [enkel]}]}]}
    assert katalog.daten_fehler(_manifest_baum(), daten)


# ── e-3 Datenquelle: Knoten formen ────────────────────────────────────────


def test_aus_dem_werkzeug_ergebnis_werden_schlanke_knoten():
    daten = themenbaum.daten_aus(_payload(), titel="Mathe")

    assert daten.pop("wurzel_url").endswith("collections?id=aaaa-1111")   # Review U1-e, Befund 2
    assert daten.pop("entwurf_moeglich") is True       # U2: die Brücke zum Entwurf ist offen
    assert daten == {
        "titel": "Mathe", "wurzel_id": "aaaa-1111", "gekuerzt": True,
        "knoten": [
            {"id": "bbbb-2222", "titel": "Algebra",
             "url": "https://wirlernenonline.de/sammlung/bbbb-2222", "mehr": True,
             "kinder": [
                 {"id": "cccc-3333", "titel": "Gleichungen",
                  "url": "https://wirlernenonline.de/sammlung/cccc-3333", "anzahl": 12},
                 {"id": "dddd-4444", "titel": "Terme",
                  "url": "https://wirlernenonline.de/sammlung/dddd-4444"},
             ]},
            # Die Themenseite geht vor der Sammlungs-Adresse (wie im MCP-Widget).
            {"id": "eeee-5555", "titel": "Geometrie",
             "url": "https://wirlernenonline.de/geometrie/", "anzahl": 7},
        ]}
    assert not katalog.daten_fehler(_manifest_baum(), daten)
    assert "GEHEIM" not in json.dumps(daten)


def test_die_knoten_sind_gedeckelt_und_unsicheres_faellt_weg():
    viele_kinder = [_knoten(f"k{i:02d}-0000", f"Kind {i}") for i in range(15)]
    oben = [_knoten(f"o{i:02d}-0000", f"Thema {i}") for i in range(40)]
    oben[0]["children"] = viele_kinder
    oben[1]["title"] = "T" * 500
    oben[2]["url"] = "javascript:alert(1)"
    oben[3]["nodeId"] = "bad id mit leerzeichen"
    oben[4]["title"] = "   "
    daten = themenbaum.daten_aus(_payload(results=oben, truncated=False))

    knoten = daten["knoten"]
    assert len(knoten) == themenbaum.HOECHSTENS_OBEN == 30
    assert len(knoten[0]["kinder"]) == themenbaum.HOECHSTENS_KINDER == 10
    assert knoten[0]["mehr"] is True                       # gekürzt = sichtbar mehr
    assert daten["gekuerzt"] is True
    assert len(knoten[1]["titel"]) <= 200
    assert "url" not in knoten[2]
    assert all(k["id"] not in ("bad id mit leerzeichen",) for k in knoten)
    assert all(k["titel"].strip() for k in knoten)
    assert not katalog.daten_fehler(_manifest_baum(), daten)


@pytest.mark.parametrize("payload", [None, "text", {"results": "x"}, {"parent": 3, "results": []}])
def test_unbrauchbare_ergebnisse_ergeben_keinen_baum(payload):
    assert themenbaum.daten_aus(payload) is None


def test_die_textfassung_ist_eine_eingerueckte_linkliste():
    text = themenbaum.textfassung(themenbaum.daten_aus(_payload(), titel="Mathe"))
    assert text.splitlines() == [
        "**Mathe**",
        "",
        "- [Algebra](https://wirlernenonline.de/sammlung/bbbb-2222)",
        "  - [Gleichungen](https://wirlernenonline.de/sammlung/cccc-3333)",
        "  - [Terme](https://wirlernenonline.de/sammlung/dddd-4444)",
        "  - …",
        "- [Geometrie](https://wirlernenonline.de/geometrie/)",
    ]


# ── e-3/e-4 Aufruf mit Datenquelle ────────────────────────────────────────


class _Rufer:
    """`datenquelle._rufen` — hält die gesendeten Argumente fest, antwortet mit JSON-Text."""

    def __init__(self, text: str | None = None, art: str = ""):
        self.calls: list[tuple[str, dict]] = []
        self.text = json.dumps(_payload()) if text is None else text
        self.art = art

    async def __call__(self, werkzeug, args):
        self.calls.append((werkzeug, dict(args)))
        return self.text, self.art


@pytest.fixture
def rufer(monkeypatch):
    r = _Rufer()
    monkeypatch.setattr(datenquelle, "_rufen", r)
    return r


@pytest.mark.anyio
async def test_das_backend_ruft_das_werkzeug_mit_argumenten_und_festen_vorgaben(rufer):
    block, text, _outcome = await datenquelle.aufruf(THEMENBAUM, {
        "subject": "Mathe", "depth": 1, "includeContentPreview": 5, "maxResults": 100})

    # Nur die genannten Argumente; die Vorgaben überschreiben, was die KI sonst noch schickt.
    assert rufer.calls == [(WERKZEUG, {"subject": "Mathe", "depth": 2, "maxResults": 31})]
    assert block is not None and block.modul == THEMENBAUM and block.art == "anzeigen"
    assert block.daten["titel"] == "Mathe" and len(block.daten["knoten"]) == 2
    assert "Algebra" in block.text                         # Textfassung für alte Widgets


@pytest.mark.anyio
async def test_die_quittung_an_die_ki_nennt_keinen_knoten(rufer):
    """Nachweis U1-e: Anzahl und Ebenen ja, Titel und Kennungen nein."""
    _block, text, _outcome = await datenquelle.aufruf(THEMENBAUM, {"subject": "Mathe"})
    assert text.startswith("OK")
    assert "2" in text and "gekürzt" in text
    for teil in ALLE_KNOTEN:
        assert teil not in text


@pytest.mark.anyio
async def test_ohne_fach_und_sammlung_wird_nichts_gerufen(rufer):
    block, text, _outcome = await datenquelle.aufruf(THEMENBAUM, {"depth": 2})
    assert block is None and rufer.calls == []
    assert "subject" in text and "nodeId" in text


@pytest.mark.anyio
@pytest.mark.parametrize("args", [{"subject": 5}, {"nodeId": "x" * 300}, "kein-dict"])
async def test_falsche_argumente_werden_abgewiesen(rufer, args):
    block, text, _outcome = await datenquelle.aufruf(THEMENBAUM, args)
    assert block is None and rufer.calls == [] and text.startswith("Fehler")


@pytest.mark.anyio
@pytest.mark.parametrize("antwort,art", [("MCP error: Kein Fachportal für X", "tool"),
                                         ("kein json", ""), ('{"results": 1}', "")])
async def test_ein_fehler_des_werkzeugs_geht_ohne_fremdtext_an_die_ki(monkeypatch, antwort, art):
    monkeypatch.setattr(datenquelle, "_rufen", _Rufer(antwort, art))
    block, text, _outcome = await datenquelle.aufruf(THEMENBAUM, {"subject": "X"})
    assert block is None and text.startswith("Fehler")
    assert "Kein Fachportal" not in text


class _ErstFehler(_Rufer):
    """Der erste Aufruf scheitert mit ``art``, der zweite liefert den Baum."""

    def __init__(self, art: str):
        super().__init__()
        self.erste_art = art

    async def __call__(self, werkzeug, args):
        self.calls.append((werkzeug, dict(args)))
        if len(self.calls) == 1:
            return "MCP error: Fehler beim Sub-Sammlungs-Abruf: upstream 502", self.erste_art
        return self.text, ""


@pytest.mark.anyio
async def test_ein_werkzeugfehler_wird_einmal_wiederholt(monkeypatch):
    """Die Datenquelle liest nur: scheitert edu-sharing hinter dem MCP-Server kurz (kommt als
    ``tool``-Fehler an), hilft ein zweiter Versuch — der MCP-Client wiederholt nur Fehler ohne
    Serverantwort."""
    r = _ErstFehler("tool")
    monkeypatch.setattr(datenquelle, "_rufen", r)
    block, _text, outcome = await datenquelle.aufruf(THEMENBAUM, {"subject": "Physik"})
    assert block is not None and len(r.calls) == 2 and outcome.status == "success"


@pytest.mark.anyio
@pytest.mark.parametrize("art", ["timeout", "auth", "transport"])
async def test_frist_anmeldung_und_verbindung_werden_nicht_noch_einmal_versucht(monkeypatch, art):
    """Eine Frist hinge doppelt so lang, ein abgewiesener Zugang bliebe abgewiesen, und
    Verbindungsfehler wiederholt der MCP-Client schon selbst."""
    r = _ErstFehler(art)
    monkeypatch.setattr(datenquelle, "_rufen", r)
    block, _text, _outcome = await datenquelle.aufruf(THEMENBAUM, {"subject": "Physik"})
    assert block is None and len(r.calls) == 1


@pytest.mark.anyio
async def test_ein_leerer_baum_ist_ein_block_mit_leerzustand(monkeypatch):
    monkeypatch.setattr(datenquelle, "_rufen",
                        _Rufer(json.dumps(_payload(results=[], total=0, truncated=False))))
    block, text, _outcome = await datenquelle.aufruf(THEMENBAUM, {"nodeId": "aaaa-1111"})
    assert block is not None and block.daten["knoten"] == []
    assert block.daten["wurzel_id"] == "aaaa-1111"
    assert "keine Unterthemen" in text


@pytest.mark.anyio
async def test_der_echte_rufweg_geht_ueber_den_mcp_client(monkeypatch):
    """`_rufen` selbst: über `call_mcp_tool_status` (Prüfung, Auflösung, Cache, Zugakte)."""
    from boerdi.services.mcp import client

    gesehen = []

    async def _status(name, args, **_kw):
        gesehen.append((name, args))
        return json.dumps(_payload()), ""

    monkeypatch.setattr(client, "call_mcp_tool_status", _status)
    block, _text, _outcome = await datenquelle.aufruf(THEMENBAUM, {"nodeId": "aaaa-1111"})
    assert gesehen == [(WERKZEUG, {"nodeId": "aaaa-1111", "depth": 2, "maxResults": 31})]
    assert block is not None


# ── e-4 Werkzeug aus dem Manifest ─────────────────────────────────────────


def test_die_ki_sieht_nur_fach_und_sammlung_als_parameter():
    [werkzeug] = modul_werkzeuge([THEMENBAUM], verfuegbar={WERKZEUG}, fuer="agent")
    f = werkzeug["function"]
    assert f["name"] == THEMENBAUM
    assert set(f["parameters"]["properties"]) == {"subject", "nodeId"}
    assert "depth" not in json.dumps(f["parameters"])
    assert "Unterthemen" in f["description"]


@pytest.mark.parametrize("verfuegbar", [None, set(), {"search_wlo_all"}])
def test_ohne_verfuegbares_werkzeug_kein_themenbaum(verfuegbar):
    """Eine Sperre auf `browse_collection_tree` darf das Modul nicht umgehen (E-3)."""
    assert modul_werkzeuge([THEMENBAUM], verfuegbar=verfuegbar, fuer="agent") == []


def test_module_ohne_datenquelle_brauchen_kein_verfuegbares_werkzeug():
    assert [t["function"]["name"] for t in modul_werkzeuge(["ui_entscheidung"], fuer="agent")] == [
        "ui_entscheidung"]


# ── e-5 Agent-Schleife ────────────────────────────────────────────────────


def test_der_agent_bekommt_den_baum_ohne_dass_knoten_durchs_modell_laufen(monkeypatch, rufer):
    """Nachweis U1-e im Lauf: der Block trägt die Knoten, keine Nachricht an das Modell."""
    out = _OutcomeFake()
    fake, run, msgs = _lauf(monkeypatch, [
        _resp_tools([_tool_call(THEMENBAUM, {"subject": "Mathe"})]),
        _resp_text("Hier sind die Themen in Mathe."),
    ], outcome=out)

    assert run.stop_reason == "text" and run.text == "Hier sind die Themen in Mathe."
    [block] = run.ui_bloecke
    assert block.modul == THEMENBAUM and len(block.daten["knoten"]) == 2
    assert out.calls == []                        # nicht der allgemeine MCP-Weg (keine Karten)
    assert run.tools_called == [THEMENBAUM]           # Review U1-e, Befund 6: protokolliert
    an_das_modell = json.dumps(msgs, ensure_ascii=False, default=str)
    for teil in ALLE_KNOTEN:
        assert teil not in an_das_modell


def test_nicht_angeboten_ruft_der_themenbaum_nichts(monkeypatch, rufer):
    _fake, run, msgs = _lauf(monkeypatch, [
        _resp_tools([_tool_call(THEMENBAUM, {"subject": "Mathe"})]),
        _resp_text("ok"),
    ], tools=["search_wlo_all"])
    assert run.ui_bloecke == [] and rufer.calls == []
    assert [m["content"] for m in msgs if m.get("role") == "tool"] == [NICHT_ANGEBOTEN]


def test_ein_fehler_der_datenquelle_geht_an_die_ki_und_der_lauf_geht_weiter(monkeypatch):
    monkeypatch.setattr(datenquelle, "_rufen", _Rufer("MCP error: weg", "transport"))
    _fake, run, msgs = _lauf(monkeypatch, [
        _resp_tools([_tool_call(THEMENBAUM, {"subject": "Mathe"})]),
        _resp_text("Der Baum ging nicht."),
    ])
    assert run.stop_reason == "text" and run.ui_bloecke == []
    [fehler] = [m["content"] for m in msgs if m.get("role") == "tool"]
    assert fehler.startswith("Fehler")


def test_der_agent_bietet_den_themenbaum_nur_mit_verfuegbarem_werkzeug():
    from boerdi.services.agent_tools import build_agent_tools

    def _namen(tools):
        return {t["function"]["name"] for t in tools}

    assert THEMENBAUM in _namen(build_agent_tools(ui_module=[THEMENBAUM]))
    assert THEMENBAUM not in _namen(build_agent_tools(ui_module=[THEMENBAUM],
                                                      blocked_tools=[WERKZEUG]))


def test_das_frontend_manifest_ist_die_quelle():
    """Kopie = Quelle (wie für die anderen Module, hier ausdrücklich für den neuen Ordner)."""
    quelle = (Path(__file__).resolve().parents[2] / "frontend" / "projects" / "ui-module" / "src"
              / "ui-themenbaum" / "manifest.json")
    assert json.loads(quelle.read_text(encoding="utf-8")) == _manifest_baum()
