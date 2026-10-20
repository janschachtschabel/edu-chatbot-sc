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

import hashlib

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

    async def _fake(name, args, **_kw):
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

    async def _fake(name, args, **_kw):
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

    async def _fake(name, args, **_kw):
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

    async def _fake(name, args, **_kw):
        if ausgang == "fehler":
            raise TimeoutError("MCP weg")
        return "" if ausgang == "leer" else "MCP-Fehler: kein solcher Knoten"

    monkeypatch.setattr(master_skill, "call_mcp_tool", _fake)
    monkeypatch.setattr(master_skill, "is_mcp_error", lambda t: "MCP-Fehler" in (t or ""))
    assert await master_skill.prompt_block(None) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("antwort", [
    "Skill knoten-1 ist nicht abrufbar (unbekannte nodeId oder kein Zugriff).",
    "# Chatbot Masterskill\nnodeId: knoten-1\n\n---\n\n"
    "_Für diesen Skill ist kein Anleitungstext abrufbar (https://repo.example/x)._",
])
async def test_ohne_anleitung_gilt_der_abruf_als_gescheitert(monkeypatch, antwort) -> None:
    """Review 2026-09-29: ``get_skill`` meldet eine unbekannte Kennung, fehlende
    Rechte oder einen Skill ohne Text als gewöhnlichen Erfolgstext, ohne
    Fehlerkennung (``tools/skills.ts``). Als Anleitung übernommen, stand dieser
    Satz fünf Minuten lang als „Gesamtanleitung“ im Prompt — und das Studio
    zeigte ihn mit Prüfsumme und ohne Fehler."""
    _schalter(monkeypatch, an=True)

    async def _fake(name, args, **_kw):
        return antwort

    monkeypatch.setattr(master_skill, "call_mcp_tool", _fake)
    assert await master_skill.prompt_block(None) is None
    zustand = master_skill.zustand()
    assert zustand["cached"] is False
    assert zustand["last_error"]


@pytest.mark.asyncio
async def test_ein_fehlschlag_wird_nicht_gecacht(monkeypatch) -> None:
    """Sonst bliebe eine kurze MCP-Stoerung eine Viertelstunde lang wirksam."""
    _schalter(monkeypatch, an=True)
    versuche = {"n": 0}

    async def _fake(name, args, **_kw):
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


def test_der_takt_ist_fuenf_minuten():
    """Nutzer-Entscheide 2026-08-20 und 2026-10-18: redaktionelle Änderungen am Master-Skill
    kommen nach spätestens 5 Minuten überall an — jetzt geholt im Hintergrund-Takt."""
    from boerdi.services import master_skill as m

    assert m.TAKT_S == 5 * 60


# ── 6. Takt im Hintergrund, Rückfall auf den letzten guten Stand (2026-10-18) ──

@pytest.mark.asyncio
async def test_ein_alter_stand_wird_ohne_abruf_ausgeliefert(monkeypatch) -> None:
    """Kein Chat-Zug wartet mehr auf das Repositorium (gemessen 1–23 s): auch ein Stand, der
    älter ist als der Takt, gilt, bis der Takt ihn ersetzt."""
    _schalter(monkeypatch, an=True)
    master_skill._zwischenspeicher["knoten-1"] = "# Anleitung\n\nAlt, aber gut."
    aufrufe: list[str] = []

    async def _fake(name, args, **_kw):
        aufrufe.append(name)
        return "# Anleitung\n\nNeu."

    monkeypatch.setattr(master_skill, "call_mcp_tool", _fake)
    block = await master_skill.prompt_block(None)
    assert block is not None and "Alt, aber gut." in block
    assert aufrufe == []


@pytest.mark.asyncio
async def test_ein_gescheitertes_auffrischen_behaelt_den_letzten_guten_stand(monkeypatch) -> None:
    _schalter(monkeypatch, an=True)

    async def _gut(name, args, **_kw):
        return "# Anleitung\n\nGuter Stand."

    async def _weg(name, args, **_kw):
        raise TimeoutError("MCP weg")

    monkeypatch.setattr(master_skill, "call_mcp_tool", _gut)
    await master_skill.auffrischen()
    monkeypatch.setattr(master_skill, "call_mcp_tool", _weg)
    await master_skill.auffrischen()

    block = await master_skill.prompt_block(None)
    assert block is not None and "Guter Stand." in block
    assert "TimeoutError" in (master_skill.zustand()["last_error"] or "")


@pytest.mark.asyncio
async def test_auffrischen_geht_am_mcp_werkzeug_cache_vorbei(monkeypatch) -> None:
    _schalter(monkeypatch, an=True)
    gesehen: list[bool] = []

    async def _fake(name, args, *, use_cache=True, **_kw):
        gesehen.append(use_cache)
        return "# Anleitung\n\nText."

    monkeypatch.setattr(master_skill, "call_mcp_tool", _fake)
    await master_skill.auffrischen()
    assert gesehen == [False]


@pytest.mark.asyncio
async def test_ohne_kennung_frischt_der_takt_nichts_auf(monkeypatch) -> None:
    # Eine leere Umgebungsvariable hieße „nicht gesetzt“ (env_ignore_empty) — dann gälte die
    # Vorgabe-Kennung. Darum die Kennung selbst leeren.
    _schalter(monkeypatch, an=True)
    monkeypatch.setattr(master_skill, "_kennung", lambda: "")
    abrufe: list[str] = []

    async def _fake(name, args, **_kw):
        # Zählen, nicht werfen: `_hole` fängt jede Ausnahme als Abruffehler ab.
        abrufe.append(name)
        return "# Anleitung\n\nText."

    monkeypatch.setattr(master_skill, "call_mcp_tool", _fake)
    await master_skill.auffrischen()
    assert abrufe == []


def test_der_takt_laeuft_weiter_auch_wenn_ein_schritt_wirft(monkeypatch):
    """Review: der Abruffehler fängt schon `_hole` ab — geprüft wird hier der Schutz der
    Schleife selbst, etwa gegen einen Programmfehler in `auffrischen`."""
    import asyncio

    monkeypatch.setattr(master_skill, "TAKT_S", 0.001)
    abrufe: list[int] = []

    async def _schritt():
        abrufe.append(1)
        if len(abrufe) == 1:
            raise RuntimeError("Programmfehler")

    monkeypatch.setattr(master_skill, "auffrischen", _schritt)

    async def szenario():
        aufgabe = master_skill.starte()
        # Auf die Bedingung warten statt fest zu schlafen (vgl. Kippler im Aufbewahrungs-Takt).
        for _ in range(2000):
            if len(abrufe) >= 3:
                break
            await asyncio.sleep(0.001)
        aufgabe.cancel()
        await asyncio.gather(aufgabe, return_exceptions=True)
        return aufgabe

    aufgabe = asyncio.run(szenario())
    assert len(abrufe) >= 3
    assert aufgabe.cancelled()


# ── 5. Zustand für Anzeige (AG-2) und Messung (K0-2) ─────────────────────
@pytest.mark.asyncio
async def test_zustand_nennt_abrufzeit_laenge_und_pruefsumme(monkeypatch) -> None:
    """Studio und Gold-Lauf müssen sagen können, WELCHER Text galt. Ohne
    Prüfsumme wären zwei Messläufe mit verschiedenem Master-Skill nicht zu
    unterscheiden."""
    _schalter(monkeypatch, an=True)
    text = "# Anleitung\n\nInhalt."

    async def _fake(name, args, **_kw):
        return text

    monkeypatch.setattr(master_skill, "call_mcp_tool", _fake)
    await master_skill.prompt_block(None)
    z = master_skill.zustand()

    assert (z["cached"], z["length"]) == (True, len(text))
    assert z["sha256"] == hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert z["fetched_at"] and z["last_error"] is None
    assert z["ttl_seconds"] == 300


@pytest.mark.asyncio
async def test_zustand_nennt_den_letzten_fehler(monkeypatch) -> None:
    _schalter(monkeypatch, an=True)

    async def _fake(name, args, **_kw):
        raise TimeoutError("MCP weg")

    monkeypatch.setattr(master_skill, "call_mcp_tool", _fake)
    await master_skill.prompt_block(None)
    z = master_skill.zustand()

    assert (z["cached"], z["length"], z["sha256"]) == (False, None, None)
    assert "MCP weg" in z["last_error"]


@pytest.mark.asyncio
async def test_anzeige_zeigt_den_wortlaut_auch_abgeschaltet(monkeypatch) -> None:
    """Das Studio zeigt, was gelten WÜRDE: wer ihn einschalten will, sieht den
    Wortlaut vorher. Ein Zug holt abgeschaltet weiterhin nichts."""
    _schalter(monkeypatch, an=False)

    async def _fake(name, args, **_kw):
        return "# Anleitung\n\nInhalt."

    monkeypatch.setattr(master_skill, "call_mcp_tool", _fake)
    anzeige = await master_skill.anzeige()

    assert (anzeige["enabled"], anzeige["text"]) == (False, "# Anleitung\n\nInhalt.")
    assert await master_skill.prompt_block(None) is None


@pytest.mark.asyncio
async def test_anzeige_ohne_kennung_holt_nichts(monkeypatch) -> None:
    # Leerzeichen statt "": ein leerer Wert gilt als ungesetzt, dann griffe die
    # Kennung aus einer lokalen backend/.env.
    _schalter(monkeypatch, an=True, kennung="   ")

    async def _fake(name, args, **_kw):
        raise AssertionError("darf nicht gerufen werden")

    monkeypatch.setattr(master_skill, "call_mcp_tool", _fake)
    anzeige = await master_skill.anzeige()
    assert (anzeige["node_id"], anzeige["text"]) == ("", None)


@pytest.mark.asyncio
async def test_neu_laden_holt_trotz_frischem_speicher(monkeypatch) -> None:
    """„Neu laden" im Studio: eine Änderung im Repositorium soll nicht bis zu
    fünf Minuten warten."""
    _schalter(monkeypatch, an=True)
    antworten = iter(["# Alt\n\nv1", "# Neu\n\nv2"])

    async def _fake(name, args, **_kw):
        return next(antworten)

    monkeypatch.setattr(master_skill, "call_mcp_tool", _fake)
    await master_skill.prompt_block(None)
    anzeige = await master_skill.neu_laden()

    assert anzeige["text"] == "# Neu\n\nv2"
    assert "v2" in (await master_skill.prompt_block(None) or "")


def _transport_liefert(monkeypatch, *antworten) -> list:
    """Echter ``call_mcp_tool`` samt Werkzeug-Cache; gefälscht ist nur der
    Transport DARUNTER — genau dort lag der Fehler, den eine Attrappe über
    dem Cache nie gesehen hätte."""
    from boerdi.services.mcp import tool_cache, transport

    tool_cache.clear_tool_cache()
    aufrufe: list = []
    folge = iter(antworten)

    async def call_tool(name, args, *, url=None):
        aufrufe.append(name)
        antwort = next(folge)
        if isinstance(antwort, Exception):
            return {"error": {"message": str(antwort), "kind": "transport"}}
        return {"result": {"content": [{"type": "text", "text": antwort}]}}

    monkeypatch.setattr(transport, "call_tool", call_tool)
    return aufrufe


@pytest.mark.asyncio
async def test_neu_laden_umgeht_auch_den_mcp_werkzeug_cache(monkeypatch) -> None:
    """Review-Befund 2026-09-26: der MCP-Client hält ``get_skill`` selbst 180 s
    vor. „Neu laden" bekam dort den alten Text und stempelte ihn als frisch."""
    _schalter(monkeypatch, an=True)
    aufrufe = _transport_liefert(monkeypatch, "# Alt\n\nv1", "# Neu\n\nv2")
    await master_skill.prompt_block(None)

    anzeige = await master_skill.neu_laden()

    assert anzeige["text"] == "# Neu\n\nv2"
    assert aufrufe == ["get_skill", "get_skill"]


@pytest.mark.asyncio
async def test_ein_gescheitertes_neu_laden_behaelt_den_bisherigen_text(monkeypatch) -> None:
    """Sonst antwortete der Agent nach einem MCP-Aussetzer ohne Anleitung, obwohl
    eine gültige im Speicher lag."""
    _schalter(monkeypatch, an=True)
    _transport_liefert(monkeypatch, "# Alt\n\nv1", TimeoutError("MCP weg"),
                       TimeoutError("MCP weg"))
    await master_skill.prompt_block(None)

    anzeige = await master_skill.neu_laden()

    assert anzeige["text"] == "# Alt\n\nv1"
    assert anzeige["last_error"]
    assert "v1" in (await master_skill.prompt_block(None) or "")


def test_die_app_startet_den_master_skill_takt_und_beendet_ihn(monkeypatch):
    """Im Lebenszyklus der App: gestartet beim Hochfahren, abgebrochen beim Herunterfahren."""
    import asyncio

    import boerdi.main as main_mod

    gestartet: list[asyncio.Task] = []

    def _starte():
        aufgabe = master_skill.starte()
        gestartet.append(aufgabe)
        return aufgabe

    # Dieselbe Naht, die conftest stilllegt — hier gewinnt der Test (wie bei der Vorwärmung).
    monkeypatch.setattr(main_mod, "starte_master_skill_takt", _starte)
    _schalter(monkeypatch, an=False)  # abgeschaltet, nichts gespeichert: der Takt holt nichts

    from tests import pg_utils

    if not pg_utils.dev_db_ready():
        pytest.skip(pg_utils.DEV_DB_SKIP_REASON)
    from fastapi.testclient import TestClient

    with TestClient(main_mod.create_app()):
        assert len(gestartet) == 1 and not gestartet[0].done()
    assert gestartet[0].cancelled()


@pytest.mark.asyncio
async def test_abgeschaltet_und_nie_gebraucht_holt_der_takt_nichts(monkeypatch) -> None:
    """Die Vorgabe-Kennung ist eine echte Knoten-ID: ohne diese Grenze fragte jede Anlage mit
    abgeschaltetem Skill (und jede Test-App) alle fünf Minuten das Repositorium ab."""
    _schalter(monkeypatch, an=False)
    abrufe: list[str] = []

    async def _fake(name, args, **_kw):
        # Zählen, nicht werfen: `_hole` fängt jede Ausnahme als Abruffehler ab.
        abrufe.append(name)
        return "# Anleitung\n\nText."

    monkeypatch.setattr(master_skill, "call_mcp_tool", _fake)
    await master_skill.auffrischen()
    assert abrufe == []


@pytest.mark.asyncio
async def test_einmal_gebraucht_frischt_der_takt_auch_abgeschaltet_auf(monkeypatch) -> None:
    """Eine Einbettung schaltet ihn je Zug ein (``environment.master_skill``): ab dem ersten
    Gebrauch hält der Takt den Stand frisch, auch wenn die Umgebung ihn abschaltet."""
    _schalter(monkeypatch, an=False)
    abrufe: list[int] = []

    async def _fake(name, args, **_kw):
        abrufe.append(1)
        return "# Anleitung\n\nText."

    monkeypatch.setattr(master_skill, "call_mcp_tool", _fake)
    assert await master_skill.prompt_block(True) is not None
    await master_skill.auffrischen()
    assert len(abrufe) == 2


@pytest.mark.asyncio
async def test_ein_spaet_fertiger_takt_ueberschreibt_kein_neueres_neu_laden(monkeypatch) -> None:
    """Review Befund 1: es gilt der zuletzt GESTARTETE Abruf, nicht der zuletzt fertige —
    sonst schriebe ein langsamer Takt (bis 23 s) nach „Neu laden“ den alten Text zurück."""
    import asyncio

    _schalter(monkeypatch, an=True)
    takt_laeuft, takt_darf = asyncio.Event(), asyncio.Event()
    abrufe: list[int] = []

    async def _fake(name, args, **_kw):
        abrufe.append(1)
        if len(abrufe) == 1:
            takt_laeuft.set()
            await takt_darf.wait()
            return "# Anleitung\n\nAlt."
        return "# Anleitung\n\nNeu."

    monkeypatch.setattr(master_skill, "call_mcp_tool", _fake)
    takt = asyncio.create_task(master_skill.auffrischen())
    await takt_laeuft.wait()
    await master_skill.neu_laden()
    takt_darf.set()
    await takt

    block = await master_skill.prompt_block(None)
    assert block is not None and "Neu." in block and "Alt." not in block


@pytest.mark.asyncio
@pytest.mark.parametrize("antwort", [
    "Skill knoten-1 ist nicht abrufbar.",
    "   ",
])
async def test_eine_antwort_ohne_anleitung_loest_den_stand_ab(monkeypatch, antwort) -> None:
    """Review Befund 2: „keine Anleitung“ oder ein leerer Text ist eine ANTWORT des Servers
    (Knoten gelöscht, geleert), kein Ausfall — der alte Stand gilt dann nicht weiter. Sonst
    bliebe ein zurückgezogener Master-Skill bis zum Neustart aktiv."""
    _schalter(monkeypatch, an=True)

    async def _gut(name, args, **_kw):
        return "# Anleitung\n\nGuter Stand."

    async def _weg(name, args, **_kw):
        return antwort

    monkeypatch.setattr(master_skill, "call_mcp_tool", _gut)
    await master_skill.auffrischen()
    monkeypatch.setattr(master_skill, "call_mcp_tool", _weg)
    await master_skill.auffrischen()

    assert await master_skill.prompt_block(None) is None
    assert master_skill.zustand()["cached"] is False



@pytest.mark.asyncio
@pytest.mark.parametrize("spaete_antwort", ["fehler", "Skill knoten-1 ist nicht abrufbar."])
async def test_ein_ueberholter_abruf_meldet_keinen_fehler(monkeypatch, spaete_antwort) -> None:
    """Review 2: der zuletzt gestartete Abruf gilt auch für die Meldung — ein älterer, der
    danach scheitert oder „keine Anleitung“ meldet, stellt keinen Fehler neben einen
    frischen, gültigen Text und entfernt ihn nicht."""
    import asyncio

    _schalter(monkeypatch, an=True)
    takt_laeuft, takt_darf = asyncio.Event(), asyncio.Event()
    abrufe: list[int] = []

    async def _fake(name, args, **_kw):
        abrufe.append(1)
        if len(abrufe) == 1:
            takt_laeuft.set()
            await takt_darf.wait()
            if spaete_antwort == "fehler":
                raise TimeoutError("spät gescheitert")
            return spaete_antwort
        return "# Anleitung\n\nNeu."

    monkeypatch.setattr(master_skill, "call_mcp_tool", _fake)
    takt = asyncio.create_task(master_skill.auffrischen())
    await takt_laeuft.wait()
    await master_skill.neu_laden()
    takt_darf.set()
    await takt

    zustand = master_skill.zustand()
    assert zustand["last_error"] is None
    assert zustand["cached"] is True
    block = await master_skill.prompt_block(None)
    assert block is not None and "Neu." in block


@pytest.mark.asyncio
async def test_ein_ueberholter_abruf_belebt_keinen_geloeschten_skill(monkeypatch) -> None:
    """Review 2: meldet der neuere Abruf „keine Anleitung“ (Knoten gelöscht), darf ein älterer,
    der danach noch den alten Text bringt, ihn nicht zurückschreiben."""
    import asyncio

    _schalter(monkeypatch, an=True)
    takt_laeuft, takt_darf = asyncio.Event(), asyncio.Event()
    abrufe: list[int] = []

    async def _fake(name, args, **_kw):
        abrufe.append(1)
        if len(abrufe) == 1:
            takt_laeuft.set()
            await takt_darf.wait()
            return "# Anleitung\n\nAlt."
        return "Skill knoten-1 ist nicht abrufbar."

    monkeypatch.setattr(master_skill, "call_mcp_tool", _fake)
    takt = asyncio.create_task(master_skill.auffrischen())
    await takt_laeuft.wait()
    await master_skill.neu_laden()
    takt_darf.set()
    await takt

    assert master_skill.zustand()["cached"] is False


# ── Paket 17 (C3): Signal auf der NOTIFY-Bahn ────────────────────────────


@pytest.mark.asyncio
async def test_der_config_store_reicht_ein_signal_nur_an_die_abonnenten() -> None:
    """``__``-Nutzlasten sind Signale, keine Bereiche: kein Abruf aus ``config_areas``."""
    from boerdi.services.config_store import ConfigStore

    store = ConfigStore(engine=object(), listen_dsn="postgresql://attrappe")  # type: ignore[arg-type]
    gehoert: list[str] = []
    store.subscribe(gehoert.append)
    # In der Schleife: ein Bereich startete hier einen Abruf.
    store._on_area_changed("__master_skill")
    assert gehoert == ["__master_skill"]
    assert store._fetching == {}


@pytest.mark.asyncio
async def test_das_signal_uebernimmt_den_geteilten_stand(monkeypatch) -> None:
    import asyncio
    from datetime import UTC, datetime

    from boerdi.services import master_skill_stand

    _schalter(monkeypatch, an=True)
    stand = master_skill_stand.Stand(text="# Geteilt", abgerufen_um=datetime.now(UTC),
                                     letzter_fehler=None, alter_s=1.0)

    async def _lies(_engine, _kennung):
        return stand

    monkeypatch.setattr(master_skill_stand, "lies", _lies)
    master_skill.bei_signal("prompts")  # anderer Bereich: nichts
    assert not master_skill._uebernahmen
    master_skill.bei_signal(master_skill_stand.SIGNAL)  # ohne Datenbank: nichts
    assert not master_skill._uebernahmen

    master_skill.binde(object())  # type: ignore[arg-type]
    try:
        master_skill.bei_signal(master_skill_stand.SIGNAL)
        await asyncio.gather(*master_skill._uebernahmen)
    finally:
        master_skill.binde(None)
    assert master_skill.zustand()["sha256"] == hashlib.sha256(b"# Geteilt").hexdigest()


@pytest.mark.asyncio
async def test_neu_laden_bei_belegter_sperre_meldet_es(monkeypatch) -> None:
    """Gesamt-Review C6: das Studio hielt das Neu-Laden für gelungen."""
    import contextlib

    from boerdi.services.sitzungssperre import SitzungBeschaeftigt

    _schalter(monkeypatch, an=True)

    @contextlib.asynccontextmanager
    async def _belegt(*_a, **_kw):
        raise SitzungBeschaeftigt("__lauf:master-skill")
        yield

    async def _keine_zeile(_kennung):
        return None

    monkeypatch.setattr(master_skill, "sitzungssperre", _belegt)
    monkeypatch.setattr(master_skill, "_lies_stand", _keine_zeile)

    async def _fake(name, args, **_kw):
        return "# A\n\nv1"

    monkeypatch.setattr(master_skill, "call_mcp_tool", _fake)
    master_skill.binde(object())  # type: ignore[arg-type]
    try:
        await master_skill.prompt_block(None)  # die Kopie hat einen Stand
        anzeige = await master_skill.neu_laden()
    finally:
        master_skill.binde(None)
    assert "Sperre" in (anzeige["last_error"] or "")
