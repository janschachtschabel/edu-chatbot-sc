"""Paket M3 (Plan 2026-11-07): Material anlegen und einsortieren in EINER Bestätigung.

Der gemeldete Fall (eine Wikipedia-Seite erschließen und in die Sammlung Optik legen) brauchte zwei
Abnahmen — anlegen, dann einsortieren — und prüfte Dubletten nur über die Volltextsuche. Der MCP
kann seit 2026-11-07 beides besser:

- ``wlo_create_content`` mit ``addToCollectionId`` nimmt den neuen Datensatz unter derselben
  Bestätigung in eine Sammlung auf;
- ``find_content_by_url`` sagt genau, ob es zu einer Adresse schon einen Datensatz gibt.
"""

from __future__ import annotations

import pathlib

import yaml

from boerdi.services.mcp.tool_args import validate_tool_args
from boerdi.services.mcp.tool_defs import TOOL_DEFINITIONS
from boerdi.services.mcp.tool_defs_curation import CURATION_TOOL_DEFINITIONS

_SEEDS = pathlib.Path(__file__).parents[1] / "seeds"


def _def(name: str) -> dict:
    alle = [*TOOL_DEFINITIONS, *CURATION_TOOL_DEFINITIONS]
    return next(d["function"] for d in alle if d["function"]["name"] == name)


def _muster(datei: str) -> dict:
    roh = next((_SEEDS / "03-patterns").glob(datei)).read_text(encoding="utf-8")
    return yaml.safe_load(roh.split("---")[1])


def test_anlegen_nimmt_die_sammlung_mit():
    out = validate_tool_args("wlo_create_content", {"title": "Brechung", "url": "https://x.de",
                                                    "addToCollectionId": "c-optik"})
    assert out["addToCollectionId"] == "c-optik"
    props = _def("wlo_create_content")["parameters"]["properties"]
    assert "addToCollectionId" in props
    assert "derselben" in props["addToCollectionId"]["description"]


def test_ohne_sammlung_reist_das_feld_nicht_mit():
    out = validate_tool_args("wlo_create_content", {"title": "Brechung"})
    assert "addToCollectionId" not in out


def test_dubletten_per_adresse():
    fn = _def("find_content_by_url")
    assert fn["parameters"]["required"] == ["urls"]
    out = validate_tool_args("find_content_by_url",
                             {"urls": [f"https://x.de/{i}" for i in range(25)],
                              "includeCollections": True})
    assert len(out["urls"]) == 20 and out["includeCollections"] is True


def test_das_server_register_und_die_muster_kennen_die_werkzeuge():
    server = yaml.safe_load((_SEEDS / "05-knowledge" / "mcp-servers.yaml").read_text(
        encoding="utf-8"))
    alle = {w for s in server["servers"] for w in s.get("tools") or []}
    assert "find_content_by_url" in alle
    for datei in ("m18-*.md", "m20-*.md"):
        assert "find_content_by_url" in _muster(datei)["tools"], datei


def test_das_erschliessen_legt_mit_einer_bestaetigung_an():
    roh = next((_SEEDS / "03-patterns").glob("m20-*.md")).read_text(encoding="utf-8")
    assert "addToCollectionId" in roh and "find_content_by_url" in roh


# ── Review M3 ─────────────────────────────────────────────────────────────────────────────

def test_ueberlange_adressen_fallen_einzeln_weg():
    """Review M3, Befund 5: über 2000 Zeichen lehnte der Server den ganzen Aufruf ab."""
    out = validate_tool_args("find_content_by_url",
                             {"urls": ["https://x.de/" + "a" * 2100, "https://y.de"]})
    assert out["urls"] == ["https://y.de"]


def test_die_dublettenpruefung_kommt_nie_aus_dem_cache():
    """Review M3, Befund 3: direkt nach dem Anlegen stünde sonst „kein Datensatz“ im Cache."""
    from boerdi.services.mcp.tool_cache import _TOOL_CACHE_BLOCKLIST

    assert "find_content_by_url" in _TOOL_CACHE_BLOCKLIST


def test_das_einloesen_traegt_die_sammlung_bis_zum_server(monkeypatch):
    """Review M3, Befund 10: die gemerkten Angaben samt ``addToCollectionId`` gehen beim „ja“
    an den Server — sonst entstünde der Datensatz ohne Einsortieren."""
    import asyncio
    import time

    from boerdi.domain.write_confirm import remember_pending
    from boerdi.services import write_approval as wa_mod
    from boerdi.services.mcp.client import McpAntwort
    from tests.test_write_approval import _SESSION, _req, _Spy

    gerufen: list = []

    async def antwort(tool, args, **_k):
        gerufen.append((tool, dict(args)))
        return McpAntwort("Angelegt und aufgenommen.")

    monkeypatch.setattr(wa_mod, "call_mcp_tool_antwort", antwort)
    monkeypatch.setattr(wa_mod, "update_session", _Spy())
    monkeypatch.setattr(wa_mod, "save_message", _Spy())
    monkeypatch.setattr(wa_mod, "schreiben_erlaubt", lambda: True)
    angaben = {"title": "Brechung", "url": "https://de.wikipedia.org/wiki/Brechung",
               "addToCollectionId": "c-optik"}
    zustand = {"persona_id": "P-AND", "entities": {"_pending_write": remember_pending(
        "wlo_create_content", angaben, "Schluessel-0123456789abcd", now=time.time())}}
    asyncio.run(wa_mod.redeem_write_approval(_SESSION, _req(), zustand))
    [(tool, args)] = gerufen
    assert tool == "wlo_create_content" and args["addToCollectionId"] == "c-optik"
    assert args["confirmToken"] == "Schluessel-0123456789abcd"
