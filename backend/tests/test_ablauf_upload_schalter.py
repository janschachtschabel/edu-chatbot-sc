"""Rückmeldung 2026-11-15: Im Ablauf „Themenbaum · aus einem Dokument“ ließ sich das Dokument nicht
lesen („Lesen lassen kann der Chat es hier nicht“), mit und ohne Anmeldung.

Ursache: Der Modul-Schritt baute den Block aus den Daten des Ablaufs, sobald sie den Vertrag des
Moduls erfüllten — ``zweck`` genügt dafür. Den Dienst, der ``schalter`` und ``grenzen`` einsetzt
(Felder ``x-nur-system``), erreichte er so nie, und ohne Schalter gilt im Widget „nicht erlaubt“.
"""

from __future__ import annotations

import asyncio

from boerdi.services.ablauf.treiber_bloecke import modul_block
from boerdi.ui_module.namen import UPLOAD

#: Die Daten des Schritts ``hochladen`` aus ``seeds/06-ablaeufe/themenbaum_aus_dokument.yaml``.
_SCHRITT = {"zweck": "sammlungsstruktur", "einzeldatei_als_struktur": True}


def test_der_upload_schritt_eines_ablaufs_traegt_die_schalter_des_systems(monkeypatch):
    from boerdi.ui_module import dienst_upload

    monkeypatch.setattr(dienst_upload, "dokument_erlaubt", lambda: True)
    block = asyncio.run(modul_block(UPLOAD, dict(_SCHRITT)))
    assert block is not None
    daten = block.daten
    assert daten["schalter"]["dokument_im_chat"] is True
    assert daten["grenzen"]["max_mb_datei"] == 50
    # Was der Ablauf mitgibt, bleibt erhalten (der Dienst nimmt es nur aus einem Ablauf an)
    assert daten["zweck"] == "sammlungsstruktur"
    assert daten["einzeldatei_als_struktur"] is True


def test_systemfelder_aus_dem_ablauf_gelten_nicht(monkeypatch):
    # Ein Ablauf (im Studio bearbeitbar) darf Lesen nicht selbst erlauben: die Schalter setzt
    # allein der Dienst, nach Studio und Anmeldung.
    from boerdi.ui_module import dienst_upload

    daten = {**_SCHRITT, "schalter": {"dokument_im_chat": True, "ablage_in_wlo": True}}
    monkeypatch.setattr(dienst_upload, "dokument_erlaubt", lambda: False)
    block = asyncio.run(modul_block(UPLOAD, daten))
    assert block is not None
    assert block.daten["schalter"]["dokument_im_chat"] is False
    assert block.daten["schalter"]["ablage_in_wlo"] is False


def test_in_der_simulation_bleibt_es_beim_platzhalter():
    block = asyncio.run(modul_block(UPLOAD, dict(_SCHRITT), simulation=True))
    assert block is not None
    assert "schalter" not in block.daten


def test_die_pruefung_meldet_fremde_felder_und_fehlende_pflicht_am_upload_schritt():
    # Review 2026-11-15, NIT 3: der Treiber reicht nur die Parameter des Dienstes weiter — ein
    # Tippfehler („hinwies“) oder ein Systemfeld fiele sonst still weg.
    from boerdi.domain.config_models.ablauf import AblaufArea
    from boerdi.services.ablauf.pruefung import pruefe

    def befunde(daten):
        return pruefe(AblaufArea.model_validate({
            "id": "probe", "titel": {"de": "Probe"}, "beschreibung": "Upload-Schritt prüfen.",
            "ausloeser": [{"art": "knopf"}],
            "schritte": [{"id": "u", "typ": "modul", "modul": UPLOAD, "daten": daten},
                         {"id": "e", "typ": "ende", "text": {"de": "Fertig."}}]}))

    assert befunde(dict(_SCHRITT)) == []
    assert any("hinwies" in b for b in befunde({**_SCHRITT, "hinwies": "x"}))
    assert any("schalter" in b for b in befunde({**_SCHRITT, "schalter": {}}))
    assert any("zweck" in b for b in befunde({"einzeldatei_als_struktur": True}))
