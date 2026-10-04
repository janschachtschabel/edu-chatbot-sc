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

import contextlib
import ipaddress
import socket
import threading
import time
from urllib.parse import urlparse

# Nur diese Schemata dürfen gefetcht werden; file://, ftp://, gopher:// etc. sind
# klassische SSRF-Vektoren und werden auch bei öffentlichem Host abgewiesen.
_ALLOWED_SCHEMES = frozenset({"http", "https"})

# Hostnamen, die nie nach außen zeigen — billig ohne DNS geblockt (die IP-Prüfung
# unten fängt die meisten ohnehin, aber ``localhost``/``.local`` haben u.U. keine
# auflösbare Adresse und müssen namentlich raus).
_BLOCKED_HOSTNAMES = frozenset({"localhost", "127.0.0.1", "0.0.0.0", "::1"})


class UnsafeUrlError(ValueError):
    """Raised when a URL has no host, a non-http(s) scheme, or an internal address."""


class DownloadAbgebrochen(Exception):
    """Ein Abruf überschritt Bytedeckel oder Gesamtfrist (Paket 4, C5)."""


#: (Verbindung, Lesen) je Vorgang in Sekunden — die Gesamtfrist kommt dazu.
ABRUF_TIMEOUT = (5, 30)
_STUECK = 64 * 1024


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
        raise UnsafeUrlError(f"Cannot resolve hostname: {hostname}") from exc
    for *_, addr in resolved:
        ip = ipaddress.ip_address(addr[0])
        # ``not is_global`` deckt private/loopback/link-local/reserved UND
        # zusätzlich multicast/unspecified (0.0.0.0/::) in einem Check ab
        # (Audit-Härtung N-… — vorher fehlten multicast/unspecified explizit).
        if not ip.is_global:
            raise UnsafeUrlError("Internal network URLs not allowed")


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
            try:
                assert_public_url(request.url)
            except UnsafeUrlError as e:
                raise requests.exceptions.InvalidURL(str(e)) from e
            return super().send(request, **kwargs)

    session = requests.Session()
    # Markdown-Präferenz wie MarkItDowns Default-Session (geht sonst verloren).
    session.headers.update(
        {"Accept": "text/markdown, text/html;q=0.9, text/plain;q=0.8, */*;q=0.1"}
    )
    guard = _SsrfGuardAdapter()
    session.mount("http://", guard)
    session.mount("https://", guard)
    return session


def hole_begrenzt(url: str, *, max_bytes: int, frist_s: float) -> tuple[bytes, str]:
    """``url`` über die SSRF-Sitzung holen — mit Frist und Bytedeckel (Paket 4, C5).

    Gibt ``(rumpf, content_type)`` zurück. ``max_bytes == 0`` heißt ohne Deckel,
    wie ``BOERDI_MAX_INGEST_MB=0`` beim Datei-Upload. Synchron (``requests``):
    der Aufrufer legt es in einen Thread.

    Vorher holte markitdown selbst — ohne Frist, und es las den ganzen Rumpf in
    den Speicher (externes Audit F17). ``ABRUF_TIMEOUT`` begrenzt jeden einzelnen
    Lesevorgang; ein Server, der tröpfelt, unterliefe das, deshalb die
    Gesamtfrist ``frist_s``. Sie zählt ab dem Aufruf, also samt Umleitungen und
    Kopfzeilen; den Rumpf schneidet ein Wächter zur Frist ab. Die Kopfzeilen
    selbst kann er nicht abschneiden (es gibt noch keine Antwort) — die
    Restlücke steht in der Befundliste.

    Raises:
        DownloadAbgebrochen: zu groß (schon laut Header oder beim Lesen) oder zu
            langsam.
        requests.RequestException: Netz- und HTTP-Fehler, auch ein Umweg auf
            eine interne Adresse (``InvalidURL`` aus dem Guard).
    """
    import requests

    beginn = time.monotonic()
    with make_ssrf_guarded_session() as session, session.get(
            url, stream=True, timeout=ABRUF_TIMEOUT) as antwort:
        antwort.raise_for_status()
        laenge = str(antwort.headers.get("Content-Length") or "")
        if max_bytes and laenge.isdigit() and int(laenge) > max_bytes:
            raise DownloadAbgebrochen(
                f"Die Seite ist größer als {max_bytes // (1024 * 1024)} MB.")
        zu_langsam = DownloadAbgebrochen(f"Die Seite lieferte nicht binnen {frist_s:g} s.")
        # ``iter_content`` wartet auf volle 64 KB, und jeder Empfang setzt die
        # Lesefrist neu: ein Server, der tröpfelt, hielte den Thread sonst
        # tagelang. Der Wächter schließt den Socket zur Frist (Prüfer 2026-10-04).
        wache = threading.Timer(max(0.0, frist_s - (time.monotonic() - beginn)),
                                _abschalten, args=(antwort,))
        wache.daemon = True
        wache.start()
        rumpf = bytearray()
        try:
            for stueck in antwort.iter_content(chunk_size=_STUECK):
                rumpf.extend(stueck)
                if max_bytes and len(rumpf) > max_bytes:
                    raise DownloadAbgebrochen(
                        f"Die Seite ist größer als {max_bytes // (1024 * 1024)} MB.")
                if time.monotonic() - beginn > frist_s:
                    raise zu_langsam
        except (requests.RequestException, OSError):
            if time.monotonic() - beginn >= frist_s:
                raise zu_langsam from None
            raise
        finally:
            wache.cancel()
        # Ohne Längenangabe endet ein abgeschalteter Rumpf wie ein fertiger —
        # er ist dann abgeschnitten, nicht vollständig.
        if time.monotonic() - beginn >= frist_s:
            raise zu_langsam
        return bytes(rumpf), str(antwort.headers.get("Content-Type") or "")


def _abschalten(antwort) -> None:
    """Den Socket einer laufenden Antwort schließen (aus dem Wächter-Thread)."""
    # Nach Rumpf-Ende oder Freigabe gibt es nichts mehr abzuschalten; der Wächter
    # darf dann nichts tun, und eine Ausnahme im Timer-Thread hülfe niemandem.
    with contextlib.suppress(Exception):
        antwort.raw.shutdown()
