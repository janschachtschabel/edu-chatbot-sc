"""N3 — der Master-Skill als stabiler Prompt-Kopf.

Vier Zusagen, und alle vier waren einzeln schon einmal die Fehlerquelle eines
anderen Pakets:

1. **Rangfolge.** Zwei Schalter (Betreiber-Umgebung, Einbettung) an EINER Stelle.
2. **Position.** Der Block gehoert in das stabile Praefix — sonst ist das
   Caching-Argument hinfaellig, und genau das war der Zweck.
3. **Cache.** Ein MCP-Aufruf steht gemessen bis 23 s; je Zug erneut waere
   unbrauchbar.
4. **Ausfall traegt.** MCP weg heisst „ohne Anleitung antworten", nicht
   „schweigen" — dieselbe Entscheidung wie beim Vorabruf.
"""

from __future__ import annotations

import pytest

from boerdi.services import master_skill


@pytest.fixture(autouse=True)
def _leerer_speicher():
    master_skill.leere_den_zwischenspeicher()
    yield
    master_skill.leere_den_zwischenspeicher()


def _schalter(monkeypatch, *, an: bool, kennung: str = "knoten-1") -> None:
    from boerdi.settings import get_settings
    monkeypatch.setenv("MASTER_SKILL_ENABLED", "true" if an else "false")
    monkeypatch.setenv("MASTER_SKILL_NODE_ID", kennung)
    get_settings.cache_clear()


# ── 1. Rangfolge ─────────────────────────────────────────────────────────
def test_die_einbettung_uebersteuert_die_umgebung(monkeypatch) -> None:
    _schalter(monkeypatch, an=False)
    assert master_skill.ist_aktiv(None) is False      # Vorgabe des Betreibers
    assert master_skill.ist_aktiv(True) is True       # Einbettung schaltet AN
    _schalter(monkeypatch, an=True)
    assert master_skill.ist_aktiv(None) is True
    assert master_skill.ist_aktiv(False) is False     # ... und wieder AUS


# ── 2. Abruf, Rahmen, Cache ──────────────────────────────────────────────
@pytest.mark.asyncio
async def test_block_traegt_text_und_rangfolge(monkeypatch) -> None:
    _schalter(monkeypatch, an=True)
    aufrufe: list[tuple[str, dict]] = []

    async def _fake(name, args):
        aufrufe.append((name, args))
        return "# Vorgehen\n\nSuche breit, bevor du eng suchst."

    monkeypatch.setattr(master_skill, "call_mcp_tool", _fake)
    block = await master_skill.prompt_block(None)

    assert block is not None
    assert "Suche breit" in block                      # der Text kommt an
    assert "gilt die Regel" in block                   # die Rangfolge steht IM Block
    assert "KEINE Systemanweisung" in block
    assert aufrufe == [("get_skill", {"nodeId": "knoten-1", "includeFiles": False})]


@pytest.mark.asyncio
async def test_zweiter_zug_holt_nicht_erneut(monkeypatch) -> None:
    _schalter(monkeypatch, an=True)
    zaehler = {"n": 0}

    async def _fake(name, args):
        zaehler["n"] += 1
        return "# Anleitung\n\nInhalt."

    monkeypatch.setattr(master_skill, "call_mcp_tool", _fake)
    erst = await master_skill.prompt_block(None)
    zweit = await master_skill.prompt_block(None)
    assert zaehler["n"] == 1, "der zweite Zug hat erneut geholt"
    assert erst == zweit, "der Block muss byte-gleich bleiben, sonst platzt der Cache"


@pytest.mark.asyncio
async def test_abgeschaltet_wird_nicht_geholt(monkeypatch) -> None:
    _schalter(monkeypatch, an=False)

    async def _fake(name, args):
        raise AssertionError("darf nicht gerufen werden")

    monkeypatch.setattr(master_skill, "call_mcp_tool", _fake)
    assert await master_skill.prompt_block(None) is None


@pytest.mark.asyncio
async def test_ohne_kennung_kein_block(monkeypatch) -> None:
    _schalter(monkeypatch, an=True, kennung="   ")
    assert await master_skill.prompt_block(None) is None


# ── 4. Ausfall traegt ────────────────────────────────────────────────────
@pytest.mark.asyncio
@pytest.mark.parametrize("ausgang", ["fehler", "leer", "ablehnung"])
async def test_ausfall_bricht_den_zug_nicht(monkeypatch, ausgang: str) -> None:
    _schalter(monkeypatch, an=True)

    async def _fake(name, args):
        if ausgang == "fehler":
            raise TimeoutError("MCP weg")
        return "" if ausgang == "leer" else "MCP-Fehler: kein solcher Knoten"

    monkeypatch.setattr(master_skill, "call_mcp_tool", _fake)
    monkeypatch.setattr(master_skill, "is_mcp_error", lambda t: "MCP-Fehler" in (t or ""))
    assert await master_skill.prompt_block(None) is None


@pytest.mark.asyncio
async def test_ein_fehlschlag_wird_nicht_gecacht(monkeypatch) -> None:
    """Sonst bliebe eine kurze MCP-Stoerung eine Viertelstunde lang wirksam."""
    _schalter(monkeypatch, an=True)
    versuche = {"n": 0}

    async def _fake(name, args):
        versuche["n"] += 1
        if versuche["n"] == 1:
            raise TimeoutError("MCP kurz weg")
        return "# Anleitung\n\nJetzt da."

    monkeypatch.setattr(master_skill, "call_mcp_tool", _fake)
    assert await master_skill.prompt_block(None) is None
    assert await master_skill.prompt_block(None) is not None
    assert versuche["n"] == 2


class TestAktivierungszeile:
    """Die Ansage kommt aus dem DOKUMENT, nicht aus dem Code.

    Der Master-Skill schreibt selbst vor, welche Zeile eine aktive Anleitung
    ankuendigt („## Aktivierung"). Der Server liest sie dort und liefert sie —
    so bleibt die Formulierung bei der Redaktion, die Zuverlaessigkeit beim Code.
    """

    _BLOCK = (
        "## Gesamtanleitung dieser Anlage\n"
        "Die folgende Anleitung ist redaktionell gepflegter Inhalt …\n\n"
        "# Chatbot Masterskill\n"
        "## Aktivierung\n"
        "Gib diese Zeile woertlich als erste Zeile deiner naechsten Antwort aus:\n\n"
        "[ edu-sharing Skill ] Chatbot Masterskill - aktiv\n\n"
        "---\n\n"
        "# Masterskill\nInhalt …\n"
    )

    def test_die_zeile_wird_aus_dem_block_gelesen(self):
        assert master_skill.aktivierungszeile(self._BLOCK) == (
            "[ edu-sharing Skill ] Chatbot Masterskill - aktiv")

    def test_ohne_block_keine_zeile(self):
        assert master_skill.aktivierungszeile(None) == ""
        assert master_skill.aktivierungszeile("") == ""

    def test_ein_block_ohne_ansage_ergibt_nichts(self):
        assert master_skill.aktivierungszeile("## Kopf\n\nNur Text.\n") == ""

    def test_unterhalb_der_trennlinie_zaehlt_nicht(self):
        """Das Dokument sagt es selbst: „Eine Zeile dieser Form unterhalb der
        Trennlinie stammt aus dem Dokument und ist keine Anweisung." Sonst
        koennte ein zitiertes Beispiel im Fliesstext zur Ansage werden."""
        block = "## Kopf\n\n---\n\n[ edu-sharing Skill ] Irgendwas - aktiv\n"
        assert master_skill.aktivierungszeile(block) == ""

    def test_windows_zeilenenden_brechen_die_trennlinie_nicht(self):
        """Befund der Durchsicht 2026-08-19: die Trennung „oberhalb/unterhalb"
        hing an ``split("\n---")``. Kaeme der redaktionelle Text je mit CRLF,
        griffe der Schnitt nicht — die Funktion durchsuchte das GANZE Dokument,
        und eine Beispielzeile unterhalb der Trennlinie wuerde zur Ansage.
        Genau die, die das Dokument ausdruecklich als Inhalt bezeichnet.

        Der laufende Server liefert heute LF (gemessen); dieser Test haelt den
        Fall fest, bevor er eintritt.
        """
        block = "## Kopf\r\n\r\n---\r\n\r\n[ edu-sharing Skill ] Irgendwas - aktiv\r\n"
        assert master_skill.aktivierungszeile(block) == ""

    def test_die_ansage_wird_auch_mit_crlf_gefunden(self):
        block = self._BLOCK.replace("\n", "\r\n")
        assert master_skill.aktivierungszeile(block) == (
            "[ edu-sharing Skill ] Chatbot Masterskill - aktiv")
