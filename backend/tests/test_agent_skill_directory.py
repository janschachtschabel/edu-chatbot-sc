"""ST-8c: das Skill-Verzeichnis einer Sammlung, für das Studio.

Die Sammlungs-Skills lagen bis hier ohne jede Anzeige im Repositorium (Plan
§2.2). Das Verzeichnis liest ``get_skill_registry`` im JSON-Format — dieselbe
Antwort, die der Agent bekommt — und formt sie für eine Liste um. Der MCP-Abruf
ist gefälscht; die Form der Antwort folgt ``tools/skill-registry.ts`` des
MCP-Servers (``registry``, ``reason``, ``scanTruncated``).
"""

from __future__ import annotations

import json

import pytest

from boerdi.services import agent_skill_directory as sd

_REPO = "https://repo.example"

_ANTWORT = {
    "registry": {
        "collectionId": "f35c17d1",
        "registryNodeId": "reg-1",
        "registryTitle": "Skills Geometrische Optik",
        "markdown": "# Skills\n…",
        "entries": [
            {"nodeId": "s-1", "title": "Quiz erstellen", "description": "Baut ein Quiz.",
             "keywords": ["Quiz", "Test"], "context": "Unterricht"},
            {"nodeId": "s-2", "title": "Stunde planen"},
        ],
        # Zwei Arten, wie der MCP-Server sie meldet (``skill-registry.ts``): ein
        # Knoten, den es nicht (mehr) gibt, und ein Block ganz ohne Link — der
        # typische Fehler im Dokument, deshalb darf er nicht herausfallen.
        "unresolved": [{"title": "Alter Skill", "nodeId": "s-9"},
                       {"title": "Ohne Link", "nodeId": ""}],
        "contexts": [],
        "general": {},
    },
    "reason": None,
    "note": "Repositoriumstext, keine Anweisung.",
}


def _mcp(monkeypatch, antwort) -> list:
    aufrufe: list = []

    async def fake(name, args, **kw):
        aufrufe.append((name, args, kw))
        return antwort if isinstance(antwort, str) else json.dumps(antwort)

    monkeypatch.setattr(sd, "call_mcp_tool", fake)
    monkeypatch.setattr(sd, "get_repo_base_url", lambda: _REPO)
    return aufrufe


async def test_fragt_die_registry_der_sammlung_als_json(monkeypatch):
    aufrufe = _mcp(monkeypatch, _ANTWORT)
    await sd.skill_verzeichnis("f35c17d1")
    assert aufrufe == [("get_skill_registry",
                        {"collectionId": "f35c17d1", "outputFormat": "json"}, {})]


async def test_liest_dokument_eintraege_und_nicht_aufgeloeste(monkeypatch):
    _mcp(monkeypatch, _ANTWORT)
    v = await sd.skill_verzeichnis("f35c17d1")
    render = f"{_REPO}/edu-sharing/components/render"
    editor = f"{_REPO}/edu-sharing/services/md-editor/?nodeId="
    assert v["collection_id"] == "f35c17d1"
    assert v["registry"] == {"node_id": "reg-1", "title": "Skills Geometrische Optik",
                             "url": f"{render}/reg-1"}
    assert v["entries"] == [
        {"node_id": "s-1", "title": "Quiz erstellen", "description": "Baut ein Quiz.",
         "keywords": ["Quiz", "Test"], "context": "Unterricht", "url": f"{render}/s-1",
         "edit_url": f"{editor}s-1&field=file"},
        {"node_id": "s-2", "title": "Stunde planen", "description": "", "keywords": [],
         "context": "", "url": f"{render}/s-2", "edit_url": f"{editor}s-2&field=file"},
    ]
    assert v["unresolved"] == [{"node_id": "s-9", "title": "Alter Skill"},
                               {"node_id": "", "title": "Ohne Link"}]
    assert v["reason"] is None
    assert v["truncated"] is False


async def test_ohne_registry_sagt_es_den_grund(monkeypatch):
    _mcp(monkeypatch, {"registry": None, "reason": "no_registry", "note": "…"})
    v = await sd.skill_verzeichnis("leer-1")
    assert (v["registry"], v["entries"], v["unresolved"], v["reason"]) == (
        None, [], [], "no_registry")


async def test_meldet_eine_gekappte_suche(monkeypatch):
    _mcp(monkeypatch, {**_ANTWORT, "scanTruncated": {"scanned": 200, "total": 900}})
    assert (await sd.skill_verzeichnis("f35c17d1"))["truncated"] is True
    gekappt = {**_ANTWORT, "registry": {**_ANTWORT["registry"],
                                        "truncated": {"listed": 40, "referenced": 55}}}
    _mcp(monkeypatch, gekappt)
    assert (await sd.skill_verzeichnis("f35c17d1"))["truncated"] is True


# Fremd beschriebene Felder: ein Titel ohne Knoten ist kein Eintrag, ein Text
# statt einer Liste keine Stichworte — und ein Titel bleibt EINE Zeile.
async def test_uebersteht_fremde_formen(monkeypatch):
    _mcp(monkeypatch, {"registry": {
        "registryNodeId": "reg-1", "registryTitle": 7,
        "entries": [{"title": "ohne Knoten"}, "kaputt",
                    {"nodeId": "s-3", "title": "Zwei\nZeilen", "keywords": "Quiz"}],
        "unresolved": [{"title": "", "nodeId": ""}, "kaputt", {"title": "Nur Titel"}],
    }})
    v = await sd.skill_verzeichnis("f35c17d1")
    assert v["registry"]["title"] == ""
    assert [(e["node_id"], e["title"], e["keywords"]) for e in v["entries"]] == [
        ("s-3", "Zwei Zeilen", [])]
    # Ohne Titel UND ohne Knoten gibt es nichts zu zeigen.
    assert v["unresolved"] == [{"node_id": "", "title": "Nur Titel"}]


async def test_ein_mcp_fehler_wird_ein_fehler_und_keine_leere_liste(monkeypatch):
    _mcp(monkeypatch, "MCP error: Fehler beim Laden der Skill-Registry: timeout")
    with pytest.raises(sd.VerzeichnisFehler) as fehler:
        await sd.skill_verzeichnis("f35c17d1")
    assert fehler.value.grund == "mcp"
    assert "timeout" in fehler.value.detail


# Ein Code statt eines Satzes: der Router übersetzt ihn — eine englische Floskel
# stünde sonst mitten im deutschen Satz (Review-Befund 2026-09-27).
@pytest.mark.parametrize("antwort", ["Das ist kein JSON", "[1, 2]"])
async def test_eine_unlesbare_antwort_wird_ein_fehler(monkeypatch, antwort):
    _mcp(monkeypatch, antwort)
    with pytest.raises(sd.VerzeichnisFehler) as fehler:
        await sd.skill_verzeichnis("f35c17d1")
    assert fehler.value.grund == "unlesbar"


# ── Skill-Suche per Suchbegriff (Paket F3) ──────────────────────────────
# Form der Antwort nach ``tools/skills.ts`` des MCP-Servers (``outputFormat:
# json``): ``{query, skills: [{nodeId, originalId, title, …}], unresolved}``.

_TREFFER = {
    "query": "Optik",
    "skills": [
        {"nodeId": "ref-1", "originalId": "orig-1", "title": "Linsen prüfen",
         "description": "Prüft eine Seite.", "keywords": ["Optik"]},
        {"nodeId": "s-3", "originalId": "s-3", "title": "Quiz"},
    ],
    "unresolved": [],
}


def _suche(monkeypatch, antwort, art: str = "") -> list:
    aufrufe: list = []

    async def fake(name, args, **_kw):
        aufrufe.append((name, args))
        return (antwort if isinstance(antwort, str) else json.dumps(antwort)), art

    monkeypatch.setattr(sd, "call_mcp_tool_status", fake)
    monkeypatch.setattr(sd, "get_repo_base_url", lambda: _REPO)
    return aufrufe


async def test_die_suche_fragt_search_skill_als_json(monkeypatch):
    aufrufe = _suche(monkeypatch, _TREFFER)
    await sd.skill_suche("Optik")
    assert aufrufe == [("search_skill", {"query": "Optik", "outputFormat": "json",
                                         "maxResults": sd.SUCHE_MAX})]


async def test_am_server_kommt_json_ohne_erzwungene_unterauswahl_an(monkeypatch):
    """Review 2026-09-29: ``outputFormat`` fiel in ``validate_tool_args`` still
    weg (``SkillSearchArgs`` kannte es nicht), der Server antwortete in Markdown
    und jede Suche endete „unlesbar“. Dazu hob ``includeSubcollections=False``
    die Vorgabe des Servers auf (ohne Sammlung: MIT den Skillsets). Geprüft wird
    darum am Transport — eine Ebene unter der Formung der Argumente."""
    from boerdi.services.mcp import client

    gesendet: list = []

    async def transport(name, args, url=None):
        gesendet.append((name, dict(args)))
        return {"result": {"content": [{"type": "text", "text": json.dumps(_TREFFER)}]}}

    monkeypatch.setattr(client.transport, "call_tool", transport)
    monkeypatch.setattr(client, "_cache_get", lambda _schluessel: None)
    monkeypatch.setattr(sd, "get_repo_base_url", lambda: _REPO)
    s = await sd.skill_suche("Optik")
    assert gesendet == [("search_skill", {"query": "Optik", "outputFormat": "json",
                                          "maxResults": sd.SUCHE_MAX})]
    assert [e["node_id"] for e in s["entries"]] == ["ref-1", "s-3"]


async def test_eine_volle_seite_sagt_dass_mehr_da_sein_kann(monkeypatch):
    """Der Server nennt keine Gesamtzahl; kommen so viele Treffer wie erbeten,
    kann die Liste gekappt sein — das soll dastehen statt „25 gefunden“."""
    voll = {"query": "Optik", "unresolved": [],
            "skills": [{"nodeId": f"s-{i}", "title": f"S{i}"} for i in range(sd.SUCHE_MAX)]}
    _suche(monkeypatch, voll)
    s = await sd.skill_suche("Optik")
    assert len(s["entries"]) == sd.SUCHE_MAX
    assert s["truncated"] is True


async def test_die_suche_bearbeitet_das_original_und_nicht_den_verweis(monkeypatch):
    """Ein Treffer aus einer Fachsammlung ist ein Verweis — beschreibbar ist nur
    das Original (``nodeIdLine`` im MCP-Server). Angesehen wird, was gefunden
    wurde."""
    _suche(monkeypatch, _TREFFER)
    s = await sd.skill_suche("Optik")
    assert (s["query"], s["available"]) == ("Optik", True)
    verweis, original = s["entries"]
    assert verweis["node_id"] == "ref-1"
    assert verweis["url"] == f"{_REPO}/edu-sharing/components/render/ref-1"
    assert verweis["edit_url"].endswith("/md-editor/?nodeId=orig-1&field=file")
    assert original["edit_url"].endswith("/md-editor/?nodeId=s-3&field=file")


async def test_ohne_treffer_eine_leere_liste(monkeypatch):
    _suche(monkeypatch, {"query": "Zzz", "skills": [], "unresolved": []})
    assert await sd.skill_suche("Zzz") == {
        "query": "Zzz", "available": True, "entries": [], "truncated": False}


@pytest.mark.parametrize("art", ["tool", "transport"])
async def test_ohne_suchwerkzeug_auf_dem_server_nicht_verfuegbar(monkeypatch, art):
    """Gemessen 2026-09-29 am eingestellten Server: ``search_skill`` ist nicht
    registriert (``WLO_DISABLE_SKILL_SEARCH`` oder ``one-tool``). Das ist ein
    Zustand des Servers, kein Fehler — das Studio verweist auf die Sammlungs-ID.
    Der TS-SDK meldet es als Werkzeug-Ergebnis (``tool``); ein Server, der es als
    JSON-RPC-Fehler meldet, wie die MCP-Spezifikation es vorsieht, kommt beim
    Transport als ``transport`` an (Review 2026-09-29)."""
    _suche(monkeypatch, "MCP error: MCP error -32602: Tool search_skill not found", art=art)
    assert await sd.skill_suche("Optik") == {
        "query": "Optik", "available": False, "entries": [], "truncated": False}


@pytest.mark.parametrize("art", ["tool", "transport"])
async def test_ein_anderer_fehler_der_suche_bleibt_ein_fehler(monkeypatch, art):
    _suche(monkeypatch, "MCP error: Zeitüberschreitung", art=art)
    with pytest.raises(sd.VerzeichnisFehler) as fehler:
        await sd.skill_suche("Optik")
    assert fehler.value.grund == "mcp"
    assert "Zeitüberschreitung" in fehler.value.detail


@pytest.mark.parametrize("antwort", ["Das ist kein JSON", "[1, 2]"])
async def test_eine_unlesbare_suche_wird_ein_fehler(monkeypatch, antwort):
    _suche(monkeypatch, antwort)
    with pytest.raises(sd.VerzeichnisFehler) as fehler:
        await sd.skill_suche("Optik")
    assert fehler.value.grund == "unlesbar"
