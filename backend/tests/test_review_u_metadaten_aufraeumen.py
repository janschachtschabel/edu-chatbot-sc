"""Review Paket U (19.11.), MAJOR 2 und NIT 8: lokale ``metadaten`` nach dem Löschen eines Inhalts.

Geht ein hier im Chat gelesener Inhalt (Löschen, Ersetzen, Ablauf der Frist), dürfen die vom LLM
erzeugten Kurzangaben (Titel, Beschreibung, Schlagworte, Fach, Stufe) und die ``upload_id`` nicht
im Vorgang bleiben: der Eintrag fällt auf „nur Name“ zurück (``lesbar: false``) — rein geprüft
hier, gegen Postgres in ``test_review_u_aufraeumen_pg.py``.
"""

from __future__ import annotations

from types import SimpleNamespace

from boerdi.services import arbeitsstand_teile as at
from boerdi.services.ablauf import inhalte_aus_dateien as iad
from boerdi.services.dokumente import metadaten_lokal as ml
from tests.test_paket_u4_orte import _A, CHAT_DATEIEN, bereitgestellt

_ANGABEN = {"titel": "Linsen im Alltag", "beschreibung": "Sammellinsen in der Brille",
            "schlagworte": ["Optik"], "fach": "Physik", "stufe": "Sekundarstufe I"}


def _teile() -> dict:
    return dict((t[0], t[2]) for t in at.teile_aus_antwort(
        {"modul": "ui_upload", "block_id": "b0000001",
         "daten": bereitgestellt("chat", dateien=CHAT_DATEIEN)}))


def _gelesen(sprache: str | None = None) -> dict:
    zeile = SimpleNamespace(id=_A, name="x", befund={"rolle": "inhalt", "angaben": _ANGABEN})
    neu, _ = ml.neu_berechnet(_teile()["metadaten"], [zeile], sprache)
    return neu


def test_der_eintrag_eines_geloeschten_inhalts_wird_nur_name():
    teile = _teile()
    wert = _gelesen()
    assert wert["inhalte"][0]["schlagworte"] == ["Optik"]
    neu = ml.ohne_uploads(wert, {_A}, teile["struktur"])
    assert neu is not None
    e = neu["inhalte"][0]
    assert e == {"i": 0, "rolle": "inhalt", "titel": "Linsen", "lesbar": False,
                 "beschreibung": "Ordner: Unterlagen"}
    assert "Linsen im Alltag" not in str(neu) and "Sammellinsen" not in str(neu)
    assert _A not in str(neu)
    assert neu["block_id"] == "b0000001" and neu["quelle"] == "chatbot"
    assert neu["titel"] == "Inhalte aus 2 Dateien (0 gelesen)"
    # der nicht gelesene bleibt, wie er war
    assert neu["inhalte"][1] == wert["inhalte"][1]


def test_ohne_passende_auswahl_heisst_der_eintrag_datei_n():
    neu = ml.ohne_uploads(_gelesen(), {_A}, {"block_id": "anderesfeld", "struktur": {}})
    assert neu["inhalte"][0] == {"i": 0, "rolle": "inhalt", "titel": "Datei 1", "lesbar": False}
    assert ml.ohne_uploads(_gelesen(), {_A}, None)["inhalte"][0]["titel"] == "Datei 1"


def test_kein_betroffener_eintrag_aendert_nichts():
    assert ml.ohne_uploads(_gelesen(), {"00000000-0000-4000-8000-000000000000"}, None) is None
    assert ml.ohne_uploads({"format": "wlo.metadaten@1", "inhalte": []}, {_A}, None) is None


def test_die_kennungen_eines_teils():
    assert ml.upload_ids(_gelesen()) == {_A}
    assert ml.upload_ids({"inhalte": [{"upload_id": 3}, "x"]}) == set()


def test_nit8_neu_berechnet_behaelt_die_sprache():
    """Der Titel des Teils folgt der Sprache — ausdrücklich oder aus dem Platzhalter."""
    assert _gelesen("en")["titel"] == "Content from 2 files (1 read)"
    roh = _teile()["metadaten"]
    roh_en = {**roh, "titel": ml.aus_antwort(bereitgestellt("chat", dateien=CHAT_DATEIEN),
                                              "b0000001", "en")["titel"]}
    neu, _ = ml.neu_berechnet(roh_en, [])
    assert neu["titel"].startswith("Content from")
    # und beim Aufräumen bleibt sie
    en = _gelesen("en")
    assert ml.ohne_uploads(en, {_A}, None)["titel"] == "Content from 2 files (0 read)"


def test_nit8_helfer_aus_inhalte_aus_dateien_sind_oeffentlich():
    for name in ("dateien_mit_pfad", "gekuerzt", "nummer", "ordnerpfad"):
        assert callable(getattr(iad, name)), name
    import inspect
    quelle = inspect.getsource(ml)
    assert "import (\n    PFAD_ZEICHEN,\n    _" not in quelle
    assert not any(f"    {n},\n" in quelle for n in ("_dateien", "_gekuerzt", "_nummer", "_pfad"))


class _Sitzung:
    """Attrappe nur für ``_metadaten_bereinigen``: Ablage als dict (gegen Postgres prüft
    ``test_review_u_aufraeumen_pg.py``)."""

    def __init__(self, ablage: dict) -> None:
        self.ablage = ablage
        self.geloescht: list[str] = []

    async def get(self, _modell, schluessel):
        inhalt = self.ablage.get(schluessel[1])
        return None if inhalt is None else SimpleNamespace(inhalt=inhalt)

    async def execute(self, stmt):
        self.geloescht.append(str(stmt.compile(compile_kwargs={"literal_binds": True})))

    async def merge(self, zeile):
        self.ablage[zeile.schluessel] = zeile.inhalt


def _bereinigen(akte: dict, ablage: dict) -> tuple[bool, _Sitzung]:
    import asyncio

    from boerdi.services import vorgaenge_dokumente

    s = _Sitzung(ablage)
    return asyncio.run(vorgaenge_dokumente._metadaten_bereinigen(s, "v1", akte, {_A})), s


def test_bereinigen_in_der_akte_mit_struktur_und_historie():
    teile = _teile()
    akte = {"teile": {"struktur": {"typ": "wlo.auswahl@1", "version": 1, "wert": teile["struktur"]},
                      "metadaten": {"typ": "wlo.metadaten@1", "version": 4, "wert": _gelesen(),
                                    "zusammenfassung": "2 Inhalte, 1 gelesen"}},
            "historie": {"metadaten": ["metadaten@3"]}}
    geaendert, s = _bereinigen(akte, {})
    assert geaendert
    eintrag = akte["teile"]["metadaten"]
    assert eintrag["version"] == 5 and eintrag["zusammenfassung"] == "2 Inhalte, 0 gelesen"
    assert eintrag["wert"]["inhalte"][0]["lesbar"] is False and _A not in str(eintrag)
    assert "metadaten" not in akte["historie"]
    assert any("metadaten@3" in q for q in s.geloescht)


def test_bereinigen_eines_grossen_teils_in_der_ablage():
    gross = _gelesen()
    gross["inhalte"] += [{"i": n, "rolle": "inhalt", "titel": "x" * 150, "lesbar": False}
                         for n in range(3, 80)]
    akte = {"teile": {"metadaten": {"typ": "wlo.metadaten@1", "version": 1,
                                    "ref": "metadaten@1"}}, "historie": {}}
    geaendert, s = _bereinigen(akte, {"metadaten@1": gross})
    assert geaendert
    assert akte["teile"]["metadaten"]["ref"] == "metadaten@2"
    assert "wert" not in akte["teile"]["metadaten"]
    assert any("metadaten@1" in q for q in s.geloescht)
    neu = s.ablage["metadaten@2"]
    assert neu["inhalte"][0]["lesbar"] is False and "Sammellinsen" not in str(neu)


def test_bereinigen_ohne_betroffenen_eintrag_laesst_die_akte():
    akte = {"teile": {"metadaten": {"typ": "wlo.metadaten@1", "version": 1,
                                    "wert": {"format": "wlo.metadaten@1", "inhalte": []}}}}
    vorher = repr(akte)
    geaendert, s = _bereinigen(akte, {})
    assert not geaendert and repr(akte) == vorher and s.geloescht == []
