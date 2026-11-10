"""Paket AS-Db (Plan 2026-11-09 §5e): Prüfung je Weg und Typen der Teile.

- Ein ``$teil``-Verweis auf einen Teil, den weder ein Schritt des Ablaufs noch irgendein Modul
  schreibt, ist ein Befund. Entsteht der Teil im Ablauf erst nach dem Schritt, ist das eine
  Warnung (kein Befund): er kann aus einem früheren Gespräch im Vorgang liegen.
- Liest ein Dienst oder ein Modul einen ganzen Teil (ohne Pfad, ohne Auswahl), muss dessen Typ
  passen — soweit die Schreiber bekannt sind.
"""

from __future__ import annotations

from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.services.ablauf import typen
from boerdi.services.ablauf.pruefung import pruefe, warnungen

_UPLOAD = {"id": "up", "typ": "modul", "modul": "ui_upload", "daten": {}, "bei_fehler": "e"}
_ENTWURF = {"id": "entwurf", "typ": "werkzeug", "werkzeug": "strukturentwurf_aus_ordnern",
            "argumente": {"struktur": {"$teil": "structure"}}, "schreibt": "eigener",
            "bei_fehler": "e"}
_ZAEHLEN = {"id": "zaehlen", "typ": "werkzeug", "werkzeug": "abdeckung_zaehlen",
            "argumente": {"entwurf": {"$teil": "eigener"}}, "schreibt": "zahlen",
            "bei_fehler": "e"}


def _ablauf(*schritte) -> AblaufArea:
    return AblaufArea.model_validate({"id": "d", "titel": {"de": "D"}, "schritte": [
        *schritte, {"id": "e", "typ": "ende"}]})


def test_ein_passender_datenfluss_hat_weder_befund_noch_warnung():
    ablauf = _ablauf(_UPLOAD | {"weiter": "entwurf"}, _ENTWURF | {"weiter": "zaehlen"}, _ZAEHLEN)
    assert pruefe(ablauf) == []
    assert warnungen(ablauf) == []


def test_ein_teil_den_nichts_schreibt_ist_ein_befund():
    lesen = _ZAEHLEN | {"argumente": {"entwurf": {"$teil": "gibtsnicht"}}}
    befunde = pruefe(_ablauf(lesen))
    assert any("gibtsnicht" in b and "schreibt" in b for b in befunde), befunde


def test_ein_teil_den_ein_modul_irgendwo_schreibt_ist_nur_eine_warnung():
    """``draft`` schreibt ``ui_strukturentwurf`` — er kann aus dem Gespräch im Vorgang liegen."""
    lesen = _ZAEHLEN | {"argumente": {"entwurf": {"$teil": "draft"}}}
    ablauf = _ablauf(lesen)
    assert not any("draft" in b for b in pruefe(ablauf))
    assert any("draft" in w for w in warnungen(ablauf))


def test_ein_teil_der_erst_spaeter_entsteht_ist_eine_warnung():
    """Kein Weg führt vom Schreiber zum Leser (Review AS-Db, Befund 7: der Ablauf ist sonst
    befundfrei)."""
    ablauf = _ablauf(_ZAEHLEN | {"weiter": "up"}, _UPLOAD | {"weiter": "entwurf"},
                     _ENTWURF | {"weiter": "e"})
    assert pruefe(ablauf) == []
    assert any("eigener" in w and "nach" in w for w in warnungen(ablauf))


def test_ein_falscher_typ_ist_ein_befund():
    """Der Ordnerbaum (``structure``) ist kein Entwurf — ``abdeckung_zaehlen`` braucht einen."""
    lesen = _ZAEHLEN | {"argumente": {"entwurf": {"$teil": "structure"}}}
    befunde = pruefe(_ablauf(_UPLOAD | {"weiter": "zaehlen"}, lesen))
    assert any("Typ" in b and "structure" in b for b in befunde), befunde


def test_mit_pfad_oder_auswahl_gibt_es_keinen_typvergleich():
    lesen = _ZAEHLEN | {"argumente": {"entwurf": {"$teil": "structure", "pfad": "struktur"}}}
    befunde = pruefe(_ablauf(_UPLOAD | {"weiter": "zaehlen"}, lesen))
    assert not any("Typ" in b for b in befunde), befunde


def test_ein_unbekannter_schreiber_wird_nicht_verglichen():
    """Die Ausgabe eines KI-Schritts hat keinen festen Typ."""
    ki = {"id": "ki", "typ": "agent", "agent": {"werkzeuge": ["search_wlo_all"],
                                                "ausgabe": "eigener"}, "weiter": "zaehlen"}
    befunde = pruefe(_ablauf(ki, _ZAEHLEN))
    assert not any("Typ" in b for b in befunde), befunde


def test_die_typtabelle_kennt_die_schreiber():
    ablauf = _ablauf(_UPLOAD | {"weiter": "entwurf"}, _ENTWURF | {"weiter": "zaehlen"}, _ZAEHLEN)
    t = typen.ausgaben(ablauf)
    assert t["structure"] == {typen.ORDNERBAUM}
    assert t["eigener"] == {typen.STRUKTUR}
    assert t["zahlen"] == {"wlo.abdeckung@1"}


def test_der_mitgelieferte_ablauf_bleibt_ohne_befund_und_warnung():
    import pathlib

    import yaml

    seed = pathlib.Path(__file__).parents[1] / "seeds" / "06-ablaeufe" / "sammlungsstruktur.yaml"
    ablauf = AblaufArea.model_validate(yaml.safe_load(seed.read_text(encoding="utf-8")))
    assert pruefe(ablauf) == []
    assert warnungen(ablauf) == []



# ── Review AS-Db ───────────────────────────────────────────────────────────

def test_die_ablage_nach_dem_upload_ist_bekannt(monkeypatch, request):
    """Befund 1: der Leitfall aus D8 — ``ablage`` schreibt ``ui_upload`` außerhalb seines
    Manifests; die nodeIds gehen als Liste an einen Flow (Querschnitts-Review AS-D: an einem
    Objekt-Argument eines Dienstes wäre die Auswahl ein Befund)."""
    from boerdi.settings import get_settings

    monkeypatch.setenv("B_API_JOBS_START_PATH", "/api/v1/jobs/flows/{flow}")
    monkeypatch.setenv("B_API_JOBS_FLOWS", "wlo/volltext")
    get_settings.cache_clear()
    request.addfinalizer(get_settings.cache_clear)
    lesen = {"id": "lesen", "typ": "auftrag", "flow": "wlo/volltext",
             "argumente": {"structure_node_ids": {"$teil": "ablage", "liste": "inhalte",
                                                  "wo": {"rolle": "struktur"}, "feld": "node_id"}},
             "schreibt": "zahlen", "bei_fehler": "e"}
    ablauf = AblaufArea.model_validate({
        **_ablauf(_UPLOAD | {"weiter": "lesen"}, lesen).model_dump(exclude_none=True),
        "voraussetzungen": ["anmeldung"]})
    assert pruefe(ablauf) == []
    assert warnungen(ablauf) == []


def test_ein_strukturabgleich_nimmt_keinen_entwurf():
    """Befund 2: ``ui_strukturabgleich`` bekommt ein fertiges Abgleich-Ergebnis."""
    abgleich = {"id": "abgleich", "typ": "modul", "modul": "ui_strukturabgleich",
                "daten": {"$teil": "eigener"}, "bei_fehler": "e"}
    befunde = pruefe(_ablauf(_UPLOAD | {"weiter": "entwurf"}, _ENTWURF | {"weiter": "abgleich"},
                             abgleich))
    assert any("Typ" in b and "eigener" in b for b in befunde), befunde


def test_der_treiber_speichert_den_typ_der_tabelle(monkeypatch):
    """Befund 3."""
    import asyncio

    from boerdi.services.ablauf import treiber, werkzeuge

    async def entwurf(_args):
        return {"titel": "Physik", "knoten": []}

    monkeypatch.setitem(werkzeuge.DIENSTE, "strukturentwurf_aus_ordnern", entwurf)
    ablauf = _ablauf(_ENTWURF)

    async def teile(name):
        return {"struktur": {}} if name == "structure" else None

    aus = asyncio.run(treiber.starten(ablauf, treiber.Umgebung(teile=teile)))
    assert aus.neue_teile and aus.neue_teile[0][1] == typen.STRUKTUR


def test_ein_teil_den_nichts_schreibt_hat_keine_warnung_dazu():
    """Befund 4: kein „aus dem Gespräch“ neben „schreibt nichts“."""
    lesen = _ZAEHLEN | {"argumente": {"entwurf": {"$teil": "gibtsnicht"}}}
    assert not any("gibtsnicht" in w for w in warnungen(_ablauf(lesen)))


def test_ein_teil_nur_aus_dem_gespraech_wird_auch_auf_den_typ_geprueft():
    """Befund 5: ``structure`` ist ein Ordnerbaum, auch ohne Upload-Schritt im Ablauf."""
    lesen = _ZAEHLEN | {"argumente": {"entwurf": {"$teil": "structure"}}}
    assert any("Typ" in b for b in pruefe(_ablauf(lesen)))


def test_ein_unbekannter_schreiber_neben_einem_bekannten_hebt_den_vergleich_auf():
    """Befund 5: Weg A ein Text, Weg B die Ausgabe einer KI."""
    suchen = {"id": "suchen", "typ": "werkzeug", "werkzeug": "search_wlo_all",
              "argumente": {"query": "x"}, "schreibt": "xx", "weiter": "zaehlen"}
    ki = {"id": "ki", "typ": "agent", "agent": {"werkzeuge": ["search_wlo_all"], "ausgabe": "xx"},
          "weiter": "zaehlen"}
    frage = {"id": "frage", "typ": "nachricht", "text": {"de": "?"},
             "optionen": [{"id": "a", "label": {"de": "A"}, "ziel": "suchen"},
                          {"id": "b", "label": {"de": "B"}, "ziel": "ki"}]}
    lesen = _ZAEHLEN | {"argumente": {"entwurf": {"$teil": "xx"}}}
    assert not any("Typ" in b for b in pruefe(_ablauf(frage, suchen, ki, lesen)))


def test_der_modul_ausloeser_ist_eine_quelle_vor_dem_start():
    ablauf = AblaufArea.model_validate({"id": "d", "titel": {"de": "D"},
                                        "ausloeser": [{"art": "modul", "modul": "ui_upload"}],
                                        "schritte": [_UPLOAD | {"weiter": "entwurf"},
                                                     _ENTWURF | {"weiter": "e"},
                                                     {"id": "e", "typ": "ende"}]})
    assert not any("structure" in w for w in warnungen(ablauf))


def test_die_teil_auswahl_im_studio_kennt_die_ablage():
    from boerdi.api.config_choices import _vorgang_teile

    werte = [c.value if hasattr(c, "value") else c["value"] for c in _vorgang_teile()]
    assert {"ablage", "structure", "document", "draft"} <= set(werte)
