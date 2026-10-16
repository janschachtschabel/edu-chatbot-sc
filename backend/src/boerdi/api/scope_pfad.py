"""Der Pfad, auf den der Router passt — ohne ``root_path``.

Aus ``studio_proxy`` gelöst (Paket 10, Audit 2026-10-10 L-4): zwei ASGI-Schichten
brauchen ihn, der Studio-Proxy und die Rumpf-Grenze (``body_limit``). Die Grenze sah
bis dahin den rohen Pfad samt Präfix, hinter einem Pfad-Präfix galten für
``/api/chat`` 16 statt 2 MiB.
"""

from __future__ import annotations

from starlette.types import Scope


def route_path(scope: Scope) -> str:
    """The path WITHOUT ``root_path``, i.e. what the router will match on.

    Behind a path-prefix reverse proxy (``--root-path /pfx``) ``scope["path"]``
    still carries the prefix, while Starlette strips it before routing. Matching
    on the raw path there meant the middleware neither gated nor rewrote anything
    and the /studio SPA mount answered instead — a silent, total outage of the
    studio API. Fails safe (no key is ever injected), but it fails.
    """
    path: str = scope.get("path", "")
    root: str = scope.get("root_path", "")
    if root and path.startswith(root):
        return path[len(root):] or "/"
    return path
