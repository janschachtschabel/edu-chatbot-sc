"""Paket 16, C9: der RAG-Bereich „Plattformwissen" folgt dem Domänen-Dokument in Fassung 2.0.

Die Agent-Schleife liest die Domänen-Schicht (`02-domain/wlo-plattform-wissen.md`) nicht — sie
erfährt die Plattform-Fakten aus diesem RAG-Bereich. Der stand auf Fassung 1.0 (Umlaute als
ue/oe, CRLF); jetzt trägt er die Kernzahlen und FAQs der 2.0 und behält, was nur 1.0 hatte
(Lösungen, Mitmachen, FAQs je Zielgruppe).
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

_SEEDS = Path(__file__).resolve().parents[1] / "seeds"


def _zeilen() -> list[dict]:
    text = (_SEEDS / "rag" / "Plattformwissen.jsonl").read_text(encoding="utf-8")
    return [json.loads(z) for z in text.splitlines() if z.strip()]


def test_traegt_die_kernzahlen_und_faqs_der_fassung_2():
    alles = "\n".join(z["content"] for z in _zeilen())
    for fakt in ("316.865", "25.178 geprüfte Inhalte in 2.970 Themensammlungen",
                 "29 Fachportale", "metaVentis", "Was sind Themenseiten?", "Wie wird geprüft?"):
        assert fakt in alles, fakt


def test_behaelt_was_nur_fassung_1_hatte():
    alles = "\n".join(z["content"] for z in _zeilen())
    for abschnitt in ("Metadata Refiner", "KI-Partnerprojekt", "FAQs — Redakteur:innen"):
        assert abschnitt in alles, abschnitt


def test_ist_ein_sauberer_bereich():
    zeilen = _zeilen()
    assert {z["area"] for z in zeilen} == {"Plattformwissen"}
    assert [z["chunk_index"] for z in zeilen] == list(range(len(zeilen)))
    assert len({(z["source"], z["title"]) for z in zeilen}) == 1   # ein Dokument
    for z in zeilen:
        assert "�" not in z["content"] and "\r" not in z["content"]
        assert 100 < len(z["content"]) < 1500


def test_die_agent_schleife_liest_den_bereich_ausdruecklich():
    rag = yaml.safe_load((_SEEDS / "05-knowledge" / "rag-config.yaml").read_text(encoding="utf-8"))
    assert rag["Plattformwissen"]["agent"] is True
    assert rag["Plattformwissen"]["description"].strip()
