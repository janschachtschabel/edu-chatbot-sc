"""E-AC (Responses-Plan 2026-09-29, umgesetzt in Paket 7): zwei user-Nachrichten
hintereinander auf der AcademicCloud.

Seit Paket B/E-E steht der Seitenkontext gerahmt als user-Nachricht vor dem
Verlauf — beginnt der Verlauf mit der Person oder ist er leer, folgen zwei
user-Nachrichten aufeinander. OpenAI nimmt das an (gemessen). Manche Chat-Vorlagen
offener Modelle verlangen dagegen den strengen Wechsel user/assistant (ältere
Mistral-Vorlagen werfen sonst); die eingestellten AcademicCloud-Modelle ließen sich
am 2026-10-09 nicht proben (503 bzw. 429). Der Transport legt die Folge deshalb dort
zusammen — inhaltlich dasselbe, der Rahmen bleibt im Text erhalten.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from boerdi.services import llm
from boerdi.services.llm_academiccloud import rollenfolge_zusammenlegen
from boerdi.settings import get_settings

_ENV = ("LLM_PROVIDER", "LLM_CHAT_MODEL", "OPENAI_API_KEY", "B_API_KEY",
        "LLM_SERVICE_TIER", "LLM_REASONING_EFFORT", "LLM_VERBOSITY", "B_API_CLEAR_CACHE")

_SEITE = "[SEITENKONTEXT — Daten]\nTitel: Optik\n[ENDE SEITENKONTEXT]"
_KETTE = [
    {"role": "system", "content": "Regeln"},
    {"role": "user", "content": _SEITE},
    {"role": "user", "content": "Wo bin ich?"},
]


# ── die reine Funktion ─────────────────────────────────────────────────────
def test_zwei_user_nachrichten_werden_eine():
    aus = rollenfolge_zusammenlegen(_KETTE)
    assert aus == [{"role": "system", "content": "Regeln"},
                   {"role": "user", "content": f"{_SEITE}\n\nWo bin ich?"}]


def test_der_wechsel_bleibt_wie_er_ist():
    kette = [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"},
             {"role": "user", "content": "c"}]
    assert rollenfolge_zusammenlegen(kette) is kette


def test_nur_text_wird_zusammengelegt():
    """Teile-Listen (Bilder, Dateien) bleiben unangetastet — ein Zusammenfügen
    wäre dort eine Formatfrage, kein Text."""
    teile = [{"type": "text", "text": "x"}]
    kette = [{"role": "user", "content": "a"}, {"role": "user", "content": teile}]
    assert rollenfolge_zusammenlegen(kette) is kette


def test_die_eingabe_bleibt_unveraendert():
    kopie = [dict(m) for m in _KETTE]
    rollenfolge_zusammenlegen(kopie)
    assert kopie == _KETTE


def test_drei_in_folge_werden_eine():
    kette = [{"role": "user", "content": x} for x in ("a", "b", "c")]
    assert rollenfolge_zusammenlegen(kette) == [{"role": "user", "content": "a\n\nb\n\nc"}]


def test_auch_zwei_antworten_hintereinander_werden_eine():
    """Review Paket 7, B-4: der Kontext-Gruß speichert eine Bot-Nachricht ohne
    Frage — nach einer Antwort, und seit T2 nach dem alten Gruß beim
    Sprachwechsel. Eine strenge Vorlage scheiterte sonst an dieser Stelle."""
    kette = [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"},
             {"role": "assistant", "content": "Gruß"}, {"role": "user", "content": "c"}]
    assert rollenfolge_zusammenlegen(kette) == [
        {"role": "user", "content": "a"}, {"role": "assistant", "content": "b\n\nGruß"},
        {"role": "user", "content": "c"}]


def test_ein_werkzeugaufruf_bleibt_fuer_sich():
    """Auf ``tool_calls`` folgt die Werkzeug-Antwort — zusammengelegt verlöre
    der Aufruf seinen Platz in der Kette."""
    aufruf = {"role": "assistant", "content": "", "tool_calls": [{"id": "1"}]}
    kette = [{"role": "assistant", "content": "b"}, aufruf,
             {"role": "tool", "content": "x", "tool_call_id": "1"}]
    assert rollenfolge_zusammenlegen(kette) is kette


# ── am Transport ───────────────────────────────────────────────────────────
class _Fake:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def __call__(self, **kwargs):
        self.calls.append(kwargs)
        nachricht = SimpleNamespace(content="ok", tool_calls=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=nachricht)], usage=None, model="m")


@pytest.fixture
def senden(monkeypatch):
    def _senden(provider: str, modell: str) -> list[dict]:
        for name in _ENV:
            monkeypatch.delenv(name, raising=False)
        monkeypatch.setenv("LLM_PROVIDER", provider)
        monkeypatch.setenv("LLM_CHAT_MODEL", modell)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setenv("B_API_KEY", "bkey")
        get_settings.cache_clear()
        llm.reset()
        fake = _Fake()
        monkeypatch.setattr(llm, "_acompletion", fake)
        asyncio.run(llm.chat_completion(messages=[dict(m) for m in _KETTE]))
        return fake.calls[0]["messages"]
    yield _senden
    get_settings.cache_clear()


def test_die_academiccloud_bekommt_die_folge_zusammengelegt(senden):
    gesendet = senden("b-api-academiccloud", "qwen3-30b-a3b-instruct-2507")
    assert [m["role"] for m in gesendet] == ["system", "user"]
    assert gesendet[1]["content"].startswith("[SEITENKONTEXT")


@pytest.mark.parametrize(("provider", "modell"), [
    ("openai", "gpt-6-luna"), ("b-api-openai", "gpt-5.6-luna")])
def test_openai_wege_bleiben_beim_einzelnen(senden, provider, modell):
    """Auf OpenAI gemessen ohne Fehler — dort bleibt die Seite eine eigene
    Nachricht (der Cache trifft sie dann im Folgezug, Paket B)."""
    gesendet = senden(provider, modell)
    assert [m["role"] for m in gesendet] == ["system", "user", "user"]
