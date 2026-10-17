"""Obergrenze für Anfrage-Rümpfe — bevor FastAPI sie liest (Audit 2026-09-29).

**Warum eine eigene Schicht.** FastAPI liest den Rumpf, bevor Abhängigkeiten
laufen: JSON landet ganz im Speicher, Multipart-Dateien ganz auf der Platte —
vor dem Studio-Schlüssel und vor der Drossel. Die fachlichen Deckel an den
Endpunkten (Audio 10 MB, Ingest, Konfig-ZIP) greifen erst danach. Ohne diese
Schicht legte ein einziger Multi-GB-POST an ``/api/chat`` eine Replika lahm,
und ein großer Upload füllte die Platte, auf der auch Postgres liegt. uvicorn
kennt keine Rumpf-Grenze, traefik puffert nicht.

**Zwei Wege.** Mit ``Content-Length`` wird vorab abgewiesen (413, der Rumpf
wird gar nicht erst gelesen). Ohne Längenangabe (chunked) zählt ``receive``
mit und bricht beim Überschreiten mit einer ``HTTPException(413)`` ab — FastAPI
reicht sie aus dem Rumpf-Parser unverändert durch.

**Die Grenzen folgen den fachlichen Deckeln**, jeweils mit 1 MiB Luft für die
Multipart-Hülle; eine Grenze, die einen erlaubten Upload abschnitte, wäre ein
neuer Fehler. ``BOERDI_MAX_INGEST_MB=0`` bleibt der dokumentierte Weg zu
unbegrenzten Ingest-Uploads.

**Lage im Stapel:** innerhalb von CORS (sonst fehlten der 413 die CORS-Kopf-
zeilen, und das Widget sähe einen CORS-Fehler) und innerhalb des
Studio-Proxys (der Pfad ist dann schon auf ``/api/*`` umgeschrieben).
"""

from __future__ import annotations

from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from boerdi.api.scope_pfad import route_path
from boerdi.services.snapshots import MAX_CONFIG_UPLOAD_BYTES
from boerdi.services.speech_proxy import MAX_AUDIO_BYTES
from boerdi.settings import get_settings

_MIB = 1024 * 1024

#: Anonyme Züge: Nachricht, Seitenkontext, Gastgeber-Anweisung, Agent-Auftrag
#: (bis 200 000 Zeichen) passen weit hinein.
_OEFFENTLICHE_ZUEGE = ("/api/chat", "/api/agent")
_OEFFENTLICH_BYTES = 2 * _MIB
#: Alles andere (Studio-JSON, Konfig-Bereiche, Text-Ingest).
_ALLGEMEIN_BYTES = 16 * _MIB
_KONFIG_UPLOADS = ("/api/config/restore", "/api/config/factory/upload")


def _unter(pfad: str, praefix: str) -> bool:
    return pfad == praefix or pfad.startswith(praefix + "/")


def body_limit_for(path: str) -> int | None:
    """Die Rumpf-Grenze für ``path`` in Bytes — ``None`` heißt unbegrenzt."""
    if path == "/api/speech/transcribe":
        return MAX_AUDIO_BYTES + _MIB
    if path in _KONFIG_UPLOADS:
        return MAX_CONFIG_UPLOAD_BYTES + _MIB
    if path == "/api/rag/ingest/file":
        max_mb = get_settings().max_ingest_mb
        return (max_mb + 1) * _MIB if max_mb > 0 else None
    if any(_unter(path, p) for p in _OEFFENTLICHE_ZUEGE):
        return _OEFFENTLICH_BYTES
    return _ALLGEMEIN_BYTES


class BodySizeLimitMiddleware:
    """Reine ASGI-Schicht: Streams und SSE laufen ungepuffert durch."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        # Ohne ``root_path``, wie der Router (Paket 10, Audit L-4).
        grenze = body_limit_for(route_path(scope))
        if grenze is None:
            await self.app(scope, receive, send)
            return

        laenge = _content_length(scope)
        if laenge is not None and laenge > grenze:
            await _zu_gross(grenze)(scope, receive, send)
            return

        gelesen = 0

        async def begrenzt() -> Message:
            nonlocal gelesen
            nachricht = await receive()
            if nachricht["type"] == "http.request":
                gelesen += len(nachricht.get("body", b""))
                if gelesen > grenze:
                    raise HTTPException(413, _text(grenze))
            return nachricht

        await self.app(scope, begrenzt, send)


def _content_length(scope: Scope) -> int | None:
    for name, wert in scope.get("headers") or []:
        if name == b"content-length":
            try:
                return int(wert)
            except ValueError:
                return None
    return None


def _text(grenze: int) -> str:
    return f"Anfrage zu groß (höchstens {grenze // _MIB} MB)."


def _zu_gross(grenze: int) -> JSONResponse:
    return JSONResponse({"detail": _text(grenze)}, status_code=413)
