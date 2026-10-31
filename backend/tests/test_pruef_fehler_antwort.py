"""Paket 19 (N-5): eine 422 spiegelt die Eingabe nicht zurück.

FastAPIs Standard-Antwort auf einen Prüffehler trägt je Eintrag ``input`` (bei ``/api/chat`` die
ganze Nachricht) und ``ctx``. Die Antwort läuft durch Proxys (b-api, Team 6), die Rümpfe
protokollieren können. Es bleiben Ort, Art, Satz und aus ``ctx`` die Grenzen des Schemas — das
Studio baut daraus „Mindestens 1.“ (``field-problems.ts``, ``NEEDS``).
"""

from __future__ import annotations

from typing import Literal

from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from boerdi.main import create_app


class _Rumpf(BaseModel):
    message: str
    stufe: int = Field(default=1, ge=1)
    art: Literal["a", "b"] = "a"
    name: str = Field(default="", max_length=3)


def _app() -> TestClient:
    app = create_app()

    @app.post("/probe-422")
    def _probe(rumpf: _Rumpf) -> dict:
        return {}

    return TestClient(app)


def test_die_422_nennt_ort_art_und_satz_ohne_eingabe() -> None:
    antwort = _app().post("/probe-422", json={"message": ["Mein geheimer Text"], "stufe": 0})
    assert antwort.status_code == 422
    assert "geheimer" not in antwort.text
    eintraege = antwort.json()["detail"]
    assert {tuple(e["loc"]) for e in eintraege} == {("body", "message"), ("body", "stufe")}
    for eintrag in eintraege:
        assert "input" not in eintrag
        assert set(eintrag) <= {"loc", "type", "msg", "ctx"}, eintrag
        assert eintrag["type"] and eintrag["msg"]


def test_die_grenzen_des_schemas_bleiben_fuers_studio() -> None:
    """Review 19-1: das Studio liest ``ctx`` (``ge``/``le``/``gt``/``lt``/``expected``) — ohne
    stünde am Feld nur die englische Meldung des Servers."""
    antwort = _app().post("/probe-422", json={
        "message": "x", "stufe": 0, "art": "geheim", "name": "geheimname"})
    assert antwort.status_code == 422
    assert "geheim" not in antwort.text
    ctx = {e["loc"][-1]: e.get("ctx") for e in antwort.json()["detail"]}
    assert ctx["stufe"] == {"ge": 1}
    assert ctx["art"] == {"expected": "'a' or 'b'"}
    assert ctx["name"] == {"max_length": 3}


def test_auch_ein_kaputter_rumpf_kommt_nicht_zurueck() -> None:
    """Bei kaputtem JSON steht in ``ctx.error`` die Stelle samt Text — sie geht nicht hinaus."""
    antwort = _app().post("/probe-422", content=b'{"message": "geheim',
                          headers={"Content-Type": "application/json"})
    assert antwort.status_code == 422
    assert "geheim" not in antwort.text
    assert [set(e) for e in antwort.json()["detail"]] == [{"loc", "type", "msg"}]
