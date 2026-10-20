"""Paket 17 (C4): ``memory://`` zählt je Pod — im Cluster ein N-fach zu hohes Limit.

Kubernetes setzt ``KUBERNETES_SERVICE_HOST`` in jeden Pod; steht das Limit dort im Speicher
des Prozesses, darf jede Replik das volle Kontingent vergeben. Der Start sagt es laut.
"""

from __future__ import annotations

import logging

import pytest

from boerdi.main import _warn_insecure_config
from boerdi.settings import get_settings


@pytest.fixture(autouse=True)
def _frisch(monkeypatch):
    monkeypatch.setenv("STUDIO_API_KEY", "lang-genug-und-kein-platzhalter")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _warnungen(caplog) -> list[str]:
    with caplog.at_level(logging.WARNING, logger="boerdi.main"):
        _warn_insecure_config(get_settings())
    return [r.getMessage() for r in caplog.records if "RATE_LIMIT_STORAGE_URI" in r.getMessage()]


def test_warnt_im_cluster_mit_speicher_limit(monkeypatch, caplog) -> None:
    monkeypatch.setenv("KUBERNETES_SERVICE_HOST", "10.0.0.1")
    monkeypatch.setenv("RATE_LIMIT_STORAGE_URI", "memory://")
    assert _warnungen(caplog)


def test_schweigt_mit_valkey_im_cluster(monkeypatch, caplog) -> None:
    monkeypatch.setenv("KUBERNETES_SERVICE_HOST", "10.0.0.1")
    monkeypatch.setenv("RATE_LIMIT_STORAGE_URI", "redis://valkey:6379/0")
    assert not _warnungen(caplog)


def test_schweigt_ausserhalb_von_kubernetes(monkeypatch, caplog) -> None:
    """Compose mit einer Kopie: ``memory://`` ist dort richtig."""
    monkeypatch.delenv("KUBERNETES_SERVICE_HOST", raising=False)
    monkeypatch.setenv("RATE_LIMIT_STORAGE_URI", "memory://")
    assert not _warnungen(caplog)
