"""Paket 19 (Audit 2026-10-31, M-16): Sprachfelder geprüft, Eingabefehler des Anbieters nicht teuer.

Bis hier nahm ``/api/speech/synthesize`` jede ``voice``, jede ``language`` und als ``speed`` auch
``nan``/``inf``; ein 400 des Anbieters wurde mit Traceback protokolliert und als 502 beantwortet.
Bei der Spracherkennung führte jeder Fehler, auch ein Eingabefehler (400/413/415/422), zum
nächsten Modell — bis zu drei bezahlte Aufrufe, anonym erreichbar.

Jetzt (mit Review, Punkt 9): ``voice`` aus einer Erlaubnisliste,
``language`` ``^[a-z]{2}(-[A-Z]{2})?$``, ``speed``
endlich in 0,25…4,0 (sonst 422, vor jedem Anbieteraufruf). Ein Eingabefehler des Anbieters
beendet die Kette sofort, ohne Traceback, als 400 (bzw. 415). Zugang, Kontingent und Ausfall
(401/403/404/429/5xx, Netz) bleiben ein Grund für das nächste Modell — dafür gibt es die Kette.
"""

from __future__ import annotations

import asyncio
import logging

import httpx
import pytest
from fastapi.testclient import TestClient

import boerdi.api.speech as speech_api
from boerdi.main import create_app
from boerdi.services import speech_proxy
from boerdi.settings import get_settings


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_CHAT", "off")
    get_settings.cache_clear()
    monkeypatch.setattr(speech_api, "speech_enabled", lambda: True)
    return TestClient(create_app())


@pytest.fixture()
def aufrufe(monkeypatch) -> list[tuple]:
    gesehen: list[tuple] = []

    async def tts(text, voice, speed):
        gesehen.append(("tts", voice, speed))
        return b"mp3"

    async def stt(content, filename, language):
        gesehen.append(("stt", language))
        return {"text": "x", "model": "m"}

    monkeypatch.setattr(speech_api, "synthesize_speech", tts)
    monkeypatch.setattr(speech_api, "transcribe_audio", stt)
    return gesehen


# ── Felder ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("speed", ["nan", "inf", "-inf", "0.1", "4.5", "0"])
def test_ungueltige_geschwindigkeit_422(client, aufrufe, speed):
    r = client.post("/api/speech/synthesize", data={"text": "Hallo", "speed": speed})
    assert r.status_code == 422
    assert aufrufe == []


@pytest.mark.parametrize("speed", ["0.25", "1", "4.0"])
def test_gueltige_geschwindigkeit(client, aufrufe, speed):
    r = client.post("/api/speech/synthesize", data={"text": "Hallo", "speed": speed})
    assert r.status_code == 200


@pytest.mark.parametrize("voice", ["robot", "NOVA", "nova; drop"])
def test_unbekannte_stimme_422(client, aufrufe, voice):
    r = client.post("/api/speech/synthesize", data={"text": "Hallo", "voice": voice})
    assert r.status_code == 422
    assert aufrufe == []


def test_die_stimme_des_widgets_gilt(client, aufrufe):
    r = client.post("/api/speech/synthesize", data={"text": "Hallo", "voice": "nova"})
    assert r.status_code == 200
    assert aufrufe == [("tts", "nova", 1.0)]


@pytest.mark.parametrize("language", ["deutsch", "DE", "de-de", "de_DE", "d", "de-DEU"])
def test_ungueltige_sprache_422(client, aufrufe, language):
    r = client.post("/api/speech/transcribe", files={"audio": ("a.webm", b"x", "audio/webm")},
                    data={"language": language})
    assert r.status_code == 422
    assert aufrufe == []


@pytest.mark.parametrize("language", ["de", "en", "de-DE"])
def test_gueltige_sprache(client, aufrufe, language):
    r = client.post("/api/speech/transcribe", files={"audio": ("a.webm", b"x", "audio/webm")},
                    data={"language": language})
    assert r.status_code == 200
    assert aufrufe == [("stt", language)]


# ── Eingabefehler des Anbieters ────────────────────────────────────────────


class _Antwort:
    def __init__(self, status: int, *, text: str = "", content: bytes = b"") -> None:
        self.status_code = status
        self.text = text
        self.content = content

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            anfrage = httpx.Request("POST", "https://anbieter.invalid/audio")
            raise httpx.HTTPStatusError(
                "fehler", request=anfrage,
                response=httpx.Response(self.status_code, request=anfrage))


def _anbieter(monkeypatch, status: int) -> list[str]:
    modelle: list[str] = []

    async def post(url, **kw):
        modelle.append((kw.get("data") or kw.get("json") or {}).get("model", ""))
        return _Antwort(status, text="ok", content=b"mp3")

    monkeypatch.setattr(speech_proxy, "_post", post)
    return modelle


@pytest.mark.parametrize("status", [413, 415, 422])
def test_stt_eingabefehler_ohne_rueckfall(monkeypatch, status):
    modelle = _anbieter(monkeypatch, status)
    with pytest.raises(speech_proxy.SpeechEingabeFehler) as e:
        asyncio.run(speech_proxy.transcribe_audio(b"x", "a.webm", "de"))
    assert e.value.status == status
    assert len(modelle) == 1


@pytest.mark.parametrize("status", [400, 401, 404, 429, 500])
def test_stt_zugang_und_ausfall_behalten_den_rueckfall(monkeypatch, status):
    """Review, Punkt 9: am STT-Weg ist 400 auch „Modell kennt Parameter nicht“ — dafür gibt es
    die Kette; 400 bricht nur am TTS-Weg ab."""
    modelle = _anbieter(monkeypatch, status)
    with pytest.raises(speech_proxy.SpeechProxyError) as e:
        asyncio.run(speech_proxy.transcribe_audio(b"x", "a.webm", "de"))
    assert not isinstance(e.value, speech_proxy.SpeechEingabeFehler)
    assert len(modelle) == 1 + len(speech_proxy.STT_FALLBACKS)


def test_tts_eingabefehler_ohne_traceback(monkeypatch, caplog):
    _anbieter(monkeypatch, 400)
    with caplog.at_level(logging.WARNING), pytest.raises(speech_proxy.SpeechEingabeFehler):
        asyncio.run(speech_proxy.synthesize_speech("Hallo", "nova", 1.0))
    assert not [r for r in caplog.records if r.exc_info]


@pytest.mark.parametrize("status,erwartet", [(413, 400), (422, 400), (415, 415)])
def test_router_antwortet_mit_4xx_statt_502(client, monkeypatch, status, erwartet):
    _anbieter(monkeypatch, status)
    r = client.post("/api/speech/transcribe", files={"audio": ("a.webm", b"x", "audio/webm")})
    assert r.status_code == erwartet
    r = client.post("/api/speech/synthesize", data={"text": "Hallo"})
    assert r.status_code == erwartet


def test_tts_400_ist_eingabefehler(client, monkeypatch):
    _anbieter(monkeypatch, 400)
    assert client.post("/api/speech/synthesize", data={"text": "Hallo"}).status_code == 400


def test_ausfall_bleibt_502(client, monkeypatch):
    _anbieter(monkeypatch, 503)
    r = client.post("/api/speech/synthesize", data={"text": "Hallo"})
    assert r.status_code == 502
