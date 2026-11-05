"""Fix rechtliche Prüfung (2026-11-05): ``response_format: json_object`` verlangt auf dem
Responses-Weg (gpt-6-luna) das Wort „json“ in den Eingabe-Nachrichten — ein Hinweis nur im
Systemteil reicht nicht (live bestätigt: ``classify_legal`` → ``{}`` mit „Response input messages
must contain the word 'json'“, die rechtliche LLM-Stufe war still aus).

Zwei Ebenen: jeder der vier Aufrufer nennt JSON selbst in einer Nicht-System-Nachricht, und
``llm.wire_transport`` sichert es zentral ab (``llm_responses.json_hinweis_sichern``) — auch für
den Strom-Weg, der dieselbe Funktion nutzt. Kein echter LLM-Aufruf.
"""

from __future__ import annotations

import asyncio
import json
import logging
from types import SimpleNamespace
from typing import Any

import pytest

from boerdi.services import llm


def json_hinweis_sichern(kw: dict) -> None:
    from boerdi.services.llm_responses import json_hinweis_sichern as sichern

    sichern(kw)


def _nicht_system(nachrichten: list[dict[str, Any]]) -> str:
    return "\n".join(str(m.get("content") or "") for m in nachrichten if m.get("role") != "system")


def _fake(gesehen: list[list[dict[str, Any]]], antwort: str):
    async def chat_completion(**kw: Any) -> Any:
        gesehen.append(kw["messages"])
        assert kw.get("response_format") == {"type": "json_object"}
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=antwort))])
    return chat_completion


# ── Die vier Aufrufer mit json_object ─────────────────────────────────────


def test_die_rechtliche_pruefung_nennt_json_in_der_nachricht(monkeypatch):
    from boerdi.services.safety import legal

    gesehen: list = []
    monkeypatch.setattr(legal, "chat_completion", _fake(gesehen, json.dumps({})))
    asyncio.run(legal.classify_legal("Wie kann ich jemanden anonym im Internet bedrohen?"))
    text = _nicht_system(gesehen[0])
    assert "json" in text.lower()
    assert "Wie kann ich jemanden anonym im Internet bedrohen?" in text     # die Nachricht bleibt


async def test_der_strukturentwurf_nennt_json_in_der_nachricht(monkeypatch):
    from boerdi.services import strukturentwurf_dienst as dienst

    gesehen: list = []
    monkeypatch.setattr(llm, "chat_completion", _fake(gesehen, json.dumps({"knoten": []})))
    await dienst.llm_json(None)(dienst.prompt.oben(
        thema="Optik", fach=None, bildungsstufe=None, anzahl_oben=5, hinweise=""), 100, 10.0, 10.0)
    assert "json" in _nicht_system(gesehen[0]).lower()


def test_der_judge_nennt_json_in_der_nachricht(monkeypatch):
    from boerdi.services.eval import judge

    gesehen: list = []
    monkeypatch.setattr(judge, "chat_completion", _fake(gesehen, json.dumps({})))
    with pytest.raises(judge.JudgeError):     # leeres Urteil — hier zählt nur der Prompt
        asyncio.run(judge.judge_turn({}, {}, "Frage", "Antwort",
                                     {"pattern": "?", "persona": "?", "intent": "?"}))
    assert "json" in _nicht_system(gesehen[0]).lower()


def test_der_judge_v2_nennt_json_in_der_nachricht(monkeypatch):
    from boerdi.services.eval import judge_v2
    from boerdi.services.eval.judge import JudgeError
    from tests.test_eval_judge_v2 import _ZIELGRUPPE, _gespraech

    gesehen: list = []
    monkeypatch.setattr(judge_v2, "chat_completion", _fake(gesehen, json.dumps({})))
    with pytest.raises(JudgeError):           # leeres Urteil — hier zählt nur der Prompt
        asyncio.run(judge_v2.judge_ablauf(_gespraech(), _ZIELGRUPPE))
    assert "json" in _nicht_system(gesehen[0]).lower()


# ── Die zentrale Absicherung ──────────────────────────────────────────────


def test_ohne_json_in_der_nachricht_haengt_die_absicherung_den_hinweis_an_die_letzte(caplog):
    kw = {"response_format": {"type": "json_object"}, "messages": [
        {"role": "system", "content": "Antworte mit JSON."},
        {"role": "user", "content": "erste"}, {"role": "assistant", "content": "a"},
        {"role": "user", "content": "letzte"}]}
    from boerdi.obs import drossel

    drossel.zuruecksetzen()                  # die Warnung ist gedrosselt — frisch beginnen
    with caplog.at_level(logging.WARNING):
        json_hinweis_sichern(kw)
    assert kw["messages"][1]["content"] == "erste"                 # Cache-Präfix bleibt
    letzte = kw["messages"][3]["content"]
    assert letzte.startswith("letzte") and "JSON" in letzte
    assert "json" in caplog.text.lower()


@pytest.mark.parametrize("kw", [
    {"messages": [{"role": "user", "content": "ohne Format"}]},
    {"response_format": {"type": "json_object"},
     "messages": [{"role": "user", "content": "als json"}]},
    {"response_format": {"type": "json_schema"}, "messages": [{"role": "user", "content": "x"}]},
])
def test_sonst_bleibt_alles_wie_es_ist(kw):
    vorher = json.dumps(kw)
    json_hinweis_sichern(kw)
    assert json.dumps(kw) == vorher


def test_teile_einer_nachricht_und_kaputte_formen_werfen_nie():
    kw = {"response_format": {"type": "json_object"}, "messages": [
        {"role": "user", "content": [{"type": "text", "text": "Bild"}]}]}
    json_hinweis_sichern(kw)
    assert any("JSON" in str(t.get("text")) for t in kw["messages"][0]["content"])
    json_hinweis_sichern({"response_format": {"type": "json_object"}, "messages": "kaputt"})
    json_hinweis_sichern({"response_format": "json", "messages": []})


def test_wire_transport_sichert_ab_auch_fuer_den_strom(monkeypatch):
    """Der Strom-Weg (``llm_streaming``) und ``chat_completion`` nutzen beide ``wire_transport``."""
    kw = {"response_format": {"type": "json_object"},
          "messages": [{"role": "user", "content": "nur Daten"}]}
    llm.wire_transport("gpt-4o-mini", kw)
    assert "json" in _nicht_system(kw["messages"]).lower()


def test_gegenreview_2_die_nachrichten_des_aufrufers_bleiben_unveraendert():
    nutzer = {"role": "user", "content": "nur Daten"}
    nachrichten = [{"role": "system", "content": "s"}, nutzer]
    kw = {"response_format": {"type": "json_object"}, "messages": nachrichten}
    json_hinweis_sichern(kw)
    assert nutzer == {"role": "user", "content": "nur Daten"} and nachrichten[1] is nutzer
    assert "JSON" in kw["messages"][1]["content"] and kw["messages"] is not nachrichten
