"""Paket U3-1b: „Als Themenbaum-Entwurf übernehmen“ in ``ui_upload`` — der Entwurf aus der
Ordnerstruktur erscheint im selben Zug, ohne LLM, als offene Frage (wie die Brücke aus dem
Bestand)."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from boerdi.api.schemas import ChatRequest, Environment
from boerdi.domain.ui_bloecke import DEBUG_KEY
from boerdi.services import ordner_aktion as aktion
from boerdi.ui_module import schalter
from boerdi.ui_module import strukturentwurf_merken as entwurf_merken
from boerdi.ui_module.antwort import OFFENE_FRAGE
from boerdi.ui_module.namen import STRUKTURENTWURF, UPLOAD
from tests.test_preflight_node import _SESSION


class _Spion:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def __call__(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append({"args": args, **kwargs})


@pytest.fixture
def db(monkeypatch):
    save, update = _Spion(), _Spion()
    monkeypatch.setattr(aktion, "save_message", save)
    monkeypatch.setattr(aktion, "update_session", update)
    return save, update


def _geprueft(aktion_name: str = "ordner_als_entwurf", kinder: list | None = None) -> dict:
    standard = [
        {"name": "01_Mechanik", "dateien": 1, "alle_dateien": 1, "kinder": []},
        {"name": "02_Optik", "dateien": 1, "alle_dateien": 1, "kinder": []}]
    struktur = {"name": "Physik 7", "dateien": 0, "alle_dateien": 2,
                "kinder": kinder if kinder is not None else standard}
    return {"block_id": "b0000001", "modul": UPLOAD, "frage": "Ordner erfassen", "labels": [],
            "daten": {"aktion": aktion_name, "struktur": struktur}}


def _req(module=(STRUKTURENTWURF, UPLOAD), locale: str = "de") -> ChatRequest:
    return ChatRequest(session_id="bb-1", message="Ordnerstruktur übernehmen",
                       environment=Environment(ui_module=list(module), locale=locale))


def _laufen(geprueft: dict, req: ChatRequest | None = None, state: dict | None = None):
    state = {"entities": {entwurf_merken.KEY: {"titel": "alt"}}} if state is None else state
    resp = asyncio.run(aktion.handle_folders_as_draft(_SESSION, req or _req(), state, geprueft))
    return resp, state


def test_nur_die_uebernahme_aus_ui_upload_ist_gemeint():
    assert aktion.ist_ordner_als_entwurf(_geprueft()) is True
    assert aktion.ist_ordner_als_entwurf(_geprueft("erfasst")) is False
    assert aktion.ist_ordner_als_entwurf(None) is False
    assert aktion.ist_ordner_als_entwurf({**_geprueft(), "modul": STRUKTURENTWURF}) is False


def test_der_entwurf_aus_ordnern_steht_als_offene_frage_ohne_llm(db):
    resp, state = _laufen(_geprueft())
    [block] = resp.ui.ui_bloecke
    assert block.modul == STRUKTURENTWURF and block.status == "offen"
    assert block.daten["quelle"] == "ordner"
    assert [k["titel"] for k in block.daten["knoten"]] == ["Mechanik", "Optik"]
    assert state["entities"][OFFENE_FRAGE]["block_id"] == block.block_id
    # Querschnitts-Review 2026-11-06 (Q4): der Entwurf aus den Ordnern ersetzt den gemerkten — ein
    # Folgezug mit ``vorlage`` griffe sonst auf einen alten ``draft`` im Vorgang zurück. Die
    # Ordnernamen gingen durch die Sicherheitsprüfung des Zugs (``sicherheits_text``).
    gemerkt = entwurf_merken.vorlage(state["entities"])
    assert gemerkt["titel"] == "Physik 7" and gemerkt["quelle"] == "ordner"
    save, update = db
    assert update.calls and save.calls[0]["args"][2] == "assistant"
    assert DEBUG_KEY in save.calls[0]["debug"]
    assert "Physik 7" in resp.content and "Mechanik" not in resp.content
    assert resp.debug.tools_called == [STRUKTURENTWURF]


def test_ohne_unterordner_eine_ehrliche_antwort(db):
    resp, _ = _laufen(_geprueft(kinder=[]))
    assert resp.ui is None or not resp.ui.ui_bloecke
    assert "Unterordner" in resp.content


def test_ohne_gemeldeten_oder_aktiven_entwurf_kein_block(db, monkeypatch):
    resp, _ = _laufen(_geprueft(), req=_req(module=(UPLOAD,)))
    assert resp.ui is None or not resp.ui.ui_bloecke
    monkeypatch.setattr(schalter, "aktiv", lambda name: name != STRUKTURENTWURF)
    resp, _ = _laufen(_geprueft())
    assert resp.ui is None or not resp.ui.ui_bloecke


def test_auf_englisch(db):
    resp, _ = _laufen(_geprueft(), req=_req(locale="en"))
    assert "draft" in resp.content.lower()
