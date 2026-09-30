"""Text und Werkzeugaufrufe als EINE Wahl — die Grenze zur LiteLLM-Brücke.

LiteLLMs Brücke auf die Responses-API (gpt-5.4 und neuer, ``gpt-6-luna``) legt
eine nicht gestreamte Antwort mit Text UND Werkzeugaufrufen auf zwei Choices:
``choices[0]`` trägt den Text (``finish_reason="stop"``), ``choices[1]`` die
Aufrufe (``"tool_calls"``) — live gemessen 2026-09-30. Jede Schleife hier steht
auf dem Vertrag von Chat Completions: EINE Wahl, Text und Aufrufe in derselben
Nachricht. Wer nur ``choices[0]`` las (Werkzeugschleife, Agent-Schleife,
Klassifikator), verlor die Aufrufe still — so fiel ein ``zeige_dokument`` mit dem
überarbeiteten Text weg, und „Formuliere es einfacher" blieb ohne Box.

Deshalb hier, an der einen Stelle, die jeder nicht gestreamte Aufruf passiert
(``llm.chat_completion``). Der gestreamte Weg ist nicht betroffen: dort setzt
die Brücke ``tool_calls``, sobald ein Aufruf im Ergebnis steht, und alles liegt
in ``choices[0]``.
"""

from __future__ import annotations

from typing import Any


def vereinige_choices(resp: Any) -> Any:
    """Führt Text und Werkzeugaufrufe mehrerer Choices in ``choices[0]`` zusammen.

    Nur wenn Aufrufe dabei sind: mehrere reine Text-Choices bleiben, wie sie
    sind — ohne Aufrufe fehlt keiner Schleife etwas. Eine einzelne Choice kommt
    unverändert zurück. Umgebaut wird die erste Choice selbst: die Texte
    aneinander, die Aufrufe in ihrer Reihenfolge, ``finish_reason="tool_calls"``.
    """
    choices = list(getattr(resp, "choices", None) or [])
    if len(choices) < 2:
        return resp
    aufrufe = [a for c in choices for a in (getattr(c.message, "tool_calls", None) or [])]
    if not aufrufe:
        return resp
    texte = [c.message.content for c in choices if getattr(c.message, "content", None)]
    erste = choices[0]
    erste.message.content = "\n\n".join(texte) if texte else None
    erste.message.tool_calls = aufrufe
    erste.finish_reason = "tool_calls"
    resp.choices = [erste]
    return resp
