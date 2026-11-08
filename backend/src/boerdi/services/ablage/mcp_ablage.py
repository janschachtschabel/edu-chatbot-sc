"""Die Stapel-Ablage in den persönlichen Bereich über das MCP (Paket U3-3a).

Gegenstück zu MA-1…MA-4 in ``wlo-mcp-server-sc``. Das Backend ruft die drei Werkzeuge selbst — kein
Modell dazwischen, die Person hat im Modul „Jetzt übertragen“ gewählt:

- :func:`vorbereiten` → ``wlo_prepare_file_batch``: Vorschau des Servers (normalisierter Plan mit
  Datei-Namen) und ein Freigabe-Schlüssel für genau diese Liste.
- :func:`datei_hochladen` → ``POST {MCP}/api/uploads``: die Bytes als **Strom** (Rohkörper,
  ``application/octet-stream``), nie ganz im Speicher; Antwort ``ref`` + Prüfsumme + erkannte Art.
- :func:`datei_ablegen` → ``wlo_store_batch_file`` (Index + ``ref``), :func:`abschliessen` →
  ``wlo_store_batch_manifest`` (``vorgang.json`` baut der Server).
- :func:`letzte_ablagen` → ``wlo_list_my_batches`` (Paket M6, MCP-Stand 2026-11-07): die eigenen
  letzten Ablagen, nur lesend — Titel, Datum, Zahlen; keine Kennungen.

Regeln: nur mit **bestätigter Anmeldung** (``has_personal_auth``) und nur mit dem **Zugangsblock des
Zuges** — nie dem der Anlage. Ergebnisse aus ``structuredContent`` (wie ``mcp/anmeldung``). Fehler
werden zu festen Codes (:class:`AblageFehler`), nie zu Servertext. Die Werkzeuge stehen in keinem
Angebot an die KI (:data:`WERKZEUGE`, Test gegen die statischen Werkzeuglisten).
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any, Final
from urllib.parse import quote

import httpx

from boerdi.obs.trace_id import ausgehende_koepfe
from boerdi.services.mcp import schutz, transport
from boerdi.services.mcp.auth import _block_des_zuges as _zug_block
from boerdi.services.mcp.auth import has_personal_auth

logger = logging.getLogger(__name__)

WERKZEUGE: Final = frozenset({"wlo_prepare_file_batch", "wlo_store_batch_file",
                              "wlo_store_batch_manifest", "wlo_list_my_batches"})
#: Paket M6: so viele eigene Ablagen zeigt das Modul neben der Vorschau.
LETZTE_ANZAHL: Final = 5
_ZAHLEN: Final = ("stored", "dropped", "unverified", "failed", "open")
#: Für Tests: eine ``httpx.MockTransport``.
_transport: httpx.AsyncBaseTransport | None = None
#: Unter der Frist des MCP-Pfads (25 s) plus Luft für die Antwort.
_UPLOAD_FRIST: Final = httpx.Timeout(30.0, connect=5.0)
#: 503 ``upstream_unreachable`` (MCP-Stand 2026-11-07, zweite Antwort): edu-sharing hat die
#: Anmeldeprüfung nicht beantwortet — nichts abgelegt, gleich noch einmal; kein Urteil über die
#: Anmeldung.
_UPLOAD_CODES: Final = {401: "kein_recht", 403: "kein_recht", 408: "zu_langsam", 413: "zu_gross",
                        415: "art", 429: "voll", 503: "nicht_erreichbar"}
#: Gründe des MCP-Stapels (``reason`` im strukturierten Teil) → Code. ``erneut``: nichts
#: angelegt, dieselbe Datei darf noch einmal geschickt werden; ``neu_vorbereiten``: die Freigabe
#: gilt nicht mehr.
_GRUENDE: Final = {"slot_missing": "erneut", "folder_failed": "erneut",
                   "mismatch_bytes": "passt_nicht",
                   "batch_unknown": "neu_vorbereiten", "batch_expired": "neu_vorbereiten",
                   "batch_mismatch": "neu_vorbereiten", "nothing_stored": "nichts_abgelegt",
                   # Paket M1: die Namen vor dem MCP-Stand vom 2026-11-07 (Rückfall).
                   "unknown": "neu_vorbereiten", "expired": "neu_vorbereiten",
                   "mismatch": "neu_vorbereiten"}
#: Codes des Antwortvertrags ohne Stapel-Stand (Paket M1). ``timeout`` mit offenem Ausgang
#: wird ``zu_langsam`` — die Datei KANN abgelegt sein (``api/ui_ablage``: „ohne Antwort“).
_FEHLER_CODES: Final = {"login_rejected": "kein_recht", "login_required": "nur_angemeldet",
                        "forbidden": "kein_recht", "timeout": "zu_langsam",
                        "not_visible": "zu_langsam", "unverified": "zu_langsam"}
#: ``timeout`` fängt :func:`_rufe` vorher ab (``zu_langsam``).
_FEHLER_ARTEN: Final = {"auth": "kein_recht", "tool": "abgewiesen", "transport": "nicht_erreichbar"}


class AblageFehler(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _mcp_wurzel() -> str:
    # Wie die Werkzeug-Aufrufe (Review, Befund 7): eine leere Einstellung fällt auf die Vorgabe.
    return schutz.wurzel(transport.resolve_mcp_url())


def _pruefe_person() -> str:
    block = _zug_block()
    if not has_personal_auth() or not block:
        raise AblageFehler("nur_angemeldet")
    return block


async def _werkzeug(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Ein Stapel-Werkzeug — sein ``structuredContent``. Eine Ablehnung MIT strukturiertem Teil
    kommt als Ergebnis zurück (``status: failed`` + ``reason``), damit der Aufrufer unterscheiden
    kann; ohne ihn ein Code. Zeitüberschreitung → ``zu_langsam`` (es KANN geschehen sein)."""
    _pruefe_person()
    antwort = await transport.call_tool(name, args)
    if fehler := antwort.get("error"):
        strukturiert = fehler.get("structured")
        if isinstance(strukturiert, dict) and strukturiert.get("status"):
            return strukturiert     # eine Ablehnung des Stapels (``status``/``reason``)
        if isinstance(strukturiert, dict) and isinstance(strukturiert.get("error"), dict):
            # Paket M1 (MCP-Stand 2026-11-07): jeder andere Fehler trägt ``error.code``.
            code = str(strukturiert["error"].get("code") or "")
            if code == "timeout" and strukturiert["error"].get("outcomeOpen") is False:
                raise AblageFehler("abgewiesen")
            raise AblageFehler(_FEHLER_CODES.get(code, "abgewiesen"))
        if fehler.get("kind") == "timeout":
            raise AblageFehler("zu_langsam")
        raise AblageFehler(_FEHLER_ARTEN.get(str(fehler.get("kind")), "nicht_erreichbar"))
    daten = (antwort.get("result") or {}).get("structuredContent")
    if not isinstance(daten, dict):
        raise AblageFehler("abgewiesen")
    return daten


#: W4 (MCP-Stand 2026-11-08): die Rolle je Eintrag im Wortschatz des Servers. Ein Server vor W4
#: verwirft das unbekannte Feld still (zod ohne ``strict``).
_ROLLEN: Final = {"struktur": "structure", "inhalt": "content"}


async def vorbereiten(ordner: str, eintraege: list[dict[str, Any]]) -> dict[str, Any]:
    """Plan an das MCP (``eintraege``: ``titel``, ``sha256``, ``groesse``, ``art``, ``rolle``
    (``inhalt`` | ``struktur``, Vorgabe ``inhalt``)) → Vorschau + ``batchToken``."""
    daten = await _werkzeug("wlo_prepare_file_batch", {
        "target": "home", "folderName": ordner,
        "entries": [{"title": e["titel"], "sha256": e["sha256"], "size": e["groesse"],
                     "ext": e["art"], "role": _ROLLEN.get(e.get("rolle", "inhalt"), "content")}
                    for e in eintraege]})
    liste = daten.get("entries")
    # Je Eintrag ein ganzzahliger Index 0…n−1 in Reihenfolge — sonst kippte
    # ``vorgang_teil.aus_plan`` mit einer 500, oder ein Index wäre über ``/datei`` nie einlösbar
    # (Review 2026-11-07, Befund 4).
    if (not isinstance(daten.get("batchToken"), str) or not isinstance(liste, list)
            or len(liste) != len(eintraege)
            or [e.get("index") if isinstance(e, dict) else None for e in liste]
            != list(range(len(liste)))
            or any(isinstance(e.get("index"), bool) for e in liste)):
        raise AblageFehler("abgewiesen")
    return daten


async def datei_hochladen(strom: AsyncIterator[bytes], laenge: int, name: str) -> dict[str, Any]:
    """Die Bytes einer Datei als Strom in einen Upload-Platz des MCP → ``ref``, Prüfsumme, Art."""
    block = _pruefe_person()
    koepfe = {**ausgehende_koepfe(), "Authorization": f"Bearer {block}",
              "Content-Type": "application/octet-stream", "Content-Length": str(laenge),
              "X-Upload-Name": quote(name[:200], safe="")}
    try:
        async with httpx.AsyncClient(timeout=_UPLOAD_FRIST, transport=_transport) as http:
            antwort = await http.post(f"{_mcp_wurzel()}/api/uploads", content=strom, headers=koepfe)
    except httpx.TimeoutException as fehler:
        raise AblageFehler("zu_langsam") from fehler
    except httpx.HTTPError as fehler:
        logger.warning("Ablage: Upload-Platz nicht erreichbar (%s)", type(fehler).__name__)
        raise AblageFehler("nicht_erreichbar") from fehler
    code = antwort.status_code
    if code == 429 and _fehlercode(antwort) == "too_many_logins":
        # Eine Betriebs-Einstellung des MCP (``AUTH_CREDENTIAL_LIMIT``; der Chatbot ist EINE Adresse
        # für alle Personen) — kein „voll“ für die Person (Review, Befund 6).
        logger.warning("Ablage: MCP weist zu viele Anmeldungen von dieser Adresse ab "
                       "(AUTH_CREDENTIAL_LIMIT prüfen)")
        raise AblageFehler("anmeldungen")
    if code != 201:
        logger.info("Ablage: Upload-Platz antwortet %d", code)
        raise AblageFehler(_UPLOAD_CODES.get(code, "fehler"))
    try:
        daten = antwort.json()
    except ValueError as fehler:
        raise AblageFehler("fehler") from fehler
    if not isinstance(daten, dict) or not isinstance(daten.get("ref"), str):
        raise AblageFehler("fehler")
    return daten


def _fehlercode(antwort: httpx.Response) -> str:
    try:
        daten = antwort.json()
    except ValueError:
        return ""
    # ``error`` trägt am Upload den Code; seit dem MCP-Stand vom 07.11. steht er auch in ``code``.
    if not isinstance(daten, dict):
        return ""
    return str(daten.get("code") or daten.get("error") or "")


def grund(ergebnis: dict[str, Any]) -> str | None:
    """Der Code einer Ablehnung des Stapels (``reason``) — ``None``, wenn es ein Stand ist."""
    if ergebnis.get("status") == "failed" and (r := ergebnis.get("reason")):
        return _GRUENDE.get(str(r), "abgewiesen")
    return None


async def datei_ablegen(batch_token: str, index: int, ref: str) -> dict[str, Any]:
    """Eine hochgeladene Datei als Eintrag ``index`` des freigegebenen Stapels ablegen."""
    return await _werkzeug("wlo_store_batch_file",
                           {"batchToken": batch_token, "index": index, "ref": ref})


def _ablage(b: Any) -> dict[str, Any] | None:
    """Eine Ablage aus ``wlo_list_my_batches`` für das Modul: Titel, Datum (ISO), Zahlen — oder
    ``lesbar: False`` ohne Zahlen. Keine ``manifestNodeId``/``folderNodeId`` — das Modul zeigt
    nur."""
    if not isinstance(b, dict) or not isinstance(b.get("title"), str):
        return None
    zahlen = b.get("counts") if isinstance(b.get("counts"), dict) else None
    # Ein unlesbarer Zähler macht nur DIESE Ablage unlesbar, nicht die Liste (Review 2026-11-07).
    if zahlen is not None and not all(isinstance(zahlen.get(k, 0), int) for k in _ZAHLEN):
        zahlen = None
    lesbar = b.get("status") == "ok" and zahlen is not None
    return {"titel": " ".join(b["title"].split())[:200],
            "datum": str(b.get("createdAt") or "")[:40], "lesbar": lesbar,
            **({k: int(zahlen.get(k) or 0) for k in _ZAHLEN} if lesbar else {})}


async def letzte_ablagen(limit: int = LETZTE_ANZAHL) -> dict[str, Any]:
    """Die eigenen letzten Ablagen (Paket M6, T1b) — ``{"ablagen": [...], "gekappt": bool}``. Nur
    mit bestätigter Anmeldung (sonst ``nur_angemeldet``), nie über den Suchindex (der Server liest
    die Knoten-Ablage des eigenen Bereichs)."""
    daten = await _werkzeug("wlo_list_my_batches", {"limit": max(1, min(20, limit))})
    roh = daten.get("batches") if isinstance(daten.get("batches"), list) else []
    return {"ablagen": [a for a in map(_ablage, roh) if a is not None][:limit],
            "gekappt": bool(daten.get("scanTruncated"))}


async def abschliessen(batch_token: str) -> dict[str, Any]:
    """``vorgang.json`` zum Stapel ablegen (baut der MCP-Server aus Freigabe und Ergebnissen)."""
    return await _werkzeug("wlo_store_batch_manifest", {"batchToken": batch_token})
