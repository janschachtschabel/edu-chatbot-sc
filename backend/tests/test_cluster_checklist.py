"""P10-3: die §8-Cluster-Checkliste, soweit sie sich ausführen lässt.

Spec §8 nennt fünf Zusagen für den N-Replika-Betrieb. Zwei davon werden hier
**gemessen**, weil sie sich messen lassen; die übrigen drei brauchen einen echten
Cluster hinter einem echten Load-Balancer und stehen als Live-Protokoll in
``docs/cluster-checkliste.md`` — dort mit dem Grund, warum sie dort stehen.

Hier gemessen:

* **„Config-Änderung propagiert < 2 s"** — die Zusage IST eine Zeit, also muss
  ein Test die Zeit messen. ``test_pg_locks_notify.py`` prüft den *Inhalt* der
  Benachrichtigung und wartet dafür bewusst bis zu 5 s; das ist eine andere
  Eigenschaft und deckt die Schranke nicht ab (vor P10-3 war sie ungeprüft).
* **„Rate-Limit konsistent über einen geteilten Zähler"** — erst seit P10-2
  prüfbar: vorher fehlte der Client als Abhängigkeit, eine gesetzte
  ``RATE_LIMIT_STORAGE_URI`` hätte den Prozess beim Import beendet statt zu
  limitieren. Seit P10-6 ist der Speicher **Valkey** (BSD-3-Clause) statt Redis 8
  (RSALv2/SSPLv1/AGPLv3 — alle drei auf der Verbotsliste der Eisernen Regel 1);
  am Protokoll und damit an diesem Test ändert der Tausch nichts.

Anderswo abgedeckt und hier bewusst NICHT wiederholt: „Session-Turns
serialisiert" — ``test_pg_locks_notify.py::test_same_session_turns_serialize``
und ``::test_different_sessions_run_parallel``.
"""

from __future__ import annotations

import asyncio
import time

import asyncpg
import pytest
from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from tests import pg_utils

#: §8: „Config-Änderung propagiert < 2 s".
PROPAGATION_BOUND_S = 2.0

#: Bewusst großzügiger als die Schranke: wer scheitert, soll die ECHTE Zeit im
#: Fehlertext lesen („kam nach 3,4 s") statt nur „kam nicht in 2 s".
ARRIVAL_DEADLINE_S = 5.0

#: DB 15 statt 0: der Test leert seinen Keyspace, und das darf niemals eine
#: laufende Instanz treffen, die versehentlich denselben Speicher benutzt.
#: Das Schema wählt auch den CLIENT — ``limits`` liest ``valkey://`` mit
#: valkey-py, und nur der ist hier Abhängigkeit.
VALKEY_URL = "valkey://localhost:6379/15"

VALKEY_SKIP = (
    "Compose-Valkey nicht erreichbar — docker compose -f deploy/compose.dev.yml up -d valkey"
)


def valkey_available() -> bool:
    try:
        import valkey

        valkey.Valkey.from_url(VALKEY_URL, socket_connect_timeout=2).ping()
        return True
    except Exception:
        return False


# ── §8: Config-Änderung propagiert < 2 s ─────────────────────────────


@pytest.mark.pg
@pytest.mark.skipif(not pg_utils.pg_available(), reason=pg_utils.SKIP_REASON)
def test_config_change_propagates_within_the_two_second_bound() -> None:
    db = "boerdi_p10_propagation_test"
    pg_utils.create_migrated_db(db)
    try:
        elapsed = asyncio.run(_measure_propagation(db))
    finally:
        pg_utils.drop_db(db)

    assert elapsed is not None, (
        f"NOTIFY kam innerhalb von {ARRIVAL_DEADLINE_S}s gar nicht an"
    )
    assert elapsed < PROPAGATION_BOUND_S, (
        f"Config-Propagation dauerte {elapsed:.2f}s — §8 fordert < {PROPAGATION_BOUND_S}s"
    )


async def _measure_propagation(db: str) -> float | None:
    """Sekunden vom Schreiben bis zum Eintreffen der Benachrichtigung."""
    from boerdi.db.notify import ConfigChangeListener

    received: list[str] = []
    listener = ConfigChangeListener(pg_utils.asyncpg_dsn(db))
    await listener.start(received.append)
    await listener.wait_connected(timeout=5.0)

    conn = await asyncpg.connect(pg_utils.asyncpg_dsn(db))
    try:
        # Erst NACH dem Verbinden die Uhr starten: gemessen wird die
        # Propagation, nicht der Verbindungsaufbau des Schreibers.
        started = time.perf_counter()
        await conn.execute(
            "INSERT INTO config_areas (area, data) "
            "VALUES ('01-base/welcome-config', '{}'::jsonb)"
        )
        while not received and time.perf_counter() - started < ARRIVAL_DEADLINE_S:
            await asyncio.sleep(0.01)
        elapsed = time.perf_counter() - started
    finally:
        await conn.close()
        await listener.stop()

    return elapsed if received else None


# ── §8: Rate-Limit konsistent über den geteilten Zähler ──────────────


def _replica(limit: str) -> TestClient:
    """Eine Replika: eigener Prozess-Zustand, geteilter Zähler.

    Absichtlich ein eigener ``Limiter`` je Aufruf statt ``api.ratelimit.limiter``
    — der wird beim Import einmal mit der Storage-URI der Umgebung gebaut, und
    genau das Auseinanderfallen zweier Instanzen soll hier geprüft werden.
    Verdrahtung wie in ``main.py`` (``app.state.limiter`` + Handler).
    """
    from boerdi.api.ratelimit import peer_ip

    limiter = Limiter(key_func=peer_ip, storage_uri=VALKEY_URL, headers_enabled=True)
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # `request` UND `response` in der Signatur: slowapi liest den Schlüssel aus
    # dem einen und hängt bei ``headers_enabled=True`` die X-RateLimit-Header
    # an den anderen — fehlt er, wirft die Erweiterung. Genau so sehen die
    # echten limitierten Endpunkte aus (z. B. `speech_status`), der Prüfstand
    # weicht hier also nicht vom Ernstfall ab.
    @app.get("/probe")
    @limiter.limit(limit)
    def probe(request: Request, response: Response) -> dict:
        return {"ok": True}

    return TestClient(app)


@pytest.fixture()
def clean_store():
    import valkey

    client = valkey.Valkey.from_url(VALKEY_URL)
    client.flushdb()
    yield
    client.flushdb()


@pytest.mark.valkey
@pytest.mark.skipif(not valkey_available(), reason=VALKEY_SKIP)
def test_two_replicas_share_one_budget_over_a_shared_store(clean_store) -> None:
    # Drei Anfragen pro Minute für den ganzen Cluster, nicht je Replika.
    a, b = _replica("3/minute"), _replica("3/minute")

    assert a.get("/probe").status_code == 200
    assert a.get("/probe").status_code == 200
    # Die dritte auf der ANDEREN Replika: sie muss die beiden ersten schon
    # sehen, sonst hätte jede Replika ihr eigenes Kontingent.
    assert b.get("/probe").status_code == 200
    assert b.get("/probe").status_code == 429, (
        "Vierte Anfrage kam durch — die Replikas teilen sich den Zähler nicht"
    )


@pytest.mark.valkey
@pytest.mark.skipif(not valkey_available(), reason=VALKEY_SKIP)
def test_a_replica_started_later_inherits_the_running_count(clean_store) -> None:
    # Rollierender Neustart: die frische Replika darf das Kontingent nicht
    # zurücksetzen — sonst wäre jeder Deploy ein Freifahrtschein.
    first = _replica("2/minute")
    assert first.get("/probe").status_code == 200
    assert first.get("/probe").status_code == 200

    fresh = _replica("2/minute")
    assert fresh.get("/probe").status_code == 429
