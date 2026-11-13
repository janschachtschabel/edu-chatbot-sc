"""Review TW-4, Befund 2, und Querschnitts-Review TW, Befunde 3/4/14: Ausstieg (N16).

- **Ausstieg:** Ein ``ende``-Schritt mit ``ausstieg: true`` („Ohne Ablauf“) oder „Abbrechen“ in der
  Ablauf-Leiste merkt sich den Ablauf für die nächsten :data:`zug.AUSSTIEG_ZUEGE` Züge. So lange
  startet er nicht wieder von selbst: weder per Wendung noch per Modul-Antwort noch als Werkzeug
  der KI. Sonst begänne die nächste Nachricht dieselbe Frage von vorn.
- **Verfall:** Danach gilt die Marke nicht mehr. Die Sperre ist kurz und sperrt niemanden aus.
- **Zurück:** Die Antwort des Ausstiegs bietet „Doch mit Ablauf“, einen Knopf, der ihn startet.
"""

from __future__ import annotations

import asyncio

import pytest

from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.services.ablauf import ausloeser, vorschlag, zug
from tests.test_ablauf_zug import _S, _req, umgebung  # noqa: F401 — Fixture


def _ablauf(**ende) -> AblaufArea:
    return AblaufArea.model_validate({
        "id": "tb", "titel": {"de": "TB"}, "aktiv": True,
        "ausloeser": [{"art": "text", "wendungen": ["einen themenbaum erstellen"]},
                      {"art": "agent"}, {"art": "knopf"}],
        "schritte": [{"id": "frei", "typ": "ende", "text": {"de": "Dann frei."}, **ende}]})


@pytest.fixture
def katalog(monkeypatch):
    ablauf = _ablauf(ausstieg=True)
    monkeypatch.setattr(ausloeser, "katalog", lambda: [ablauf])
    monkeypatch.setattr(ausloeser, "erfuellt", lambda _a: True)
    return ablauf


def test_das_feld_gilt_nur_am_ende_und_abgewaehlt_ist_nicht_gesetzt():
    assert _ablauf(ausstieg=True).schritte[0].ausstieg is True
    assert _ablauf().schritte[0].ausstieg is None
    assert _ablauf(ausstieg=False).schritte[0].ausstieg is None   # NIT 13: Fassung bleibt


def test_die_marke_gilt_einige_zuege_und_verfaellt_dann():
    state = {"entities": {}, "turn_count": 7}
    zug.ausstieg_merken(state, "tb")
    assert zug.abgelehnt("s", state) == "tb"
    state["turn_count"] = 7 + zug.AUSSTIEG_ZUEGE - 1
    assert zug.abgelehnt("s", state) == "tb"
    state["turn_count"] = 7 + zug.AUSSTIEG_ZUEGE
    assert zug.abgelehnt("s", state) is None
    assert zug.abgelehnt("s", {"entities": {}}) is None


def test_wendung_und_ki_lassen_den_abgelehnten_aus(katalog):
    satz = "Ich möchte einen Themenbaum erstellen"
    assert zug.text_ausloeser(satz).id == "tb"
    assert zug.text_ausloeser(satz, ohne="tb") is None
    assert [w["function"]["name"] for w in vorschlag.werkzeuge("de")] == ["ablauf-tb"]
    assert vorschlag.werkzeuge("de", ohne="tb") == []


def test_der_ausstieg_merkt_sich_den_ablauf_und_bietet_doch_mit_ablauf(umgebung):  # noqa: F811
    roh = _ablauf(ausstieg=True).model_dump(mode="json", exclude_none=True)
    umgebung.katalog["wert"] = {**umgebung.katalog["wert"],
                                "ablaeufe": [*umgebung.katalog["wert"]["ablaeufe"], roh]}
    state: dict = {"entities": {}, "turn_count": 3}
    antwort = asyncio.run(zug.starten(_S(), _req(action=zug.AKTION, action_params={"ablauf": "tb"}),
                                      state))
    assert zug.abgelehnt("sitzung", state) == "tb"
    [knopf] = antwort.quick_replies
    praefix, _label, aktion, params = knopf.split("|", 3)
    assert (praefix, aktion) == ("__action__", zug.AKTION) and '"tb"' in params


def test_abbrechen_in_der_leiste_ist_auch_ein_ausstieg(umgebung, monkeypatch):  # noqa: F811
    """Querschnitts-Review TW, Befund 3: sonst startete die nächste Wendung ihn gleich wieder.
    Seit 13.11. fragt der Zug nur noch an Auftrag und Freigabe nach — dort sperrt die Rückfrage
    allein nichts; an einer Frage bricht der Knopf sofort ab, und auch das ist ein Ausstieg."""
    import json

    from tests.test_ablauf_leiste import _WARTET, _abbrechen, _gestartet, _wartet_auftrag
    from tests.test_ablauf_leiste import _ablauf as _leisten_ablauf

    zustand = _wartet_auftrag(umgebung, monkeypatch)
    params = json.loads(_abbrechen(zustand).quick_replies[0].split("|", 3)[3])
    assert zug.abgelehnt("s", zustand) is None            # die Rückfrage allein sperrt nichts
    _abbrechen(zustand, **params)
    assert zug.abgelehnt("s", zustand) is not None

    umgebung.speicher.v.clear()
    sofort = _gestartet(umgebung, _leisten_ablauf(_WARTET).model_dump(exclude_none=True))
    _abbrechen(sofort)
    assert zug.abgelehnt("s", sofort) is not None


def test_zweites_review_1_die_marke_wird_mit_der_sitzung_gespeichert(umgebung, monkeypatch):  # noqa: F811
    """Zweites Review TW, Befund 1: erst nach ``update_session`` gesetzt, ging sie verloren.

    Der nächste Zug lädt die Entities aus der DB, nicht aus diesem Dict — die Marke muss also im
    geschriebenen Stand stehen.
    """
    import copy

    from boerdi.services.ablauf import zug_basis

    geschrieben: list[dict] = []

    async def merken(_session, _sid, *, entities, **_):
        geschrieben.append(copy.deepcopy(entities))

    monkeypatch.setattr(zug_basis, "update_session", merken)
    roh = _ablauf(ausstieg=True).model_dump(mode="json", exclude_none=True)
    umgebung.katalog["wert"] = {**umgebung.katalog["wert"],
                                "ablaeufe": [*umgebung.katalog["wert"]["ablaeufe"], roh]}
    state: dict = {"entities": {}, "turn_count": 3}
    asyncio.run(zug.starten(_S(), _req(action=zug.AKTION, action_params={"ablauf": "tb"}), state))
    assert geschrieben and geschrieben[-1].get(zug.basis.AUSSTIEG_KEY, {}).get("ablauf") == "tb"


def test_zweites_review_8_ein_neuer_start_hebt_die_marke_auf(umgebung):  # noqa: F811
    """„Doch mit Ablauf“ startet ihn — danach darf die Marke ihn nicht weiter sperren."""
    roh = _ablauf().model_dump(mode="json", exclude_none=True)   # ende ohne Ausstieg
    umgebung.katalog["wert"] = {**umgebung.katalog["wert"],
                                "ablaeufe": [*umgebung.katalog["wert"]["ablaeufe"], roh]}
    state: dict = {"entities": {}, "turn_count": 3}
    zug.ausstieg_merken(state, "tb")
    asyncio.run(zug.starten(_S(), _req(action=zug.AKTION, action_params={"ablauf": "tb"}), state))
    assert zug.abgelehnt("sitzung", state) is None
