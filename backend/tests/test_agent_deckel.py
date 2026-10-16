"""AG-6 — Kostenbremse für anonymen Chat-Verkehr (Plan 2026-09-26 §8, D-9).

Jeder Client wählt die Maschine (Kopfzeile ``X-Boerdi-Engine``), und bis hier
galten für einen anonymen Zug dieselben Deckel wie für eine angemeldete
Einbettung — nach Vorgabe bis 30 Runden und 900 000 Token, gebremst nur vom
Rate-Limit. ``agent.anonymous`` setzt engere Deckel. Seit D-9 (2026-09-27) sind
sie mit den aktuellen Werten vorbelegt: keine harte Deckelung, aber im Studio
sichtbar und senkbar.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from boerdi.domain.config_models.engine import AgentLimits, AnonymousLimits
from boerdi.services import agent_deckel


def _angemeldet(monkeypatch, ja: bool) -> None:
    monkeypatch.setattr(agent_deckel, "has_personal_auth", lambda: ja)


def test_die_vorgabe_sind_die_aktuellen_werte() -> None:
    """D-9 (Nutzer, 2026-09-27): das Token-Budget nicht hart deckeln, sondern
    als Studio-Option anbieten, vorbelegt mit den heute geltenden Werten."""
    normal, anonym = AgentLimits(), AnonymousLimits()
    assert AgentLimits().anonymous == anonym
    assert (anonym.max_iterations, anonym.deadline_s, anonym.token_budget) == (
        normal.max_iterations, normal.deadline_s, normal.token_budget)


def test_die_vorgabe_aendert_keinen_zug(monkeypatch) -> None:
    _angemeldet(monkeypatch, False)
    limits = AgentLimits()
    assert agent_deckel.fuer_diesen_zug(limits) is limits


@pytest.mark.parametrize("feld,wert", [
    ("max_iterations", 0), ("max_iterations", 51), ("deadline_s", 4),
    ("deadline_s", 1801), ("token_budget", 999),
])
def test_die_grenzen_gelten_wie_beim_normalen_deckel(feld, wert) -> None:
    """Das Studio schreibt direkt gegen dieses Modell: eine Frist von 0 s
    beendete jeden anonymen Lauf vor dem ersten Werkzeug."""
    with pytest.raises(ValidationError):
        AnonymousLimits(**{feld: wert})


def test_ohne_anmeldung_gilt_der_engere_deckel(monkeypatch) -> None:
    _angemeldet(monkeypatch, False)
    limits = AgentLimits(max_iterations=20, deadline_s=300, token_budget=400_000,
                         anonymous=AnonymousLimits(max_iterations=8, token_budget=150_000))
    got = agent_deckel.fuer_diesen_zug(limits)
    # Die Frist steht auf der Vorgabe (900 s) und liegt damit über dem normalen
    # Deckel — das Minimum lässt den normalen stehen.
    assert (got.max_iterations, got.deadline_s, got.token_budget) == (8, 300, 150_000)
    assert got.write_mode == limits.write_mode


def test_geleerte_anonyme_felder_heissen_wie_angemeldet(monkeypatch) -> None:
    """Review-Befund 2026-09-27: seit die Vorgabe gefüllt ist, prüfte kein Test
    mehr den Leer-Zweig. Ein geleertes Feld ist „wie angemeldet" — auch wenn der
    normale Deckel über der Vorgabe liegt."""
    _angemeldet(monkeypatch, False)
    limits = AgentLimits(
        max_iterations=40, deadline_s=1200, token_budget=1_500_000,
        anonymous=AnonymousLimits(max_iterations=None, deadline_s=None, token_budget=None))
    assert agent_deckel.fuer_diesen_zug(limits) is limits


def test_ein_anonymer_wert_hebt_nichts_an(monkeypatch) -> None:
    """Minimum statt Ersatz: wer den normalen Deckel senkt und den anonymen
    vergisst, darf anonym nicht mehr bekommen als angemeldet."""
    _angemeldet(monkeypatch, False)
    limits = AgentLimits(max_iterations=10, anonymous=AnonymousLimits(max_iterations=30))
    assert agent_deckel.fuer_diesen_zug(limits).max_iterations == 10


def test_mit_anmeldung_bleibt_alles_wie_konfiguriert(monkeypatch) -> None:
    _angemeldet(monkeypatch, True)
    limits = AgentLimits(max_iterations=20, anonymous=AnonymousLimits(max_iterations=8))
    assert agent_deckel.fuer_diesen_zug(limits) is limits


def test_ohne_anonyme_deckel_derselbe_satz(monkeypatch) -> None:
    _angemeldet(monkeypatch, False)
    limits = AgentLimits()
    assert agent_deckel.fuer_diesen_zug(limits) is limits


@pytest.mark.anyio
async def test_respond_agent_deckelt_anonyme_zuege(monkeypatch) -> None:
    from boerdi.graph.nodes.respond_agent import respond_agent
    from tests.test_respond_agent import _ctx, _patch

    konfig = AgentLimits(token_budget=400_000,
                         anonymous=AnonymousLimits(token_budget=100_000))
    for angemeldet, erwartet in ((False, 100_000), (True, 400_000)):
        seen: dict = {}
        _patch(monkeypatch, seen, limits=konfig, personal=angemeldet)
        _angemeldet(monkeypatch, angemeldet)
        await respond_agent(_ctx())
        assert seen["run_agent_loop"]["limits"].token_budget == erwartet, angemeldet


# -- Review 2026-09-26: Zusatzfelder und der anonyme Block --------------------


def _im_zug(block, fn):
    """Im eigenen Kontext wie ein Zug: der Block bleibt nicht am Test haengen."""
    import contextvars

    from tests.helfer_anmeldung import als_person

    def lauf():
        als_person(block)   # bestätigt, wenn er eine Person meinen kann (Paket 10)
        return fn()

    return contextvars.copy_context().run(lauf)


@pytest.mark.parametrize("block,gedeckelt", [
    ("wlo-anon.v1", True),        # oeffentlich dokumentiert, keine Anmeldung
    ("wlo2.abc.def.ghi", False),  # kann eine Person meinen
    (None, True),
])
def test_der_anonyme_block_ist_keine_anmeldung(block, gedeckelt) -> None:
    """Sonst schaltete jeder oeffentliche Client die Bremse mit einer
    Kopfzeile ab, deren Wert in der AUTH.md des MCP-Servers steht."""
    limits = AgentLimits(max_iterations=20, anonymous=AnonymousLimits(max_iterations=8))
    got = _im_zug(block, lambda: agent_deckel.fuer_diesen_zug(limits))
    assert (got.max_iterations == 8) is gedeckelt


def test_zusatzfelder_unter_anonymous_wirken_nicht(monkeypatch) -> None:
    """``extra="allow"`` laesst ein fremdes Feld durch die Pruefung. Es darf
    weder jeden anonymen Zug sprengen (Tippfehler) noch den Schreibmodus
    lockern (``"execute" < "propose"``)."""
    _angemeldet(monkeypatch, False)
    limits = AgentLimits.model_validate({"max_iterations": 20, "anonymous": {
        "max_iteration": 8, "write_mode": "execute"}})
    got = agent_deckel.fuer_diesen_zug(limits)
    assert got.write_mode == "propose"
    assert got.max_iterations == 20
