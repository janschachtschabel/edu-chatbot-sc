"""Safety package (3-4) — multi-stage risk assessment run BEFORE pattern
selection, independent of persona/pattern logic so it cannot be bypassed.

Public surface: ``assess_safety`` (the orchestrator). The stage modules
(``regex_gate`` / ``moderation`` / ``legal``) are package-internal — reach the
always-on backstop via ``from boerdi.services.safety.regex_gate import regex_gate``
(re-exporting the function here would shadow the same-named submodule).
"""

from boerdi.services.safety.service import assess_safety

__all__ = ["assess_safety"]
