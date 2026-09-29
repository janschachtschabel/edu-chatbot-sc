"""Die Deckel eines Chat-Zugs der Agent-Schleife — anonym enger (AG-6, D-9).

Jeder Client wählt die Maschine über ``X-Boerdi-Engine``, und bis hier galten
für einen anonymen Zug dieselben Deckel wie für eine angemeldete Einbettung:
nach Vorgabe bis 30 Runden, 900 s und 900 000 Token je Zug, öffentlich
auslösbar und nur vom Rate-Limit gebremst (Plan 2026-09-26 §2.3 Punkt 5).

**Minimum statt Ersatz.** Ein gesetzter anonymer Wert gilt nur, wenn er
enger ist. Wer im Studio den normalen Deckel senkt und den anonymen vergisst,
gibt anonymen Zügen sonst mehr als angemeldeten.

Eigenes Modul und nicht neben ``agent_write.enforce_write_mode``, obwohl beide
an ``has_personal_auth`` hängen: dort geht es darum, ob geschrieben werden
darf, hier darum, was ein Zug kosten darf — zwei Gründe zur Änderung.
"""

from __future__ import annotations

from boerdi.domain.config_models.engine import AgentLimits, AnonymousLimits
from boerdi.services.mcp.auth import has_personal_auth


def fuer_diesen_zug(limits: AgentLimits) -> AgentLimits:
    """Die Deckel dieses Zugs: mit angemeldeter Person unverändert, sonst je
    Deckel das Minimum aus normalem und anonymem Wert.

    Nur die drei deklarierten Deckel zählen (Review 2026-09-26): das Modell
    lässt Zusatzfelder durch (``extra="allow"``), und ein ``write_mode`` unter
    ``anonymous`` hätte über den Vergleich ``"execute" < "propose"`` sonst die
    Schreibregel gelockert; ein vertippter Name hätte jeden anonymen Zug
    gesprengt."""
    if has_personal_auth():
        return limits
    enger = {
        name: wert for name in AnonymousLimits.model_fields
        if (wert := getattr(limits.anonymous, name)) is not None
        and wert < getattr(limits, name)
    }
    return limits.model_copy(update=enger) if enger else limits
