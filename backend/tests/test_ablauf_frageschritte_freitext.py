"""Rückmeldung 13.11. (Ablauf „Themenbaum · aus einem Thema“): Eine getippte Antwort auf eine Frage
mit Schnellantworten („für eine Webseite über Karate“) blieb liegen. Der Schritt nahm nur die
Knöpfe an, der Text ging an die KI, und die KI kann einen Ablauf nicht weiterschalten. Der Lauf
stand bei „Schritt 2 von 6“, obwohl die KI weitere Fragen angekündigt hatte.

Regel für die Seeds: Eine Frage, deren Antwort ein Teil wird (``schreibt``), nimmt auch getippten
Text an (``freitext``). Ausgenommen sind Steuerfragen mit Ausstieg („Ohne Ablauf“). Dort ist ein
getippter Text ein Gespräch mit der KI. Ausgenommen sind auch Fragen mit ``kein_treffer`` (WF-2,
Plan 2026-11-15, etwa die Gruppenwahl der Führung): Getippter Text trifft dort über Synonyme, ein
Fehlversuch bekommt den Hinweis — ein Freitext nähme jeden Satz als Antwort. Und in Abläufen mit
``endet_bei_text`` die Wiederholung einer solchen Frage mit demselben Teil und denselben Knöpfen
(Rückmeldung 16.11., der Hilfetext der Führung): Dort beendet getippter Text ohne Treffer den Lauf
mit Absicht, wie in der Tour, und der Chat antwortet.
"""

from __future__ import annotations

import pathlib

import pytest
import yaml

from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.services.ablauf import wahl_zug

_ORDNER = pathlib.Path(__file__).parents[1] / "seeds" / "06-ablaeufe"


def _ablauf(name: str) -> AblaufArea:
    return AblaufArea.model_validate(
        yaml.safe_load((_ORDNER / f"{name}.yaml").read_text(encoding="utf-8")))


def _frage(s):
    return (s.schreibt, tuple(o.id for o in s.optionen or []))


def _frageschritte(ablauf: AblaufArea):
    ausstiege = {s.id for s in ablauf.schritte if s.typ == "ende" and s.ausstieg}
    # Review 16.11., m8: nur die Wiederholung einer Frage mit ``kein_treffer`` — nicht jede Frage
    # eines Ablaufs mit ``endet_bei_text``
    wiederholt = ({_frage(s) for s in ablauf.schritte if s.kein_treffer is not None}
                  if ablauf.endet_bei_text else set())
    for s in ablauf.schritte:
        if s.typ == "nachricht" and s.optionen and s.schreibt and s.kein_treffer is None \
                and not any(o.ziel in ausstiege for o in s.optionen) \
                and _frage(s) not in wiederholt:
            yield s


@pytest.mark.parametrize("datei", sorted(_ORDNER.glob("*.yaml")), ids=lambda p: p.stem)
def test_jede_frage_mit_teil_nimmt_auch_getippten_text(datei):
    ablauf = _ablauf(datei.stem)
    ohne = [s.id for s in _frageschritte(ablauf) if s.freitext is None]
    assert ohne == [], f"{ablauf.id}: Frage ohne freitext {ohne}"


def test_freitext_schreibt_denselben_teil_wie_die_knoepfe():
    for datei in sorted(_ORDNER.glob("*.yaml")):
        ablauf = _ablauf(datei.stem)
        for s in _frageschritte(ablauf):
            assert s.freitext is not None and s.freitext.schreibt == s.schreibt, (ablauf.id, s.id)


def test_getippter_zweck_bleibt_nicht_bei_der_ki_liegen(monkeypatch):
    """Die Nachstellung der Rückmeldung: Lauf wartet an ``wofuer``, die Person tippt."""
    ablauf = _ablauf("themenbaum_aus_thema")
    wofuer = next(s for s in ablauf.schritte if s.id == "wofuer")
    lauf = {"ablauf": ablauf.id, "schritt": "wofuer", "status": "wartet_wahl"}
    monkeypatch.setattr(wahl_zug, "_wartend", lambda _sid, _state: (lauf, ablauf, wofuer))
    assert wahl_zug.nimmt_getippt("s1", {}, "für eine Webseite über Karate")
    assert wahl_zug.nimmt_getippt("s1", {}, "Überblick über das Thema")
