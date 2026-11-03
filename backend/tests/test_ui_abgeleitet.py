"""Paket U1-c1: Blöcke, die aus der fertigen Antwort abgeleitet werden (Linkbox).

Entscheid (Plan §12): Treffer und Links kommen ZUSÄTZLICH als Blöcke; ``web_links`` bleibt.
Abgeleitet wird an der API-Grenze — live nach ``widget_postprocess`` (das Links noch ergänzt),
im Verlauf aus ``_web_links``. Die Kennung hängt nur an Modul und Daten, damit beide gleich sind.
"""

from __future__ import annotations

from boerdi.api import publikum
from boerdi.api.schemas import ChatResponse, DebugInfo, WebLink
from boerdi.api.schemas_ui import UiInfo
from boerdi.domain import ui_bloecke
from boerdi.ui_module import abgeleitet, katalog

_LINKS = [{"title": "WirLernenOnline", "url": "https://wirlernenonline.de/"},
          {"title": "", "url": "https://example.org/seite"}]


def _manifest() -> dict:
    return katalog.katalog()["ui_linkbox"]


def test_aus_den_links_wird_eine_linkbox():
    b = abgeleitet.linkbox_block(_LINKS)
    assert (b.modul, b.version, b.art, b.status) == ("ui_linkbox", 1, "anzeigen", "nur_anzeige")
    assert b.daten == {"links": [{"titel": "WirLernenOnline", "url": "https://wirlernenonline.de/"},
                                 {"titel": "", "url": "https://example.org/seite"}]}
    assert katalog.daten_fehler(_manifest(), b.daten) == []
    assert "https://wirlernenonline.de/" in b.text


def test_pydantic_links_wie_dicts():
    b = abgeleitet.linkbox_block([WebLink(title="WLO", url="https://wirlernenonline.de/")])
    assert b.daten["links"] == [{"titel": "WLO", "url": "https://wirlernenonline.de/"}]


def test_ohne_brauchbare_links_kein_block():
    assert abgeleitet.linkbox_block([]) is None
    assert abgeleitet.linkbox_block([{"title": "x", "url": "javascript:alert(1)"},
                                     {"title": "y", "url": "ftp://a"}, "kaputt", None]) is None


def test_doppelte_fallen_weg_und_der_deckel_gilt():
    viele = [{"title": f"L{i}", "url": f"https://a.example/{i}"} for i in range(40)]
    b = abgeleitet.linkbox_block([*viele, viele[0]])
    assert len(b.daten["links"]) == 30
    assert katalog.daten_fehler(_manifest(), b.daten) == []


def test_die_kennung_haengt_nur_an_den_daten():
    a, b = abgeleitet.linkbox_block(_LINKS), abgeleitet.linkbox_block(list(_LINKS))
    assert a.block_id == b.block_id
    assert a.block_id != abgeleitet.linkbox_block(_LINKS[:1]).block_id


def test_erlaubt_steuert_die_abgeleiteten_module():
    assert [b.modul for b in abgeleitet.abgeleitete_bloecke(web_links=_LINKS, erlaubt=None)] \
        == ["ui_linkbox"]
    assert abgeleitet.abgeleitete_bloecke(web_links=_LINKS, erlaubt=frozenset()) == []


# ── an der API-Grenze ─────────────────────────────────────────────────────
def _antwort(**mehr) -> ChatResponse:
    return ChatResponse(session_id="bb-12345678-1234", content="x",
                        debug=DebugInfo(pattern=mehr.pop("pattern", "M05")), **mehr)


def test_live_haengt_die_linkbox_nach_den_gelieferten_bloecken_an():
    rahmen = ui_bloecke.neuer_block("ui_inhaltsrahmen", 1, "anzeigen",
                                    {"titel": "T", "art": "dokument", "markdown": "m"}, "m")
    resp = _antwort(web_links=[WebLink(**link) for link in _LINKS])
    resp.ui = UiInfo(ui_bloecke=[rahmen])
    aus = publikum.antwort_fuer(resp, intern=False)
    assert [b.modul for b in aus.ui.ui_bloecke] == ["ui_inhaltsrahmen", "ui_linkbox"]
    assert aus.web_links, "das alte Feld bleibt (Entscheid: Blöcke zusätzlich)"


def test_verlauf_und_live_tragen_dieselbe_linkbox():
    live = publikum.antwort_fuer(_antwort(web_links=[WebLink(**link) for link in _LINKS]),
                                 intern=False)
    verlauf = publikum.ui_aus_gespeichert({"pattern": "M05", "_web_links": _LINKS})
    assert [b.block_id for b in verlauf.ui_bloecke] == [b.block_id for b in live.ui.ui_bloecke]


def test_tour_nachrichten_bekommen_keine_linkbox():
    """Wie die heutige Box (``isTourMessage``): die Führung zeigt keine Webseiten-Box."""
    aus = publikum.antwort_fuer(
        _antwort(pattern="TOUR:start", web_links=[WebLink(**link) for link in _LINKS]),
        intern=False)
    assert aus.ui.ui_bloecke == []


def test_ohne_links_bleibt_alles_wie_es_ist():
    aus = publikum.antwort_fuer(_antwort(), intern=False)
    assert aus.ui.ui_bloecke == []


def test_die_linkbox_haelt_webseiten_max_ein_wie_die_bisherige_box(monkeypatch):
    """``display_rules.groups.webseiten_max`` (Vorgabe 3) — ``widget_postprocess`` ergänzt Links
    nach dem Speichern; ohne die Grenze zeigte die Linkbox mehr als die bisherige Box."""
    monkeypatch.setattr("boerdi.services.config_loader.load_display_rules_config",
                        lambda: {"groups": {"webseiten_max": 2}})
    viele = [WebLink(title=f"L{i}", url=f"https://a.example/{i}") for i in range(5)]
    live = publikum.antwort_fuer(_antwort(web_links=viele), intern=False)
    assert [link["titel"] for link in live.ui.ui_bloecke[0].daten["links"]] == ["L0", "L1"]
    verlauf = publikum.ui_aus_gespeichert(
        {"pattern": "M05", "_web_links": [v.model_dump() for v in viele]})
    assert verlauf.ui_bloecke[0].block_id == live.ui.ui_bloecke[0].block_id


# ── Review U1-c1 ──────────────────────────────────────────────────────────
def test_typ_fokus_antworten_bekommen_keine_linkbox():
    """Wie die bisherige Box (``groupedWebLinks``): bei Typ-Fokus nie Webseiten — auch nicht die
    Links, die ``widget_postprocess`` nach dem Leeren noch ergänzt."""
    resp = _antwort(web_links=[WebLink(**link) for link in _LINKS])
    resp.ui = UiInfo(type_focus="Video")
    assert publikum.antwort_fuer(resp, intern=False).ui.ui_bloecke == []
    verlauf = publikum.ui_aus_gespeichert(
        {"pattern": "M05", "_type_focus": "Video", "_web_links": _LINKS})
    assert verlauf.ui_bloecke == []


def test_ohne_links_wird_keine_einstellung_gelesen(monkeypatch):
    """Der Verlauf fragt je Nachricht — ohne Links darf das nichts kosten."""
    def nie():
        raise AssertionError("gelesen")
    monkeypatch.setattr("boerdi.services.config_loader.load_display_rules_config", nie)
    monkeypatch.setattr("boerdi.services.config_loader.load_pattern_definitions", nie)
    assert publikum.ui_aus_gespeichert({"pattern": "M05"}).ui_bloecke == []
    assert publikum.antwort_fuer(_antwort(), intern=False).ui.ui_bloecke == []


def test_das_schema_wird_klein_geschrieben():
    """Das Manifest verlangt ``^https?://`` — ``HTTPS://`` würde den eigenen Vertrag brechen."""
    b = abgeleitet.linkbox_block([{"title": "x", "url": "HTTPS://Example.org/Pfad"}])
    assert b.daten["links"][0]["url"] == "https://Example.org/Pfad"
    assert katalog.daten_fehler(_manifest(), b.daten) == []
