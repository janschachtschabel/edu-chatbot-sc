"""Reine Entscheidungs-Helfer des Route-Kopfes (Gegenstück zu ``route_tail``).

Drei framework-freie Funktionen, die ALT im Kopf von ``_route_pattern`` bzw. in
``chat_turn_setup`` inline stehen hatte und die NEU bis A4c im Graph-Knoten
``graph/nodes/route.py`` wohnten: der Persona-Merge (R-06), die strenge
RAG-Whitelist je Pattern (Welle E) und der Memory-Prompt-Block.

**Warum sie hier stehen:** sie sind pur (stdlib, keine I/O, kein Framework) — und
diese Anwendung legt pure Logik nach ``domain/``, Orchestrierung in den Knoten.
Der Anlass war A4c: der Agent-Modus kam als dritter Grund zur Änderung in eine
Datei, die schon zwei hatte. Verhaltensgleiche Verschiebung, Zeilen unverändert;
``graph/nodes/route.py`` importiert sie zurück, damit die Namen dort weiterhin
auflösbar und in Tests patchbar bleiben (Randkonvention des Knotens).
"""

from __future__ import annotations

from typing import Any


def _resolve_rag_areas(
    pattern_output: dict[str, Any], rag_config: dict[str, Any]
) -> list[str]:
    """Strenge RAG-Whitelist je Pattern (Welle E, ALT ``_route_pattern`` Schritt 4).

    1) ``rag_areas`` gesetzt (auch leere Liste) → exakt diese, gegen die Config
       gefiltert (Tippschutz); leer bleibt leer.
    2) ``sources`` ohne ``rag`` → gar kein RAG.
    3) Default → always-on-Areas (+ on-demand, wenn ``sources`` „rag" enthält).
    """
    pattern_sources = pattern_output.get("sources")
    pattern_rag_areas = pattern_output.get("rag_areas")
    if pattern_rag_areas is not None:
        available_rag_areas = [a for a in pattern_rag_areas if a in rag_config]
    elif pattern_sources is not None and "rag" not in pattern_sources:
        available_rag_areas = []
    else:
        available_rag_areas = [
            area for area, cfg in rag_config.items() if cfg.get("mode") == "always"
        ]
        if pattern_sources is not None and "rag" in pattern_sources:
            for area, cfg in rag_config.items():
                if cfg.get("mode") == "on-demand" and area not in available_rag_areas:
                    available_rag_areas.append(area)
    return available_rag_areas


def _render_memory_context(memories: list[dict[str, Any]]) -> str:
    """Session-Erinnerungen zu einem Prompt-Block rendern (max. 10; ALT Schritt 5)."""
    mems = memories or []
    if not mems:
        return ""
    mem_parts = [f"- {m['key']}: {m['value']}" for m in mems[:10]]
    return "\nErinnerungen:\n" + "\n".join(mem_parts)


def _update_persona(session_state: dict[str, Any], classification: Any) -> None:
    """R-06: Persona einmal persistieren, bei Korrektur oder expliziter Änderung
    überschreiben (in-place auf ``session_state``, wie ALT ``chat_turn_setup``)."""
    detected = classification.persona_id
    if not session_state.get("persona_id"):
        session_state["persona_id"] = detected
    elif classification.turn_type == "correction":
        session_state["persona_id"] = detected
    elif detected != "P-AND" and detected != session_state["persona_id"]:
        session_state["persona_id"] = detected
