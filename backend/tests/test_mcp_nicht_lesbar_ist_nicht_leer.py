"""Abgelehnt ist nicht leer — und auch kein Ausfall (MCP-Stand 14.11.2026, zweite Runde).

Der MCP sagt jetzt, wenn das Repository einen Zweig mit dieser Anmeldung nicht herausgibt
(401/403/404): ``restricted: true`` an einer Liste samt festem Hinweissatz, im Baum je Knoten
``childrenRefused`` / ``contentsRefused``. Dazu neu für einen Ausfall beim Inhaltsabruf:
``contentsUnread``. Die Formen stammen aus dem Quelltext des Servers
(``services/collection-traversal.ts`` ``RESTRICTED_NOTICE``, ``tools/collections.ts``,
``tools/browse.ts``, ``formatter.ts`` ``renderToJson``).

Für den Chatbot heißt das zweierlei:

- Die KI muss den Satz sehen, auch hinter einer Kürzung — sonst sagt sie „mehr gibt es dort nicht“.
- Für den Cache ist es KEIN Ausfall: ein erneuter Aufruf ändert nichts, die Antwort darf so lange
  stehen wie jede andere (der Schlüssel trägt die Anmeldung).
"""
from __future__ import annotations

import json

import pytest

from boerdi.domain import mcp_unvollstaendig as mu
from boerdi.domain.tool_result_redaction import (
    _redact_search_content_for_llm,
    redigiere_strukturell,
)
from boerdi.services.mcp import client

_HINWEIS = ("Hinweis: Ein Teil des durchsuchten Bereichs ist mit dieser Anmeldung nicht lesbar und "
            "fehlt in dieser Antwort — ob dort etwas liegt, ist offen. Ein erneuter Aufruf ändert "
            "daran nichts.")
_SAMMLUNGEN = "search_wlo_collections"
_INHALTE = "get_collection_contents"
_BAUM = "browse_collection_tree"
_LISTE = {"total": 2, "count": 2, "restricted": True,
          "results": [{"title": "Optik", "nodeId": "n1"}, {"title": "Mechanik", "nodeId": "n2"}]}
#: JSON-Modus: der erste Block bleibt reines JSON, der Satz ist ein eigener Block dahinter.
_LISTE_TEXT = json.dumps(_LISTE, ensure_ascii=False) + "\n" + _HINWEIS
_LEER_TEXT = (json.dumps({"total": 0, "count": 0, "results": [], "restricted": True}) + "\n"
              'In den lesbaren Teilen wurde keine Sammlung für "Optik" gefunden.\n\n' + _HINWEIS)


def _baum(**kennzeichen) -> dict:
    return {"parent": "p1", "results": [{"nodeId": "n1", "title": "Physik", "children": [
        {"nodeId": "n2", "title": "Optik", **kennzeichen}]}]}


# ── Der Cache: abgelehnt ist kein Ausfall ───────────────────────────────────────────────────────

@pytest.mark.parametrize("werkzeug, strukturiert, text", [
    (_SAMMLUNGEN, {"total": 2, "count": 2, "restricted": True}, _LISTE_TEXT),
    (_SAMMLUNGEN, {"total": 0, "count": 0, "restricted": True}, _LEER_TEXT),
    (_INHALTE, {"total": 2, "restricted": True}, _LISTE_TEXT),
    (_BAUM, _baum(childrenRefused=True), json.dumps(_baum(childrenRefused=True))),
    (_BAUM, _baum(contentsRefused=True), json.dumps(_baum(contentsRefused=True))),
])
def test_eine_abgelehnte_unterliste_ist_kein_ausfall(werkzeug, strukturiert, text):
    assert mu.ist_unvollstaendig(werkzeug, strukturiert, text) is False
    assert client._cachebar(werkzeug, text, strukturiert)


def test_ein_ausfall_beim_inhaltsabruf_eines_zweigs_ist_einer():
    """``contentsUnread`` ist neu neben ``childrenUnread``: gerade nicht lesbar, später schon."""
    baum = _baum(contentsUnread=True)
    assert mu.ist_unvollstaendig(_BAUM, baum, json.dumps(baum)) is True
    assert mu.ist_unvollstaendig(_BAUM, None, json.dumps(baum)) is True


def test_abgelehnt_und_ausgefallen_zugleich_bleibt_ein_ausfall():
    """``restricted`` und ``incomplete`` sind unabhängig; der Ausfall bestimmt die Cache-Frist."""
    beides = {"total": 0, "count": 0, "results": [], "incomplete": True, "restricted": True}
    assert mu.ist_unvollstaendig(_SAMMLUNGEN, beides, json.dumps(beides)) is True


# ── Was die KI sieht: der Satz reist mit ────────────────────────────────────────────────────────

def test_der_hinweis_nicht_lesbar_wird_als_satz_des_servers_erkannt():
    assert mu.hinweissaetze(_SAMMLUNGEN, _LISTE_TEXT) == [_HINWEIS]
    # … aber nur hinter dem Umschlag: ein Treffer mit dieser Wendung im Titel ist keine Meldung.
    im_titel = json.dumps({"results": [{"title": "mit dieser Anmeldung nicht lesbar"}]})
    assert mu.hinweissaetze(_SAMMLUNGEN, im_titel) == []


def test_die_kuerzung_der_sammlungssuche_behaelt_kennzeichen_und_satz():
    for kurz in (redigiere_strukturell(_SAMMLUNGEN, _LISTE_TEXT),
                 _redact_search_content_for_llm(_SAMMLUNGEN, _LISTE_TEXT, [], False)):
        umschlag, _, rest = kurz.partition("\n\n")
        assert json.loads(umschlag).get("restricted") is True
        assert rest == _HINWEIS


def test_der_satz_ueberlebt_den_zeichen_deckel():
    lang = json.dumps({"total": 80, "count": 80, "restricted": True,
                       "results": [{"title": "T" * 80, "nodeId": f"n{i}"} for i in range(80)]})
    kurz = _redact_search_content_for_llm(_INHALTE, lang + "\n" + _HINWEIS, [], False)
    assert kurz.endswith(_HINWEIS)


def test_ohne_ablehnung_aendert_sich_die_kuerzung_nicht():
    voll = json.dumps({"total": 1, "count": 1, "results": [{"title": "Optik", "nodeId": "n1"}]})
    kurz = redigiere_strukturell(_SAMMLUNGEN, voll)
    assert "restricted" not in kurz and "nicht lesbar" not in kurz
