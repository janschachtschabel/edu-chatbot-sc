"""Die zwei Zahlen der Kontext-Bestätigung (2026-08-14).

Nutzer-Vorgabe: die Begrüßung soll ZEIGEN, dass der Kontext angekommen ist —
Anzahl der Materialien und Anzahl der freigegebenen Anleitungen, statt es nur
zu behaupten. Beide Werkzeuge gibt es bereits; neu ist die Zusammenfassung.

Die Antwortformen unten sind am echten Server gemessen (Sammlung „Optik",
2026-08-14), nicht erfunden: ``get_collection_stats`` liefert ``fileCount``
flach, ``get_skill_registry`` seine Einträge unter ``registry.entries``.

MCP an der Boundary gefakt — NEU-Konvention ``setattr(module, 'call_mcp_tool')``.
"""

from __future__ import annotations

import asyncio
import json
import time

import pytest

from boerdi.services import context_facts as cf
from boerdi.services.page_context import MAX_SKILL_ENTRIES

_STATS = json.dumps({
    "nodeId": "9e7ae956", "title": "Optik",
    "fileCount": 35, "subCollectionCount": 4, "sampledFiles": 35,
    "breakdown": {"discipline": [{"label": "Physik", "count": 32}]},
})
_REGISTRY = json.dumps({
    "registry": {
        "collectionId": "9e7ae956",
        "registryTitle": "Skillkatalog Physik Optik",
        "entries": [{"nodeId": f"n{i}", "title": f"Skill {i}"} for i in range(28)],
    },
    "reason": None,
})


def _fake(antworten: dict[str, str | Exception], *, spur: list | None = None):
    async def _call(tool_name: str, arguments: dict):
        if spur is not None:
            spur.append(("start", tool_name))
        await asyncio.sleep(0)  # ein Umschaltpunkt, damit Nebenläufigkeit sichtbar wird
        if spur is not None:
            spur.append(("ende", tool_name))
        wert = antworten.get(tool_name)
        if isinstance(wert, Exception):
            raise wert
        if wert is None:
            raise AssertionError(f"unerwartetes Werkzeug: {tool_name}")
        return wert
    return _call


def _lauf(monkeypatch, antworten, *, spur=None):
    monkeypatch.setattr(cf, "call_mcp_tool", _fake(antworten, spur=spur))
    return asyncio.run(cf.collect_context_facts("9e7ae956"))


def test_beide_zahlen_kommen_aus_den_gemessenen_antwortformen(monkeypatch):
    fakten = _lauf(monkeypatch, {
        "get_collection_stats": _STATS,
        "get_skill_registry": _REGISTRY,
    })
    assert fakten["materials"] == 35
    assert fakten["sub_collections"] == 4
    assert fakten["skills"] == 28


def test_die_skill_titel_kommen_als_uebersicht(monkeypatch):
    """Nutzer-Vorgabe 2026-08-14: „nur die Übersicht der skill registry",
    höchstens eine A4-Seite.

    Deshalb TITEL und keine ``nodeId``: gemessen an der echten Registry passen
    100 Titel auf eine A4-Seite (3 361 Zeichen), 100 Titel mit ID nicht
    (7 161). Den Volltext holt das Modell gezielt über ``get_skill_registry`` →
    ``get_skill``, nicht aus diesem Block — die ``nodeId``, die hier fehlt,
    liefert der erste der beiden Schritte nach."""
    fakten = _lauf(monkeypatch, {
        "get_collection_stats": _STATS,
        "get_skill_registry": _REGISTRY,
    })
    assert fakten["skill_titles"][:2] == ["Skill 0", "Skill 1"]
    assert len(fakten["skill_titles"]) == 28


def test_ein_ausfall_kostet_nur_seine_eigene_zahl(monkeypatch):
    # Die Begrüßung ist das ERSTE, was jemand sieht — sie darf nicht daran
    # hängen, dass beide Werkzeuge antworten.
    fakten = _lauf(monkeypatch, {
        "get_collection_stats": _STATS,
        "get_skill_registry": RuntimeError("MCP weg"),
    })
    assert fakten == {"materials": 35, "sub_collections": 4}


def test_unlesbare_antworten_geben_gar_keine_zahl_und_werfen_nicht(monkeypatch):
    assert _lauf(monkeypatch, {
        "get_collection_stats": "kein json",
        "get_skill_registry": "<html>Fehlerseite</html>",
    }) == {}


def test_ohne_sammlung_wird_nichts_abgerufen(monkeypatch):
    gerufen: list[str] = []

    async def _call(tool_name: str, arguments: dict):
        gerufen.append(tool_name)
        return "{}"

    monkeypatch.setattr(cf, "call_mcp_tool", _call)
    assert asyncio.run(cf.collect_context_facts("  ")) == {}
    assert gerufen == []


def test_die_beiden_abrufe_laufen_nebeneinander(monkeypatch):
    """Nicht nacheinander — sonst wartet die Begrüßung auf die SUMME.

    Geprüft an der Verschränkung statt an einer Uhr: beide Aufrufe müssen
    begonnen haben, bevor der erste endet. Ein serieller Aufbau ergäbe
    start/ende/start/ende.
    """
    spur: list = []
    _lauf(monkeypatch, {
        "get_collection_stats": _STATS,
        "get_skill_registry": _REGISTRY,
    }, spur=spur)
    assert [s for s, _ in spur[:2]] == ["start", "start"], spur


def test_ein_haengendes_werkzeug_haelt_die_begruessung_nicht_auf(monkeypatch):
    """Der Deckel. Ohne ihn wartet die erste Nachricht auf ein langsames
    Repository — genau dort, wo Wartezeit am meisten auffällt."""
    async def _call(tool_name: str, arguments: dict):
        if tool_name == "get_skill_registry":
            await asyncio.sleep(30)
        return _STATS

    monkeypatch.setattr(cf, "call_mcp_tool", _call)
    monkeypatch.setattr(cf, "DEADLINE", 0.05)
    fakten = asyncio.run(cf.collect_context_facts("9e7ae956"))
    assert fakten == {"materials": 35, "sub_collections": 4}


@pytest.mark.parametrize("roh", ['{"fileCount": "35"}', '{"fileCount": -1}', "[]"])
def test_unsinnige_zahlen_werden_verworfen(monkeypatch, roh):
    # Der Server ist fremd beschrieben; eine Zahl, die keine ist, gehört nicht
    # in einen Satz, der Verlässlichkeit behauptet.
    fakten = _lauf(monkeypatch, {
        "get_collection_stats": roh,
        "get_skill_registry": _REGISTRY,
    })
    assert "materials" not in fakten
    assert fakten["skills"] == 28


# ── Die Naht zum MCP-Client (Live-Befund 2026-08-14) ─────────────────────


def test_das_json_format_ueberlebt_die_argument_pruefung():
    """Ohne diese Zusicherung liefern beide Werkzeuge MARKDOWN — und ``collect_
    context_facts`` bekam nie eine Zahl.

    Gemessen an der Live-Instanz: die Argument-Modelle sind Pydantic und werfen
    unbekannte Felder still weg. ``outputFormat`` reiste also gar nicht mit, der
    Server antwortete in seinem Vorgabeformat, ``json.loads`` scheiterte, und
    die Begrüßung blieb ohne Zahlen — ohne dass irgendwo ein Fehler stand.

    ``call_mcp_tool`` setzt das Format sonst zentral (``_JSON_CAPABLE_TOOLS``);
    diese beiden stehen dort bewusst NICHT drin, weil der Agent-Vorabruf die
    Registry als lesbares Markdown zeigt. Deshalb der Weg über das Argument.
    """
    from boerdi.services.mcp.tool_args import validate_tool_args

    for name, args in (
        ("get_collection_stats", {"nodeId": "n1"}),
        ("get_skill_registry", {"collectionId": "c1"}),
    ):
        gewuenscht = validate_tool_args(name, {**args, "outputFormat": "json"})
        assert gewuenscht.get("outputFormat") == "json", f"{name}: json fällt weg"
        vorgabe = validate_tool_args(name, dict(args))
        assert vorgabe.get("outputFormat") == "markdown", f"{name}: Vorgabe verschoben"


def test_der_katalog_wird_schon_beim_sammeln_gekappt(monkeypatch):
    """Review-Befund 2026-08-14: der Deckel sass nur im Renderer.

    ``session_state['entities']`` wird je Zug als jsonb geschrieben
    (``turn_persist.py:222``). Alles zu speichern, was nie gerendert wird, ist
    Schreiblast ohne Gegenwert: 500 Titel sind als JSON gemessene **15,5 kB**
    je Zug (31,8 Bytes je Eintrag). (Hier stand zunächst 45 kB — nachgemessen
    45,8 kB, aber für die ALTE Form mit ``nodeId``, 94 Bytes je Eintrag; sie
    stimmte also für ihre Form und wurde nur beim Umbau nicht mitgezogen.)
    Der Deckel ist derselbe wie im Renderer — importiert, nicht abgeschrieben.

    ``skills`` bleibt die WAHRE Zahl, sonst stimmte „… und N weitere" nicht.
    """
    gross = json.dumps({"registry": {"entries": [
        {"nodeId": f"n{i}", "title": f"Skill {i}"} for i in range(200)]}})
    fakten = _lauf(monkeypatch, {
        "get_collection_stats": _STATS,
        "get_skill_registry": gross,
    })
    assert fakten["skills"] == 200
    assert len(fakten["skill_titles"]) == MAX_SKILL_ENTRIES
    assert fakten["skill_titles"][0] == "Skill 0"


# ── retry_due: der Leer-Vermerk (Review-Befund 2026-08-14, 2. Runde) ───────


def test_ohne_fakten_ist_der_abruf_faellig():
    assert cf.retry_due(None) is True
    assert cf.retry_due({}) is True
    assert cf.retry_due("kaputt") is True


def test_echte_fakten_loesen_keinen_neuen_abruf_aus():
    assert cf.retry_due({"materials": 35, "skills": 28}) is False


def test_ein_frischer_vermerk_haelt_die_ruhezeit():
    assert cf.retry_due(cf.empty_marker()) is False


def test_ein_abgelaufener_vermerk_gibt_wieder_frei():
    alt = {cf.EMPTY_MARKER: time.time() - cf.EMPTY_RETRY_SECONDS - 1}
    assert cf.retry_due(alt) is True


def test_ein_zeitstempel_aus_der_zukunft_blockiert_nicht(monkeypatch):
    """Review-Befund: ``time.time() - zukunft`` ist NEGATIV, und negativ ist nie
    ``>= EMPTY_RETRY_SECONDS`` — der Vermerk hielte dann, bis die Wanduhr
    aufgeholt hat.

    Auslöser wären eine rückwärts gestellte Uhr oder Zeitversatz zwischen
    Replikaten. Ein Zeitstempel aus der Zukunft ist kein junger Vermerk, sondern
    ein kaputter, und wird wie ein unlesbarer behandelt: neu abrufen.
    """
    zukunft = {cf.EMPTY_MARKER: time.time() + 10_000}
    assert cf.retry_due(zukunft) is True


def test_ein_unlesbarer_zeitstempel_gibt_frei():
    assert cf.retry_due({cf.EMPTY_MARKER: "gestern"}) is True
    assert cf.retry_due({cf.EMPTY_MARKER: None}) is True
