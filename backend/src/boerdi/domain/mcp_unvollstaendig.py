"""Ausfall ist nicht „nichts gefunden“ (Plan 2026-11-13, C1).

Seit der Audit-Nacharbeit sagt der MCP-Server, wenn eine Quelle nicht (vollständig) geantwortet
hat — statt eine leere oder kurze Liste wie einen Befund aussehen zu lassen. Die Formen, am
Arbeitsstand des Servers gelesen (Reviews C1):

- im strukturierten Teil ``incomplete: true`` an einer Liste oder an einem Topf von
  ``search_wlo_all`` (``collections``, ``topicPages``);
- im JSON-TEXT steht das Kennzeichen nur bei ``search_wlo_all`` (je Topf) und im Leerfall der
  Themenseiten; ``search_wlo_collections`` schreibt dort nur ``{total, count, results}`` und hängt
  den Hinweissatz als eigenen Block an — im Text also HINTER dem Umschlag;
- ``childrenUnread: true`` an einem Knoten von ``browse_collection_tree``, seit dem MCP-Stand
  vom 14.11.2026 auch ``contentsUnread: true`` (der Inhaltsabruf des Zweigs) — dieses auch je
  Eintrag in ``subcollections`` von ``get_collection_overview``;
- ``unreachable: true`` bei ``get_wikipedia_summary``;
- ``reason: "source_unreachable"`` bei ``get_topic_page_content``;
- im Markdown-Modus nur ein Hinweissatz.

Dieses Modul erkennt das an einer Stelle. Wer es braucht: der Cache (eine solche Antwort bleibt
nur kurz stehen) und die Kürzung für die KI (der Satz des Servers reist mit).

**Nur für die Werkzeuge in** :data:`WERKZEUGE`. Bei jedem anderen — einer Anleitung, einem
Volltext, einem fremden MCP-Server — könnte dieselbe Wendung oder dasselbe Feld etwas anderes
heißen (zweites Review C1).

**Abgelehnt ist kein Ausfall** (MCP-Stand 14.11.2026): gibt das Repository einen Zweig mit
dieser Anmeldung nicht heraus, steht ``restricted: true`` an der Liste bzw. ``childrenRefused`` /
``contentsRefused`` am Knoten, dazu ein fester Hinweissatz. Ein erneuter Aufruf ändert daran
nichts — die Antwort bleibt also so lange im Cache wie jede andere (der Schlüssel trägt die
Anmeldung). Der Satz reist aber mit zur KI wie die Ausfall-Sätze, sonst läse sie „mehr gibt es
dort nicht“.

Bewusst nicht erkannt: die Skill-Suche. Ihr ``incomplete`` mit ``incompleteNote`` und ihr Satz
(„Die Sammlung wurde nicht vollständig gelesen“) stehen auch für dauerhafte Grenzen (Seitengröße,
Tiefe).
"""

from __future__ import annotations

import json
from typing import Any, Final

#: Die lesenden WLO-Werkzeuge, deren Antwort einen Ausfall kennzeichnen kann.
WERKZEUGE: Final = frozenset({
    "search_wlo_all", "search_wlo_collections", "search_wlo_content", "search_wlo_topic_pages",
    "search_wlo_within_collection", "get_collection_contents", "browse_collection_tree",
    "get_collection_overview", "get_topic_page_content", "get_wikipedia_summary",
    "search_wlo_content_many", "list_collection_tree"})
#: Wendungen aus den Hinweissätzen des Servers (``services/collection-search.ts``
#: ``incompleteNotice``, ``tools/wikipedia.ts``, ``tools/collections.ts`` ``WALK_INCOMPLETE_NOTE``,
#: ``tools/browse.ts``).
_SAETZE: Final = ("hat nicht (vollständig) geantwortet", "war nur teilweise erreichbar",
                  "Wikipedia hat gerade nicht geantwortet", "ließ sich gerade nicht lesen",
                  "ließen sich gerade nicht lesen")
#: Wendung der Hinweise auf einen ABGELEHNTEN Teil (``services/collection-traversal.ts``
#: ``RESTRICTED_NOTICE``, ``tools/browse.ts`` je Knoten): kein Ausfall, aber die KI muss es wissen.
_SAETZE_ABGELEHNT: Final = ("mit dieser Anmeldung nicht lesbar",)
#: Der Grund von ``get_topic_page_content``, wenn die Suche nach der Seite nicht geantwortet hat.
GRUND_AUSFALL: Final = "source_unreachable"
_SATZ_ZEICHEN: Final = 400
#: So viele Hinweissätze reisen höchstens mit (der Baum kann je Zweig einen tragen).
_SAETZE_HOECHSTENS: Final = 3
#: So tief wird ein Baum nach ``childrenUnread`` durchsucht (der Server liefert höchstens 3 Ebenen).
_BAUM_TIEFE: Final = 6
_LESER: Final = json.JSONDecoder()


def _zweig_ungelesen(knoten: Any, tiefe: int = 0) -> bool:
    """``childrenUnread`` oder ``contentsUnread`` an einem Knoten des Baums
    (``results[].children[]…``). ``childrenRefused`` / ``contentsRefused`` zählen nicht: abgelehnt
    bleibt abgelehnt."""
    if not isinstance(knoten, list) or tiefe > _BAUM_TIEFE:
        return False
    return any(isinstance(k, dict) and (k.get("childrenUnread") is True
                                         or k.get("contentsUnread") is True
                                         or _zweig_ungelesen(k.get("children"), tiefe + 1))
               for k in knoten)


def gekennzeichnet(daten: Any) -> bool:
    """Trägt der Umschlag ein Kennzeichen — oben, an einem seiner Töpfe oder an einem Zweig?"""
    if not isinstance(daten, dict) or "incompleteNote" in daten:
        return False                    # ``incompleteNote``: die Skill-Suche (siehe Modulkopf)
    if (daten.get("incomplete") is True or daten.get("unreachable") is True
            or daten.get("reason") == GRUND_AUSFALL):
        return True
    # ``subcollections``: die Übersicht führt je Untersammlung ``contentsUnread`` (MCP 14.11.).
    # Die Mehrfachsuche (N4) führt ihre Töpfe eine Ebene tiefer: ``results[id].incomplete``.
    je_anfrage = daten.get("results")
    toepfe = [*daten.values(), *(je_anfrage.values() if isinstance(je_anfrage, dict) else ())]
    return (_zweig_ungelesen(daten.get("results")) or _zweig_ungelesen(daten.get("subcollections"))
            or any(isinstance(topf, dict) and topf.get("incomplete") is True for topf in toepfe))


def _zerlegt(text: str) -> tuple[Any, str]:
    """Der JSON-Umschlag am Anfang des Textes und der Rest dahinter — ohne Umschlag ``None`` und
    der ganze Text. ``raw_decode`` liest genau einen Wert und sagt, wo er endet."""
    roh = text.lstrip().lstrip("﻿")
    if roh[:1] in ("{", "["):
        try:
            umschlag, ende = _LESER.raw_decode(roh)
        except (ValueError, RecursionError):
            return None, text
        return umschlag, roh[ende:]
    return None, text


def ohne_umschlag(text: str) -> str:
    """Der Text HINTER dem JSON-Umschlag — für Antworten, deren Umschlag nur der Chatbot liest
    (Mehrfachsuche, N4). Ohne Umschlag oder ohne Text dahinter bleibt der Text, wie er ist."""
    umschlag, rest = _zerlegt(text or "")
    return rest.strip() if isinstance(umschlag, dict) and rest.strip() else text


def _saetze_im(rest: str, wendungen: tuple[str, ...] = _SAETZE) -> list[str]:
    return [zeile.strip()[:_SATZ_ZEICHEN] for zeile in rest.splitlines()
            if any(satz in zeile for satz in wendungen)][:_SAETZE_HOECHSTENS]


def hinweissaetze(tool_name: str, text: str) -> list[str]:
    """Die Hinweissätze des Servers im Text — Ausfall UND abgelehnter Teil —, nur AUSSERHALB des
    Umschlags: ein Treffer, dessen Titel so eine Wendung enthält, ist keine Meldung des Servers.
    Höchstens drei."""
    if tool_name not in WERKZEUGE or not text:
        return []
    return _saetze_im(_zerlegt(text)[1], _SAETZE + _SAETZE_ABGELEHNT)


def ist_unvollstaendig(tool_name: str, strukturiert: dict[str, Any] | None, text: str) -> bool:
    """Hat eine Quelle dieser Antwort nicht (vollständig) geantwortet? Erst der strukturierte
    Teil, dann der Umschlag im Text, dann die Hinweissätze dahinter."""
    if tool_name not in WERKZEUGE:
        return False
    if gekennzeichnet(strukturiert):
        return True
    if not text:
        return False
    umschlag, rest = _zerlegt(text)
    return gekennzeichnet(umschlag) or bool(_saetze_im(rest))


def kennzeichen(topf: dict[str, Any]) -> dict[str, bool]:
    """Für die Kürzung eines Topfs: ``incomplete`` (Ausfall) und ``restricted`` (abgelehnter
    Teil) bleiben, wenn der Server sie gesetzt hat."""
    return {feld: True for feld in ("incomplete", "restricted") if topf.get(feld) is True}


def mit_hinweissaetzen(tool_name: str, gekuerzt: str, roh: str) -> str:
    """``gekuerzt`` mit den Hinweissätzen des Servers aus ``roh``, soweit sie der Kürzung zum
    Opfer fielen (Deckel, Ersatz durch eine Ansage, Umschlag ohne Begleittext)."""
    fehlend = [satz for satz in hinweissaetze(tool_name, roh) if satz not in gekuerzt]
    return gekuerzt + "\n\n" + "\n".join(fehlend) if fehlend else gekuerzt
