"""Plan 2026-11-19, Paket C (C3): das Upload-Feld erfährt vom Server, ob „Hier im Chat“ gescannte
Seiten per Texterkennung liest — ``orte.chat.texterkennung`` (wie die Grenzen ``lokal_*``). Die
Oberfläche sagt dann vor dem Hochladen „Gescannte Seiten gehen als Bild an das KI-Modell“."""

from __future__ import annotations

from boerdi.domain.config_models.upload import UploadSettings
from boerdi.ui_module import katalog, upload_orte
from boerdi.ui_module.namen import UPLOAD
from tests.test_paket_u4_orte import lage  # noqa: F401 — Fixture


def test_mit_texterkennung_traegt_der_ort_chat_die_angabe(lage):  # noqa: F811
    lage["ocr"] = True
    o = upload_orte.orte()
    assert o["chat"] == {"geht": True, "ueber_grenze": "ueber_grenze", "texterkennung": True}


def test_ohne_texterkennung_fehlt_die_angabe(lage):  # noqa: F811
    assert "texterkennung" not in upload_orte.orte()["chat"]


def test_gesperrter_ort_nennt_keine_texterkennung(lage):  # noqa: F811
    lage["ocr"] = True
    lage["cfg"] = UploadSettings(dokument_im_chat=False)
    assert upload_orte.orte()["chat"] == {"geht": False, "grund": "aus"}


def test_die_texterkennung_folgt_ocr_aktiv(monkeypatch):
    from boerdi.services.dokumente import ocr

    gesehen = []
    monkeypatch.setattr(ocr, "aktiv", lambda cfg=None: gesehen.append(cfg) or True)
    cfg = UploadSettings()
    assert upload_orte._texterkennung(cfg) is True and gesehen == [cfg]


def test_das_manifest_kennt_die_angabe():
    manifest = katalog.katalog()[UPLOAD]
    chat = manifest["eingabe"]["properties"]["orte"]["properties"]["chat"]
    assert chat["properties"]["texterkennung"]["type"] == "boolean"
