"""T1 (Paket 7, Nutzer-Entscheid 2026-10-09: „RAG neben der Klassifikation“).

Die Einbettung der Nachricht läuft im Muster-Weg neben der Klassifikation
(``graph/nodes/assess``); der Abruf nach der Musterwahl spart sich dann den
Aufruf. Gemessen 2026-10-09 (OpenAI direkt, warm): Einbettung 0,28–1,0 s, die
ganze Suche 0,9–1,2 s. Nur die Einbettung, nicht die ganze Suche: das
Nachsortieren ist CPU-Arbeit, und die meisten Muster (die Suchmuster) nehmen
kein RAG — es liefe dort umsonst und nähme dem echten Abruf die Kerne.
"""

from __future__ import annotations

import asyncio
import logging

from boerdi.services.rag import vorab


def _wire(monkeypatch, *, rag=None, backend="api", embed=None):
    aufrufe: list[tuple[str, str]] = []

    async def _embed(text, *, kind="query"):
        aufrufe.append((text, kind))
        if embed is not None:
            return await embed(text)
        return [0.1, 0.2]

    monkeypatch.setattr(vorab, "load_rag_config", lambda: rag if rag is not None else {
        "FAQ": {"mode": "always"}, "Recht": {"mode": "on-demand"}})
    monkeypatch.setattr(vorab, "embed_backend", lambda: backend)
    monkeypatch.setattr(vorab, "embed_text", _embed)
    return aufrufe


def test_mit_always_bereich_wird_die_nachricht_eingebettet(monkeypatch):
    aufrufe = _wire(monkeypatch)
    out = asyncio.run(vorab.rag_einbettung_vorab("Was ist WLO?"))
    assert out == ("Was ist WLO?", [0.1, 0.2])
    assert aufrufe == [("Was ist WLO?", "query")]


def test_ohne_always_bereich_wird_nichts_eingebettet(monkeypatch):
    """Ohne ``mode: always`` holt der Muster-Weg nichts vorab — nur auf Zuruf
    des Modells, dann mit dessen eigener Suchanfrage statt der Nachricht."""
    aufrufe = _wire(monkeypatch, rag={"Recht": {"mode": "on-demand"}})
    assert asyncio.run(vorab.rag_einbettung_vorab("Was ist WLO?")) is None
    assert aufrufe == []


def test_lokale_einbettung_wird_nicht_vorab_gerechnet(monkeypatch):
    """Lokal ist die Einbettung CPU-Arbeit im selben Pool wie das Nachsortieren —
    vorab gerechnet stünde sie bei den vielen Zügen ohne RAG nur im Weg."""
    aufrufe = _wire(monkeypatch, backend="local")
    assert asyncio.run(vorab.rag_einbettung_vorab("Was ist WLO?")) is None
    assert aufrufe == []


def test_ein_fehler_kostet_nichts(monkeypatch, caplog):
    """Vorarbeit darf den Zug nicht kosten — der Abruf bettet dann selbst ein."""
    async def _kaputt(_text):
        raise RuntimeError("Einbettung weg")

    _wire(monkeypatch, embed=_kaputt)
    with caplog.at_level(logging.WARNING):
        assert asyncio.run(vorab.rag_einbettung_vorab("Was ist WLO?")) is None
    assert "Einbettung vorab" in caplog.text


def test_passt_nur_auf_denselben_text():
    einbettung = ("Was ist WLO?", [0.1])
    assert vorab.vektor_fuer(einbettung, "Was ist WLO?") == [0.1]
    assert vorab.vektor_fuer(einbettung, "Etwas anderes") is None
    assert vorab.vektor_fuer(None, "Was ist WLO?") is None
