"""Die OpenAI-Wege am Transport vorbereiten — Form und Parameter, nicht der Inhalt.

Zwei Aufgaben, beide aus Messungen an LiteLLM 1.91:

* **Systemteil** (Plan ``docs/plans/2026-09-29-responses-systemteil-und-cache.md``,
  Paket A): Auf dem Weg über ``/v1/responses`` hebt LiteLLM jede
  String-System-Nachricht in ``instructions`` und hängt mehrere mit EINEM
  Leerzeichen aneinander (``litellm/completion_extras/litellm_responses_transformation/
  transformation.py``). Gemessen stand „… kein Werkzeug. ## Gesamtanleitung dieser
  Anlage“ mitten in einer Zeile. Über ``/v1/responses`` geht es ausdrücklich
  (``openai/responses/…``, siehe ``llm_models._GROUPS``) und still: ab gpt-5.4 leitet
  LiteLLM jeden Aufruf mit Werkzeugen und ``reasoning_effort`` dorthin um, auch hinter
  der b-api, weil die App jeden Anbieter als ``openai/…`` anspricht. Auf
  Chat-Completions ist eine verbundene System-Nachricht inhaltlich dasselbe.
* **Denktiefe und Ausführlichkeit** (Paket 7, L2): An einem lokalen Fang-Server
  gemessen (2026-10-09) kam bei gpt-6 weder ``reasoning_effort`` noch ``verbosity``
  an — LiteLLM kennt gpt-6 nicht als Denkmodell und verwirft beide still
  (``drop_params``). Bei gpt-5.6 kam ``verbosity`` nie an. ``extra_body`` reicht der
  OpenAI-Client dagegen unverändert durch. OpenAI direkt nimmt beide auf
  ``/v1/responses`` an (gpt-6-luna, 2026-10-09; ohne sie gilt „medium“).
"""

from __future__ import annotations

import logging
from typing import Any, Final

#: So beginnt der Modellname, den ``llm.route`` für den ausdrücklichen Responses-Weg setzt.
RESPONSES_PRAEFIX: Final = "openai/responses/"


def _ist_systemtext(nachricht: dict[str, Any]) -> bool:
    return nachricht.get("role") == "system" and isinstance(nachricht.get("content"), str)


def systemteil_verbinden(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Die System-Nachrichten am Anfang der Kette als EINE, mit Leerzeile getrennt.

    Verbunden wird nur der zusammenhängende Anfang. Eine System-Nachricht mitten in
    der Kette (Muster-Weg, UI-Box-Status) bleibt, wo sie ist: sie nach vorn zu holen
    wäre eine Änderung am Inhalt. Sind es weniger als zwei, kommt dieselbe Liste
    unverändert zurück.
    """
    anfang = 0
    while anfang < len(messages) and _ist_systemtext(messages[anfang]):
        anfang += 1
    if anfang < 2:
        return messages
    verbunden = "\n\n".join(m["content"] for m in messages[:anfang])
    return [{"role": "system", "content": verbunden}, *messages[anfang:]]


def denkparameter_verlegen(kwargs: dict[str, Any], *, gpt5_familie: bool) -> None:
    """``reasoning_effort`` und ``verbosity`` dorthin, wo der Weg sie versteht.

    - **Ausdrücklicher Responses-Weg:** beide in ``extra_body`` als
      ``reasoning.effort`` und ``text.verbosity``.
    - **Chat-Completions:** Die Denktiefe bleibt Parameter — LiteLLM reicht sie
      durch, und an ihr hängt seine stille Umleitung nach ``/v1/responses``.
      Leitet es um (Werkzeug UND Denktiefe), geht die Ausführlichkeit als ``text``
      mit, sonst als ``verbosity``.
    - Mit Antwortformat bleibt ``text`` frei: LiteLLM legt das Format in
      ``text.format``, ein ``text`` im ``extra_body`` ersetzte es.
    - Die Ausführlichkeit gibt es nur in der gpt-5- und gpt-6-Familie
      (Nutzer-Vorgabe 2026-10-09); o1/o3/o4 bekommen sie nicht.
    """
    verbosity = kwargs.pop("verbosity", None)
    if not gpt5_familie:
        verbosity = None
    extra: dict[str, Any] = dict(kwargs.get("extra_body") or {})
    text_frei = kwargs.get("response_format") is None
    if str(kwargs.get("model", "")).startswith(RESPONSES_PRAEFIX):
        effort = kwargs.pop("reasoning_effort", None)
        if effort is not None:
            extra["reasoning"] = {"effort": effort}
        if verbosity is not None and text_frei:
            extra["text"] = {"verbosity": verbosity}
    elif verbosity is not None:
        if kwargs.get("tools") and "reasoning_effort" in kwargs:
            if text_frei:
                extra["text"] = {"verbosity": verbosity}
        else:
            extra["verbosity"] = verbosity
    if extra:
        kwargs["extra_body"] = extra


#: Angehängt, wenn ``json_object`` verlangt ist und keine Eingabe-Nachricht „json“ nennt.
JSON_HINWEIS: Final = "Antworte als JSON-Objekt."
_JSON_ABSTAND_S: Final = 300.0
_logger = logging.getLogger(__name__)


def _text(inhalt: Any) -> str:
    if isinstance(inhalt, str):
        return inhalt
    if isinstance(inhalt, list):
        return " ".join(str(t.get("text") or "") for t in inhalt if isinstance(t, dict))
    return ""


def json_hinweis_sichern(kwargs: dict[str, Any]) -> None:
    """Fix 2026-11-05 (Absicherung): ``response_format: json_object`` verlangt auf dem
    Responses-Weg das Wort „json“ in den Eingabe-Nachrichten; ein Hinweis nur im Systemteil reicht
    nicht (die rechtliche Prüfung scheiterte so still). Fehlt es, hängt diese Funktion
    :data:`JSON_HINWEIS` an eine Kopie der LETZTEN Nutzernachricht (in einer neuen Liste unter
    ``kwargs["messages"]``) — der Anfang der Kette (Cache-Präfix)
    bleibt — und schreibt eine gedrosselte Warnung. Wirft nie."""
    try:
        formt = kwargs.get("response_format")
        nachrichten = kwargs.get("messages")
        if not (isinstance(formt, dict) and formt.get("type") == "json_object"
                and isinstance(nachrichten, list)):
            return
        eingaben = [m for m in nachrichten if isinstance(m, dict) and m.get("role") != "system"]
        if any("json" in _text(m.get("content")).lower() for m in eingaben):
            return
        letzte = next((m for m in reversed(eingaben) if m.get("role") == "user"), None)
        if letzte is None:
            return
        inhalt = letzte.get("content")
        if isinstance(inhalt, list):
            ergaenzt: Any = [*inhalt, {"type": "text", "text": JSON_HINWEIS}]
        else:
            ergaenzt = f"{inhalt or ''}\n\n{JSON_HINWEIS}"
        # Neue Liste, neues Dict: die Nachrichten des Aufrufers bleiben unverändert (er kann sie
        # für einen zweiten Versuch oder den eigenen Verlauf weiterverwenden).
        kwargs["messages"] = [{**m, "content": ergaenzt} if m is letzte else m
                              for m in nachrichten]
        from boerdi.obs.drossel import gedrosselt

        gedrosselt(_logger, logging.WARNING, "json_hinweis", _JSON_ABSTAND_S,
                   "json_object ohne „json“ in den Eingabe-Nachrichten — Hinweis angehängt")
    except Exception:  # noqa: BLE001 — eine Absicherung darf den Aufruf nie verhindern
        _logger.debug("json_hinweis_sichern übersprungen", exc_info=True)


def nichts_ablegen(kwargs: dict[str, Any], *, gpt5_familie: bool) -> None:
    """``store: false`` für jeden Aufruf, der bei OpenAI auf ``/v1/responses`` landen kann.

    Paket 19 (H-2): Dort ist die Vorgabe ``store: true`` — OpenAI hält Anfrage und
    Antwort (Nachricht, Verlauf, Seitentext) 30 Tage abrufbar, sichtbar im Dashboard;
    über die b-api ebenso, sie reicht ``/openai/responses`` durch. Weder LiteLLM noch
    die App setzten den Parameter. Er geht als ``extra_body`` mit: die Responses-Brücke
    von LiteLLM hebt ihn heraus (``_extract_extra_body_params``), auf Chat-Completions
    reicht der OpenAI-Client ihn durch — dort ist ``false`` ohnehin die Vorgabe, aber
    ab gpt-5.4 leitet LiteLLM gegen ``api.openai.com`` Aufrufe mit Werkzeugen still
    nach ``/v1/responses`` um. Deshalb gilt es für die ganze gpt-5-/gpt-6-Familie
    (nur bei ``openai``/``b-api-openai``, ``llm_models.param_rules``), nicht für die
    AcademicCloud. Folgezüge verweisen auf keine gespeicherten Einträge: die
    Schleifen bauen die Assistenten-Nachricht neu, ohne ``reasoning_items``.
    """
    if gpt5_familie or str(kwargs.get("model", "")).startswith(RESPONSES_PRAEFIX):
        kwargs["extra_body"] = {**(kwargs.get("extra_body") or {}), "store": False}
