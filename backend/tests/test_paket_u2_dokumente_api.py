"""Paket U2 (Plan 2026-11-17): ``POST /api/ui/dokumente`` nimmt ``rolle: inhalt|struktur``.

Bei ``inhalt`` entstehen nach Umwandlung und Moderation Kurzangaben (LLM-Attrappe), gespeichert am
Upload (serverseitig); in die Antwort gehen Befund und Kurzangaben, nie der Text. Die Grenzen je
Sitzung (``ablage.GrenzeErreicht``) werden zu eigenen Codes."""

from __future__ import annotations

import pytest

import boerdi.api.ui_dokumente as api
from boerdi.services.dokumente import ablage
from boerdi.services.dokumente.aufnahme import Abweisung
from tests import test_ui_dokumente_api as basis
from tests.test_ui_dokumente_api import _KENNUNG, _post

# Fixtures des Endpunkt-Tests wiederverwenden (dieselbe Lage, derselbe Client)
lage = basis.lage
client = basis.client
_umgebung = basis._umgebung

_ANGABEN = {"titel": "Linsen", "beschreibung": "Sammellinsen", "schlagworte": ["Optik"]}


@pytest.fixture
def angaben(monkeypatch):
    aufrufe: list[tuple[str, str]] = []

    async def ermitteln(markdown, name, **_k):
        aufrufe.append((markdown, name))
        return dict(_ANGABEN)

    monkeypatch.setattr(api, "inhalt_angaben_ermitteln", ermitteln)
    return aufrufe


def test_ohne_rolle_bleibt_es_ein_strukturdokument_ohne_llm(client, lage, angaben):
    r = _post(client)
    assert r.status_code == 200, r.text
    assert r.json()["rolle"] == "struktur" and "angaben" not in r.json()
    assert lage.gespeichert[0]["rolle"] == "struktur" and lage.gespeichert[0]["angaben"] is None
    assert angaben == []


def test_inhalt_bekommt_kurzangaben_gespeichert_und_in_der_antwort(client, lage, angaben):
    r = _post(client, name="Linsen.md", rolle="inhalt")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["rolle"] == "inhalt" and body["angaben"] == _ANGABEN
    assert body["upload_id"] == _KENNUNG and "markdown" not in body
    assert "# Lehrplan" not in r.text                     # kein Text des Dokuments
    [g] = lage.gespeichert
    assert g["rolle"] == "inhalt" and g["angaben"] == _ANGABEN
    assert angaben == [("# Lehrplan", "Linsen.md")]       # aus dem umgewandelten Text


def test_inhalt_ohne_angaben_wird_trotzdem_gespeichert(client, lage, monkeypatch):
    async def nichts(markdown, name, **_k):
        return None

    monkeypatch.setattr(api, "inhalt_angaben_ermitteln", nichts)
    r = _post(client, rolle="inhalt")
    assert r.status_code == 200 and r.json().get("angaben") is None
    assert lage.gespeichert[0]["angaben"] is None


def test_von_der_moderation_abgewiesen_kein_llm_aufruf(client, lage, angaben):
    lage.ergebnis = Abweisung(400, "abgewiesen")
    r = _post(client, rolle="inhalt")
    assert (r.status_code, r.json()["detail"]) == (400, "abgewiesen")
    assert angaben == [] and lage.gespeichert == []


def test_p1_beides_bekommt_kurzangaben_und_bleibt_beides(client, lage, angaben):
    """Plan 2026-11-20, P1: „Gliederung und Material“ ist auch ein Inhalt — mit Kurzangaben."""
    r = _post(client, rolle="beides")
    assert r.status_code == 200, r.text
    assert r.json()["rolle"] == "beides" and r.json()["angaben"] == _ANGABEN
    assert lage.gespeichert[0]["rolle"] == "beides"
    assert angaben == [("# Lehrplan", "Lehrplan.md")]


def test_unbekannte_rolle_wird_abgewiesen(client, lage, angaben):
    assert _post(client, rolle="bild").status_code == 422
    assert lage.aufbereitet == []


@pytest.mark.parametrize(("code", "status"), [("grenze_anzahl", 409), ("grenze_gesamt", 413)])
def test_grenzen_der_sitzung_als_eigene_codes(client, lage, angaben, code, status):
    lage.speichern_wirft = ablage.GrenzeErreicht(code)
    r = _post(client, rolle="inhalt")
    assert (r.status_code, r.json()["detail"]) == (status, code)
    assert lage.db.rollbacks == 1 and lage.db.commits == 0


def test_grenze_vor_der_umwandlung_spart_arbeit(client, lage, angaben, monkeypatch):
    """Was die Sitzung schon hält, prüft der Endpunkt vor Umwandlung und LLM (ohne Sperre, die
    verbindliche Prüfung bleibt in ``ablage.speichern``)."""
    async def voll(s, session_id, **_k):
        return "grenze_anzahl"

    monkeypatch.setattr(ablage, "grenze_vorab", voll)
    r = _post(client, rolle="inhalt")
    assert (r.status_code, r.json()["detail"]) == (409, "grenze_anzahl")
    assert lage.aufbereitet == [] and angaben == []


def test_review_u_der_verbrauch_der_kurzangaben_wird_fuer_die_sitzung_gebucht(client, lage,
                                                                             monkeypatch):
    """Kosten sichtbar (Wächter ``test_usage_coverage``): der Merkposten des LLM-Aufrufs geht mit
    der Sitzung in ``usage_events`` — auch, wenn das Speichern danach an der Grenze scheitert."""
    gebucht: list = []

    async def ermitteln(markdown, name, *, usage_acc=None, **_k):
        usage_acc["models"]["m"] = {"prompt": 10, "completion": 5}
        return dict(_ANGABEN)

    async def buchen(session, session_id, acc, **_k):
        gebucht.append((session_id, dict(acc["models"])))
        return 1

    monkeypatch.setattr(api, "inhalt_angaben_ermitteln", ermitteln)
    monkeypatch.setattr(api, "record_turn_usage", buchen)
    assert _post(client, rolle="inhalt").status_code == 200
    assert gebucht == [(basis._SITZUNG, {"m": {"prompt": 10, "completion": 5}})]
    gebucht.clear()
    lage.speichern_wirft = ablage.GrenzeErreicht("grenze_anzahl")
    assert _post(client, rolle="inhalt").status_code == 409
    assert len(gebucht) == 1, "auch ohne gespeicherten Upload gebucht"


def test_review_u_ohne_llm_aufruf_keine_buchung(client, lage, angaben, monkeypatch):
    gebucht: list = []

    async def buchen(session, session_id, acc, **_k):
        gebucht.append(acc)
        return 0

    monkeypatch.setattr(api, "record_turn_usage", buchen)
    assert _post(client).status_code == 200                 # Strukturdokument: kein LLM
    assert gebucht == []
