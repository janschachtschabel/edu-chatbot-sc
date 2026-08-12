"""Erreicht überhaupt ein Muster die eingelesenen RAG-Korpora? (F1, 2026-08-10)

Gemessen 2026-08-10 gegen die laufende Entwicklungs-Datenbank: 906 Bruchstücke
in **acht** Korpora. Über den echten Resolver ``_resolve_rag_areas`` erreichbar
waren davon **zwei** — ``WissenLebtOnline`` (M04) und ``Plattformwissen``
(M04, M15). Die übrigen sechs, zusammen **650 Bruchstücke (72 %)**, konnte kein
Muster abfragen:

    OER-Wissen 231 · ITSJOINTLY-Schlussbericht 175 · WirLernenOnline 93 ·
    Edu-Sharing-Network 68 · Edu-Sharing-Metaventis 53 · FAQ 30

Am deutlichsten bei M04: sein eigenes ``when_to_use`` nennt „Bildungs-,
Plattform- und OER-Themen", aber der Korpus **`OER-Wissen`** — der
zweitgrösste — lag ausserhalb seiner Reichweite. Auf „Was bedeutet OER?"
antwortete der Bot also an seinem OER-Wissen vorbei.

Ursache ist eine Drift, kein Denkfehler: der Bestand wuchs beim Neu-Einlesen
(P11 Schritt 2), die ``rag_areas`` der Muster stammen aus dem ALT-Import und
wuchsen nicht mit. ``mode: always`` in ``rag-config.yaml`` hilft dagegen nicht —
der Zweig, der es auswertet, wird nie erreicht, weil jedes RAG-Muster seine
Bereiche ausdrücklich deklariert.

Dieser Wächter prüft die **Klasse**, nicht den Einzelfall: wer künftig einen
Korpus einliest und ihn keinem Muster zuordnet, fällt hier auf.

Kein Netz, keine Datenbank — gefahren wird über den ausgelieferten Seed.
"""

from __future__ import annotations

import pathlib

import pytest
import yaml

from boerdi.domain.pattern_engine import PatternDef, phase3_modulate
from boerdi.graph.nodes.route import _resolve_rag_areas

_SEEDS = pathlib.Path(__file__).resolve().parents[1] / "seeds"


def _rag_config() -> dict:
    return yaml.safe_load(
        (_SEEDS / "05-knowledge" / "rag-config.yaml").read_text(encoding="utf-8")
    )


def _muster() -> list[dict]:
    return [
        yaml.safe_load(p.read_text(encoding="utf-8").split("---")[1]) or {}
        for p in sorted((_SEEDS / "03-patterns").glob("*.md"))
    ]


def _abgefragte_bereiche(frontmatter: dict, rag_config: dict) -> list[str]:
    """Was der ECHTE Resolver für dieses Muster hergibt."""
    pd = PatternDef(**{
        k: v for k, v in frontmatter.items() if k in PatternDef.model_fields
    })
    out = phase3_modulate(pd, signals=[], device="desktop", entities={},
                          persona_id="P-AND")
    return _resolve_rag_areas(out, rag_config)


def test_jeder_korpus_wird_von_mindestens_einem_muster_abgefragt():
    rag_config = _rag_config()
    erreicht: set[str] = set()
    for fm in _muster():
        erreicht.update(_abgefragte_bereiche(fm, rag_config))

    unerreichbar = sorted(set(rag_config) - erreicht)
    assert unerreichbar == [], (
        f"Eingelesen, aber von keinem Muster abfragbar: {unerreichbar}. "
        "Entweder einem Muster in 'rag_areas' zuordnen oder aus "
        "rag-config.yaml entfernen — eingelesene Bruchstücke, die niemand "
        "liest, kosten Platz und täuschen Wissen vor."
    )


@pytest.mark.parametrize("korpus", ["OER-Wissen", "FAQ", "WirLernenOnline"])
def test_wissens_muster_erreicht_die_wissens_korpora(korpus):
    """M04 ist das Muster für Wissensfragen; sein ``when_to_use`` nennt
    ausdrücklich „Bildungs-/Plattform-/OER-Themen". Diese drei Korpora sind
    genau das — sie dürfen ihm nicht fehlen."""
    rag_config = _rag_config()
    m04 = next(fm for fm in _muster() if fm.get("id") == "M04")
    assert korpus in _abgefragte_bereiche(m04, rag_config)


def test_bereiche_stehen_wirklich_in_der_konfiguration():
    """Gegenrichtung: ein Tippfehler in ``rag_areas`` fällt sonst nicht auf —
    ``_resolve_rag_areas`` filtert unbekannte Namen still weg."""
    rag_config = _rag_config()
    for fm in _muster():
        for bereich in fm.get("rag_areas") or []:
            assert bereich in rag_config, (
                f"Muster {fm.get('id')} nennt den RAG-Bereich {bereich!r}, "
                "den rag-config.yaml nicht kennt — er wird still verworfen."
            )
