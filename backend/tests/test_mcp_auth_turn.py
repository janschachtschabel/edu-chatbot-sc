"""C5-a: Zugangsblock **je Zug** statt je Prozess.

Bis hierher las `build_http_client_factory()` einen einzigen `SecretStr` aus den
Einstellungen — jeder Besucher handelte unter derselben Kennung. Ein
*persönlicher* Block in `MCP_AUTH_TOKEN` machte das schlimmer statt besser:
dann kuratiert jeder anonyme Besucher unter einem echten Namen.

**Warum ein `ContextVar` und kein Parameter:** gemessen 2026-08-10 gibt es
**23 Aufrufstellen von ``call_mcp_tool`` in 9 Dateien**; einen Block durch alle
Signaturen zu fädeln wäre ein Eingriff in ein Dutzend Module für einen Wert, der
niemanden unterwegs interessiert. Dasselbe Problem löst dieses Paket schon
zweimal mit einem `ContextVar` (`_query_metas` in `mcp/client.py`,
`_request_hints` in `mcp/arg_resolvers.py`), je mit derselben Begründung —
„per-async-task scoped so concurrent sessions don't bleed". Wir nehmen das
etablierte Mittel; die 23 Aufrufstellen bleiben unberührt.

**Warum die Prüfung am Rand:** der Block kommt ab jetzt aus einer Kopfzeile,
also aus unvertrauter Hand. Zwei Dinge müssen dort enden — Steuerzeichen (die
sonst eine zweite Kopfzeile anhängen könnten) und fremde Zugangsdaten: ohne
Präfix-Prüfung wäre unser Backend ein beliebiger Weiterleiter für
`Authorization`-Werte an den MCP-Wirt, und dessen Rate-Schranke zählt je
Adresse — also gegen *unsere*.

**Die Zusicherung der Bestandsdatei gilt hier weiter:** der Block darf nirgends
sichtbar werden, auch nicht in der Ablehnung.
"""

from __future__ import annotations

import asyncio
import logging

import pytest
from pydantic import SecretStr

from boerdi.services.mcp import auth as auth_mod
from boerdi.services.mcp.auth import (
    auth_mode,
    build_http_client_factory,
    has_auth_token,
    set_turn_auth_block,
)

_EINSTELLUNG = "wlo2.aus-der-einstellung"
_ZUG = "wlo2.vom-menschen-dieses-zuges"


@pytest.fixture(autouse=True)
def _kein_zug_block():
    """Jeder Test startet ohne Zug-Block — und räumt hinterher auf.

    Ohne das Aufräumen tröpfelt ein gesetzter Block in Nachbartests: pytest
    fährt alle Tests in derselben Task, der `ContextVar` überlebt also.
    """
    set_turn_auth_block(None)
    yield
    set_turn_auth_block(None)


@pytest.fixture
def mit_einstellung(monkeypatch):
    from boerdi.settings import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "mcp_auth_token", SecretStr(_EINSTELLUNG), raising=False)
    return s


@pytest.fixture
def ohne_einstellung(monkeypatch):
    from boerdi.settings import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "mcp_auth_token", SecretStr(""), raising=False)
    return s


# ── Der Zug-Block gewinnt ────────────────────────────────────────────────


class TestZugBlockGewinnt:
    def test_zug_block_schlaegt_die_einstellung(self, mit_einstellung):
        assert set_turn_auth_block(_ZUG) is True
        client = build_http_client_factory()()
        assert client.headers["authorization"] == f"Bearer {_ZUG}"

    def test_ohne_zug_block_bleibt_die_einstellung(self, mit_einstellung):
        client = build_http_client_factory()()
        assert client.headers["authorization"] == f"Bearer {_EINSTELLUNG}"

    def test_zug_block_traegt_auch_ohne_einstellung(self, ohne_einstellung):
        assert has_auth_token() is False
        set_turn_auth_block(_ZUG)
        assert has_auth_token() is True
        client = build_http_client_factory()()
        assert client.headers["authorization"] == f"Bearer {_ZUG}"

    def test_zuruecksetzen_stellt_die_einstellung_wieder_her(self, mit_einstellung):
        set_turn_auth_block(_ZUG)
        set_turn_auth_block(None)
        client = build_http_client_factory()()
        assert client.headers["authorization"] == f"Bearer {_EINSTELLUNG}"

    def test_health_meldet_weiter_die_betriebsart_der_anlage(self, ohne_einstellung):
        """``auth_mode()`` beantwortet ``/health`` — dort gibt es keinen Zug.

        Bewusst NICHT zug-abhängig: sonst meldete dieselbe Anlage je nach
        zufällig laufender Anfrage eine andere Betriebsart.
        """
        set_turn_auth_block(_ZUG)
        assert auth_mode() == "anonymous"


# ── Prüfung am Rand ──────────────────────────────────────────────────────


class TestPruefungAmRand:
    @pytest.mark.parametrize(
        ("roh", "warum"),
        [
            ("", "leer"),
            ("   ", "nur Leerzeichen"),
            # AUTH.md §5a: das mitgereiste Wort „Bearer" kostete dort live
            # einen Nachmittag — die Seite bietet deshalb zwei Kopier-Knöpfe.
            ("Bearer wlo2.abc", "das Wort Bearer reist mit"),
            ("wlo2.abc\r\nX-Schmuggel: ja", "Steuerzeichen — hinge sonst eine Kopfzeile an"),
            ("wlo2.abc def", "Leerzeichen im Block"),
            ("Basic aGFsbG86d2VsdA==", "fremde Zugangsdaten — wir sind kein Weiterleiter"),
            ("wlo2." + "a" * 9000, "über der Längengrenze"),
        ],
    )
    def test_wird_abgelehnt(self, roh, warum, ohne_einstellung):
        assert set_turn_auth_block(roh) is False, warum
        assert has_auth_token() is False, warum

    @pytest.mark.parametrize(
        "roh",
        [
            "wlo2.QUJD-_x=.aXY.Y3Q",  # die echte Form: wlo2.<b64u>.<b64u>.<b64u>
            "wlo-anon.v1",            # „ohne Konto verbinden" (AUTH.md §5b)
            "  wlo-anon.v1  ",        # Randleerzeichen sind kein Fehler
        ],
    )
    def test_wird_angenommen(self, roh, ohne_einstellung):
        assert set_turn_auth_block(roh) is True
        assert has_auth_token() is True

    def test_eine_ablehnung_loescht_einen_frueheren_block(self, ohne_einstellung):
        """Sonst hinge ein Zug am Block des vorigen — die schlimmste Verwechslung."""
        set_turn_auth_block(_ZUG)
        assert set_turn_auth_block("Basic abc") is False
        assert has_auth_token() is False


# ── Kein Leck ────────────────────────────────────────────────────────────


class TestKeinLeck:
    def test_annahme_und_ablehnung_protokollieren_nichts(self, caplog, ohne_einstellung):
        with caplog.at_level(logging.DEBUG, logger=auth_mod.__name__):
            set_turn_auth_block(_ZUG)
            set_turn_auth_block("Basic " + _ZUG)
        assert _ZUG not in caplog.text

    def test_betriebsart_nennt_den_zug_block_nicht(self, ohne_einstellung):
        set_turn_auth_block(_ZUG)
        assert _ZUG not in auth_mode()


# ── Nebenläufigkeit: zwei Menschen gleichzeitig ──────────────────────────


class TestNebenlaeufigkeit:
    def test_zwei_zuege_sehen_ihren_eigenen_block(self, ohne_einstellung):
        """Der eigentliche Grund für den ``ContextVar``.

        Zwei gleichzeitige Züge dürfen sich nicht gegenseitig anmelden. Jede
        Task bekommt beim Erzeugen eine Kopie des Kontexts; ein ``set`` darin
        bleibt darin.
        """
        gesehen: dict[str, str] = {}

        async def zug(name: str, block: str) -> None:
            set_turn_auth_block(block)
            await asyncio.sleep(0)  # Taskwechsel erzwingen
            gesehen[name] = build_http_client_factory()().headers.get("authorization", "")

        async def beide() -> None:
            await asyncio.gather(
                zug("a", "wlo2.person-a"),
                zug("b", "wlo2.person-b"),
            )

        asyncio.run(beide())
        assert gesehen == {
            "a": "Bearer wlo2.person-a",
            "b": "Bearer wlo2.person-b",
        }

    def test_ein_zug_faerbt_den_aufrufer_nicht_ein(self, ohne_einstellung):
        """Gegenrichtung: was in einer Task gesetzt wird, bleibt dort."""

        async def zug() -> None:
            set_turn_auth_block("wlo2.nur-hier-drin")

        asyncio.run(zug())
        assert has_auth_token() is False
