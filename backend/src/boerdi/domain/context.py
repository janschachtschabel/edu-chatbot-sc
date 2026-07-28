"""Context-Layer (T-04/05 aus Triple-Schema v2).

Baut eine formalisierte ``ContextSnapshot`` aus den Roh-Eingaben (env, session,
classification, memories). Zentralisiert, was in ALT über ``chat.py`` verstreut
war.

1:1-Port aus ALT ``app/services/context_service.py`` (reine Aggregation → Domäne,
kein I/O — einziger Import ist das ``ContextSnapshot``-Schema). Deviation ggü.
ALT: nur der Import-Pfad + die Prosa (Docstring/Kommentar) ins Deutsche; der Code
ist byte-identisch.
"""

from __future__ import annotations

from typing import Any

from boerdi.api.schemas import ContextSnapshot


def build_context(
    env: dict[str, Any],
    session_state: dict[str, Any],
    classification: Any | None = None,
    memories: list[dict] | None = None,
) -> ContextSnapshot:
    """Aggregiere die Request-Eingaben zu einer einzelnen ``ContextSnapshot``."""
    snap = ContextSnapshot(
        page=env.get("page", "/"),
        device=env.get("device", "desktop"),
        locale=env.get("locale", "de-DE"),
        session_duration=int(env.get("session_duration", 0) or 0),
        turn_count=int(session_state.get("turn_count", 0) or 0),
        entities={
            k: v for k, v in (session_state.get("entities") or {}).items()
            if not k.startswith("_")  # interne Scratchpad-Keys verbergen
        },
        recent_signals=list((session_state.get("signal_history") or [])[-10:]),
        memory_keys=[m.get("key", "") for m in (memories or [])][:10],
    )
    if classification is not None:
        snap.last_intent = getattr(classification, "intent_id", "") or ""
        snap.last_state = getattr(classification, "next_state", "") or ""
    return snap
