"""Widget bundle + demo pages (public, C4/P7-Rest).

A host page embeds the widget with two lines and no key:

    <script src="https://api.example.com/widget/boerdi-widget.js" defer></script>
    <boerdi-chat api-url="https://api.example.com"></boerdi-chat>

**Improvement V1 — the stable path points at a hashed one.** ALT served the
bundle straight from ``/widget/boerdi-widget.js`` with ``no-store``, so every
page load re-downloaded ~412 kB. Here the stable path answers with a redirect to
``/widget/boerdi-widget.<digest>.js``, and *that* URL is ``immutable`` for a
year: the browser stops asking. Because the digest comes from the file's
content, a new build mints a new URL by itself — which also ends the "studio new,
widget old" failure class, where a cached bundle silently outlived its config.

**Two things deliberately differ from ALT:**

* The directory comes from ``WIDGET_DIST_DIR`` alone. ALT computed
  ``parents[3]/frontend/dist/widget/browser`` and fell back to a copy in
  ``backend/widget_dist`` because it had no setting; this project configures
  static roots explicitly (like ``STUDIO_DIST_DIR`` in ``studio_static.py``),
  which covers both of ALT's cases without guessing from ``__file__``.
* The hashed name is served **by the catch-all**, not by a route of its own. The
  route surface is frozen (``docs/api/openapi-v1.json``), and a path of its own
  would be contract drift for something that is an implementation detail of the
  redirect. (``/frameless`` was added to the contract deliberately in U1 — a
  demo page for a new embed mode is a capability, not an internal detail. The
  step was purely additive: one path, nothing changed or removed.)

**Zwei bewusste Vertrags-Schritte am 2026-08-13**, beide additiv und beide neu
eingefroren (``scripts/export_openapi.py``):

* Die drei Live-Demos nehmen ``?kontext=&wert=`` für den Seitenkontext-Simulator
  entgegen — optionale Parameter mit Vorgabe, kein Pfad kam hinzu oder fiel weg
  (der Bestands-Wächter ``test_route_inventory_matches_spec_5_1`` blieb still).
* Die vier Seiten wurden **umgewidmet**, nicht umbenannt: ``/`` ist jetzt die
  Übersicht, ``/classic`` der schwebende Knopf, ``/inline`` der eingebettete
  Chat. Vorher zeigten drei von vier denselben schwebenden Knopf. Umwidmen statt
  Löschen genau deshalb, weil die Pfade im Vertrag stehen — was eine Seite
  *zeigt*, ist keine Vertragszusage, ihr Vorhandensein schon.

**No ``/api/static`` mount.** ALT had one, for a logo its demo pages and widget
loaded by absolute URL. Nothing in this project reads it: the widget carries the
logo inline (``ui/src/branding/boerdi-logo.ts`` exports the SVG and a data URL),
and the one helper that would build such a URL — ``boerdiLogoUrl()`` — has no
caller. Mounting a directory nothing requests, to serve an asset nothing loads,
is not a port. Whoever starts calling that helper adds the mount with it.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response

from boerdi.api import widget_demo_html
from boerdi.settings import get_settings

public_router = APIRouter(prefix="/widget", tags=["widget"])

#: What ``npm run build:widget`` emits — one file, enforced by the §5.5 gate.
BUNDLE = "main.js"

#: ``boerdi-widget.<12 hex>.js`` — minted by the redirect below, never on disk.
_HASHED = re.compile(r"^boerdi-widget\.[0-9a-f]{12}\.js$")

_IMMUTABLE = "public, max-age=31536000, immutable"
_NO_STORE = "no-store, must-revalidate"

_MEDIA_TYPES = {".js": "application/javascript", ".css": "text/css", ".map": "application/json"}


def _widget_dir() -> Path:
    """Resolved per call, not at import: tests point the setting elsewhere."""
    return Path(get_settings().widget_dist_dir)


def _resolve(asset_name: str) -> Path:
    """A path inside the widget directory, or an HTTP error.

    The containment check runs **before** the existence check on purpose: a
    "not found" for a path outside the directory would answer whether a file
    exists on the host filesystem. Both cases now look the same from outside.
    """
    base = _widget_dir()
    target = (base / asset_name).resolve()
    try:
        target.relative_to(base.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid path") from None
    if not target.is_file():
        raise HTTPException(status_code=404, detail=f"asset not found: {asset_name}")
    return target


def _public(resp: Response, cache: str) -> Response:
    """Embed headers. ``*`` because the point is to load from foreign pages."""
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Cache-Control"] = cache
    return resp


def _digest(bundle: Path) -> str:
    """Content hash of the bundle, short enough to read in a log.

    Recomputed per request rather than cached: it is only ever hit on the stable
    path (once per page load, then the browser holds the hashed URL for a year),
    and a cache here would need its own invalidation — the exact mechanism whose
    failure this improvement exists to prevent.
    """
    return hashlib.sha256(bundle.read_bytes()).hexdigest()[:12]


@public_router.get("/boerdi-widget.js")
def widget_bundle() -> Response:
    """The stable entry point every host page embeds — redirects to the hash."""
    bundle = _widget_dir() / BUNDLE
    if not bundle.is_file():
        # 503, not 404: the route exists, the deploy is incomplete. Naming the
        # command is the difference between a two-minute and a two-hour fix.
        raise HTTPException(
            status_code=503,
            detail="Widget bundle not built yet. Run `cd frontend && npm run build:widget` first.",
        )
    target = f"{public_router.prefix}/boerdi-widget.{_digest(bundle)}.js"
    # 302, never 301: the mapping changes with every build, and a permanent
    # redirect would pin browsers to a dead URL for good.
    return _public(RedirectResponse(target, status_code=302), _NO_STORE)


#: Die Wahl des Kontext-Simulators, wie sie im Query-String reist. Als
#: ``Query``-Parameter DEKLARIERT, anders als ``X-Boerdi-Engine`` bei den
#: Kopfzeilen: die Demo-Seiten stehen nicht im eingefrorenen Vertrag der
#: ``/api``-Fläche, und ein deklarierter Parameter ist hier der ehrlichere Weg —
#: er steht in ``/docs`` und FastAPI prüft die Länge, bevor der Wert die
#: Erlaubnisliste in ``widget_demo_context`` überhaupt erreicht.
#:
#: Seit P5 ``None``-fähig, und das ist keine Kosmetik: ``None`` heisst „stand
#: nicht in der Adresse" — dann greift die Voreinstellung —, ``""`` heisst
#: „nichts Bestimmtem", also ausdrücklich aus. Das Formular schickt immer beide
#: Felder mit; ohne diesen Unterschied käme die Voreinstellung zurück, sobald
#: man sie abwählt (``widget_demo_context.resolve_choice``).
_Kontext = Annotated[str | None, Query(max_length=32)]
_Wert = Annotated[str | None, Query(max_length=2048)]


@public_router.get("/")
def widget_demo() -> Response:
    """Overview of the three embed situations — no widget of its own."""
    return HTMLResponse(widget_demo_html.index_page())


@public_router.get("/inline")
def widget_demo_inline(kontext: _Kontext = None, wert: _Wert = None) -> Response:
    """The embedded look: frameless inside the page's own container, open."""
    return HTMLResponse(widget_demo_html.inline_page((kontext, wert)))


@public_router.get("/classic")
def widget_demo_classic(kontext: _Kontext = None, wert: _Wert = None) -> Response:
    """The default embed: the floating owl button, opening on click."""
    return HTMLResponse(widget_demo_html.classic_page((kontext, wert)))


@public_router.get("/frameless")
def widget_demo_frameless(kontext: _Kontext = None, wert: _Wert = None) -> Response:
    """The frameless embed (U1), started collapsed — the "give it a height" case."""
    return HTMLResponse(widget_demo_html.frameless_page((kontext, wert)))


@public_router.get("/{asset_name}")
def widget_asset(asset_name: str) -> Response:
    """Any other file the build emits — plus the hashed bundle alias.

    The concrete routes above win over this one; FastAPI matches in declaration
    order, so moving them below would make ``/widget/inline`` look for a file
    called ``inline``.
    """
    if _HASHED.match(asset_name):
        # Serves whatever the current digest is: exactly one bundle exists at a
        # time, and this URL is only ever reached through the redirect above,
        # which is itself uncacheable — so the content always matches the hash
        # the client was just handed.
        return _public(
            FileResponse(_resolve(BUNDLE), media_type=_MEDIA_TYPES[".js"]), _IMMUTABLE
        )
    target = _resolve(asset_name)
    return _public(
        FileResponse(target, media_type=_MEDIA_TYPES.get(target.suffix)), _NO_STORE
    )
