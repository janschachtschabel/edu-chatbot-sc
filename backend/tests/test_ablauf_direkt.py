"""Plan 2026-11-10, TB-E3 (Nutzer-Entscheid N4, offen seit AS-5c): die KI darf einen Ablauf
**direkt** starten — wie ein Werkzeug, weil der Ablauf es so festlegt (Auslöser ``agent`` mit
``modus: direkt``).

Der Start geht denselben Weg wie ein Klick: die Zusammenstellung setzt den Knopf wie bisher und
merkt ihn als Direktstart; die Antwort trägt ihn in ``ui.direkt_start`` — nur, wenn er nach der
letzten Kürzung noch unter den Schnellantworten steht. Das Widget drückt ihn nach dem Zug selbst.
So laufen Preflight, Sicherheitsprüfung, die Bremse „läuft schon“ und die Herkunft ``ki`` der
Daten unverändert. ``direkt`` gilt nur für Abläufe, die nichts schreiben (kein schreibendes
Werkzeug, kein Auftrag, kein Upload) — sonst bleibt es ein Vorschlag, und die Prüfung meldet es.
"""

from __future__ import annotations

import pytest

from boerdi.api.publikum import antwort_fuer
from boerdi.api.schemas import ChatResponse, DebugInfo
from boerdi.api.schemas_ui import UiInfo
from boerdi.domain.config_models.ablauf import Ausloeser
from boerdi.services.ablauf import ausloeser, pruefung, vorschlag
from tests.test_ablauf_vorschlag import _SCHRITTE, _roh

_UPLOAD = [{"id": "u", "typ": "modul", "modul": "ui_upload"}, {"id": "e", "typ": "ende"}]


@pytest.fixture
def katalog(monkeypatch):
    eintraege: list = []
    monkeypatch.setattr(ausloeser, "_roh_liste", lambda: eintraege)
    return eintraege


def _direkt(id_, schritte=None, **mehr):
    return _roh(id_, schritte=schritte or _SCHRITTE,
                ausloeser=[{"art": "agent", "modus": "direkt"}], **mehr)


def test_das_modell_kennt_direkt():
    assert Ausloeser(art="agent", modus="direkt").modus == "direkt"
    assert Ausloeser(art="agent").modus == "vorschlagen"


def test_ein_direkter_ablauf_quittiert_anders(katalog):
    katalog += [_direkt("baum"), _roh("vorschlag")]
    assert vorschlag.merken([], "ablauf-baum", {}) == vorschlag.QUITTUNG_DIREKT
    assert vorschlag.merken([], "ablauf-vorschlag", {}) == vorschlag.QUITTUNG
    assert vorschlag.ist_quittung(vorschlag.QUITTUNG_DIREKT)


def test_der_direktknopf_ist_der_knopf_des_vorschlags(katalog):
    katalog += [_direkt("baum"), _roh("vorschlag")]
    [knopf] = vorschlag.schnellantworten([{"ablauf": "baum"}], "de")
    assert vorschlag.direkt_knopf([{"ablauf": "baum"}], "de") == knopf
    assert vorschlag.direkt_knopf([{"ablauf": "vorschlag"}], "de") is None
    assert vorschlag.direkt_knopf(None, "de") is None


def test_ein_schreibender_ablauf_startet_nie_direkt(katalog):
    katalog.append(_direkt("upload", schritte=_UPLOAD))
    assert vorschlag.merken([], "ablauf-upload", {}) == vorschlag.QUITTUNG
    assert vorschlag.direkt_knopf([{"ablauf": "upload"}], "de") is None


def test_die_pruefung_meldet_direkt_bei_einem_schreibenden_ablauf(katalog):
    from boerdi.domain.config_models.ablauf import AblaufArea

    roh = _direkt("upload", schritte=_UPLOAD)
    befunde = pruefung.pruefe(AblaufArea.model_validate(roh), "de")
    assert any("direkt" in b for b in befunde)
    assert not any("direkt" in b for b in pruefung.pruefe(
        AblaufArea.model_validate(_direkt("baum")), "de"))


def test_die_antwort_traegt_den_direktstart_nur_wenn_der_knopf_steht():
    knopf = "__action__|Baum|ablauf_starten|{}"
    zustand = {vorschlag.DIREKT_KEY: knopf}
    assert vorschlag.direkt_fuer_antwort(zustand, [knopf, "Mehr"]) == knopf
    assert vorschlag.DIREKT_KEY not in zustand                      # gilt nur für diesen Zug
    zustand = {vorschlag.DIREKT_KEY: "__action__|Baum|ablauf_starten|{}"}
    assert vorschlag.direkt_fuer_antwort(zustand, ["Mehr"]) is None  # gekürzt: kein Start
    assert vorschlag.direkt_fuer_antwort({}, ["Mehr"]) is None


def test_der_direktstart_reist_bis_zur_api_grenze():
    resp = ChatResponse(session_id="s", content="Ich starte den Ablauf.",
                        quick_replies=["__action__|Baum|ablauf_starten|{}"],
                        debug=DebugInfo(),
                        ui=UiInfo(direkt_start="__action__|Baum|ablauf_starten|{}"))
    assert antwort_fuer(resp, intern=False).ui.direkt_start == "__action__|Baum|ablauf_starten|{}"


async def test_die_zusammenstellung_merkt_den_direktknopf(katalog):
    from tests.test_turn_assembly import _call

    katalog.append(_direkt("baum"))
    zustand = {"entities": {}, vorschlag.SITZUNG_KEY: [{"ablauf": "baum"}]}
    _cards, qrs, *_ = await _call(session_state=zustand)
    assert zustand[vorschlag.DIREKT_KEY] == qrs[0]
    zustand = {"entities": {}, vorschlag.SITZUNG_KEY: [{"ablauf": "baum"}]}
    await _call(session_state=zustand, _qr_mode="none")              # unter einer Frage nie
    assert vorschlag.DIREKT_KEY not in zustand


# ── Review TB-E3 ──────────────────────────────────────────────────────────────────────────────

def test_review_1_die_beschreibung_eines_direkten_ablaufs_sagt_dass_er_startet(katalog):
    katalog += [_direkt("baum"), _roh("vorschlag")]
    beschreibungen = {w["function"]["name"]: w["function"]["description"]
                      for w in vorschlag.werkzeuge("de")}
    assert "von selbst" in beschreibungen["ablauf-baum"]
    assert "startet nichts" not in beschreibungen["ablauf-baum"]
    assert "startet nichts" in beschreibungen["ablauf-vorschlag"]


def test_review_2_die_muster_schleife_nimmt_einen_direkten_vorschlag_an(katalog):
    from types import SimpleNamespace

    katalog.append(_direkt("baum"))
    aufruf = SimpleNamespace(id="c1", function=SimpleNamespace(name="ablauf-baum", arguments="{}"))
    zustand: dict = {}
    nachrichten: list = []
    abgewiesen: set = set()
    erledigt, stillstand = vorschlag.nimm_an([aufruf], {"ablauf-baum"}, zustand, nachrichten,
                                             abgewiesen=abgewiesen)
    assert erledigt == {"c1"} and stillstand is False
    assert nachrichten[0]["content"] == vorschlag.QUITTUNG_DIREKT
    assert abgewiesen == set()          # angenommen, nicht als abgewiesen gezählt


def test_review_3_ein_agent_schritt_mit_upload_schreibt(katalog):
    from boerdi.domain.config_models.ablauf import AblaufArea
    from boerdi.services.ablauf import werkzeuge

    schritte = [{"id": "k", "typ": "agent", "agent": {"werkzeuge": ["ui_upload"]},
                 "text": {"de": "Lade hoch."}}, {"id": "e", "typ": "ende"}]
    ablauf = AblaufArea.model_validate(_direkt("upload", schritte=schritte))
    assert werkzeuge.ablauf_schreibt(ablauf)
    katalog.append(_direkt("upload", schritte=schritte))
    assert vorschlag.direkt_knopf([{"ablauf": "upload"}], "de") is None


def test_review_4_die_api_grenze_streicht_einen_knopf_der_nicht_mehr_steht():
    resp = ChatResponse(session_id="s", content="Los.", quick_replies=["Mehr"], debug=DebugInfo(),
                        ui=UiInfo(direkt_start="__action__|Baum|ablauf_starten|{}"))
    assert antwort_fuer(resp, intern=False).ui.direkt_start is None


def test_review_8_direkt_an_einem_anderen_ausloeser_hat_einen_eigenen_befund():
    from boerdi.domain.config_models.ablauf import AblaufArea

    roh = _roh("knopf", ausloeser=[{"art": "knopf", "modus": "direkt"}])
    befunde = pruefung.pruefe(AblaufArea.model_validate(roh), "de")
    assert any("nur am Auslöser agent" in b for b in befunde)
