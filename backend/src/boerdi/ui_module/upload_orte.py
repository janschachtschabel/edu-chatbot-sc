"""„Wo verarbeiten?“ — die Orte des Upload-Felds (Plan 2026-11-17, Paket U4, E13).

Nach der Auswahl fragt ``ui_upload``, wo die Dateien verarbeitet werden. Dieses Modul rechnet im
laufenden Zug (wie ``dienst_upload.schalter``), was die Oberfläche dafür braucht — als Daten, nie
als Satz (die Oberfläche übersetzt die Codes):

- ``chat`` „Nur hier im Chat lesen“ (bis Plan 2026-11-20, P2: „Hier im Chat“): liest Inhalte und
  Strukturdokumente selbst, begrenzt (Studio ``lokal_max_dateien``, ``lokal_max_mb_gesamt``), auch
  ohne Anmeldung (``dokument_ohne_anmeldung``).
  Gesperrt mit ``aus`` (Studio), ``nur_angemeldet`` oder — Review Paket U (19.11.), MAJOR 3 —
  ``grenze_sitzung`` (die Sitzung hält schon so viele Uploads, wie sie darf; der Dienst zählt).
  ``texterkennung: true`` (Plan 2026-11-19, Paket C): gescannte PDF liest der Chat per
  Texterkennung, ihre Seiten gehen als Bild an das KI-Modell — die Oberfläche sagt es vorher.
  ``ueber_grenze`` nennt den Code, den die Oberfläche zeigt, wenn die Auswahl die Grenze
  überschreitet: ``ueber_grenze_anmelden`` (ohne Anmeldung, und die Anmeldung öffnete den ganzen
  Weg über WLO: Ablage da, Flow startbar, vom Ablauf erlaubt — MINOR 5) bzw. ``ueber_grenze``.
- ``wlo`` „In WLO ablegen und erschließen“: Stapel-Ablage des MCP plus Kestra-Flow über den MCP.
  Ohne Anmeldung gesperrt mit ``nur_angemeldet`` (wenn die Ablage danach ginge), sonst ``aus``.
  Mit Anmeldung, aber ohne Flow-Träger: geht als Ablage ohne Erschließung, Hinweis
  ``ohne_erschliessung`` mit dem Grund ``grund_erschliessung`` (Review P2, Befund 3):
  ``flow_nicht_freigegeben`` (der MCP trägt, gibt den Flow aber nicht frei) bzw.
  ``dienst_nicht_erreichbar`` (kein Träger: MCP fehlt oder ist kurz weg).
- ``namen`` „Nur die Dateinamen senden“: geht immer (Datenschutz-Ausweg, E7).

Vorauswahl (E13, Plan 2026-11-20 P2/UO-5): ``vorzug`` ``auto`` ist die Regel — angemeldet mit dem
ganzen WLO-Weg → ``wlo``; sonst ``chat``, wenn es geht; sonst ``wlo``, wenn es geht; sonst
``namen``.
``wlo``/``chat`` nehmen diesen Ort, wenn er geht (``wlo`` auch ohne Erschließung), sonst gilt
``auto``. Den Vorzug wählt ``dienst_upload``: im freien Chat das Studio (``vorauswahl``, Vorgabe
``chat``), aus einem Ablauf der Schritt. Ein Ablauf kann die Orte über das Modul-Argument ``orte``
einschränken (gesperrt mit ``ablauf``); ``namen`` bleibt.
"""

from __future__ import annotations

from typing import Any, Final

from boerdi.services.config_loader.upload import load_upload_config
from boerdi.services.mcp.auth import has_personal_auth

ORTE: Final = ("chat", "wlo", "namen")
#: P2: die Werte von ``vorzug`` (Studio ``upload-config.vorauswahl``, Schritt-Daten ``vorauswahl``).
VORZUEGE: Final = ("auto", "wlo", "chat")
#: Das erste Werkzeug der Stapel-Ablage (``services/ablage/mcp_ablage``).
_ABLAGE_WERKZEUG: Final = "wlo_prepare_file_batch"


def _ablage_da() -> bool:
    """Führt der MCP die Stapel-Ablage? (wie ``dienst_upload.schalter``)"""
    from boerdi.services.mcp import faehigkeiten

    return faehigkeiten.kennt_werkzeug(_ABLAGE_WERKZEUG)


def _flow_da() -> bool:
    """Kann ein Träger den Metadaten-Flow starten (Paket K: nur der MCP)?"""
    from boerdi.services.ablauf import auftrag_zug
    from boerdi.services.ablauf.zug_basis import METADATEN_FLOW

    return auftrag_zug.kann_starten(METADATEN_FLOW, repo_schreibt=True)


def flow_da() -> bool:
    """P2: kann WLO nach der Ablage Metadaten erzeugen (der Metadaten-Flow ist startbar)? Für
    ``api/ui_ablage`` — nur dann hält der Teil ``ablage`` das Häkchen ``erschliessen`` fest."""
    return _flow_da()


def _ohne_flow_grund() -> str:
    """Review P2, Befund 3: warum WLO gerade keine Metadaten erzeugt — als Code für die
    Oberfläche (Plan §4 „Metadaten kann WLO gerade nicht erzeugen ({Grund})“). Gefragt nur bei
    bestätigter Anmeldung; trägt der MCP (``auftrag_zug.traeger``), fehlt nur die Freigabe."""
    from boerdi.services.ablauf import auftrag_zug

    weg, _ = auftrag_zug.traeger(repo_schreibt=True)
    return "flow_nicht_freigegeben" if weg == auftrag_zug.MCP else "dienst_nicht_erreichbar"


def _flow_nach_anmeldung() -> bool:
    """Ginge der Metadaten-Flow, wenn die Person angemeldet wäre? Ohne Anmeldung gibt es für diesen
    Zug keinen Starter (:func:`_flow_da` ist dann immer falsch) — Durchtest U8 (19.11.)."""
    from boerdi.services.ablauf.zug_basis import METADATEN_FLOW
    from boerdi.services.auftraege import mcp_starter

    return mcp_starter.verfuegbar() and mcp_starter.flow_erlaubt(METADATEN_FLOW)


def _texterkennung(cfg: Any) -> bool:
    """Liest „Hier im Chat“ gescannte PDF per Texterkennung (Paket C, ``dokumente/ocr``)?"""
    from boerdi.services.dokumente import ocr

    return ocr.aktiv(cfg)


def _chat(cfg: Any, person: bool, voll: bool) -> dict[str, Any]:
    if not cfg.dokument_im_chat:
        return {"geht": False, "grund": "aus"}
    if not (person or cfg.dokument_ohne_anmeldung):
        return {"geht": False, "grund": "nur_angemeldet"}
    if voll:
        return {"geht": False, "grund": "grenze_sitzung"}
    chat: dict[str, Any] = {"geht": True, "ueber_grenze": "ueber_grenze"}
    if _texterkennung(cfg):
        chat["texterkennung"] = True
    return chat


def _wlo(ablage: bool, person: bool) -> dict[str, Any]:
    if not ablage:
        return {"geht": False, "grund": "aus"}
    if not person:
        return {"geht": False, "grund": "nur_angemeldet"}
    if not _flow_da():
        return {"geht": True, "hinweis": "ohne_erschliessung",
                "grund_erschliessung": _ohne_flow_grund()}
    return {"geht": True}


def orte(erlaubt: list[str] | None = None, *, voll: bool = False,
         vorzug: str = "auto") -> dict[str, Any]:
    """Die Orte mit ``geht``, ``grund``/``hinweis`` (Codes) und die ``vorauswahl``. ``voll``: die
    Sitzung hat ihre Grenze für „Hier im Chat“ erreicht (``dienst_upload`` zählt). ``vorzug``:
    ``auto``, ``wlo`` oder ``chat`` (P2) — ein Ort, der nicht geht, fällt auf ``auto`` zurück."""
    cfg = load_upload_config()
    person = has_personal_auth()
    ablage = cfg.ablage_in_wlo and _ablage_da()
    aus: dict[str, Any] = {"chat": _chat(cfg, person, voll),
                           "wlo": _wlo(ablage, person), "namen": {"geht": True}}
    if erlaubt is not None:
        for ort in ("chat", "wlo"):
            if ort not in erlaubt:
                aus[ort] = {"geht": False, "grund": "ablauf"}
    # MINOR 5: erst nach der Einschränkung — die Anmeldung hilft nur, wenn der Ablauf WLO zulässt
    # und der ganze Weg (Ablage und Metadaten-Flow) danach ginge
    if (aus["chat"]["geht"] and ablage and not person
            and (erlaubt is None or "wlo" in erlaubt) and _flow_nach_anmeldung()):
        aus["chat"]["ueber_grenze"] = "ueber_grenze_anmelden"
    if vorzug in ("wlo", "chat") and aus[vorzug]["geht"]:
        aus["vorauswahl"] = vorzug
    elif aus["wlo"]["geht"] and "hinweis" not in aus["wlo"]:
        aus["vorauswahl"] = "wlo"
    else:
        aus["vorauswahl"] = next((o for o in ("chat", "wlo") if aus[o]["geht"]), "namen")
    return aus
