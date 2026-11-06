"""Paket K1b: der Treiber zeigt zu einem gestarteten Auftrag das Modul ``ui_fortschritt``.

Der Block trägt Ablauf, Text und ein Kürzel der Job-ID (nie die ID selbst) — das Modul fragt damit
``/api/ui/auftrag/stand`` und holt das Ergebnis per „Stand prüfen“ ab. Der Knopf bleibt daneben
(ohne Modul, ohne Bündel). Ein im Studio ausgeschaltetes Modul baut keinen Block.
"""

from __future__ import annotations

import asyncio
import hashlib

from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.i18n import bot_text
from boerdi.services.ablauf import auftrag_zug, treiber
from boerdi.services.auftraege import client
from boerdi.ui_module import katalog, schalter
from boerdi.ui_module.namen import FORTSCHRITT
from tests.test_ablauf_auftrag import (  # noqa: F401 — Fixtures
    _SCHRITTE,
    _pruefe,
    _roh,
    _starte,
    _umgebung,
    freigeschaltet,
    im_zug,
)

_KUERZEL = hashlib.sha256(b"job-1").hexdigest()[:12]


def test_das_kuerzel_verraet_die_job_id_nicht():
    assert client.kuerzel("job-1") == _KUERZEL
    assert "job" not in client.kuerzel("job-1") and len(client.kuerzel("x" * 200)) == 12


def test_das_manifest_ist_im_katalog_und_nicht_fuer_die_ki():
    manifest = katalog.katalog()[FORTSCHRITT]
    assert manifest["art"] == "anzeigen" and manifest["laden"] == "bei_bedarf"
    assert manifest["agent"] is False and manifest["faehigkeiten"] == ["auftrag"]


def test_der_start_zeigt_den_fortschritt():
    ablauf = AblaufArea.model_validate(_roh())
    umgebung, _ = _umgebung({"document": {"upload_id": "u1"}})
    aus = asyncio.run(treiber.starten(ablauf, umgebung))
    [block] = aus.bloecke
    assert block.modul == FORTSCHRITT and block.art == "anzeigen"
    assert block.daten == {"ablauf": "lesen", "kuerzel": _KUERZEL,
                           "text": "Ich lasse das Dokument lesen."}
    assert "job-1" not in str(block.model_dump())
    assert block.text == "Ich lasse das Dokument lesen."


def test_ohne_text_im_schritt_ein_vorgabetext():
    schritte = [{k: v for k, v in _SCHRITTE[0].items() if k != "text"}, *_SCHRITTE[1:]]
    ablauf = AblaufArea.model_validate(_roh(schritte=schritte))
    umgebung, _ = _umgebung({"document": {"upload_id": "u1"}})
    [block] = asyncio.run(treiber.starten(ablauf, umgebung)).bloecke
    assert block.daten["text"] == bot_text("de", "action.ablauf.auftragGestartet")


def test_ein_ausgeschaltetes_modul_baut_keinen_block(monkeypatch):
    monkeypatch.setattr(schalter, "aktiv", lambda name: name != FORTSCHRITT)
    ablauf = AblaufArea.model_validate(_roh())
    umgebung, gestartet = _umgebung({"document": {"upload_id": "u1"}})
    aus = asyncio.run(treiber.starten(ablauf, umgebung))
    assert aus.bloecke == [] and gestartet and aus.lauf["status"] == treiber.WARTET_AUFTRAG


def test_im_zug_block_und_knopf(im_zug):  # noqa: F811
    state: dict = {"entities": {}}
    antwort = _starte(state)
    [block] = antwort.ui.ui_bloecke
    assert block.modul == FORTSCHRITT and block.daten["kuerzel"] == _KUERZEL
    assert antwort.quick_replies[0].split("|")[2] == auftrag_zug.AKTION
    # Abgeholt: der Lauf geht weiter, kein neuer Fortschritt.
    im_zug.staende.append(client.Stand("fertig", {"markdown": "# T"}, []))
    weiter = _pruefe(state)
    assert weiter.ui is None or not weiter.ui.ui_bloecke


def test_befund_5_ein_langer_schritttext_kuerzt_statt_den_block_zu_verlieren():
    schritte = [{**_SCHRITTE[0], "text": {"de": "Lang " * 100}}, *_SCHRITTE[1:]]
    ablauf = AblaufArea.model_validate(_roh(schritte=schritte))
    umgebung, _ = _umgebung({"document": {"upload_id": "u1"}})
    [block] = asyncio.run(treiber.starten(ablauf, umgebung)).bloecke
    assert len(block.daten["text"]) <= 300 and block.daten["text"].startswith("Lang Lang")
