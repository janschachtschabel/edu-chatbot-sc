"""Ein Zug mit bestätigter Person — wie nach ``wlo_auth_status`` (Paket 10, Kurzaudit A-1).

Seit Paket 10 genügt die Form eines Blocks nicht mehr; ``has_personal_auth`` will die
Bestätigung des MCP-Servers. Tests, die den Block direkt setzen statt über einen
Endpunkt, holen sie hier nach. Die Kennung ist der Fingerabdruck des Blocks — wie
die Netz-Attrappe in ``conftest``.
"""

from __future__ import annotations

from boerdi.services.mcp import auth


def als_person(block: str | None) -> bool:
    """Block übernehmen und, wenn er eine Person meinen kann, als Person bestätigen."""
    gilt = auth.set_turn_auth_block(block)
    if auth.zug_block_wirkt_persoenlich():
        auth.setze_bestaetigung(person=True, kennung=f"p:{auth.caller_fingerprint()}")
    return gilt
