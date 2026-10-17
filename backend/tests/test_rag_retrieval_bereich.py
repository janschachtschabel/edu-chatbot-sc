"""``01-base/rag-retrieval`` im Studio pflegbar (Paket 7, P4 — ST-5 Befund 2, P5-4).

Die Werte der Wissenssuche (``top_k``, ``min_score``, ``max_chars_per_area``)
wurden aus diesem Bereich gelesen (``rag/retrieval.get_retrieval_settings``),
der Bereich hatte aber kein Modell: im Studio nicht pflegbar, nur über den
Rohtext — und ein falscher Wert fiel still auf die Vorgabe zurück. Leer gilt
weiter die Vorgabe des Codes, und eine gesetzte Umgebungsvariable geht vor.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from boerdi.domain.area_effects import AREA_EFFECTS
from boerdi.domain.config_models import AREA_MODELS
from boerdi.domain.config_models.knowledge import RagRetrievalArea
from boerdi.services.rag import retrieval

_UMGEBUNG = ("RAG_TOP_K", "RAG_MIN_SCORE", "RAG_MAX_CHARS_PER_AREA")


def test_der_bereich_ist_registriert_und_wirkt_in_beiden_modi():
    assert AREA_MODELS["01-base/rag-retrieval"] is RagRetrievalArea
    assert AREA_EFFECTS["01-base/rag-retrieval"] == {"pattern": "voll", "agent": "voll"}


def test_das_modell_nimmt_was_der_leser_nimmt():
    gelesen = RagRetrievalArea.model_validate(
        {"retrieval": {"top_k": 8, "min_score": 0.25, "max_chars_per_area": 0}})
    assert gelesen.retrieval.top_k == 8
    assert RagRetrievalArea().retrieval.top_k is None   # leer = Vorgabe


@pytest.mark.parametrize("falsch", [
    {"top_k": 0}, {"min_score": 1.5}, {"max_chars_per_area": -1},
])
def test_das_modell_weist_ab_was_der_leser_still_verwarf(falsch):
    with pytest.raises(ValidationError):
        RagRetrievalArea.model_validate({"retrieval": falsch})


def test_studio_wert_wirkt_und_die_umgebung_geht_vor(monkeypatch):
    for name in _UMGEBUNG:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(retrieval, "area", lambda key: (
        {"retrieval": {"top_k": 7, "min_score": 0.4}} if key == "01-base/rag-retrieval" else {}))
    werte = retrieval.get_retrieval_settings()
    assert (werte["top_k"], werte["min_score"]) == (7, 0.4)
    assert werte["max_chars_per_area"] == retrieval._RAG_DEFAULTS["max_chars_per_area"]
    monkeypatch.setenv("RAG_TOP_K", "12")
    assert retrieval.get_retrieval_settings()["top_k"] == 12
