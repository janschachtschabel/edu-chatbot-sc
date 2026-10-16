"""Die Nachrichtenfolge je Anbieter formen — Form, nicht Inhalt (Review Paket 7, B-7).

Ein Ort für die Eigenheiten der Anbieter, den beide Einstiege nutzen:
``llm.wire_transport`` (Chat, Streaming) und der Klassifikator, der über
``instructor`` an ``wire_transport`` vorbei sendet.

* OpenAI, direkt wie über die b-api: die System-Blöcke als einer — LiteLLM
  verbände sie auf ``/v1/responses`` mit einem Leerzeichen
  (``llm_responses.systemteil_verbinden``, Responses-Plan Paket A, E-A1).
* AcademicCloud: gleiche Rollen hintereinander als eine Nachricht
  (``llm_academiccloud``, E-AC).
"""

from __future__ import annotations

from typing import Any

from boerdi.services.llm_academiccloud import rollenfolge_zusammenlegen
from boerdi.services.llm_responses import systemteil_verbinden


def nachrichten_fuer(provider: str, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """``messages`` in der Form, die ``provider`` verträgt; die Eingabe bleibt unverändert."""
    if provider in ("openai", "b-api-openai"):
        return systemteil_verbinden(messages)
    if provider == "b-api-academiccloud":
        return rollenfolge_zusammenlegen(messages)
    return messages
