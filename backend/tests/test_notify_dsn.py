"""``db.notify.asyncpg_dsn`` — die Verbindungszeile für den NOTIFY-Hörer.

Audit 2026-09-29. ``POSTGRES_PASSWORD`` landet unverändert in
``DATABASE_URL`` (``deploy/compose.prod.yml``), und INSTALL.md empfiehlt
``openssl rand -base64 32`` — rund jedes zweite Ergebnis enthält ``/``.
SQLAlchemy liest so eine URL richtig (``migrate`` läuft durch), asyncpg zerlegt
sie mit ``urllib.parse``: der Rechnername endete am ``/`` im Passwort, der
Hörer verband sich nie, und der App-Start brach nach fünf Sekunden ab.
"""

from __future__ import annotations

from urllib.parse import unquote, urlparse

import pytest

from boerdi.db.notify import asyncpg_dsn


# Der Zeichenvorrat von base64 (openssl rand -base64): A-Z a-z 0-9 + / =
@pytest.mark.parametrize("passwort", ["ab/cd+ef=", "Zq/9+x/Lw==", "einfach"])
def test_das_passwort_ueberlebt_den_weg_zu_asyncpg(passwort):
    url = f"postgresql+asyncpg://boerdi:{passwort}@postgres:5432/boerdi"
    teile = urlparse(asyncpg_dsn(url))
    assert teile.scheme == "postgresql"
    assert teile.hostname == "postgres"
    assert teile.port == 5432
    assert teile.username == "boerdi"
    assert unquote(teile.password) == passwort
    assert teile.path == "/boerdi"


def test_eine_schlichte_url_bleibt_wie_sie_ist():
    url = "postgresql+asyncpg://boerdi:boerdi@localhost:5432/boerdi"
    assert asyncpg_dsn(url) == "postgresql://boerdi:boerdi@localhost:5432/boerdi"


def test_eine_schon_kodierte_url_wird_nicht_doppelt_kodiert():
    url = "postgresql+asyncpg://boerdi:ab%2Fcd@postgres:5432/boerdi"
    assert unquote(urlparse(asyncpg_dsn(url)).password) == "ab/cd"
