"""Review Paket U (19.11.), MAJOR 3 und MINOR 5 — die Orte des Upload-Felds und die Sitzung.

- MAJOR 3: „Hier im Chat“ wird nicht angeboten, wenn die Sitzung voll ist (``chat.geht: false``,
  Grund ``grenze_sitzung``); ein Rest steht in ``grenzen.lokal_frei_dateien``/``lokal_frei_mb``.
  Gezählt werden nur nicht abgelaufene Uploads der Sitzung (``Umgebung.belegung``); nichts wird
  gelöscht.
- MINOR 5: ``ueber_grenze_anmelden`` erst nach der Einschränkung durch den Ablauf und nur, wenn
  ``wlo`` erlaubt ist und der Metadaten-Flow startbar ist.
- Abstimmung mit der Oberfläche: ``schalter.dokument_ohne_anmeldung``.
"""

from __future__ import annotations

import asyncio

import pytest

from boerdi.domain.config_models.upload import UploadSettings
from boerdi.ui_module import dienst, dienst_upload, katalog, upload_orte
from boerdi.ui_module.aufruf import Umgebung
from boerdi.ui_module.namen import UPLOAD
from tests.test_paket_u4_orte import lage  # noqa: F401 — Fixture

_MIB = 1024 * 1024
#: Vor der Fixture gemerkt — die Fixture ``lage`` ersetzt die Funktion je Test.
_FLOW_NACH_ANMELDUNG = upload_orte._flow_nach_anmeldung


def _belegung(anzahl: int, bytes_: int):
    async def lader() -> tuple[int, int]:
        return anzahl, bytes_
    return lader


def _daten(umgebung: Umgebung, args: dict | None = None) -> dict:
    erg = asyncio.run(dienst.aufruf(katalog.katalog()[UPLOAD],
                                    {"zweck": "bereitstellen", **(args or {})}, umgebung))
    assert erg.block is not None, erg.text           # das Schema nimmt die Daten
    return erg.block.daten


# ── MAJOR 3: Sitzung voll ───────────────────────────────────────────────────────────────────────

def test_volle_sitzung_sperrt_hier_im_chat_mit_eigenem_grund(lage):  # noqa: F811
    o = upload_orte.orte(voll=True)
    assert o["chat"] == {"geht": False, "grund": "grenze_sitzung"}
    assert o["vorauswahl"] == "wlo"
    lage["person"] = False
    o = upload_orte.orte(voll=True)
    assert o["chat"] == {"geht": False, "grund": "grenze_sitzung"}
    assert o["vorauswahl"] == "namen"


def test_studio_aus_geht_vor_der_vollen_sitzung(lage):  # noqa: F811
    lage["cfg"] = UploadSettings(dokument_im_chat=False)
    assert upload_orte.orte(voll=True)["chat"] == {"geht": False, "grund": "aus"}


def test_der_dienst_nennt_den_rest_der_sitzung(lage):  # noqa: F811
    d = _daten(Umgebung(belegung=_belegung(7, 20 * _MIB + _MIB // 2)))
    assert d["grenzen"]["lokal_frei_dateien"] == 3
    assert d["grenzen"]["lokal_frei_mb"] == 29.5
    assert d["orte"]["chat"]["geht"] is True


@pytest.mark.parametrize(("anzahl", "bytes_"), [(10, 0), (12, 0), (1, 50 * _MIB),
                                                 (1, 50 * _MIB - 10)])
def test_der_dienst_sperrt_bei_voller_sitzung(lage, anzahl, bytes_):  # noqa: F811
    d = _daten(Umgebung(belegung=_belegung(anzahl, bytes_)))
    assert d["orte"]["chat"] == {"geht": False, "grund": "grenze_sitzung"}
    assert d["grenzen"]["lokal_frei_dateien"] >= 0 and d["grenzen"]["lokal_frei_mb"] >= 0


def test_ohne_belegung_keine_restwerte(lage):  # noqa: F811
    """Ohne Zählung (Studio-Vorschau, älterer Aufrufer) gilt nur die ganze Grenze."""
    d = _daten(Umgebung())
    assert "lokal_frei_dateien" not in d["grenzen"] and "lokal_frei_mb" not in d["grenzen"]
    assert d["orte"]["chat"]["geht"] is True


def test_eine_fehlerhafte_zaehlung_sperrt_nicht(lage):  # noqa: F811
    async def kaputt():
        raise RuntimeError("db weg")

    d = _daten(Umgebung(belegung=kaputt))
    assert d["orte"]["chat"]["geht"] is True and "lokal_frei_dateien" not in d["grenzen"]


def test_der_ablauf_reicht_die_belegung_an_das_modul(monkeypatch):
    """Der Weg aus einem Ablauf (``treiber_bloecke.modul_block``) zählt wie der freie Chat."""
    from boerdi.services.ablauf import treiber_bloecke
    from boerdi.ui_module import aufruf

    gesehen: list = []

    async def asynchron(name, args, umgebung):
        gesehen.append(umgebung)
        return type("E", (), {"block": None})()

    monkeypatch.setattr(aufruf, "asynchron", asynchron)
    lader = _belegung(1, 1)
    asyncio.run(treiber_bloecke.modul_block(UPLOAD, {"zweck": "bereitstellen"}, belegung=lader))
    assert gesehen and gesehen[0].belegung is lader and gesehen[0].aus_ablauf is True


# ── MINOR 5: ueber_grenze_anmelden ──────────────────────────────────────────────────────────────

def test_anmelden_hilft_nur_wenn_der_ablauf_wlo_erlaubt(lage):  # noqa: F811
    lage["person"] = False
    assert upload_orte.orte()["chat"]["ueber_grenze"] == "ueber_grenze_anmelden"
    assert upload_orte.orte(erlaubt=["chat", "namen"])["chat"]["ueber_grenze"] == "ueber_grenze"


def test_anmelden_hilft_nur_mit_flow(lage):  # noqa: F811
    lage["person"], lage["flow"] = False, False
    assert upload_orte.orte()["chat"]["ueber_grenze"] == "ueber_grenze"


def test_ohne_anmeldung_zaehlt_der_flow_nach_der_anmeldung(lage, monkeypatch):  # noqa: F811
    # Durchtest U8 (19.11.): ohne Anmeldung gibt es keinen Starter (``starter()`` → None), der
    # Flow wäre nach der Anmeldung aber da — dann hilft die Anmeldung
    from boerdi.services.auftraege import mcp_starter

    lage["person"], lage["flow"] = False, False      # ``_flow_da`` (für diesen Zug) ist falsch
    monkeypatch.setattr(upload_orte, "_flow_nach_anmeldung", _FLOW_NACH_ANMELDUNG)  # die echte
    monkeypatch.setattr(mcp_starter, "verfuegbar", lambda: True)
    monkeypatch.setattr(mcp_starter, "flow_erlaubt", lambda flow: True)
    assert upload_orte.orte()["chat"]["ueber_grenze"] == "ueber_grenze_anmelden"
    monkeypatch.setattr(mcp_starter, "verfuegbar", lambda: False)
    assert upload_orte.orte()["chat"]["ueber_grenze"] == "ueber_grenze"


# ── Abstimmung Oberfläche: dokument_ohne_anmeldung ──────────────────────────────────────────────

@pytest.mark.parametrize("an", [True, False])
def test_schalter_nennt_dokument_ohne_anmeldung(monkeypatch, an):
    monkeypatch.setattr(dienst_upload, "load_upload_config",
                        lambda: UploadSettings(dokument_ohne_anmeldung=an))
    monkeypatch.setattr(dienst_upload, "has_personal_auth", lambda: True)
    assert dienst_upload.schalter()["dokument_ohne_anmeldung"] is an


def test_das_schema_kennt_die_neuen_felder():
    eingabe = katalog.katalog()[UPLOAD]["eingabe"]["properties"]
    assert "dokument_ohne_anmeldung" in eingabe["schalter"]["properties"]
    assert {"lokal_frei_dateien", "lokal_frei_mb"} <= set(eingabe["grenzen"]["properties"])
    assert "grenze_sitzung" in eingabe["orte"]["properties"]["chat"]["properties"]["grund"]["enum"]
