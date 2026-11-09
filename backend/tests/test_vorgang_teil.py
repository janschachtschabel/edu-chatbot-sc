"""Review Q1 (Befund 6/7): Regeln des Teils ``ablage`` — wann ein offener Stapel noch hält, was als
``frueher`` bleibt."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from boerdi.services.ablage import vorgang_teil as vt

_JETZT = datetime(2026, 11, 6, 12, 0, tzinfo=UTC)


def _teil(**mehr):
    return {"abgeschlossen": False, "erstellt": (_JETZT - timedelta(minutes=5)).isoformat(),
            "inhalte": [{"index": 0, "titel": "A", "stand": "stored", "node_id": "n-0"},
                        {"index": 1, "titel": "B", "stand": "offen"}], **mehr}


def test_ein_junger_offener_stapel_mit_abgelegten_haelt():
    assert vt.haelt_noch(_teil(), _JETZT) is True


def test_nach_der_freigabe_haelt_er_nicht_mehr():
    alt = (_JETZT - vt.FREIGABE - timedelta(seconds=1)).isoformat()
    assert vt.haelt_noch(_teil(erstellt=alt), _JETZT) is False


def test_ohne_abgelegte_abgeschlossen_oder_kaputt_haelt_nichts():
    assert vt.haelt_noch(_teil(inhalte=[{"stand": "offen"}]), _JETZT) is False
    assert vt.haelt_noch(_teil(abgeschlossen=True), _JETZT) is False
    assert vt.haelt_noch(_teil(erstellt="kaputt"), _JETZT) is False
    assert vt.haelt_noch(_teil(erstellt="2026-11-06T11:58:00"), _JETZT) is False   # ohne Zone
    assert vt.haelt_noch(None, _JETZT) is False


def test_frueher_erbt_auch_ueber_einen_abgeschlossenen_stapel():
    """Befund 7: die nodeIds eines davor verlassenen Stapels gehen nicht verloren."""
    vorher = _teil(abgeschlossen=True, frueher=[{"titel": "X", "node_id": "n-x"}])
    neu = vt.aus_plan({"entries": []}, "tok-0123456789", "b1", vorher)
    assert neu["frueher"] == [{"titel": "X", "node_id": "n-x"}]


def test_frueher_nimmt_die_abgelegten_eines_offenen_stapels():
    neu = vt.aus_plan({"entries": []}, "tok-0123456789", "b1", _teil())
    assert neu["frueher"] == [{"titel": "A", "node_id": "n-0", "rolle": "inhalt"}]


def test_frueher_ist_gedeckelt():
    vorher = _teil(frueher=[{"titel": str(i), "node_id": f"n-{i}"} for i in range(250)])
    assert len(vt.aus_plan({"entries": []}, "tok-0123456789", "b1", vorher)["frueher"]) == 200
