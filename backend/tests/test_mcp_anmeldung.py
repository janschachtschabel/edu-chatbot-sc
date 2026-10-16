"""Echtheit des Zugangsblocks (Paket 10, Kurzaudit 2026-10-10: A-1, S-1, A-3).

Bis hier prüfte ``has_personal_auth()`` nur die FORM des Blocks: wer
``WLO-Access-Block: wlo2.x`` mitschickte und den Agent-Modus wählte, bekam die
vollen Deckel (A-1), und ein abgelaufener Block bot weiter Schreibwerkzeuge an
(A-3). Jetzt fragt der Zug einmal ``wlo_auth_status``; das Ergebnis gilt je
Fingerabdruck einige Minuten.

S-1: der MCP-Server verschlüsselt jeden Block mit zufälligem Schlüssel — ein neuer
Ticket-Tausch derselben Person ändert den Fingerabdruck. Eine Abnahme hängt deshalb
an der bestätigten Person, nicht am Block.

Geprüft wird innerhalb des Zuges (``asyncio.run`` setzt Kontextvariablen in einer
Kopie) — so wie Endpunkt und Graph im Betrieb.
"""

from __future__ import annotations

import asyncio

import pytest
from pydantic import SecretStr

from boerdi.services.mcp import anmeldung, auth

_BLOCK = "wlo2.persoenlich-erste-fassung"
_ZWEITER = "wlo2.persoenlich-zweite-fassung"
# Die echte Abfrage — ``conftest`` ersetzt sie für alle übrigen Tests (kein Netz).
_ECHT_FRAGEN = anmeldung._fragen


@pytest.fixture(autouse=True)
def _sauber(monkeypatch):
    from boerdi.settings import get_settings

    monkeypatch.setattr(anmeldung, "_fragen", _ECHT_FRAGEN)
    monkeypatch.setattr(get_settings(), "mcp_auth_token", SecretStr(""), raising=False)
    anmeldung._cache.clear()
    auth.set_turn_auth_block(None)
    yield
    anmeldung._cache.clear()
    auth.set_turn_auth_block(None)


def _person(authority: str) -> dict:
    return {"result": {"content": [], "structuredContent": {
        "mode": "user", "authenticated": True, "authority": authority}}}


def _server(monkeypatch, antwort) -> list[str]:
    """``transport.call_tool`` als Attrappe; ``antwort`` ist ein Dict oder eine
    Funktion des gerade gesetzten Blocks. Gibt die Liste der Aufrufe zurück."""
    aufrufe: list[str] = []

    async def call_tool(name, args=None, *, url=None):
        aufrufe.append(name)
        return antwort(auth._turn_block.get("")) if callable(antwort) else antwort

    monkeypatch.setattr(anmeldung.transport, "call_tool", call_tool)
    return aufrufe


def _zug(block: str | None) -> dict:
    async def lauf():
        auth.set_turn_auth_block(block)
        await anmeldung.bestaetige_anmeldung()
        return {
            "person": auth.has_personal_auth(),
            "mit_block": auth.has_auth_token(),
            "abgelehnt": anmeldung.abgelehnt_in_diesem_zug(),
            "kennung": auth.aufrufer_kennung(),
        }
    return asyncio.run(lauf())


class TestNurBestaetigtZaehlt:
    def test_die_form_allein_reicht_nicht(self):
        auth.set_turn_auth_block(_BLOCK)
        assert not auth.has_personal_auth()
        auth.setze_bestaetigung(person=True, kennung="k")
        assert auth.has_personal_auth()

    def test_ein_neuer_block_braucht_eine_neue_bestaetigung(self):
        auth.set_turn_auth_block(_BLOCK)
        auth.setze_bestaetigung(person=True, kennung="k")
        auth.set_turn_auth_block(_ZWEITER)
        assert not auth.has_personal_auth()

    def test_der_anonyme_block_ist_nie_eine_person(self):
        auth.set_turn_auth_block("wlo-anon.v1")
        auth.setze_bestaetigung(person=True, kennung="k")
        assert not auth.has_personal_auth()


class TestPruefungJeZug:
    def test_eine_person_wird_bestaetigt_und_gemerkt(self, monkeypatch):
        aufrufe = _server(monkeypatch, _person("lehrerin"))
        assert _zug(_BLOCK)["person"]
        assert _zug(_BLOCK)["person"]
        assert aufrufe == ["wlo_auth_status"]          # einmal je Fingerabdruck

    def test_ohne_persoenlichen_block_fragt_niemand(self, monkeypatch):
        aufrufe = _server(monkeypatch, _person("lehrerin"))
        for block in (None, "wlo-anon.v1"):
            assert not _zug(block)["person"]
        assert aufrufe == []

    @pytest.mark.parametrize("antwort", [
        {"error": {"message": "401 Unauthorized", "kind": "auth"}},
        {"result": {"content": [], "structuredContent": {
            "mode": "user", "authenticated": False, "authority": None}}},
    ], ids=["401", "nicht-angemeldet"])
    def test_ein_abgewiesener_block_faellt_weg_und_wird_gemeldet(self, monkeypatch, antwort):
        """A-3: der Zug läuft anonym weiter, statt an jedem Werkzeug zu scheitern —
        und das Widget erfährt es."""
        _server(monkeypatch, antwort)
        zug = _zug(_BLOCK)
        assert not zug["person"] and not zug["mit_block"] and zug["abgelehnt"]

    def test_ohne_antwort_keine_person_aber_der_block_bleibt(self, monkeypatch):
        _server(monkeypatch, {"error": {"message": "connect failed", "kind": "transport"}})
        zug = _zug(_BLOCK)
        assert not zug["person"] and zug["mit_block"] and not zug["abgelehnt"]

    def test_ein_dienstkonto_ist_keine_person(self, monkeypatch):
        _server(monkeypatch, {"result": {"content": [], "structuredContent": {
            "mode": "service", "authenticated": True, "authority": "dienst"}}})
        zug = _zug(_BLOCK)
        assert not zug["person"] and zug["mit_block"] and not zug["abgelehnt"]


class TestDieAbnahmeHaengtAnDerPerson:
    def test_ein_neuer_ticket_tausch_derselben_person_behaelt_die_kennung(self, monkeypatch):
        _server(monkeypatch, _person("lehrerin"))
        erste, zweite = _zug(_BLOCK)["kennung"], _zug(_ZWEITER)["kennung"]
        assert erste and erste == zweite

    def test_zwei_personen_haben_verschiedene_kennungen(self, monkeypatch):
        _server(monkeypatch, lambda block: _person("eins" if block == _BLOCK else "zwei"))
        assert _zug(_BLOCK)["kennung"] != _zug(_ZWEITER)["kennung"]

    def test_ohne_bestaetigung_bleibt_es_beim_fingerabdruck(self):
        auth.set_turn_auth_block(_BLOCK)
        assert auth.aufrufer_kennung() == auth.caller_fingerprint() != ""


def test_eine_abweisung_in_einem_knoten_gilt_fuer_den_ganzen_zug():
    """LangGraph lässt jeden Knoten als eigene Task laufen — ein ``ContextVar.set``
    dort käme beim nächsten Knoten und beim Endpunkt nicht an (``graph/build``,
    ``begin_turn``). Ein 401 mitten im Zug muss trotzdem für alle gelten."""
    async def knoten_mit_401():
        anmeldung.markiere_abgelehnt()

    async def spaeterer_knoten():
        return auth.has_auth_token()

    async def lauf():
        auth.set_turn_auth_block(_BLOCK)
        await asyncio.create_task(knoten_mit_401())
        mit_block = await asyncio.create_task(spaeterer_knoten())
        return mit_block, anmeldung.abgelehnt_in_diesem_zug()

    mit_block, abgelehnt = asyncio.run(lauf())
    assert not mit_block and abgelehnt
