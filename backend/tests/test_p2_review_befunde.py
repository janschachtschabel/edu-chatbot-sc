"""Plan 2026-11-20 (Upload-Ort und Erschließung), Review P2 — die Befunde im Backend.

- **Befund 1 (MAJOR):** das Häkchen „Metadaten von WLO erzeugen lassen“ gibt es nur, wenn der
  Ablauf-Schritt ``erschliessen`` ausdrücklich setzt (er hat danach einen Schritt, der die
  Erschließung nutzt — P3, ``zustimmung: upload``). Ohne die Angabe (freier Chat, Schritt ohne
  sie) steht ``erschliessen`` nicht in den Block-Daten: kein Häkchen, nur ablegen. Die KI erfährt
  in der Quittung und im Rahmen der Ablage, ob erschlossen wird — sie bietet oder behauptet nie
  Metadaten gegen die Wahl.
- **Befund 3:** ohne Metadaten-Flow nennt der Ort WLO den Grund als Code
  (``grund_erschliessung``).
- **Befund 5/6 (NIT):** die Zählungen „Inhalte“ zählen Material (``inhalt`` und ``beides``),
  keine reinen Gliederungen.
"""

from __future__ import annotations

import asyncio

import pytest

from boerdi.services.ablauf import auftrag_zug, metadaten, zug_basis
from boerdi.services.arbeitsstand_teile import teile_aus_antwort
from boerdi.ui_module import dienst, dienst_upload, katalog, upload_orte, upload_rahmen
from boerdi.ui_module.aufruf import Umgebung
from boerdi.ui_module.namen import UPLOAD
from tests.test_paket_u4_orte import (
    ABLAGE,
    bereitgestellt,
    lage,  # noqa: F401 — Fixture (Studio, Anmeldung, Träger)
)


def _aufruf(args: dict, *, ablauf: bool):
    erg = asyncio.run(dienst.aufruf(katalog.katalog()[UPLOAD], {"zweck": "bereitstellen", **args},
                                    Umgebung(aus_ablauf=ablauf)))
    assert erg.block is not None, erg.text
    return erg


# ── Befund 1: das Häkchen nur, wenn der Schritt es vorsieht ──────────────────────────────────────

def test_freier_chat_hat_kein_haekchen(lage):  # noqa: F811
    assert "erschliessen" not in _aufruf({}, ablauf=False).block.daten
    # die KI kann es nicht einschalten
    assert "erschliessen" not in _aufruf({"erschliessen": True}, ablauf=False).block.daten


def test_ein_schritt_ohne_angabe_hat_kein_haekchen(lage):  # noqa: F811
    assert "erschliessen" not in _aufruf({}, ablauf=True).block.daten


@pytest.mark.parametrize("wert", [True, False])
def test_ein_schritt_mit_angabe_gibt_die_vorgabe_weiter(lage, wert):  # noqa: F811
    assert _aufruf({"erschliessen": wert}, ablauf=True).block.daten["erschliessen"] is wert


@pytest.fixture
def ablage_an(monkeypatch):
    monkeypatch.setattr(dienst_upload, "schalter", lambda: {"ablage_in_wlo": True,
                                                            "dokument_im_chat": True})
    monkeypatch.setattr(zug_basis, "wlo_erschliessen", lambda: True)


def test_quittung_ohne_haekchen_verspricht_keine_metadaten(lage, ablage_an):  # noqa: F811
    for text in (_aufruf({}, ablauf=False).text, _aufruf({}, ablauf=True).text):
        assert "nur ablegen" in text
        assert "Metadaten erzeugt WLO dabei nicht" in text
        assert "Häkchen" not in text


def test_quittung_mit_haekchen_nennt_es(lage, ablage_an):  # noqa: F811
    text = _aufruf({"erschliessen": True}, ablauf=True).text
    assert "Häkchen „Metadaten von WLO erzeugen lassen“" in text
    assert "nur ablegen" not in text


def _rahmen(**ablage) -> str:
    daten = bereitgestellt("wlo", dateien=[{"i": 0, "rolle": "inhalt"}],
                           ablage={**ABLAGE, **ablage})
    kopf, zeilen = upload_rahmen.zeilen({"daten": daten})
    return "\n".join([kopf, *zeilen])


def test_das_schema_nimmt_die_wahl_in_der_ablage():
    for wert in (True, False):
        daten = bereitgestellt("wlo", dateien=[{"i": 0, "rolle": "inhalt"}, {"i": 1,
                               "rolle": "inhalt"}, {"i": 2, "rolle": "struktur"}],
                               ablage={**ABLAGE, "erschliessen": wert})
        assert katalog.antwort_fehler(katalog.katalog()[UPLOAD], daten) == []


def test_der_rahmen_sagt_der_ki_ob_erschlossen_wird():
    mit = _rahmen(erschliessen=True)
    assert "„Metadaten von WLO erzeugen lassen“ gewählt" in mit
    assert "sag nicht, sie seien schon da" in mit
    ohne = _rahmen(erschliessen=False)
    assert "Nur abgelegt: Metadaten erzeugt WLO für diese Dateien nicht" in ohne
    assert "biete sie nicht an" in ohne
    # ältere Widgets schicken nichts — dann sagt der Rahmen nichts dazu
    alt = _rahmen()
    assert "Metadaten" not in alt


# ── Befund 3: der Grund, wenn WLO keine Metadaten erzeugen kann ──────────────────────────────────

@pytest.mark.parametrize(("traeger", "grund"), [
    ((auftrag_zug.MCP, ""), "flow_nicht_freigegeben"),
    ((None, "ohne_mcp"), "dienst_nicht_erreichbar"),
    ((None, auftrag_zug.MCP_KURZ_WEG), "dienst_nicht_erreichbar"),
])
def test_ohne_flow_nennt_der_ort_den_grund(monkeypatch, traeger, grund):
    monkeypatch.setattr(auftrag_zug, "traeger", lambda **_: traeger)
    assert upload_orte._ohne_flow_grund() == grund


def test_der_grund_steht_im_ort_und_passt_zum_schema(lage):  # noqa: F811
    lage["flow"] = False
    wlo = _aufruf({}, ablauf=True).block.daten["orte"]["wlo"]
    assert wlo == {"geht": True, "hinweis": "ohne_erschliessung",
                   "grund_erschliessung": "dienst_nicht_erreichbar"}


# ── Befund 5/6: „Inhalte“ zählt Material ─────────────────────────────────────────────────────────

_ID = "{}1111111-1111-4111-8111-111111111111"


def test_der_titel_der_metadaten_zaehlt_nur_material():
    inhalte = [{"node_id": _ID.format(n), "rolle": r} for n, r in
               enumerate(("struktur", "inhalt", "beides"))]
    assert metadaten._teil(inhalte, [])["titel"] == "Metadaten zu 2 Inhalten"


def test_die_kurzbeschreibung_der_struktur_zaehlt_material():
    daten = bereitgestellt("namen")         # inhalt, inhalt (nicht lesbar), struktur
    daten["struktur"]["dateiliste"][2]["rolle"] = "beides"
    daten["zahlen"]["inhalte"] = 2           # beides zählt in ``zahlen`` bei den Strukturdokumenten
    teile = teile_aus_antwort({"modul": UPLOAD, "block_id": "b1", "daten": daten})
    kurz = next(t[3] for t in teile if t[0] == "structure")
    assert kurz == "1 Ordner, 3 Inhalte"
