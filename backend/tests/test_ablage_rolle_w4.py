"""Paket W4-Anbindung (MCP-Stand 2026-11-08): die Rolle einer Datei im Stapel.

Das Modul ``ui_upload`` kennt je Datei die Rolle ``inhalt`` oder ``struktur``. Seit W4 nimmt
``wlo_prepare_file_batch`` sie je Eintrag an (``role``: ``content`` | ``structure``); sie ist Teil
der Freigabe und steht im Manifest. Der Chatbot

- reicht sie durch (Vorgabe ``inhalt`` → ``content``),
- merkt sie im Teil ``ablage`` des Vorgangs — so weiß ein späterer Schritt, welcher Knoten das
  Strukturdokument ist,
- nimmt dabei die Rolle aus der Vorschau des Servers (sie ist die Freigabe) und, wo ein älterer
  Server sie nicht zurückgibt, die erbetene,
- zeigt sie dem Modul mit der Vorschau.
"""

from __future__ import annotations

import asyncio

import pytest

from boerdi.services.ablage import mcp_ablage
from boerdi.services.ablage import vorgang_teil as vt
from tests.test_ablage_mcp import _ok, mcp  # noqa: F401 — Fixture
from tests.test_ui_ablage_api import (  # noqa: F401 — Fixtures
    _EINTRAEGE,
    _PLAN,
    _umgebung,
    _vorbereiten,
    client,
    lage,
)


def _plan_mit(*rollen):
    eintraege = [{**e, **({"role": r} if r else {})}
                 for e, r in zip(_PLAN["entries"], rollen, strict=True)]
    return {**_PLAN, "entries": eintraege}


def test_die_rolle_geht_an_den_server(mcp):  # noqa: F811
    mcp["antworten"]["wlo_prepare_file_batch"] = _ok({
        "batchToken": "tok-1234567890", "layout": "flat", "folderName": "X", "count": 2,
        "totalBytes": 2, "entries": [
            {"index": 0, "title": "Gliederung", "ext": "docx", "size": 1, "fileName": "g.docx",
             "role": "structure"},
            {"index": 1, "title": "Optik", "ext": "pdf", "size": 1, "fileName": "o.pdf",
             "role": "content"}]})
    asyncio.run(mcp_ablage.vorbereiten("X", [
        {"titel": "Gliederung", "sha256": "a" * 64, "groesse": 1, "art": "docx",
         "rolle": "struktur"},
        {"titel": "Optik", "sha256": "b" * 64, "groesse": 1, "art": "pdf"}]))
    [(_name, args)] = mcp["gerufen"]
    assert [e["role"] for e in args["entries"]] == ["structure", "content"]


def test_aus_plan_nimmt_die_rolle_der_vorschau():
    teil = vt.aus_plan(_plan_mit("structure", "content"), "tok-0123456789", "b1")
    assert [e["rolle"] for e in teil["inhalte"]] == ["struktur", "inhalt"]
    assert all(e["rolle_bestaetigt"] for e in teil["inhalte"])


def test_ohne_rolle_vom_server_gilt_die_erbetene():
    """Ein Server vor W4 gibt keine ``role`` zurück — dann die erbetene, sonst ``inhalt``."""
    teil = vt.aus_plan(_plan_mit(None, None), "tok-0123456789", "b1",
                       rollen=["struktur", "inhalt"])
    assert [e["rolle"] for e in teil["inhalte"]] == ["struktur", "inhalt"]
    # Review W4, Befund 5: nicht vom Server bestätigt — weder Fingerabdruck noch Manifest.
    assert not any(e["rolle_bestaetigt"] for e in teil["inhalte"])
    teil = vt.aus_plan(_plan_mit(None, None), "tok-0123456789", "b1")
    assert [e["rolle"] for e in teil["inhalte"]] == ["inhalt", "inhalt"]


@pytest.mark.parametrize("server", [("structure", "content"), (None, None)],
                         ids=["seit_w4", "vor_w4"])
def test_der_endpunkt_reicht_die_rolle_durch(client, lage, server):  # noqa: F811
    """Review W4, Befund 1/2: auch vor W4 (ohne ``role`` in der Vorschau) steht die erbetene Rolle
    im GESPEICHERTEN Teil, nicht nur in der Antwort."""
    lage.plan = _plan_mit(*server)
    eintraege = [{**_EINTRAEGE[0], "rolle": "struktur"}, _EINTRAEGE[1]]
    r = _vorbereiten(client, eintraege=eintraege)
    assert r.status_code == 200, r.text
    [(_art, _ordner, gesendet)] = [m for m in lage.mcp if m[0] == "vorbereiten"]
    assert [e["rolle"] for e in gesendet] == ["struktur", "inhalt"]
    assert [e["rolle"] for e in r.json()["eintraege"]] == ["struktur", "inhalt"]
    assert [e["rolle"] for e in lage.teil["inhalte"]] == ["struktur", "inhalt"]


@pytest.mark.parametrize("rolle", ["ignorieren", "structure", ""])
def test_eine_fremde_rolle_wird_abgewiesen(client, lage, rolle):  # noqa: F811
    eintraege = [{**_EINTRAEGE[0], "rolle": rolle}, _EINTRAEGE[1]]
    assert _vorbereiten(client, eintraege=eintraege).status_code == 422
    assert not [m for m in lage.mcp if m[0] == "vorbereiten"]


@pytest.mark.parametrize("eintraege", [
    [{**_EINTRAEGE[0], "rolle": "struktur"}, {**_EINTRAEGE[1], "rolle": "struktur"}],
    [{**_EINTRAEGE[0], "art": "png", "rolle": "struktur"}, _EINTRAEGE[1]],
], ids=["zwei", "bild"])
def test_hoechstens_ein_strukturdokument_einer_lesbaren_art(client, lage, eintraege):  # noqa: F811
    """Review W4, Befund 4: die Regel des Moduls gilt auch am öffentlichen Endpunkt."""
    assert _vorbereiten(client, eintraege=eintraege).status_code == 422
    assert not [m for m in lage.mcp if m[0] == "vorbereiten"]


def test_ein_ersetzter_stapel_behaelt_die_rolle_seiner_abgelegten():
    """Review W4, Befund 3."""
    vorher = vt.aus_plan(_plan_mit("structure", "content"), "tok-0123456789", "b1")
    vorher["inhalte"][0].update(stand="stored", node_id="n-struktur")
    neu = vt.aus_plan(_plan_mit(None, None), "tok-9876543210", "b2", vorher)
    assert neu["frueher"] == [{"titel": "Mechanik", "node_id": "n-struktur", "rolle": "struktur"}]
    nachher = vt.mit_frueher(neu, vorher["inhalte"][0], {"status": "stored", "nodeId": "n-2"})
    assert nachher["frueher"][-1]["rolle"] == "struktur"

