"""Paket K5 (Plan 2026-11-17, E14): Strukturdokumente gehen durch den Metadaten-Flow.

- Der Schritt ``metadaten`` des Ablaufs „Themenbaum erstellen“ gibt dem Flow die abgelegten
  Einträge der Ablage mit Rolle ``inhalt`` **und** ``struktur`` (hebt MINOR 7 auf).
- Die Rückfrage davor sagt, dass auch Strukturdokumente Angaben bekommen.
- Die Vorbelegung nimmt Fach, Bildungsstufe und Thema auch aus den Metadaten der
  Strukturdokumente (erkannt über ``ablage`` → Rolle). Vorrang wie bisher: ein Argument der KI vor
  den Antworten der Person vor den Daten.
- Fehlt der Volltext eines Strukturdokuments aus WLO noch, sagt das Werkzeug der KI, dass er gerade
  entsteht und der Ablauf an diesem Schritt wartet.
"""

from __future__ import annotations

import asyncio
import pathlib

import yaml

from boerdi.domain.config_models.ablauf import AblaufArea, Schritt
from boerdi.services.ablauf import vorbelegung as vb
from boerdi.services.teil_verweise import aufloesen
from boerdi.ui_module import dienst

_SEED = AblaufArea.model_validate(yaml.safe_load(
    (pathlib.Path(__file__).parents[1] / "seeds" / "06-ablaeufe" / "themenbaum.yaml")
    .read_text(encoding="utf-8")))

_INHALT = "11111111-1111-4111-8111-111111111111"
_STRUKTUR = "22222222-2222-4222-8222-222222222222"
_STRUKTUR_2 = "33333333-3333-4333-8333-333333333333"

_ABLAGE = {"format": "wlo.ablage@1", "block_id": "b1", "inhalte": [
    {"index": 0, "i": 0, "titel": "Linsen.pdf", "stand": "stored", "node_id": _INHALT,
     "rolle": "inhalt"},
    {"index": 1, "i": 1, "titel": "Lehrplan.pdf", "stand": "stored", "node_id": _STRUKTUR,
     "rolle": "struktur"},
    {"index": 2, "i": 2, "titel": "Kaputt.pdf", "stand": "failed", "rolle": "struktur"},
    {"index": 3, "i": 3, "titel": "Offen.pdf", "stand": "offen", "rolle": "inhalt"}]}


def _metadaten(*eintraege: dict) -> dict:
    return {"format": "wlo.metadaten@1", "titel": "Metadaten", "fehlend": [],
            "inhalte": list(eintraege)}


def _eintrag(node_id: str, rolle: str, **felder) -> dict:
    return {"node_id": node_id, "i": 0, "rolle": rolle, "titel": felder.pop("titel", "T"),
            "beschreibung": "", "schlagworte": [], "faecher": [], "stufen": [], "arten": [],
            "lizenz": "", **felder}


_LEHRPLAN = _eintrag(_STRUKTUR, "struktur", titel="Rahmenlehrplan Physik",
                     faecher=["Physik"], stufen=["Sekundarstufe I"])
_MATERIAL = _eintrag(_INHALT, "inhalt", titel="Linsen", faecher=["Chemie"],
                     stufen=["Primarstufe"])


def _schritt() -> Schritt:
    return Schritt.model_validate({"id": "entwurf", "typ": "agent", "agent": {
        "werkzeuge": ["ui_strukturentwurf"], "ausgabe": "draft", "vorbelegen": True}})


def _belegt(teile: dict, lauf: tuple[str, ...] = ()) -> dict:
    async def lader(name):
        return teile.get(name)

    return asyncio.run(vb.vorbelegung(_schritt(), lader, lauf, ablauf=_SEED))


# ── Seed ─────────────────────────────────────────────────────────────────────────────────────────

def test_der_flow_bekommt_inhalte_und_strukturdokumente():
    auftrag = next(s for s in _SEED.schritte if s.id == "metadaten")
    node_ids = auftrag.argumente["node_ids"]
    assert aufloesen(_ABLAGE, node_ids) == [_INHALT, _STRUKTUR]


def test_die_rueckfrage_nennt_die_strukturdokumente():
    frage = next(s for s in _SEED.schritte if s.id == "metadaten_frage")
    assert "Strukturdokument" in frage.text["de"]
    assert "structure document" in frage.text["en"]


# ── Vorbelegung aus den Strukturdokumenten ───────────────────────────────────────────────────────

def test_fach_stufe_und_thema_aus_dem_strukturdokument():
    belegt = _belegt({"ablage": _ABLAGE, "metadaten": _metadaten(_MATERIAL, _LEHRPLAN)})
    assert belegt["fach"] == "Physik"
    assert belegt["bildungsstufe"] == "Sekundarstufe I"
    assert belegt["thema"] == "Rahmenlehrplan Physik"


def test_inhalte_belegen_nichts_vor():
    """Nur Strukturdokumente tragen Fach und Stufe des Baums — Materialien bleiben der KI."""
    belegt = _belegt({"ablage": _ABLAGE, "metadaten": _metadaten(_MATERIAL)})
    assert "fach" not in belegt and "bildungsstufe" not in belegt and "thema" not in belegt


def test_die_rolle_kommt_aus_der_ablage_nicht_aus_den_metadaten():
    """Ein Eintrag in ``metadaten``, der sich ``struktur`` nennt, zählt nur, wenn die Ablage den
    Knoten als Strukturdokument führt."""
    falsch = _eintrag(_INHALT, "struktur", titel="Linsen", faecher=["Chemie"])
    belegt = _belegt({"ablage": _ABLAGE, "metadaten": _metadaten(falsch)})
    assert "fach" not in belegt
    assert "fach" not in _belegt({"metadaten": _metadaten(_LEHRPLAN)})      # ohne Ablage


def test_die_antwort_der_person_geht_vor():
    teile = {"ablage": _ABLAGE, "metadaten": _metadaten(_LEHRPLAN), "stufe": "Grundschule",
             "grundlage": "Optik im Alltag"}
    belegt = _belegt(teile, lauf=("stufe", "grundlage"))
    assert belegt["bildungsstufe"] == "Primarstufe"
    assert belegt["thema"] == "Optik im Alltag"
    assert belegt["fach"] == "Physik"
    # „Für alle“ heißt bewusst keine Stufe — dann auch keine aus dem Dokument
    ohne = _belegt({**teile, "stufe": "Für alle"}, lauf=("stufe",))
    assert "bildungsstufe" not in ohne


def test_das_argument_der_ki_geht_vor():
    belegt = _belegt({"ablage": _ABLAGE, "metadaten": _metadaten(_LEHRPLAN)})
    aufruf = vb.vorbelegt({"thema": "Wellen", "fach": "Mathematik"}, belegt)
    assert aufruf["fach"] == "Mathematik" and aufruf["thema"] == "Wellen"
    assert aufruf["bildungsstufe"] == "Sekundarstufe I"
    assert "fach" in vb.zeile(belegt)


def test_unbekannte_stufen_und_zu_lange_faecher_fallen_weg():
    zweites = _eintrag(_STRUKTUR_2, "struktur", titel="Lehrplan 2",
                       # Review N3 (MINOR 7): „Förderschule“ ist ein WLO-Label, also bekannt
                       faecher=["x" * 61, "Biologie"], stufen=["Mondschule", "Sekundarstufe II"])
    ablage = {**_ABLAGE, "inhalte": [*_ABLAGE["inhalte"],
                                     {"index": 4, "stand": "stored", "node_id": _STRUKTUR_2,
                                      "rolle": "struktur"}]}
    belegt = _belegt({"ablage": ablage, "metadaten": _metadaten(
        _eintrag(_STRUKTUR, "struktur", titel="Lehrplan 1"), zweites)})
    assert belegt["fach"] == "Biologie"
    assert belegt["bildungsstufe"] == "Sekundarstufe II"
    assert belegt["thema"] == "Lehrplan 1"


def test_ein_lesefehler_beendet_die_vorbelegung_nicht():
    async def kaputt(name):
        if name in ("ablage", "metadaten"):
            raise RuntimeError("weg")
        return None

    belegt = asyncio.run(vb.vorbelegung(_schritt(), kaputt, (), ablauf=_SEED))
    assert "fach" not in belegt


# ── Volltext fehlt noch ──────────────────────────────────────────────────────────────────────────

def test_ein_fehlender_volltext_aus_wlo_heisst_er_entsteht_gerade():
    """Der Lauf scheitert nicht: der KI-Schritt hält (sein Startknopf ist „Stand prüfen“), das
    Werkzeug sagt der KI, dass WLO den Text gerade erzeugt."""
    text = dienst._FEHLER["volltext_fehlt_datei"]
    assert "gerade erzeugt" in text
    assert "wartet" in text
