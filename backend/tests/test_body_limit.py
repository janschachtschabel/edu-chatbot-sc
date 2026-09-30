"""``api/body_limit`` — Obergrenze für Anfrage-Rümpfe (Audit 2026-09-29).

FastAPI liest den ganzen Rumpf, bevor Abhängigkeiten laufen: JSON landet
vollständig im Speicher, Multipart-Dateien vollständig auf der Platte — VOR dem
Studio-Schlüssel und VOR der Drossel. Ein einziger Multi-GB-POST an
``/api/chat`` legte eine Replika lahm, ein großer Upload an
``/api/speech/transcribe`` füllte die Platte, auf der auch Postgres liegt.
Die Grenzen folgen den fachlichen Deckeln, die es schon gibt.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from boerdi.api.body_limit import body_limit_for
from boerdi.main import create_app
from boerdi.services.snapshots import MAX_CONFIG_UPLOAD_BYTES
from boerdi.services.speech_proxy import MAX_AUDIO_BYTES

MIB = 1024 * 1024


def test_oeffentliche_zuege_haben_die_engste_grenze():
    for pfad in ("/api/chat", "/api/chat/stream", "/api/agent", "/api/agent/stream"):
        assert body_limit_for(pfad) == 2 * MIB


def test_uploads_folgen_ihren_fachlichen_deckeln(monkeypatch):
    assert body_limit_for("/api/speech/transcribe") == MAX_AUDIO_BYTES + MIB
    assert body_limit_for("/api/config/restore") == MAX_CONFIG_UPLOAD_BYTES + MIB
    assert body_limit_for("/api/config/factory/upload") == MAX_CONFIG_UPLOAD_BYTES + MIB
    monkeypatch.setenv("BOERDI_MAX_INGEST_MB", "25")
    assert body_limit_for("/api/rag/ingest/file") == 26 * MIB


def test_ingest_ohne_deckel_bleibt_ohne_deckel(monkeypatch):
    # ``BOERDI_MAX_INGEST_MB=0`` ist der dokumentierte Weg zu unbegrenzten
    # Uploads auf großen Rechnern — die Grenze hier hebelt ihn nicht aus.
    monkeypatch.setenv("BOERDI_MAX_INGEST_MB", "0")
    assert body_limit_for("/api/rag/ingest/file") is None


def test_alles_andere_hat_eine_allgemeine_grenze():
    assert body_limit_for("/api/config/data/01-base/engine") == 16 * MIB
    assert body_limit_for("/health") == 16 * MIB


def test_ein_zu_grosser_rumpf_wird_vorab_abgewiesen():
    client = TestClient(create_app(), raise_server_exceptions=False)
    antwort = client.post(
        "/api/chat", content=b"x" * (2 * MIB + 1),
        headers={"content-type": "application/json"},
    )
    assert antwort.status_code == 413


def test_ein_gestreamter_rumpf_ohne_laenge_wird_beim_lesen_abgebrochen():
    # Ohne ``Content-Length`` (chunked) kann nur das Mitzählen helfen.
    client = TestClient(create_app(), raise_server_exceptions=False)

    def teile():
        for _ in range(3):
            yield b"x" * MIB

    antwort = client.post(
        "/api/chat", content=teile(), headers={"content-type": "application/json"},
    )
    assert antwort.status_code == 413


def test_die_abweisung_traegt_die_cors_kopfzeilen():
    # Das Widget ruft von fremden Seiten. Ohne CORS-Kopfzeilen sähe der
    # Browser statt der 413 einen CORS-Fehler — deshalb sitzt die Grenze
    # innerhalb der CORS-Schicht.
    client = TestClient(create_app(), raise_server_exceptions=False)
    antwort = client.post(
        "/api/chat", content=b"x" * (2 * MIB + 1),
        headers={"content-type": "application/json", "origin": "https://gast.example"},
    )
    assert antwort.status_code == 413
    assert "access-control-allow-origin" in antwort.headers
