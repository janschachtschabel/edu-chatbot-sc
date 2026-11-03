"""Paket U1-c2a: die Trefferliste als abgeleiteter Block (Plan §12).

Aus den fertigen Karten (live nach ``widget_postprocess``, im Verlauf aus der Kartenspalte), den
Such-Angaben (``query_metas`` → Such-Absprung) und der Seitenangabe. ``cards`` bleibt daneben
(Entscheid „Blöcke zusätzlich“).
"""

from __future__ import annotations

from boerdi.api import publikum
from boerdi.api.schemas import ChatResponse, DebugInfo, PaginationInfo, QueryMetaEntry, WebLink
from boerdi.api.schemas_cards import WloCard
from boerdi.api.schemas_ui import UiInfo
from boerdi.ui_module import abgeleitet, katalog

_KARTEN = [WloCard(node_id="c1", title="Sammlung Optik", node_type="collection",
                   url="https://wirlernenonline.de/c1"),
           WloCard(node_id="m1", title="Video Licht", node_type="content",
                   url="https://wirlernenonline.de/m1")]
_META = QueryMetaEntry(tool_name="search_wlo_content", search_term="Optik",
                       search_url="https://wirlernenonline.de/suche?q=Optik")


def _antwort(**mehr) -> ChatResponse:
    return ChatResponse(session_id="bb-12345678-1234", content="x",
                        debug=DebugInfo(pattern=mehr.pop("pattern", "M05 (Suche)")), **mehr)


def test_aus_karten_und_such_angaben_wird_eine_trefferliste():
    b = abgeleitet.trefferliste_block(_KARTEN, [_META], None, "")
    assert (b.modul, b.art) == ("ui_trefferliste", "anzeigen")
    assert [k["node_id"] for k in b.daten["karten"]] == ["c1", "m1"]
    assert b.daten["such_metas"][0]["search_term"] == "Optik"
    assert katalog.daten_fehler(katalog.katalog()["ui_trefferliste"], b.daten) == []
    assert "Sammlung Optik" in b.text


def test_ohne_karten_und_ohne_such_angaben_keine_trefferliste():
    assert abgeleitet.trefferliste_block([], [], None, "") is None


def test_typ_fokus_nur_der_such_absprung():
    b = abgeleitet.trefferliste_block([], [_META], None, "Video")
    assert b.daten["karten"] == [] and b.daten["typ_fokus"] == "Video"


def test_live_zuerst_die_trefferliste_dann_die_linkbox_alte_felder_bleiben():
    resp = _antwort(cards=list(_KARTEN), query_metas=[_META],
                    web_links=[WebLink(title="WLO", url="https://wirlernenonline.de/")],
                    pagination=PaginationInfo(total_count=12, page_size=5, has_more=True,
                                              collection_id="c1", collection_title="Optik"))
    aus = publikum.antwort_fuer(resp, intern=False)
    assert [b.modul for b in aus.ui.ui_bloecke] == ["ui_trefferliste", "ui_linkbox"]
    assert aus.ui.ui_bloecke[0].daten["seiten"]["has_more"] is True
    assert aus.cards and aus.web_links


def test_verlauf_aus_der_kartenspalte_mit_derselben_kennung():
    live = publikum.antwort_fuer(_antwort(cards=list(_KARTEN), query_metas=[_META]),
                                 intern=False)
    (zeile,) = publikum.verlauf_fuer([{
        "role": "assistant", "content": "x", "cards": [k.model_dump() for k in _KARTEN],
        "debug": {"pattern": "M05 (Suche)", "_query_metas": [_META.model_dump()]},
    }], intern=False)
    assert [b["block_id"] for b in zeile["ui"]["ui_bloecke"]] \
        == [b.block_id for b in live.ui.ui_bloecke]


def test_typ_fokus_live_trefferliste_ohne_linkbox():
    resp = _antwort(query_metas=[_META],
                    web_links=[WebLink(title="WLO", url="https://wirlernenonline.de/")])
    resp.ui = UiInfo(type_focus="Video")
    assert [b.modul for b in publikum.antwort_fuer(resp, intern=False).ui.ui_bloecke] \
        == ["ui_trefferliste"]


def test_tour_bekommt_keine_trefferliste():
    aus = publikum.antwort_fuer(_antwort(pattern="TOUR:start", cards=list(_KARTEN)), intern=False)
    assert aus.ui.ui_bloecke == []


def test_ein_muster_kann_die_trefferliste_abschalten(monkeypatch):
    monkeypatch.setattr("boerdi.services.config_loader.load_pattern_definitions",
                        lambda: [{"id": "M05", "ui_module": ["ui_linkbox"]}])
    aus = publikum.antwort_fuer(_antwort(cards=list(_KARTEN)), intern=False)
    assert aus.ui.ui_bloecke == []


# ── Review U1-c2a ─────────────────────────────────────────────────────────
def test_typ_fokus_behaelt_die_karten_wie_die_bisherigen_boxen():
    """``turn_links`` streicht bei Typ-Fokus nur Sammlungen und Themenseiten — Einzelinhalte
    bleiben (Materialien-Box mit „Inhalt anzeigen“). Die Liste übernimmt, was ankommt."""
    inhalt = WloCard(node_id="m1", title="Video Licht", node_type="content")
    b = abgeleitet.trefferliste_block([inhalt], [_META], None, "Video")
    assert [k["node_id"] for k in b.daten["karten"]] == ["m1"]
    assert b.daten["typ_fokus"] == "Video"


def test_die_seitenangabe_gibt_es_nur_live():
    """Ehrlich festgehalten: mit Seitenangabe unterscheidet sich die Kennung live und im Verlauf
    (die Seitenangabe wird nicht gespeichert) — gleich ist sie nur bei gleichen Daten."""
    seiten = PaginationInfo(total_count=12, page_size=5, has_more=True, collection_id="c1")
    live = publikum.antwort_fuer(_antwort(cards=list(_KARTEN), pagination=seiten), intern=False)
    (zeile,) = publikum.verlauf_fuer([{
        "role": "assistant", "content": "x", "cards": [k.model_dump() for k in _KARTEN],
        "debug": {"pattern": "M05 (Suche)"}}], intern=False)
    assert live.ui.ui_bloecke[0].daten["seiten"] is not None
    assert zeile["ui"]["ui_bloecke"][0]["daten"]["seiten"] is None
    assert zeile["ui"]["ui_bloecke"][0]["block_id"] != live.ui.ui_bloecke[0].block_id


def test_der_verlauf_liest_die_muster_einmal_je_abruf(monkeypatch):
    aufrufe = []

    def definitionen():
        aufrufe.append(1)
        return [{"id": "M05"}]
    monkeypatch.setattr("boerdi.services.config_loader.load_pattern_definitions", definitionen)
    zeile = {"role": "assistant", "content": "x", "cards": [k.model_dump() for k in _KARTEN],
             "debug": {"pattern": "M05 (Suche)"}}
    publikum.verlauf_fuer([dict(zeile) for _ in range(5)], intern=False)
    assert len(aufrufe) == 1
