"""G1 — der Anweisungs-Kanal der Gastanwendung.

Drei Ebenen, und alle drei müssen halten, sonst ist die Zusage „wirkt in allen
Maschinen" nicht wahr: der reine Block, der Deckel im Schema, und die
Verdrahtung in BEIDE Prompt-Wege (Muster ↔ Schleife).
"""

from __future__ import annotations

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


def test_die_anweisung_hat_keinen_zeichendeckel_mehr() -> None:
    """Deckel entfernt (Nutzer-Entscheid 2026-08-18).

    Er lag bei 2000 Zeichen und wies mit 422 ab. Aus der Praxis gemeldet: eine
    Schritt-Anleitung ist rund 2500 Zeichen lang, und Angaben ueber die
    Gastseite sollen dazu passen. Die Begruendung des Deckels — „reist in JEDEN
    Modellaufruf des Zuges" — trifft die ``message`` genauso, und die durfte das
    Fuenffache: der Schnitt lag also nicht dort, wo die Kosten entstehen.
    """
    env = Environment(host_instruction="x" * 50_000)
    assert env.host_instruction is not None
    assert len(env.host_instruction) == 50_000


def test_vorgabe_ist_keine_anweisung() -> None:
    # Ein Zug ohne Gastgeber-Anweisung darf keinen leeren Block erzeugen.
    assert Environment().host_instruction is None
