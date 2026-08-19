"""Shared fixtures.

Settings are lru-cached (boerdi.settings.get_settings). Tests that monkeypatch
env vars need a fresh Settings read — clear the cache around EVERY test so no
test can leak env-dependent state into the next.

Und die Suite BESITZT ihre Konfiguration: ``backend/.env`` bleibt draussen.
"""

from pathlib import Path

import pytest

from boerdi.settings import Settings, get_settings

_ENV_DATEI = Path(__file__).resolve().parents[1] / ".env"


def _schluessel_der_env_datei() -> tuple[str, ...]:
    """Die NAMEN in ``backend/.env`` — Werte braucht niemand.

    Gelesen wird die Datei selbst statt einer gepflegten Liste: was der Betreiber
    dort eintraegt, faellt damit automatisch aus den Tests heraus, ohne dass
    jemand eine zweite Stelle nachziehen muss.
    """
    if not _ENV_DATEI.exists():
        return ()
    namen = []
    for zeile in _ENV_DATEI.read_text(encoding="utf-8").splitlines():
        gestrafft = zeile.strip()
        if gestrafft and not gestrafft.startswith("#") and "=" in gestrafft:
            namen.append(gestrafft.split("=", 1)[0].strip())
    return tuple(namen)


_ENV_SCHLUESSEL = _schluessel_der_env_datei()


@pytest.fixture(autouse=True)
def _fresh_settings_cache(monkeypatch):
    """Frische Settings je Test — und ohne die Betriebs-``.env``.

    **Warum die Env-Datei ausgehaengt wird** (Befund 2026-08-19): ``Settings``
    liest ``backend/.env``, und damit las die Suite die Konfiguration des
    Rechners mit, auf dem sie lief. Als dort ``MASTER_SKILL_ENABLED=true``
    landete, wurden drei Tests rot, ohne dass sich am Produkt etwas geaendert
    hatte. Die groessere Gefahr ist die Umkehrung: **CI hat keine ``.env``, ein
    Entwicklerrechner schon** — beide liefen gegen unterschiedliche
    Konfigurationen, und ein Test konnte hier gruen und dort rot sein oder
    umgekehrt einen Fehler verdecken.

    **Zwei Wege, beide noetig.** Das Aushaengen der Env-DATEI allein genuegt
    nicht: ``litellm`` ruft beim Import ``load_dotenv()`` und kippt
    ``backend/.env`` in ``os.environ`` — gemessen 2026-08-19, ``import
    boerdi.main`` reicht dafuer. Die Werte stehen dann laengst in der
    Prozessumgebung, wo ``env_file=None`` nichts mehr ausrichtet. Deshalb
    verschwinden zusaetzlich genau die Schluessel, die in der Datei stehen.

    ``monkeypatch`` stellt beides nach jedem Test wieder her; wer eine
    Einstellung braucht, setzt sie ausdruecklich per ``monkeypatch.setenv`` —
    dieser Weg bleibt unberuehrt.
    """
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    for name in _ENV_SCHLUESSEL:
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _no_startup_warmups(monkeypatch):
    """Start-Vorwärmung (W1) in Tests stilllegen.

    ``spawn_startup_warmups`` startet echte MCP-/LLM-Round-Trips. Jeder Test, der
    den Lifespan fährt (``with TestClient(app)``), löste sie sonst mit aus — 16
    SDK-Deprecation-Warnungen und Netz-I/O in einer Unit-Suite.

    Der EINE Test, der die Verdrahtung prüfen muss
    (``test_startup_warmup.test_lifespan_actually_spawns_the_warmups``), patcht
    dasselbe Attribut selbst und gewinnt damit — die Naht bleibt also bewiesen.
    """
    import boerdi.main as main_mod
    monkeypatch.setattr(main_mod, "spawn_startup_warmups", lambda: None)
