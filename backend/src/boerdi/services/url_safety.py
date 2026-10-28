"""URL-Sicherheit — SSRF-Schutz für vom Studio/Nutzer gelieferte URLs.

Einziger Choke-Point für die drei Stellen, die eine gelieferte URL prüfen:
MCP-Discover, MCP-Server-Save (``routers/config.py``) und RAG-URL-Ingest
(``rag_service.convert_url_to_markdown``). Eine URL muss ein http(s)-Schema und
einen Host haben und darf nicht auf einen internen/privaten/Loopback-/Link-local-
Host zeigen (Cloud-Metadaten 169.254.169.254, localhost, private Ranges). So
erreicht eine registrierte oder abgefragte URL nicht das interne Netz (SSRF).

Bewusst framework-frei (kein FastAPI): der Aufrufer übersetzt ``UnsafeUrlError``
in seine HTTP-Antwort. Damit bleibt die Prüfung auch außerhalb eines Request-
Kontexts (z.B. call-time) nutzbar.

simplify (Audit T9, DNS-Rebind-TOCTOU nicht vollständig geschlossen): geprüft wird
die DNS-Auflösung zur Prüfzeit, nicht die IP zur Fetch-Zeit — es bleibt ein
Rebinding-Fenster zwischen Prüfung und späterem Fetch. Ein echtes Pinning müsste
im gemeinsamen HTTP-Transport landen (``mcp_client`` httpx-Client + markitdown
lösen intern selbst auf; der Primary-MCP-Server darf zudem bewusst intern sein) —
das ist ein eigener Transport-Umbau, kein Einzeiler hier. Diese Funktion
verhindert immerhin, dass eine interne URL überhaupt gespeichert/abgefragt wird.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from urllib.parse import urlparse

import httpx

# Nur diese Schemata dürfen gefetcht werden; file://, ftp://, gopher:// etc. sind
# klassische SSRF-Vektoren und werden auch bei öffentlichem Host abgewiesen.
_ALLOWED_SCHEMES = frozenset({"http", "https"})

# Hostnamen, die nie nach außen zeigen — billig ohne DNS geblockt (die IP-Prüfung
# unten fängt die meisten ohnehin, aber ``localhost``/``.local`` haben u.U. keine
# auflösbare Adresse und müssen namentlich raus).
_BLOCKED_HOSTNAMES = frozenset({"localhost", "127.0.0.1", "0.0.0.0", "::1"})


class UnsafeUrlError(ValueError):
    """Raised when a URL has no host, a non-http(s) scheme, or an internal address.

    ``grund`` (Paket 9): ``"nicht_erlaubt"`` oder ``"unbekannt"`` — der Name ließ
    sich nicht auflösen (``host``), meist ein Tippfehler. Der Text bleibt englisch
    fürs Log; den Satz in der Sprache des Studios bildet der Router, wie bei
    :class:`DownloadAbgebrochen` (bis Paket 9 stand der englische Text in ihm).
    """

    def __init__(self, text: str, *, grund: str = "nicht_erlaubt", host: str = "") -> None:
        super().__init__(text)
        self.grund = grund
        self.host = host


class DownloadAbgebrochen(Exception):
    """Ein Abruf überschritt Bytedeckel oder Gesamtfrist (Paket 4, C5).

    ``grund`` ist ``"zu_gross"`` (``wert`` in MB) oder ``"zu_langsam"`` (``wert``
    in Sekunden). Der Router macht daraus einen Satz in der Sprache des Studios
    (Paket 6, B6); der deutsche Text bleibt fürs Log.
    """

    def __init__(self, grund: str, wert: float) -> None:
        self.grund = grund
        self.wert = wert
        text = (f"Die Seite ist größer als {wert:g} MB." if grund == "zu_gross"
                else f"Die Seite lieferte nicht binnen {wert:g} s.")
        super().__init__(text)


#: Markdown-Vorliebe wie markitdowns eigene Sitzung (geht sonst verloren).
_ACCEPT = "text/markdown, text/html;q=0.9, text/plain;q=0.8, */*;q=0.1"


def assert_public_url(url: str) -> None:
    """Return ``None`` if *url* is safe to fetch; raise ``UnsafeUrlError`` otherwise.

    Blocks URLs without a host, with a non-http(s) scheme, and any host that
    resolves to a private, loopback, link-local, or reserved address.
    """
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    if not hostname:
        raise UnsafeUrlError("Invalid URL")
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise UnsafeUrlError("Only http(s) URLs are allowed")
    if hostname in _BLOCKED_HOSTNAMES or hostname.endswith(".local"):
        raise UnsafeUrlError("Internal URLs not allowed")
    try:
        resolved = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise UnsafeUrlError(f"Cannot resolve hostname: {hostname}",
                             grund="unbekannt", host=hostname) from exc
    for *_, addr in resolved:
        ip = ipaddress.ip_address(addr[0])
        # ``not is_global`` deckt private/loopback/link-local/reserved UND
        # zusätzlich multicast/unspecified (0.0.0.0/::) in einem Check ab
        # (Audit-Härtung N-… — vorher fehlten multicast/unspecified explizit).
        if not ip.is_global:
            raise UnsafeUrlError("Internal network URLs not allowed")


#: Frist je Folgeabruf von markitdown (Verbinden, Lesen) — Befundliste §1.4, Paket 11. Die
#: Gesamtfrist trägt der Kindprozess (``rag_conversion_timeout_s``); ohne diese hier hielte ein
#: einziger hängender Abruf die ganze Umwandlung bis dorthin auf und ließe sie scheitern.
FOLGEABRUF_FRIST = (10.0, 30.0)


def make_ssrf_guarded_session():
    """Eine ``requests.Session``, die JEDE Request-URL — inkl. Redirect-Hops —
    gegen :func:`assert_public_url` prüft.

    Schließt die Redirect-SSRF-Lücke (Audit N-2): ``assert_public_url`` validiert
    nur die Start-URL, ``requests`` folgt aber Redirects. Da ``requests`` für
    jeden Hop ``adapter.send()`` aufruft, fängt ein prüfender Adapter auch ein
    302 auf ``169.254.169.254``/localhost ab. Verwendbar als
    ``MarkItDown(requests_session=make_ssrf_guarded_session())``.
    """
    import requests
    from requests.adapters import HTTPAdapter

    class _SsrfGuardAdapter(HTTPAdapter):
        def send(self, request, **kwargs):  # noqa: D401
            if kwargs.get("timeout") is None:
                kwargs["timeout"] = FOLGEABRUF_FRIST
            try:
                assert_public_url(request.url)
            except UnsafeUrlError as e:
                raise requests.exceptions.InvalidURL(str(e)) from e
            return super().send(request, **kwargs)

    session = requests.Session()
    # Markdown-Präferenz wie MarkItDowns Default-Session (geht sonst verloren).
    session.headers.update({"Accept": _ACCEPT})
    guard = _SsrfGuardAdapter()
    session.mount("http://", guard)
    session.mount("https://", guard)
    return session


class _SsrfTransport(httpx.AsyncBaseTransport):
    """Prüft JEDE Anfrage gegen :func:`assert_public_url` — auch jeden Schritt
    einer Umleitung, denn ``httpx`` schickt jeden durch den Transport (N-2 auf
    dem ``httpx``-Weg). Die DNS-Prüfung läuft im Thread: ``getaddrinfo``
    blockiert.
    """

    def __init__(self) -> None:
        self._netz = httpx.AsyncHTTPTransport()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        await asyncio.to_thread(assert_public_url, str(request.url))
        return await self._netz.handle_async_request(request)

    async def aclose(self) -> None:
        await self._netz.aclose()


async def hole_begrenzt(url: str, *, max_bytes: int, frist_s: float) -> tuple[bytes, str]:
    """``url`` holen — mit Bytedeckel und einer Gesamtfrist für ALLES (Paket 6, B2).

    Gibt ``(rumpf, content_type)`` zurück. ``max_bytes == 0`` heißt ohne Deckel,
    wie ``BOERDI_MAX_INGEST_MB=0`` beim Datei-Upload.

    Bis Paket 6 holte ``requests`` im Thread: Die Gesamtfrist erreichte nur den
    Rumpf, ein Server, der Kopfzeilen oder Umleitungen tröpfelte, hielt den
    Abruf, solange er wollte (gemessen: 3,3 s bei einer Frist von 0,3 s). Jetzt
    läuft alles unter ``asyncio.timeout``: Verbindung, Kopfzeilen, Umleitungen
    und Rumpf. Abgebrochen wird über die Aufgabe, nicht über einen Socket aus
    einem Wächter-Thread. Eigene Fristen je Vorgang braucht es daneben nicht.

    Umleitungen folgt der Abruf selbst und schließt jeden Schritt ungelesen
    (Review Paket 6): ``follow_redirects`` liest in ``httpx`` jeden 3xx-Rumpf
    ganz (``aread``), am Bytedeckel vorbei. Höchstens ``max_redirects`` Schritte,
    wie bisher.

    Raises:
        DownloadAbgebrochen: zu groß (schon laut Header oder beim Lesen) oder zu
            langsam.
        UnsafeUrlError: ein Schritt der Umleitung zeigt auf eine interne Adresse.
        httpx.HTTPError: Netz- und HTTP-Fehler, auch zu viele Umleitungen.
    """
    try:
        async with (
            asyncio.timeout(frist_s),
            httpx.AsyncClient(transport=_SsrfTransport(), follow_redirects=False,
                              headers={"Accept": _ACCEPT}, timeout=None) as client,
        ):
            anfrage = client.build_request("GET", url)
            for _ in range(client.max_redirects + 1):
                antwort = await client.send(anfrage, stream=True)
                try:
                    if antwort.next_request is None:
                        return await _lies_begrenzt(antwort, max_bytes)
                    anfrage = antwort.next_request
                finally:
                    await antwort.aclose()
            raise httpx.TooManyRedirects("zu viele Umleitungen", request=anfrage)
    except TimeoutError:
        raise DownloadAbgebrochen("zu_langsam", frist_s) from None


async def _lies_begrenzt(antwort: httpx.Response, max_bytes: int) -> tuple[bytes, str]:
    """Den Rumpf der letzten Antwort lesen, höchstens ``max_bytes`` (0 = ohne Deckel)."""
    antwort.raise_for_status()
    laenge = antwort.headers.get("Content-Length", "")
    if max_bytes and laenge.isdigit() and int(laenge) > max_bytes:
        raise DownloadAbgebrochen("zu_gross", max_bytes // (1024 * 1024))
    rumpf = bytearray()
    async for stueck in antwort.aiter_bytes():
        rumpf.extend(stueck)
        if max_bytes and len(rumpf) > max_bytes:
            raise DownloadAbgebrochen("zu_gross", max_bytes // (1024 * 1024))
    return bytes(rumpf), antwort.headers.get("Content-Type", "")
