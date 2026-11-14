"""Der Themenbaum (Paket U1-e): Ergebnis von ``browse_collection_tree`` → Block-Daten.

Der Server schickt je Knoten ein volles ``FormattedNode`` (rund 25 Felder samt Beschreibung,
``wlo-mcp-server-sc/src/apps/outputSchemas.ts:200-228``). Der Block braucht davon fünf: Kennung,
Titel, Adresse, Anzahl, „es gibt mehr“. Alles andere bliebe nur Gewicht in Antwort und Verlauf.

Gedeckelt wie das Manifest (``ui-themenbaum/manifest.json``): 30 Knoten oben, 10 Kinder je Knoten,
zwei Ebenen. Ein gekürzter Zweig sagt es (``mehr``) — ein abgeschnittener Baum, der vollständig
aussieht, stellte den Bestand falsch dar (Regel des MCP-Widgets, ``browse/render.ts:248-252``).
Adressen nur http/https, Kennungen nur in der Form, die das Manifest erlaubt: die Daten kommen
aus dem Repositorium und landen in Links und Element-Kennungen des Widgets.

**Oben gekürzt** (Review U1-e, Befund 2): Der Server liefert höchstens ``maxResults`` Knoten der
ersten Ebene und sagt nicht, ob es mehr gibt — ``truncated`` meint nur gekürzte Zweige
(``collection-traversal.ts:239-314``). Die Vorgabe holt deshalb einen Knoten mehr, als der Baum
zeigt (``maxResults`` = :data:`HOECHSTENS_OBEN` + 1); kommt er, steht ``wurzel_mehr`` in den
Daten. Die Wurzel bekommt ihre Adresse in WLO (``wurzel_url``), damit die Person dort alles sieht.

**Nicht lesbar** (N5, 2026-11-14): Der Server kennzeichnet einen Knoten, dessen Unterthemen er
nicht lesen konnte (``childrenUnread``, ein Ausfall) oder nicht lesen durfte (``childrenRefused``,
mit dieser Anmeldung). Der Knoten trägt dann ``nicht_lesbar`` (``ausfall`` / ``gesperrt``) — ohne
das Feld sähe er aus wie ein Thema ohne Unterthemen. Die Kennzeichen zum Inhaltsabruf
(``contentsUnread`` / ``contentsRefused``) entstehen nur mit Inhaltszahlen, die der Baum nicht
anfordert.
"""

from __future__ import annotations

import re
from typing import Any, Final

from boerdi.ui_module.abgeleitet import http_url, md_link

HOECHSTENS_OBEN: Final = 30
HOECHSTENS_KINDER: Final = 10
_TITEL_ZEICHEN: Final = 200
_UEBERSCHRIFT_ZEICHEN: Final = 160
#: Form einer Knoten-Kennung in den Block-Daten (was der Server schickt).
KENNUNG: Final = r"^[A-Za-z0-9-]{1,80}$"
#: Eingabe des Aufklappens (U1-h, ``api/ui_themenbaum``): nur die Form einer edu-sharing-Kennung
#: (UUID). Review U1-h, Befund 8 — die weite Form ließe Namen und Sonderkennungen des
#: Repositoriums (``-userhome-``, ``-inbox-``) über den öffentlichen Endpunkt zum MCP-Server.
KNOTEN_UUID: Final = (r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}"
                      r"-[0-9a-fA-F]{12}$")
_KENNUNG: Final = re.compile(KENNUNG)
#: Kennzeichen des Servers → Wert von ``nicht_lesbar``. Abgelehnt geht vor: es bleibt so.
_NICHT_LESBAR: Final = (("childrenRefused", "gesperrt"), ("childrenUnread", "ausfall"))
#: Zusatz in der Textfassung, je Wert.
_TEXT_NICHT_LESBAR: Final = {"ausfall": "Unterthemen gerade nicht lesbar",
                             "gesperrt": "Unterthemen nicht zugänglich"}


def _kennung(wert: Any) -> str | None:
    return wert if isinstance(wert, str) and _KENNUNG.match(wert) else None


def _text(wert: Any) -> str:
    return " ".join(wert.split()) if isinstance(wert, str) else ""


def _knoten(roh: Any, *, mit_kindern: bool) -> tuple[dict[str, Any] | None, bool]:
    """Ein schlanker Knoten und ob darunter gekürzt wurde; ``None`` für Unbrauchbares."""
    if not isinstance(roh, dict):
        return None, False
    kennung, titel = _kennung(roh.get("nodeId")), _text(roh.get("title"))[:_TITEL_ZEICHEN]
    if kennung is None or not titel:
        return None, False
    knoten: dict[str, Any] = {"id": kennung, "titel": titel}
    # Die Themenseite vor der Sammlungs-Adresse, wie das MCP-Widget (``browse/render.ts:219``).
    for feld in ("topicPageUrl", "url"):
        if url := http_url(_text(roh.get(feld))):
            knoten["url"] = url
            break
    anzahl = next((roh[f] for f in ("fileCount", "contentsCount")
                   if isinstance(roh.get(f), int) and not isinstance(roh.get(f), bool)), None)
    if anzahl is not None and anzahl >= 0:
        knoten["anzahl"] = anzahl
    if grund := next((wert for feld, wert in _NICHT_LESBAR if roh.get(feld) is True), None):
        knoten["nicht_lesbar"] = grund
    gekuerzt = roh.get("hasMoreChildren") is True
    if mit_kindern and isinstance(roh.get("children"), list):
        kinder = [k for k, _ in (_knoten(c, mit_kindern=False) for c in roh["children"]) if k]
        if len(kinder) > HOECHSTENS_KINDER:
            kinder, gekuerzt = kinder[:HOECHSTENS_KINDER], True
        if kinder:
            knoten["kinder"] = kinder
    if gekuerzt:
        knoten["mehr"] = True
    return knoten, gekuerzt


def _wurzel_url(kennung: str) -> str | None:
    """Die Sammlung in WLO, wie die Karten sie verlinken (``domain/cards/normalize``)."""
    from boerdi.domain.cards.normalize import _repo_collection_browse_url
    from boerdi.services.config_loader import get_repo_base_url

    basis = get_repo_base_url()
    return http_url(_repo_collection_browse_url(kennung, basis)) if basis else None


def daten_aus(payload: Any, titel: str = "") -> dict[str, Any] | None:
    """Block-Daten aus dem Ergebnis des Werkzeugs; ``None``, wenn es keinen Baum enthält."""
    if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
        return None
    if "parent" in payload and not isinstance(payload["parent"], str):
        return None
    knoten: list[dict[str, Any]] = []
    gekuerzt = payload.get("truncated") is True
    for roh in payload["results"]:
        k, zweig_gekuerzt = _knoten(roh, mit_kindern=True)
        if k is None:
            continue
        if len(knoten) == HOECHSTENS_OBEN:
            break
        knoten.append(k)
        gekuerzt = gekuerzt or zweig_gekuerzt
    daten: dict[str, Any] = {}
    if ueberschrift := _text(titel)[:_UEBERSCHRIFT_ZEICHEN]:
        daten["titel"] = ueberschrift
    if wurzel := _kennung(payload.get("parent")):
        daten["wurzel_id"] = wurzel
        if url := _wurzel_url(wurzel):
            daten["wurzel_url"] = url
    if gekuerzt:
        daten["gekuerzt"] = True
    # Gezählt wird, was der Server schickte: auch ein unbrauchbarer Knoten fehlt im Baum.
    if len(payload["results"]) > HOECHSTENS_OBEN:
        daten["wurzel_mehr"] = True
    if _entwurf_moeglich():
        daten["entwurf_moeglich"] = True
    daten["knoten"] = knoten
    return daten


def _entwurf_moeglich() -> bool:
    """Paket U2 (Review, Befund 9): „Als Entwurf bearbeiten“ nur, wenn der Strukturentwurf im
    Studio aktiv ist — sonst wiese die Direktaktion ab (``services/strukturentwurf_aktion``).
    Dass das Widget ihn meldet, gilt für jedes Widget, das den Knopf kennt."""
    from boerdi.ui_module import schalter
    from boerdi.ui_module.namen import STRUKTURENTWURF

    return schalter.aktiv(STRUKTURENTWURF)


def _zeile(knoten: dict[str, Any], einzug: str) -> str:
    zusatz = _TEXT_NICHT_LESBAR.get(knoten.get("nicht_lesbar") or "")
    return (f"{einzug}- {md_link(knoten['titel'], knoten.get('url') or '')}"
            + (f" ({zusatz})" if zusatz else ""))


def gesperrt_daten() -> dict[str, Any]:
    """Die Antwort des Aufklappens für einen Zweig, den das Repository nicht herausgibt: keine
    Knoten und der Grund. Das Widget zeigt ihn am Eintrag, ohne „Erneut laden“."""
    return {"knoten": [], "nicht_lesbar": "gesperrt"}


def _nicht_lesbar_satz(daten: dict[str, Any]) -> str:
    """Wie viele Themen nicht lesbar waren, getrennt nach Grund — ohne ihre Namen."""
    alle = [k for oben in daten["knoten"] for k in (oben, *oben.get("kinder", []))]
    saetze = []
    for grund, satz in (
        ("ausfall", " Bei {n} ließen sich die Unterthemen gerade nicht lesen; im Baum steht es "
                    "am Thema, und die Person kann sie dort erneut laden."),
        ("gesperrt", " Bei {n} sind die Unterthemen nicht zugänglich (nicht freigegeben); ob es "
                     "welche gibt, ist offen — behaupte nicht, dort gebe es nichts."),
    ):
        if n := sum(1 for k in alle if k.get("nicht_lesbar") == grund):
            saetze.append(satz.format(n="1 Thema" if n == 1 else f"{n} Themen"))
    return "".join(saetze)


def textfassung(daten: dict[str, Any]) -> str:
    """Eingerückte Markdown-Liste mit Links — für Widgets, die das Modul nicht kennen."""
    zeilen = [f"**{daten['titel']}**", ""] if daten.get("titel") else []
    for k in daten["knoten"]:
        zeilen.append(_zeile(k, ""))
        zeilen.extend(_zeile(kind, "  ") for kind in k.get("kinder", []))
        if k.get("mehr"):
            zeilen.append("  - …")
    if daten.get("wurzel_mehr"):
        zeilen.append("- …")
    return "\n".join(zeilen)


def quittung(daten: dict[str, Any]) -> str:
    """Das Werkzeug-Ergebnis für die KI: Umfang ja, Knoten nein (Nachweis U1-e)."""
    oben = len(daten["knoten"])
    if not oben:
        return ("OK: Der Themenbaum steht unter deiner Antwort; diese Sammlung hat keine "
                "Unterthemen. Sag das in einem Satz; die Person kann dort die Inhalte öffnen.")
    mit_kindern = sum(1 for k in daten["knoten"] if k.get("kinder"))
    gekuerzt = " Einige Zweige sind gekürzt; die Person kann sie dort öffnen." if daten.get(
        "gekuerzt") else ""
    if daten.get("wurzel_mehr"):
        gekuerzt += (" Es gibt mehr Themen, als der Baum zeigt; alle sieht die Person in WLO "
                     "(Link am Baum).")
    nicht_lesbar = _nicht_lesbar_satz(daten)
    # Eine Schlussanweisung, nicht je Grund eine (Review N5, Befund 4).
    schluss = (" — darin steht, dass ein Teil der Unterthemen nicht lesbar war." if nicht_lesbar
               else ".")
    return (f"OK: Der Themenbaum steht unter deiner Antwort — {oben} Themen, {mit_kindern} "
            f"davon mit Unterthemen.{gekuerzt}{nicht_lesbar} Die Themen sieht die "
            f"Person dort, du kennst sie nicht: zähle keine auf, schreibe höchstens einen kurzen "
            f"Begleitsatz{schluss}")
