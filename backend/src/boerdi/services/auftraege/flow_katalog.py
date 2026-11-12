"""Paket KF (K-E4): die Flows, die die b-api für ``B_API_KEY`` meldet — Vorschläge im Studio.

``GET /api/v1/jobs/flows`` (gemessen 2026-11-12): eine Liste von Objekten mit ``namespace``,
``flowId``, ``description``, ``active`` … Vorgeschlagen werden die aktiven, innerhalb der
Obergrenze ``B_API_JOBS_FLOWS``, dazu die schon freigegebenen (damit ein gespeicherter Wert in der
Liste bleibt, auch wenn die b-api ihn gerade nicht nennt).

Zwischenspeicher :data:`_FRIST_S` — das Studio lädt alle Kataloge eines Formulars auf einmal; ein
Fehlschlag wird kürzer gemerkt (:data:`_FRIST_FEHLER_S`), dann gilt nur die Freigabe. Die
Beschreibung der b-api ist Text Dritter: nur die erste Zeile, gekürzt, als Beschriftung.
"""

from __future__ import annotations

import logging
import time
import unicodedata
from typing import Any, Final

import httpx

from boerdi.domain.config_models.kestra_flows import ist_flow
from boerdi.services.auftraege import client
from boerdi.settings import get_settings

logger = logging.getLogger(__name__)

_FRIST_S: Final = 300.0
_FRIST_FEHLER_S: Final = 60.0
_BESCHREIBUNG_ZEICHEN: Final = 80
_PFAD: Final = "/api/v1/jobs/flows"
#: Review KF, Befund 1: das Studio wartet beim ersten Formular auf alle Kataloge (K-E4: 5 s).
_ZEITLIMIT: Final = httpx.Timeout(5.0)
#: Review KF, Befund 7: mehr Einträge übernimmt die Auswahl nicht.
_MAX_EINTRAEGE: Final = 200

#: (Zeitpunkt, Flows der b-api als Kennung → Beschreibung), ``None`` = noch nie geholt.
_gemerkt: tuple[float, float, dict[str, str]] | None = None


def leeren() -> None:
    """Für Tests: den Zwischenspeicher leeren."""
    global _gemerkt
    _gemerkt = None


def _kennung(eintrag: Any) -> str | None:
    # Review KF, Befund 8: nur ausdrücklich aktive (K-E4)
    if not isinstance(eintrag, dict) or eintrag.get("active") is not True:
        return None
    ns, fid = eintrag.get("namespace"), eintrag.get("flowId")
    if not isinstance(ns, str) or not isinstance(fid, str):
        return None
    kennung = f"{ns}/{fid}"
    return kennung if ist_flow(kennung) else None


def _beschreibung(eintrag: dict[str, Any]) -> str:
    text = eintrag.get("description")
    zeile = text.strip().splitlines()[0].strip() if isinstance(text, str) and text.strip() else ""
    # Review KF, Befund 7: Text Dritter — ohne unsichtbare Steuerzeichen (Cf, etwa Bidi)
    zeile = "".join(z for z in zeile if unicodedata.category(z) != "Cf").strip()
    if len(zeile) > _BESCHREIBUNG_ZEICHEN:
        zeile = zeile[: _BESCHREIBUNG_ZEICHEN - 1].rstrip() + "…"
    return zeile


async def _von_der_bapi() -> dict[str, str]:
    global _gemerkt
    # Review KF, Befund 2: ohne Schlüssel der Anlage kein Abruf (K-E4 „für ``B_API_KEY``“) — eine
    # Anlage ohne b-api fragte sonst aus dem Studio regelmäßig einen Fremdhost
    if not get_settings().b_api_key.get_secret_value().strip():
        return {}
    jetzt = time.monotonic()
    if _gemerkt is not None and jetzt - _gemerkt[0] < _gemerkt[1]:
        return _gemerkt[2]
    try:
        antwort = await client._anfrage("GET", _PFAD, timeout=_ZEITLIMIT)
        daten = antwort.json() if antwort.status_code == 200 else None
    except (client.AuftragFehler, ValueError):
        daten = None
    if not isinstance(daten, list):
        logger.info("Kestra-Flows: keine Liste von der b-api — nur die Freigabe")
        _gemerkt = (jetzt, _FRIST_FEHLER_S, {})
        return {}
    flows = {k: _beschreibung(e) for e in daten[:_MAX_EINTRAEGE] if (k := _kennung(e))}
    _gemerkt = (jetzt, _FRIST_S, flows)
    return flows


async def vorschlaege() -> list[tuple[str, str]]:
    """``(Kennung, Beschriftung)``, sortiert nach Kennung."""
    obergrenze = client.obergrenze()
    flows = {k: b for k, b in (await _von_der_bapi()).items()
             if obergrenze is None or k in obergrenze}
    for kennung in client.studio_flows() or []:
        flows.setdefault(kennung, "")
    return [(k, f"{k} — {b}" if b else k) for k, b in sorted(flows.items())]
