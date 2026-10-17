"""Eigene Hinweise in Nutzerrolle steuern nicht die Antwortsprache (Paket 9).

Review Paket 7 (MINOR 37): die Sprachregel lautet „antworte in der Sprache, in der
die Person schreibt“ (K2). Drei unserer Hinweise stehen deutsch in der Rolle
``user`` — die Abschlussbitte des Agenten, die Korrektur der Werkzeugschleife und
die Zusammenfassungsbitte am Iterationsdeckel. Ein englisches Gespräch kippte so
womöglich ins Deutsche. Jeder trägt jetzt den Satz, dass er nicht von der Person kommt.
"""

from __future__ import annotations

from boerdi.i18n.prompt_language import SPRACHE_DER_PERSON


def test_die_abschlussbitte_des_agenten():
    from boerdi.services.agent_abschluss import ABSCHLUSS_BITTE as _ABSCHLUSS_BITTE

    assert _ABSCHLUSS_BITTE.endswith(SPRACHE_DER_PERSON)


def test_die_zusammenfassungsbitte_am_iterationsdeckel():
    from boerdi.services.tool_loop_fallback import ZUSAMMENFASSUNG_BITTE

    assert ZUSAMMENFASSUNG_BITTE.endswith(SPRACHE_DER_PERSON)


def test_die_korrektur_der_werkzeugschleife(monkeypatch):
    from tests.test_tool_loop import _resp_text, _run_loop

    _fake, _result, st = _run_loop(monkeypatch, [
        _resp_text("first"), _resp_text("second"),
    ], pattern_output={"force_tool_use": True, "tools": ["search_wlo_content"]})
    korrektur = [m for m in st["messages"] if m.get("role") == "user"][-1]["content"]
    assert korrektur.startswith("⚠ KORREKTUR") and korrektur.endswith(SPRACHE_DER_PERSON)
