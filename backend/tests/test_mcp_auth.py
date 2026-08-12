"""C1–C3: Zugangsblock und Betriebsart des MCP-Clients.

Der Server nimmt laut seiner eigenen Übergabedoku (`INTEGRATION.md` §2.5) einen
Zugangsblock als ``Authorization: Bearer wlo2.…`` entgegen. Ohne Kopfzeile
antwortet er weiter mit ``200`` und der vollen Werkzeugliste — ``401`` kommt nur
bei einem *vorgelegten, aber unbrauchbaren* Token. Deshalb gibt es genau zwei
Betriebsarten und keinen dritten Fehlerzustand.

Wichtigste Zusicherung dieser Datei: **der Block darf nirgends sichtbar
werden** — nicht im ``repr`` der Einstellungen, nicht in Protokollzeilen, nicht
in der Health-Auskunft.
"""

from __future__ import annotations

import logging

import pytest
from pydantic import SecretStr

from boerdi.services.mcp import auth as auth_mod
from boerdi.services.mcp.auth import (
    auth_mode,
    build_http_client_factory,
    has_auth_token,
)

_BLOCK = "wlo2.geheim-nur-im-test"


@pytest.fixture
def mit_block(monkeypatch):
    """Einstellungen mit hinterlegtem Zugangsblock."""
    from boerdi.settings import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "mcp_auth_token", SecretStr(_BLOCK), raising=False)
    return s


@pytest.fixture
def ohne_block(monkeypatch):
    from boerdi.settings import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "mcp_auth_token", SecretStr(""), raising=False)
    return s


# ── Betriebsart ──────────────────────────────────────────────────────────


class TestBetriebsart:
    def test_ohne_block_anonym(self, ohne_block):
        assert has_auth_token() is False
        assert auth_mode() == "anonymous"

    def test_mit_block_dienst(self, mit_block):
        assert has_auth_token() is True
        assert auth_mode() == "service"

    def test_nur_leerzeichen_gilt_als_nicht_gesetzt(self, monkeypatch):
        # Die Docker-Compose-Falle ``${MCP_AUTH_TOKEN:-}`` liefert einen leeren
        # String; ein Block aus Leerzeichen ist kein Block.
        from boerdi.settings import get_settings

        monkeypatch.setattr(get_settings(), "mcp_auth_token", SecretStr("   "),
                            raising=False)
        assert has_auth_token() is False
        assert auth_mode() == "anonymous"


# ── Der Block darf nirgends auftauchen ───────────────────────────────────


class TestKeinLeck:
    def test_auth_mode_nennt_den_block_nicht(self, mit_block):
        assert _BLOCK not in auth_mode()

    def test_einstellungs_repr_nennt_den_block_nicht(self, mit_block):
        assert _BLOCK not in repr(mit_block)
        assert _BLOCK not in str(mit_block.mcp_auth_token)

    def test_fabrik_protokolliert_den_block_nicht(self, mit_block, caplog):
        with caplog.at_level(logging.DEBUG, logger=auth_mod.__name__):
            build_http_client_factory()
        assert _BLOCK not in caplog.text


# ── httpx-Fabrik (C1) ────────────────────────────────────────────────────


class TestClientFabrik:
    def test_mit_block_setzt_die_kopfzeile(self, mit_block):
        client = build_http_client_factory()(headers={"X-Vorher": "bleibt"})
        try:
            assert client.headers["authorization"] == f"Bearer {_BLOCK}"
            # Vorhandene Kopfzeilen des SDK dürfen nicht verloren gehen.
            assert client.headers["x-vorher"] == "bleibt"
        finally:
            pass

    def test_ohne_block_keine_kopfzeile(self, ohne_block):
        client = build_http_client_factory()(headers={"X-Vorher": "bleibt"})
        assert "authorization" not in client.headers
        assert client.headers["x-vorher"] == "bleibt"

    def test_fabrik_ohne_kopfzeilen_aufrufbar(self, mit_block):
        # Das SDK ruft die Fabrik auch ohne ``headers`` auf.
        client = build_http_client_factory()()
        assert client.headers["authorization"] == f"Bearer {_BLOCK}"


# ── Verdrahtung im Transport (C1) ────────────────────────────────────────
# Alle rund 25 Aufrufstellen laufen über EINE Naht: ``_open_session``. Hier
# wird geprüft, dass sie die Fabrik übergibt — und zwar über
# ``httpx_client_factory``, nicht über den im SDK als veraltet markierten
# ``headers``-Parameter.


class TestTransportVerdrahtung:
    @staticmethod
    def _fang_kwargs(monkeypatch) -> dict:
        from contextlib import asynccontextmanager

        from boerdi.services.mcp import transport as transport_mod

        gefangen: dict = {}

        @asynccontextmanager
        async def _fake_client(url, **kwargs):
            gefangen["url"] = url
            gefangen["kwargs"] = kwargs
            raise AssertionError("Naht geprüft — kein echter Verbindungsaufbau")
            yield  # pragma: no cover — unerreichbar, hält den Generator-Typ

        monkeypatch.setattr(transport_mod, "streamablehttp_client", _fake_client)
        return gefangen

    def test_open_session_uebergibt_die_fabrik(self, monkeypatch, mit_block):
        import asyncio

        from boerdi.services.mcp.transport import _open_session

        gefangen = self._fang_kwargs(monkeypatch)

        async def _lauf():
            async with _open_session("https://beispiel.test/mcp"):
                pass

        with pytest.raises(AssertionError, match="Naht geprüft"):
            asyncio.run(_lauf())

        assert "httpx_client_factory" in gefangen["kwargs"]
        # Der veraltete Weg darf NICHT genutzt werden.
        assert "headers" not in gefangen["kwargs"]
        client = gefangen["kwargs"]["httpx_client_factory"]()
        assert client.headers["authorization"] == f"Bearer {_BLOCK}"

    def test_ohne_block_bleibt_die_sdk_fabrik(self, monkeypatch, ohne_block):
        import asyncio

        from mcp.client.streamable_http import create_mcp_http_client

        from boerdi.services.mcp.transport import _open_session

        gefangen = self._fang_kwargs(monkeypatch)

        async def _lauf():
            async with _open_session("https://beispiel.test/mcp"):
                pass

        with pytest.raises(AssertionError, match="Naht geprüft"):
            asyncio.run(_lauf())

        assert gefangen["kwargs"]["httpx_client_factory"] is create_mcp_http_client


# ── Lesbare Ursache bei Transportfehlern ─────────────────────────────────
# Erst durch C1 kann ein Aufruf an der ANMELDUNG scheitern. Live gemessen
# (2026-08-10, unbrauchbarer Block gegen den echten Server): das SDK wirft eine
# ``ExceptionGroup``, deren ``str()`` nur „unhandled errors in a TaskGroup
# (1 sub-exception)" lautet — der ``401`` steckt in der Unterausnahme. Ohne
# Auspacken bekäme ein Betreiber mit falschem Block bei JEDER Suche diesen
# nichtssagenden Satz und keinen Hinweis auf die Ursache.


class TestFehlerursache:
    def test_gruppe_wird_ausgepackt(self):
        from boerdi.services.mcp.transport import _cause_text

        gruppe = ExceptionGroup(
            "unhandled errors in a TaskGroup",
            [RuntimeError("Client error '401 Unauthorized' for url …")],
        )
        text = _cause_text(gruppe)
        assert "401 Unauthorized" in text
        assert "TaskGroup" not in text

    def test_verschachtelte_gruppe(self):
        from boerdi.services.mcp.transport import _cause_text

        innen = ExceptionGroup("innen", [ValueError("echte Ursache")])
        assert "echte Ursache" in _cause_text(ExceptionGroup("aussen", [innen]))

    def test_einzelne_ausnahme_bleibt_wortgleich(self):
        # Bestandsverhalten: für gewöhnliche Ausnahmen bleibt es bei ``str(exc)``.
        from boerdi.services.mcp.transport import _cause_text

        assert _cause_text(RuntimeError("connect refused")) == "connect refused"


# ── Betriebsart in der Health-Auskunft (C3) ──────────────────────────────


class TestHealthAuskunft:
    def test_nennt_die_betriebsart_ohne_den_block(self, mit_block):
        from boerdi.api.health import _health_detail

        info = _health_detail()
        assert info["mcp_auth"] == "service"
        assert _BLOCK not in repr(info)

    def test_anonym_wenn_kein_block(self, ohne_block):
        from boerdi.api.health import _health_detail

        assert _health_detail()["mcp_auth"] == "anonymous"
