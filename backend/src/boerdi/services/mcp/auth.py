"""Zugangsblock und Betriebsart des MCP-Clients (C1–C3, C5-a).

Der WLO-MCP-Server nimmt einen **Zugangsblock** als
``Authorization: Bearer wlo2.…`` entgegen. Serverseitig gibt es davon **drei**
Betriebsarten (`docs/AUTH.md` §2: ``anonymous`` / ``service`` / ``user``) — eine
frühere Fassung dieses Kommentars behauptete „genau zwei" und lag falsch; live
gegen `wlo_auth_status` gemessen 2026-08-10.

Ein ``401`` kommt **nur bei einem vorgelegten, aber unbrauchbaren** Block —
anonym zu bleiben ist kein Fehler.

**Zwei Quellen, eine Rangfolge (C5-a).** Der Block dieses *Zuges* schlägt den
der *Anlage*:

* **Zug** — die Person hat sich beim MCP-Server angemeldet; das Widget schickt
  ihren Block je Anfrage mit. Er lebt in einem ``ContextVar``, also je
  asyncio-Task, und wird bei uns **nirgends gespeichert**.
* **Anlage** — ``MCP_AUTH_TOKEN`` aus den Einstellungen. Dort gehört ein
  *Dienstkonto* hin oder nichts: ein persönlicher Block ließe jeden anonymen
  Besucher unter einem echten Namen handeln.

Warum ein ``ContextVar`` und kein Parameter: es gibt 23 Aufrufstellen von
``call_mcp_tool`` in 9 Dateien (gemessen 2026-08-10); der Block interessiert
unterwegs niemanden. Dasselbe Mittel löst hier schon ``_query_metas``
(`mcp/client.py`) und ``_request_hints`` (`mcp/arg_resolvers.py`).

Der Block ist ein Geheimnis — aus beiden Quellen. Er wird hier nur an die
httpx-Fabrik durchgereicht und **nirgends protokolliert oder ausgegeben**;
dieses Modul loggt bewusst gar nicht, auch keine Ablehnung.
"""

from __future__ import annotations

import contextvars as _ctxvars
import re

import httpx
from mcp.client.streamable_http import create_mcp_http_client
from mcp.shared._httpx_utils import McpHttpClientFactory

from boerdi.settings import get_settings

# Der Zugangsblock DIESES Zuges. Je asyncio-Task, damit zwei gleichzeitige
# Züge sich nicht gegenseitig anmelden. Der Standard ist unveränderlich (str),
# gesetzt wird immer neu gebunden — nichts kann aus dem Standard auslaufen.
_turn_block: _ctxvars.ContextVar[str] = _ctxvars.ContextVar("_turn_block", default="")

# Prüfung am Rand: der Block kommt aus einer Kopfzeile, also aus unvertrauter
# Hand. Das Muster erzwingt beides in einem Ausdruck —
#  * Präfix ``wlo``: sonst wäre unser Backend ein beliebiger Weiterleiter für
#    fremde ``Authorization``-Werte an den MCP-Wirt, dessen Missbrauchsschranke
#    je Adresse zählt (also gegen unsere). Deckt ``wlo2.…`` und ``wlo-anon.v1``
#    ab und überlebt ein künftiges ``wlo3.``.
#  * Zeichenvorrat: base64url + Trennpunkte. Schliesst Steuerzeichen aus, die
#    sonst eine zweite Kopfzeile anhängen könnten, und das mitgereiste Wort
#    „Bearer " (AUTH.md §5a: genau das kostete dort live einen Nachmittag).
# ``\Z`` statt ``$``, weil ``$`` auch vor einem abschliessenden Zeilenumbruch passt.
_WOHLGEFORMT = re.compile(r"^wlo[A-Za-z0-9._~+/=-]*\Z")
_MAX_BLOCK_LEN = 4096

# Der ausdrücklich ANONYME Block des MCP-Servers (`auth/credential.ts:
# ANONYMOUS_ACCESS_TOKEN`, heute ``wlo-anon.v1``). Als Präfix geprüft, damit ein
# künftiges ``wlo-anon.v2`` nicht durchrutscht.
_ANONYM_PRAEFIX = "wlo-anon."


def _ist_wohlgeformt(block: str) -> bool:
    """Form und Länge — die Bedingung, unter der ein Block weitergereicht wird."""
    return bool(block) and len(block) <= _MAX_BLOCK_LEN and bool(_WOHLGEFORMT.match(block))


def _token() -> str:
    """Der Zugangsblock der ANLAGE, getrimmt — leer, wenn keiner gesetzt ist.

    Leerzeichen zählen wie „nicht gesetzt": die Compose-Falle
    ``${MCP_AUTH_TOKEN:-}`` liefert einen leeren String, und ein Block aus
    Leerzeichen ist kein Block.
    """
    return (get_settings().mcp_auth_token.get_secret_value() or "").strip()


def _effective_token() -> str:
    """Der Block, der für den laufenden Aufruf gilt — Zug vor Anlage."""
    return _turn_block.get("") or _token()


def set_turn_auth_block(raw: str | None) -> bool:
    """Übernimm den Zugangsblock dieses Zuges. Gibt zurück, ob einer nun gilt.

    Ein abgelehnter Wert **löscht** einen früher gesetzten Block, statt ihn
    stehen zu lassen — sonst hinge ein Zug an der Anmeldung des vorigen, was die
    schwerste denkbare Verwechslung wäre.

    ``None``/leer löscht ebenfalls und gibt ``False`` — das ist der Normalfall
    „keine Kopfzeile", kein Fehler. Wer eine Ablehnung *melden* will, muss die
    beiden Fälle beim Aufrufer unterscheiden (``raw`` war da, Rückgabe ist
    ``False``); dieses Modul protokolliert bewusst nicht, weil hier der Block
    liegt.
    """
    block = (raw or "").strip()
    if not _ist_wohlgeformt(block):
        _turn_block.set("")
        return False
    _turn_block.set(block)
    return True


def is_personal_block(raw: str | None) -> bool:
    """Kann ``raw`` die Anmeldung einer PERSON sein — statt bloß irgendein Block?

    Zwei Fragen in einer: wohlgeformt (sonst reicht ihn ohnehin niemand weiter)
    **und** nicht der ausdrücklich anonyme Block. Ohne die zweite wäre eine
    Prüfung darauf eine Formalie — die anonyme Konstante steht in der
    öffentlichen ``AUTH.md`` des MCP-Servers, jeder könnte sie mitschicken.

    **Was das ausdrücklich NICHT ist: ein Beweis.** Ob der Block gilt und wem er
    gehört, entscheidet allein der MCP-Server. Hier steht nur, ob überhaupt
    einer vorgelegt wurde, der eine Person meinen *kann*. Wer daraus eine
    Zugangsschranke baut, braucht daneben eine Mengenbremse — siehe
    ``api/turn_auth.require_agent_caller``.

    Ohne Seiteneffekt, anders als :func:`set_turn_auth_block`: die Frage stellt
    sich vor der Übernahme, in einer FastAPI-Abhängigkeit.
    """
    block = (raw or "").strip()
    return _ist_wohlgeformt(block) and not block.lower().startswith(_ANONYM_PRAEFIX)


def has_auth_token() -> bool:
    """Gilt für den laufenden Aufruf ein Zugangsblock — aus Zug oder Anlage?"""
    return bool(_effective_token())


def has_personal_auth() -> bool:
    """Steht hinter DIESEM Zug eine angemeldete Person? (A3a)

    Der Unterschied zu :func:`has_auth_token` ist die Anlage: deren Block hat
    der Betreiber einmal für alle gesetzt, er gehört einem Dienstkonto und nicht
    der Person vor dem Bildschirm. Für „darf gelesen werden" ist das egal — der
    MCP entscheidet ohnehin selbst. Für „darf **geschrieben** werden" ist es der
    ganze Unterschied: erlaubt ist das nur, wo eine echte Person mit
    WLO-Rechten dahintersteht (Nutzer-Entscheid 2026-08-12).
    """
    return bool(_turn_block.get(""))


def auth_mode() -> str:
    """Betriebsart der ANLAGE — ``"service"`` oder ``"anonymous"``.

    Bewusst NICHT zug-abhängig: das beantwortet ``/health``, und dort gibt es
    keinen Zug. Wäre es zug-abhängig, meldete dieselbe Anlage je nach zufällig
    mitlaufender Anfrage eine andere Betriebsart. Enthält den Block nie.
    """
    return "service" if _token() else "anonymous"


def build_http_client_factory() -> McpHttpClientFactory:
    """Die httpx-Fabrik, die das SDK je Verbindung aufruft.

    Ohne Block ist das der SDK-Standard, unverändert. Mit Block ergänzt die
    Fabrik die ``Authorization``-Kopfzeile und lässt alles andere durch, was das
    SDK mitgibt (eigene Kopfzeilen, Timeout, ``auth``).

    Welcher Block gilt, entscheidet :func:`_effective_token` — Zug vor Anlage.
    Die Fabrik wird je Aufruf in ``transport._open_session`` neu gebaut, also
    liest sie den Block des gerade laufenden Zuges und nicht den beim Start.

    Bewusst ``httpx_client_factory`` und NICHT der ``headers=``-Parameter von
    ``streamablehttp_client``: der ist im SDK als veraltet markiert
    („Parameters headers, timeout, sse_read_timeout, and auth are deprecated").
    ``create_mcp_http_client`` kommt aus demselben öffentlichen Modul wie
    ``streamablehttp_client`` — kein privater SDK-Pfad.
    """
    block = _effective_token()
    if not block:
        return create_mcp_http_client

    def factory(
        headers: dict[str, str] | None = None,
        timeout: httpx.Timeout | None = None,
        auth: httpx.Auth | None = None,
    ) -> httpx.AsyncClient:
        return create_mcp_http_client(
            headers={**(headers or {}), "Authorization": f"Bearer {block}"},
            timeout=timeout,
            auth=auth,
        )

    return factory
