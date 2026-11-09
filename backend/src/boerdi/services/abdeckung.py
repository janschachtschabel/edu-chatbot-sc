"""Paket M1 (Plan 2026-11-08, E-1/E-2): wie viele WLO-Inhalte es zu den Punkten einer
Gliederung gibt.

Der Dienst zu ``count_wlo_content_matches`` (MCP, lesend, seit Paket M4): deterministisch, ohne
LLM, in Bündeln zu :data:`JE_AUFRUF` Anfragen, höchstens :data:`HOECHSTENS` Punkte. Die Zahlen
gelten für **ganz WLO**, nicht für eine Sammlung (eine Suche je Punkt, ohne Teilbaum-Bezug —
Server ``services/content-count.ts``).

- :func:`punkte_aus_entwurf`: die Gliederungspunkte eines Strukturentwurfs (Ebene 1 und 2), je mit
  Fach und Bildungsstufe als Filter — vom Punkt, sonst vom Elternpunkt, sonst vom Entwurf (Review
  M1, Befund 3). Klartext-Labels; der Server löst sie auf, ein nicht auflösbarer Filter steht als
  ``unresolved_filter`` beim Punkt, ein geratener in ``geraten``.
- :func:`zaehlen`: die Treffer je Punkt; was der Server nicht zählen konnte, steht mit einem Code
  aus seiner festen Liste unter ``fehlen`` — nie ein Text des Servers.

Robust gegen einen kaputten Entwurf (Review M1, Befund 2): ein Dienst bekommt Teile ungeprüft.
Der Server wird ohne Cache gefragt: nur so trägt die Antwort ihren strukturierten Teil.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, Final

from boerdi.ui_module import strukturentwurf as se

logger = logging.getLogger(__name__)

WERKZEUG: Final = "count_wlo_content_matches"
#: So viele Anfragen nimmt der Server je Aufruf.
JE_AUFRUF: Final = 30
#: So viele Punkte zählt der Dienst höchstens (zwei Aufrufe).
HOECHSTENS: Final = 60
#: Bis zu so vielen Treffern (einschließlich) gilt ein Punkt als Lücke (U5).
LUECKE_BIS: Final = 2
#: So viele beste Treffer je Punkt.
TOP: Final = 2
#: Die Codes des Servers für ``missing`` (``tools/content-count.ts``) — und unsere eigenen.
_CODES: Final = frozenset({"unresolved_filter", "timeout", "forbidden", "upstream_busy",
                           "upstream_error"})
#: Nach diesen Arten bleibt der Rest ungezählt (Review M1, Befund 5): keine Antwort, ausgelastet
#: oder abgewiesen — ein zweites Bündel belastete nur den Server und den Zug.
_ABBRUCH: Final = frozenset({"timeout", "busy", "auth", "transport"})
_GERATEN: Final = frozenset({"educationalContext", "discipline", "userRole",
                             "learningResourceType"})
_TITEL: Final = 120
_URL: Final = 300
_KENNUNG: Final = re.compile(se.KENNUNG)
_UNSICHER: Final = re.compile(r"[\s\x00-\x1f\x7f​-‏ -‮⁦-⁩﻿]")


@dataclass(frozen=True)
class Punkt:
    """Ein Gliederungspunkt, der gezählt wird."""

    id: str
    titel: str
    ebene: int
    #: Der Suchtext (Titel, dazu bis zu zwei Schlagwörter).
    anfrage: str
    #: Fach und Bildungsstufe (Filter der Zählung), geerbt.
    filter_: dict[str, str] = field(default_factory=dict)
    #: Gesamt-Review, Befund 6: Titel oder Schlagwörter sehen nach persönlichen Daten aus — nicht
    #: als Suche an WLO (die Sperre der Sicherheitsprüfung sieht nur die Nachricht des Zugs).
    persoenlich: bool = False


@dataclass
class Zaehlung:
    """Treffer je Punkt (``id`` → ``{total, top, geraten?}``) und was fehlt (``id`` → Code)."""

    treffer: dict[str, dict[str, Any]] = field(default_factory=dict)
    fehlen: dict[str, str] = field(default_factory=dict)


def _text(wert: Any, deckel: int) -> str:
    return " ".join(wert.split())[:deckel] if isinstance(wert, str) else ""


def _filter(k: dict[str, Any], erbe: dict[str, str]) -> dict[str, str]:
    eigen = dict(erbe)
    if fach := se.fach(k.get("fach")):
        eigen["discipline"] = fach
    if stufe := se.bildungsstufe(k.get("bildungsstufe")):
        eigen["educationalContext"] = stufe
    return eigen


def _knoten(knoten: Any, ebene: int, tiefe: int, erbe: dict[str, str]
            ) -> Iterator[tuple[dict[str, Any], int, dict[str, str]]]:
    """Nur Dicts, nur Listen als ``kinder``, nicht tiefer als ``tiefe`` (kein
    ``RecursionError``)."""
    if ebene > tiefe or not isinstance(knoten, list):
        return
    for k in knoten:
        if not isinstance(k, dict):
            continue
        eigen = _filter(k, erbe)
        yield k, ebene, eigen
        yield from _knoten(k.get("kinder"), ebene + 1, tiefe, eigen)


def punkte_aus_entwurf(entwurf: Any, *, tiefe: int = 2) -> list[Punkt]:
    """Die Punkte eines Entwurfs (``wlo.sammlungsstruktur@1``) bis ``tiefe`` — höchstens
    :data:`HOECHSTENS`, in Lesereihenfolge; ohne gültige Kennung oder Titel nicht."""
    if not isinstance(entwurf, dict):
        return []
    punkte: list[Punkt] = []
    gesehen: set[str] = set()
    for k, ebene, filter_ in _knoten(entwurf.get("knoten"), 1, tiefe, filter_aus_entwurf(entwurf)):
        kennung = k.get("id") if isinstance(k.get("id"), str) else ""
        titel = _text(k.get("titel"), _TITEL)
        if not _KENNUNG.match(kennung) or not titel or kennung in gesehen:
            continue
        gesehen.add(kennung)
        roh = k.get("keywords") if isinstance(k.get("keywords"), list) else []
        worte = [_text(w, 40) for w in roh if _text(w, 40)][:2]
        anfrage = " ".join([titel, *worte])[:500]
        punkte.append(Punkt(kennung, titel, ebene, anfrage, filter_, persoenlich(anfrage)))
        if len(punkte) >= 4 * HOECHSTENS:
            break
    # Review U5, NIT 9: über dem Deckel erst alle Punkte der oberen Ebenen, in Lesereihenfolge
    if len(punkte) > HOECHSTENS:
        behalten = set(sorted(range(len(punkte)), key=lambda i: (punkte[i].ebene, i))[:HOECHSTENS])
        punkte = [p for i, p in enumerate(punkte) if i in behalten]
    return punkte


_EMAIL: Final = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_TELEFON: Final = re.compile(r"(?:\+|\b0)\d[\d\s/()-]{6,}\d")
_IBAN: Final = re.compile(r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){3,}", re.IGNORECASE)


def persoenlich(text: str) -> bool:
    """Sieht der Text nach persönlichen Daten aus? E-Mail, Telefonnummer, IBAN — und was die
    Sicherheitsprüfung als persönliche Angabe erkennt (``regex_gate``). Namen erkennt das nicht;
    die Zählung bleibt eine Suche nach Gliederungspunkten (Rest-Risiko in der Notiz)."""
    from boerdi.services.safety.regex_gate import enthaelt_persoenliches

    return bool(_EMAIL.search(text) or _TELEFON.search(text) or _IBAN.search(text)
                or enthaelt_persoenliches(text))


def filter_aus_entwurf(entwurf: Any) -> dict[str, str]:
    """Fach und Bildungsstufe des ganzen Entwurfs als Filter (Bildungsstufe nur als WLO-Label;
    das Fach ist ein kurzes Label, ob WLO es kennt, sagt erst der Server)."""
    return _filter(entwurf, {}) if isinstance(entwurf, dict) else {}


async def zaehlen(punkte: list[Punkt]) -> Zaehlung:
    """Die Treffer je Punkt — in Bündeln zu :data:`JE_AUFRUF`. Ein Bündel ohne Antwort setzt seine
    Punkte auf ``keine_antwort``; nach einem Ausfall (:data:`_ABBRUCH`) auch den Rest."""
    from boerdi.services.mcp.client import call_mcp_tool_antwort, is_mcp_error

    erg = Zaehlung()
    erg.fehlen.update({p.id: "persoenlich" for p in punkte[:HOECHSTENS] if p.persoenlich})
    punkte = [p for p in punkte[:HOECHSTENS] if not p.persoenlich]
    for start in range(0, len(punkte), JE_AUFRUF):
        buendel = punkte[start:start + JE_AUFRUF]
        anfragen = [{"id": p.id, "query": p.anfrage,
                     **({"filters": dict(p.filter_)} if p.filter_ else {})} for p in buendel]
        antwort = await call_mcp_tool_antwort(WERKZEUG, {"queries": anfragen, "top": TOP},
                                              use_cache=False)
        art, code = antwort.art, antwort.code
        sc = antwort.strukturiert if isinstance(antwort.strukturiert, dict) else None
        if art or is_mcp_error(antwort.text) or sc is None:
            grund = (code or art or "ohne strukturierten Teil")[:40]
            logger.info("Abdeckung: Bündel nicht gezählt (%s)", grund)
            rest = punkte[start:] if art in _ABBRUCH else buendel
            erg.fehlen.update({p.id: "keine_antwort" for p in rest})
            if art in _ABBRUCH:
                break
            continue
        _uebernehmen(erg, buendel, sc)
    return erg


def _liste(wert: Any) -> list[Any]:
    return wert if isinstance(wert, list) else []


def _uebernehmen(erg: Zaehlung, buendel: list[Punkt], sc: dict[str, Any]) -> None:
    """Gesamt-Review, Befund 2: jeder Eintrag erst auf seine Form geprüft — eine kaputte Antwort
    (Kennung als Liste, Filter als Objekt) wirft nicht, sie zählt nicht."""
    bekannt = {p.id for p in buendel}
    for r in _liste(sc.get("results")):
        if not isinstance(r, dict) or not isinstance(r.get("id"), str):
            continue
        total = r.get("total")
        if r["id"] not in bekannt or type(total) is not int or total < 0:
            continue
        treffer: dict[str, Any] = {"total": total, "top": _top(r.get("top"))}
        geraten = [f for f in _liste(r.get("fuzzyFilters")) if isinstance(f, str) and f in _GERATEN]
        if geraten:
            treffer["geraten"] = sorted(set(geraten))      # Review M1, Befund 4
        erg.treffer[r["id"]] = treffer
    for m in _liste(sc.get("missing")):
        teil = m.get("part") if isinstance(m, dict) else None
        if isinstance(teil, str) and teil in bekannt and teil not in erg.treffer:
            code = m.get("code")
            erg.fehlen[teil] = code if isinstance(code, str) and code in _CODES else "fehler"
    for p in buendel:
        if p.id not in erg.treffer and p.id not in erg.fehlen:
            erg.fehlen[p.id] = "fehler"


def _top(roh: Any) -> list[dict[str, str]]:
    """Die besten Treffer, nur Kennung, Titel und (sichere) Adresse; zu lange Kennungen und
    Adressen fallen weg statt gekürzt zu werden (Review M1, Befund 9)."""
    aus: list[dict[str, str]] = []
    for t in roh if isinstance(roh, list) else []:
        if not isinstance(t, dict) or not isinstance(t.get("nodeId"), str) or \
                not 0 < len(t["nodeId"]) <= 80 or _UNSICHER.search(t["nodeId"]):
            continue
        url = t.get("url") if isinstance(t.get("url"), str) else ""
        sicher = (url.startswith(("https://", "http://")) and len(url) <= _URL
                  and not _UNSICHER.search(url))
        aus.append({"nodeId": t["nodeId"], "titel": _text(t.get("title"), _TITEL),
                    **({"url": url} if sicher else {})})
        if len(aus) >= TOP:
            break
    return aus


def ist_luecke(treffer: dict[str, Any] | None) -> bool:
    """Ein gezählter Punkt mit höchstens :data:`LUECKE_BIS` Treffern."""
    return isinstance(treffer, dict) and type(treffer.get("total")) is int and \
        treffer["total"] <= LUECKE_BIS


async def fuer_entwurf(entwurf: Any) -> dict[str, Any]:
    """Der Ablauf-Dienst ``abdeckung_zaehlen``: Punkte mit Treffern, Lücken und Fehlstellen —
    ``{punkte: [{id, titel, ebene, total?, top?, luecke?, geraten?, fehlt?}], gezaehlt, luecken,
    filter_unaufgeloest}``. ``filter_unaufgeloest``: kein Punkt gezählt, weil WLO Fach oder
    Bildungsstufe nicht kennt (Review M1, Befund 4)."""
    punkte = punkte_aus_entwurf(entwurf)
    if not punkte:
        return {"punkte": [], "gezaehlt": 0, "luecken": 0, "filter_unaufgeloest": False}
    z = await zaehlen(punkte)
    zeilen: list[dict[str, Any]] = []
    for p in punkte:
        zeile: dict[str, Any] = {"id": p.id, "titel": p.titel, "ebene": p.ebene}
        if (t := z.treffer.get(p.id)) is not None:
            zeile |= {"total": t["total"], "top": t["top"], "luecke": ist_luecke(t),
                      **({"geraten": t["geraten"]} if t.get("geraten") else {})}
        else:
            zeile["fehlt"] = z.fehlen.get(p.id, "fehler")
        zeilen.append(zeile)
    return {"punkte": zeilen, "gezaehlt": len(z.treffer),
            "luecken": sum(1 for zl in zeilen if zl.get("luecke")),
            "filter_unaufgeloest": not z.treffer and bool(z.fehlen) and all(
                c == "unresolved_filter" for c in z.fehlen.values())}
