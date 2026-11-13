"""Paket R2-b (Plan 2026-11-12): die Voraussetzung ``dokument_lesen``.

Ein Ablauf, der ein Dokument liest (etwa „aus einem Dokument“), braucht das Studio-Recht „Dokument
im Chat“ für diese Person (``01-base/upload-config``: ``dokument_im_chat``, ohne Anmeldung nur mit
``dokument_ohne_anmeldung``). Fehlt es, startet er nicht, und die Person erfährt WARUM:
- fehlt nur die Anmeldung → derselbe Satz wie bei ``anmeldung`` (auch der Hinweis darunter);
- ist Lesen ganz aus → ein eigener Satz, nie „melde dich an“.
"""

from __future__ import annotations

import asyncio
import pathlib

import pytest
import yaml

from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.domain.config_models.upload import UploadSettings
from boerdi.i18n import bot_text
from boerdi.services.ablauf import ausloeser, zug
from boerdi.services.ablauf.pruefung import pruefe
from tests.test_ablauf_zug import _S, _katalog, _req, umgebung  # noqa: F401


def _ablauf(**mehr) -> AblaufArea:
    return AblaufArea.model_validate({
        "id": "lesen", "titel": {"de": "Lesen"}, "aktiv": True, "ausloeser": [{"art": "knopf"}],
        "voraussetzungen": ["dokument_lesen"],
        "schritte": [{"id": "ende", "typ": "ende", "text": {"de": "Fertig."}}], **mehr})


@pytest.fixture
def schalter(monkeypatch):
    stand = {"cfg": UploadSettings(), "person": False}
    monkeypatch.setattr(ausloeser, "load_upload_config", lambda: stand["cfg"])
    monkeypatch.setattr(ausloeser, "has_personal_auth", lambda: stand["person"])
    return stand


@pytest.mark.parametrize(("im_chat", "ohne_anmeldung", "person", "fehlt"), [
    (True, True, False, None),
    (True, False, True, None),
    (True, False, False, "anmeldung"),
    (False, True, True, "dokument_lesen"),
    (False, True, False, "dokument_lesen"),
])
def test_was_fehlt(schalter, im_chat, ohne_anmeldung, person, fehlt):
    schalter["cfg"] = UploadSettings(dokument_im_chat=im_chat,
                                     dokument_ohne_anmeldung=ohne_anmeldung)
    schalter["person"] = person
    assert ausloeser.fehlt(_ablauf()) == fehlt
    assert ausloeser.erfuellt(_ablauf()) is (fehlt is None)


def test_die_pruefung_kennt_die_voraussetzung():
    assert not any("Voraussetzung" in b for b in pruefe(_ablauf()))


def test_ist_lesen_aus_sagt_der_start_es_ohne_anmeldesatz(umgebung, schalter):  # noqa: F811
    schalter["cfg"] = UploadSettings(dokument_im_chat=False)
    umgebung.katalog["wert"] = _katalog(voraussetzungen=["dokument_lesen"])
    ablauf = ausloeser.laden("sammlungsstruktur")
    antwort = asyncio.run(zug.starten_mit(_S(), _req(), {"entities": {}}, ablauf))
    assert antwort.content == bot_text("de", "action.ablauf.dokumentLesenAus")
    assert umgebung.speicher.v == {}


def test_fehlt_nur_die_anmeldung_bleibt_es_beim_anmeldesatz(umgebung, schalter):  # noqa: F811
    schalter["cfg"] = UploadSettings(dokument_ohne_anmeldung=False)
    umgebung.katalog["wert"] = _katalog(voraussetzungen=["dokument_lesen"])
    ablauf = ausloeser.laden("sammlungsstruktur")
    antwort = asyncio.run(zug.starten_mit(_S(), _req(), {"entities": {}}, ablauf))
    assert antwort.content == bot_text("de", "action.ablauf.anmeldung")


def test_der_hinweis_unter_der_antwort_nur_wenn_die_anmeldung_hilft(umgebung, schalter):  # noqa: F811
    umgebung.katalog["wert"] = _katalog(voraussetzungen=["dokument_lesen"])
    schalter["cfg"] = UploadSettings(dokument_im_chat=False)
    assert zug.anmelde_satz("Themenbaum aus meinem Ordner", "de") is None
    assert zug.anmelde_zeile("Themenbaum aus meinem Ordner", "de") is None
    schalter["cfg"] = UploadSettings(dokument_ohne_anmeldung=False)
    assert zug.anmelde_satz("Themenbaum aus meinem Ordner", "de") is not None


def test_das_seitenangebot_nur_wenn_jeder_lesen_darf(monkeypatch, schalter):
    ablauf = _ablauf(ausloeser=[{"art": "seite", "muster": ["/x"]}])
    monkeypatch.setattr(ausloeser, "_aktive", lambda art: [(ablauf, ablauf.ausloeser[0])])
    assert [a["id"] for a in ausloeser.seiten_angebote()] == ["lesen"]
    schalter["cfg"] = UploadSettings(dokument_ohne_anmeldung=False)
    assert ausloeser.seiten_angebote() == []


def test_der_dokument_ablauf_braucht_das_lesen():
    pfad = (pathlib.Path(__file__).parents[1] / "seeds" / "06-ablaeufe"
            / "themenbaum_aus_dokument.yaml")
    ablauf = AblaufArea.model_validate(yaml.safe_load(pfad.read_text(encoding="utf-8")))
    assert "dokument_lesen" in ablauf.voraussetzungen
