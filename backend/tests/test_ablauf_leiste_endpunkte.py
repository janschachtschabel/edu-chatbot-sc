"""Zweites Review AS-U, Befund 4: der Stand der Ablauf-Leiste kommt an allen Endpunkten an — an der
Antwort (POST und Strom), an der Fehlerblase und im Verlauf. Fiele eine Verdrahtung weg, verschwände
die Leiste still; diese Tests halten sie fest."""

from __future__ import annotations

import pytest

from boerdi.api import chat as chat_api
from boerdi.api import sessions as sessions_api
from boerdi.api.schemas import ChatResponse
from tests.test_kennung_oeffentlich import (
    _umgebung,  # noqa: F401 — autouse-Fixture
    client,  # noqa: F401 — Fixture
)

_STAND = {"id": "probe", "titel": "Probe", "nr": 1, "von": 3, "status": "wartet_wahl",
          "lauf": "a1b2", "persoenlich": False, "teile": [],
          "weg": None}   # AS-7: der Weg nur bei wartet_seite
_SID = "bb-0123456789abcdef"


@pytest.fixture()
def mit_stand(monkeypatch):
    gesehen: list = []

    def stand(entities, aufrufer, lang):
        gesehen.append(entities)
        return dict(_STAND)

    monkeypatch.setattr(chat_api.fortschritt, "stand", stand)
    return gesehen


def _graph(monkeypatch, *, wirft: bool = False):
    class _Graph:
        async def ainvoke(self, state):
            if wirft:
                raise RuntimeError("kaputt")
            return {"response": ChatResponse(session_id=_SID, content="OK"),
                    "session_state": {"entities": {"_vorgang": {"id": "v"}}}}

    monkeypatch.setattr(chat_api, "build_turn_graph", lambda **k: _Graph())


def test_die_antwort_traegt_den_stand(client, monkeypatch, mit_stand):  # noqa: F811
    _graph(monkeypatch)
    r = client.post("/api/chat", json={"session_id": _SID, "message": "hallo"})
    assert r.json()["ui"]["ablauf"] == _STAND
    assert mit_stand == [{"_vorgang": {"id": "v"}}]       # aus dem Zustand des Zugs


class _Sitzung:
    """Eine Sitzungsfabrik für den Strom (``async with sitzungen() as session``)."""

    async def __aenter__(self):
        return object()

    async def __aexit__(self, *_a):
        return False


def test_der_strom_traegt_den_stand(client, monkeypatch, mit_stand):  # noqa: F811
    from boerdi.api.deps import get_session_factory

    client.app.dependency_overrides[get_session_factory] = lambda: _Sitzung
    _graph(monkeypatch)
    r = client.post("/api/chat/stream", json={"session_id": _SID, "message": "hallo"})
    assert '"ablauf"' in r.text and '"lauf":"a1b2"' in r.text.replace(" ", "")


def test_die_fehlerblase_traegt_den_stand(client, monkeypatch, mit_stand):  # noqa: F811
    _graph(monkeypatch, wirft=True)

    async def gespeichert(*_a, **_k):
        return 1

    async def sitzung(*_a, **_k):
        return {"_vorgang": {"id": "v"}}

    monkeypatch.setattr(chat_api, "save_message", gespeichert)
    monkeypatch.setattr(chat_api, "sitzung_entities", sitzung)
    r = client.post("/api/chat", json={"session_id": _SID, "message": "hallo"})
    assert r.json()["ui"]["ablauf"] == _STAND


def test_scheitert_das_speichern_fragt_die_fehlerblase_nicht_noch_einmal(
        client, monkeypatch, mit_stand):  # noqa: F811
    """Zweites Review AS-U, Kleinigkeit 10: bei einem Datenbank-Ausfall kein zweiter Versuch."""
    _graph(monkeypatch, wirft=True)
    gefragt: list = []

    async def kaputt(*_a, **_k):
        raise RuntimeError("DB weg")

    async def sitzung(*_a, **_k):
        gefragt.append(1)
        return {}

    monkeypatch.setattr(chat_api, "save_message", kaputt)
    monkeypatch.setattr(chat_api, "sitzung_entities", sitzung)
    r = client.post("/api/chat", json={"session_id": _SID, "message": "hallo"})
    assert r.status_code == 200 and gefragt == []


def test_der_verlauf_traegt_den_stand_an_der_letzten_antwort(client, monkeypatch, mit_stand):  # noqa: F811
    async def nachrichten(*_a, **_k):
        return [{"id": 1, "role": "user", "content": "los", "debug": {}},
                {"id": 2, "role": "assistant", "content": "Weiter?", "debug": {}}]

    async def sitzung(*_a, **_k):
        return {"_vorgang": {"id": "v"}}

    monkeypatch.setattr(sessions_api, "get_messages", nachrichten)
    monkeypatch.setattr(sessions_api, "sitzung_entities", sitzung)
    r = client.get(f"/api/sessions/{_SID}/messages")
    assert r.json()[1]["ui"]["ablauf"] == _STAND
    assert "ablauf" not in r.json()[0]["ui"]


def test_q1_der_verlauf_einer_angemeldeten_person_zeigt_ihren_lauf(client, monkeypatch):  # noqa: F811
    """Querschnitts-Review AS-U/BU, Q-1: der Verweis gehört der angemeldeten Person — ohne ihre
    Anmeldung fand der Verlauf ihn nie, die Leiste fehlte nach Neuladen, „Fortsetzen“ und
    Wiederkehr.
    Trägt der Abruf den Zugangsblock, rechnet der Stand mit ihr; ohne bleibt es die Sitzung."""
    from boerdi.services import arbeitsstand

    gesehen: list = []

    def stand(entities, aufrufer, lang):
        gesehen.append(aufrufer)
        return dict(_STAND)

    async def nachrichten(*_a, **_k):
        return [{"id": 1, "role": "user", "content": "los", "debug": {}},
                {"id": 2, "role": "assistant", "content": "Weiter?", "debug": {}}]

    async def sitzung(*_a, **_k):
        return {arbeitsstand.VERWEIS: {"id": "v-1"}}

    async def frei(*_a, **_k):
        return None

    bestaetigt: list = []

    async def bestaetige():
        bestaetigt.append(True)

    monkeypatch.setattr(chat_api.fortschritt, "stand", stand)
    monkeypatch.setattr(sessions_api, "get_messages", nachrichten)
    monkeypatch.setattr(sessions_api, "sitzung_entities", sitzung)
    monkeypatch.setattr(sessions_api, "bestaetige_anmeldung", bestaetige)
    # angemeldet gilt nur nach der Bestätigung — und die gibt es nur mit Zugangsblock
    monkeypatch.setattr(arbeitsstand, "has_personal_auth", lambda: bool(bestaetigt))
    monkeypatch.setattr(sessions_api, "verbindung_freigeben", frei)
    monkeypatch.setattr(arbeitsstand, "aufrufer_kennung", lambda: "person-a")
    ohne = client.get(f"/api/sessions/{_SID}/messages")
    mit = client.get(f"/api/sessions/{_SID}/messages", headers={"WLO-Access-Block": "wloTestBlock"})
    assert ohne.json()[1]["ui"]["ablauf"] == _STAND and mit.json()[1]["ui"]["ablauf"] == _STAND
    assert gesehen == [f"sitzung:{_SID}", "person-a"]


def _verlauf_mit_verweis(monkeypatch, vorgang):
    from boerdi.services import arbeitsstand, vorgaenge

    async def nachrichten(*_a, **_k):
        return [{"id": 1, "role": "user", "content": "los", "debug": {}},
                {"id": 2, "role": "assistant", "content": "Weiter?", "debug": {}}]

    async def sitzung(*_a, **_k):
        return {"_vorgang": {"id": "v-1"}}

    async def lesen(s, vid, aufrufer):
        return vorgang if vid == "v-1" else None

    monkeypatch.setattr(sessions_api, "get_messages", nachrichten)
    monkeypatch.setattr(sessions_api, "sitzung_entities", sitzung)
    monkeypatch.setattr(arbeitsstand, "verweis", lambda ents, _wer: ents.get("_vorgang"))
    monkeypatch.setattr(vorgaenge, "lesen", lesen)


@pytest.mark.parametrize("vorgang", [None, type("V", (), {"status": "fertig"})()])
def test_z5_ein_anderswo_geloeschter_oder_beendeter_vorgang_zeigt_keine_leiste(
        client, monkeypatch, mit_stand, vorgang):  # noqa: F811
    """Zweites Review, Z-5: der Verweis der Sitzung kann veraltet sein (in einem anderen Tab
    gelöscht oder beendet) — der Verlauf fragt den Vorgang einmal nach, statt eine tote Leiste
    zu zeigen."""
    _verlauf_mit_verweis(monkeypatch, vorgang)
    r = client.get(f"/api/sessions/{_SID}/messages")
    assert "ablauf" not in r.json()[1]["ui"]


def test_z5_ein_offener_vorgang_zeigt_die_leiste(client, monkeypatch, mit_stand):  # noqa: F811
    _verlauf_mit_verweis(monkeypatch, type("V", (), {"status": "wartet_person"})())
    assert client.get(f"/api/sessions/{_SID}/messages").json()[1]["ui"]["ablauf"] == _STAND


def test_z6_eine_langsame_bestaetigung_haelt_den_verlauf_nicht_auf(
        client, monkeypatch, mit_stand):  # noqa: F811
    """Zweites Review, Z-6: der Verlauf wartet höchstens kurz auf die Bestätigung der Anmeldung —
    danach kommt er ohne den persönlichen Stand, statt bis zu 5 s zu hängen."""
    import asyncio
    import time

    from boerdi.services import arbeitsstand

    async def langsam():
        await asyncio.sleep(30)        # weit über der Frist: misst nur, ob der Verlauf wartet

    async def nachrichten(*_a, **_k):
        return [{"id": 2, "role": "assistant", "content": "Weiter?", "debug": {}}]

    async def sitzung(*_a, **_k):
        return {arbeitsstand.VERWEIS: {"id": "v-1"}}

    async def frei(*_a, **_k):
        return None

    monkeypatch.setattr(sessions_api, "bestaetige_anmeldung", langsam)
    monkeypatch.setattr(sessions_api, "get_messages", nachrichten)
    monkeypatch.setattr(sessions_api, "sitzung_entities", sitzung)
    monkeypatch.setattr(sessions_api, "verbindung_freigeben", frei)
    anfang = time.monotonic()
    r = client.get(f"/api/sessions/{_SID}/messages", headers={"WLO-Access-Block": "wloTestBlock"})
    # Spielraum für eine ausgelastete Maschine (die volle Suite kippte bei 2,5 s)
    assert r.status_code == 200 and time.monotonic() - anfang < 10
    # Paket R2-c: ohne Bestätigung und ohne Stand ist er unbestimmt — das Widget pingt einmal
    monkeypatch.setattr(chat_api.fortschritt, "stand", lambda *_a: None)
    r = client.get(f"/api/sessions/{_SID}/messages", headers={"WLO-Access-Block": "wloTestBlock"})
    assert r.json()[-1]["ui"]["ablauf_unbestimmt"] is True


def test_r2c_ohne_verweis_ist_nichts_unbestimmt(client, monkeypatch, mit_stand):  # noqa: F811
    async def nachrichten(*_a, **_k):
        return [{"id": 2, "role": "assistant", "content": "Hallo", "debug": {}}]

    async def sitzung(*_a, **_k):
        return {}

    monkeypatch.setattr(sessions_api, "get_messages", nachrichten)
    monkeypatch.setattr(sessions_api, "sitzung_entities", sitzung)
    r = client.get(f"/api/sessions/{_SID}/messages", headers={"WLO-Access-Block": "wloTestBlock"})
    assert not r.json()[-1].get("ui", {}).get("ablauf_unbestimmt")


def test_pr51_ohne_verweis_keine_bestaetigung_und_kein_stand(client, monkeypatch, mit_stand):  # noqa: F811
    """Review PR #51 (Backend, R2): ohne Verweis in der Sitzung gibt es keine Leiste — dann wartet
    der Verlauf auch nicht (bis zu 1 s) auf die Bestätigung der Anmeldung."""
    bestaetigt: list = []

    async def bestaetige():
        bestaetigt.append(True)

    async def nachrichten(*_a, **_k):
        return [{"id": 2, "role": "assistant", "content": "Weiter?", "debug": {}}]

    async def sitzung(*_a, **_k):
        return {"thema": "Optik"}

    monkeypatch.setattr(sessions_api, "bestaetige_anmeldung", bestaetige)
    monkeypatch.setattr(sessions_api, "get_messages", nachrichten)
    monkeypatch.setattr(sessions_api, "sitzung_entities", sitzung)
    r = client.get(f"/api/sessions/{_SID}/messages", headers={"WLO-Access-Block": "wloTestBlock"})
    assert r.status_code == 200 and "ablauf" not in r.json()[0]["ui"]
    assert bestaetigt == [] and mit_stand == []


def test_review_r2_6_der_verlauf_uebernimmt_den_anonymen_vorgang(
        client, monkeypatch, mit_stand):  # noqa: F811
    """Review R2, Befund 6: gleich nach der Anmeldung lädt das Widget den Verlauf — dort schon
    übernehmen (und die Sitzung speichern), sonst fehlte die Leiste bis zum nächsten Zug."""
    from boerdi.services import arbeitsstand

    gerufen: list = []

    async def uebernehmen(_s, sid, entities, _aufrufer):
        gerufen.append(sid)
        return True

    async def speichern(_s, sid, **k):
        gerufen.append(("gespeichert", sid))

    async def nachrichten(*_a, **_k):
        return [{"id": 2, "role": "assistant", "content": "Weiter?", "debug": {}}]

    async def sitzung(*_a, **_k):
        return {arbeitsstand.VERWEIS: {"id": "v-1"}}

    monkeypatch.setattr(arbeitsstand, "anonymen_uebernehmen", uebernehmen)
    monkeypatch.setattr(sessions_api, "update_session", speichern)
    monkeypatch.setattr(sessions_api, "get_messages", nachrichten)
    monkeypatch.setattr(sessions_api, "sitzung_entities", sitzung)
    client.get(f"/api/sessions/{_SID}/messages")
    assert gerufen == [_SID, ("gespeichert", _SID)]


def test_review_r1_r4_4_nur_der_verweis_wird_zurueckgeschrieben(
        client, monkeypatch, mit_stand):  # noqa: F811
    """Querschnitts-Review R1–R4, Befund 4: der GET schreibt nicht den alten Stand zurück."""
    from boerdi.services import arbeitsstand

    geschrieben: list = []
    lesungen = [{arbeitsstand.VERWEIS: {"id": "alt"}},
                {arbeitsstand.VERWEIS: {"id": "alt"}, "_neu_aus_tab_2": 1}]

    async def sitzung(*_a, **_k):
        return dict(lesungen.pop(0)) if lesungen else {}

    async def uebernehmen(_s, _sid, entities, _aufrufer):
        entities[arbeitsstand.VERWEIS] = {"id": "neu"}
        return True

    async def speichern(_s, _sid, **k):
        geschrieben.append(k["entities"])

    async def nachrichten(*_a, **_k):
        return [{"id": 2, "role": "assistant", "content": "Weiter?", "debug": {}}]

    monkeypatch.setattr(arbeitsstand, "anonymen_uebernehmen", uebernehmen)
    monkeypatch.setattr(sessions_api, "update_session", speichern)
    monkeypatch.setattr(sessions_api, "get_messages", nachrichten)
    monkeypatch.setattr(sessions_api, "sitzung_entities", sitzung)
    client.get(f"/api/sessions/{_SID}/messages")
    assert geschrieben == [{arbeitsstand.VERWEIS: {"id": "neu"}, "_neu_aus_tab_2": 1}]
