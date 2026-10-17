"""Werte der Wissenssuche nur in ihrem Typ (Paket 9, Review Paket 7 MINOR 33).

``RagAbruf`` nahm ``"20"``, ``20.0``, ``True`` und ``"0.5"`` an — gespeichert sah
das Studio sie als gültig, der Leser verwarf sie still, und ``True`` galt dort als
``top_k = 1``.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

import boerdi.services.rag.retrieval as rr
from boerdi.domain.config_models.knowledge import RagAbruf


@pytest.mark.parametrize("feld,wert", [
    ("top_k", "20"), ("top_k", 20.0), ("top_k", True),
    ("min_score", "0.5"), ("min_score", True),
    ("max_chars_per_area", "3000"), ("max_chars_per_area", False),
])
def test_das_modell_weist_lose_typen_ab(feld, wert):
    with pytest.raises(ValidationError):
        RagAbruf.model_validate({feld: wert})


def test_gueltige_werte_bleiben():
    abruf = RagAbruf.model_validate({"top_k": 20, "min_score": 1, "max_chars_per_area": 0})
    assert (abruf.top_k, abruf.min_score, abruf.max_chars_per_area) == (20, 1.0, 0)


def test_ein_wahrheitswert_in_der_datenbank_gilt_nicht_als_eins(monkeypatch):
    """Steht schon ein loser Wert gespeichert, gilt die Vorgabe des Codes."""
    for name in ("RAG_TOP_K", "RAG_MIN_SCORE", "RAG_MAX_CHARS_PER_AREA"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(rr, "area", lambda _k: {"retrieval": {
        "top_k": True, "min_score": True, "max_chars_per_area": True}})
    assert rr.get_retrieval_settings() == dict(rr._RAG_DEFAULTS)
