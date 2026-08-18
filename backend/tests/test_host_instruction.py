"""G1 — der Anweisungs-Kanal der Gastanwendung.

Drei Ebenen, und alle drei müssen halten, sonst ist die Zusage „wirkt in allen
Maschinen" nicht wahr: der reine Block, der Deckel im Schema, und die
Verdrahtung in BEIDE Prompt-Wege (Muster ↔ Schleife).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from boerdi.api.schemas import Environment
from boerdi.domain import host_instruction


def test_ohne_anweisung_kein_block() -> None:
    # Leer heisst leer — ein Kopf ohne Inhalt wäre ein Absatz, den das Modell
    # deuten müsste.
    assert host_instruction.prompt_block(None) == ""
    assert host_instruction.prompt_block("   ") == ""


def test_block_traegt_text_und_rangfolge() -> None:
    block = host_instruction.prompt_block("  Bewerte den Füllstand.  ")
    assert "Bewerte den Füllstand." in block
    # Die Rangfolge muss IM Prompt stehen, nicht nur in der Doku: sonst weiss das
    # Modell nichts davon, dass eine Regel über der Anweisung steht.
    assert "gilt die Regel" in block
    assert "NICHT von der Person" in block


def test_zu_lange_anweisung_wird_abgewiesen() -> None:
    # Abweisen statt kürzen: eine halbierte Anweisung ist eine ANDERE Anweisung,
    # und der Gastgeber hätte keine Möglichkeit, das zu bemerken. Gleiche
    # Entscheidung wie beim `result_schema` nebenan.
    with pytest.raises(ValidationError):
        Environment(host_instruction="x" * (host_instruction.MAX_CHARS + 1))


def test_deckel_laesst_die_grenze_selbst_durch() -> None:
    env = Environment(host_instruction="x" * host_instruction.MAX_CHARS)
    assert env.host_instruction is not None


def test_vorgabe_ist_keine_anweisung() -> None:
    # Ein Zug ohne Gastgeber-Anweisung darf keinen leeren Block erzeugen.
    assert Environment().host_instruction is None
