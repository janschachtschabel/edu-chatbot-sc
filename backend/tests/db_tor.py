"""Wann ein Überspringen durch ein DB-Tor ein Fehler ist (Paket 6, B3).

Die Tore in ``pg_utils`` überspringen ganze Module, wenn die Compose-Datenbank
fehlt — lokal bequem. In der CI ist sie bereitgestellt (``ci.yml``, Schritt
„Provision DB“); ein Überspringen heißt dort, dass die Probe an Last oder
Zeit scheiterte, und ein grüner Lauf hätte die Module nie geprüft. Der Hook in
``conftest.py`` macht daraus deshalb einen Fehler.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from tests import pg_utils

#: Die Gründe der beiden Tore — woran ein solcher Sprung zu erkennen ist.
DB_GRUENDE = (pg_utils.SKIP_REASON, pg_utils.DEV_DB_SKIP_REASON)

FEHLERTEXT = (
    "DB-Tor in der CI übersprungen — die Datenbank ist dort bereitgestellt, ein "
    "Überspringen hieße „grün, obwohl nicht geprüft“ (Paket 6, B3). Grund: {grund}"
)


def in_der_ci(env: Mapping[str, str]) -> bool:
    """GitHub Actions setzt ``CI=true``."""
    return env.get("CI", "").strip().lower() in {"1", "true", "yes"}


def sprung_grund(bericht: Any) -> str:
    """Der Text eines Überspringens (``longrepr`` ist dann ein Tupel)."""
    longrepr = getattr(bericht, "longrepr", None)
    if isinstance(longrepr, tuple) and len(longrepr) == 3:
        return str(longrepr[2])
    return ""


def ist_verbotener_sprung(bericht: Any, env: Mapping[str, str]) -> bool:
    """Ist ``bericht`` ein Überspringen durch ein DB-Tor, und läuft die CI?"""
    if not getattr(bericht, "skipped", False) or not in_der_ci(env):
        return False
    grund = sprung_grund(bericht)
    return any(g in grund for g in DB_GRUENDE)
