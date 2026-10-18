"""Paket 16, C6: Feld-Unterschiede zwischen Werksfassung und eigener Fassung (rein).

Die Sicherung zeigt je Bereich eine Tabelle *Feld · Werk · Eigen* statt nur des YAML-Diffs. Nur
abweichende Blätter, Werte als gekürzter JSON-Text, ``None`` = das Feld fehlt auf dieser Seite.
"""

from __future__ import annotations

from boerdi.services.feld_unterschiede import feld_unterschiede


def test_nur_abweichende_blaetter_mit_pfad():
    werk = {"welcome": {"greeting": "Hallo", "quick_replies": ["a", "b"]}, "enabled": True}
    eigen = {"welcome": {"greeting": "Moin", "quick_replies": ["a", "b"]}, "enabled": True}
    felder, gesamt = feld_unterschiede(werk, eigen)
    assert felder == [{"pfad": "welcome.greeting", "werk": '"Hallo"', "eigen": '"Moin"'}]
    assert gesamt == 1


def test_fehlende_felder_sind_none_nicht_null():
    felder, _ = feld_unterschiede({"a": 1, "b": None}, {"b": None, "c": 2})
    assert felder == [
        {"pfad": "a", "werk": "1", "eigen": None},
        {"pfad": "c", "werk": None, "eigen": "2"},
    ]


def test_listen_von_objekten_je_eintrag_listen_von_werten_als_ganzes():
    werk = {"steps": [{"id": "s1", "text": "eins"}, {"id": "s2", "text": "zwei"}], "tags": ["x"]}
    eigen = {"steps": [{"id": "s1", "text": "eins"}, {"id": "s2", "text": "ZWEI"}],
             "tags": ["x", "y"]}
    felder, _ = feld_unterschiede(werk, eigen)
    assert [f["pfad"] for f in felder] == ["steps[1].text", "tags"]
    assert felder[1] == {"pfad": "tags", "werk": '["x"]', "eigen": '["x", "y"]'}


def test_zusaetzlicher_listeneintrag_fehlt_im_werk():
    felder, _ = feld_unterschiede({"g": [{"a": 1}]}, {"g": [{"a": 1}, {"a": 2}]})
    assert felder == [{"pfad": "g[1]", "werk": None, "eigen": '{"a": 2}'}]


def test_lange_werte_werden_gekuerzt_und_die_liste_begrenzt():
    werk = {f"k{i}": "x" * 400 for i in range(5)}
    eigen = {f"k{i}": "y" * 400 for i in range(5)}
    felder, gesamt = feld_unterschiede(werk, eigen, grenze=3)
    assert gesamt == 5 and len(felder) == 3
    assert len(felder[0]["werk"]) <= 161 and felder[0]["werk"].endswith("…")


def test_gleiche_fassungen_haben_keine_unterschiede():
    assert feld_unterschiede({"a": [{"b": 1}]}, {"a": [{"b": 1}]}) == ([], 0)
