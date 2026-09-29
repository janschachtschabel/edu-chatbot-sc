"""Die Vorschau des Prompt-Anfangs der Agent-Schleife — für das Studio (ST-8d).

Was das Modell in einem Chat-Zug zuerst liest, stand bis hier nur im Code von
``respond_agent``: der Kopf aus Rolle, Anrede, Grenzen und Sprache (AG-3), dazu
die Wissens-Regel, dahinter der Master-Skill. Die Vorschau baut diesen stabilen
Anfang aus denselben Funktionen wie der Zug — ``agent_kopf.kopf``,
``WISSENS_REGEL``, ``master_skill.prompt_block`` — und ein Test hält fest, dass
er Wort für Wort gleich bleibt.

Was je Zug dazukommt (Einbettung, Seite, Verlauf, Nachricht), hängt an Dingen,
die es im Studio nicht gibt. Die Vorschau nennt diese Blöcke deshalb nur, in der
Reihenfolge des Zugs; das Studio sagt, wann sie erscheinen.
"""

from __future__ import annotations

import json
from typing import Any, Final

from boerdi.i18n.locale import Locale
from boerdi.services import master_skill
from boerdi.services.agent_knowledge import WISSENS_REGEL, wissen_werkzeug
from boerdi.services.agent_kopf import kopf
from boerdi.services.agent_tools import build_agent_tools
from boerdi.services.config_loader import load_engine, load_rag_config

#: Was ``respond_agent`` je Zug hinter den stabilen Anfang setzt, in dessen
#: Reihenfolge. ``result_schema`` ist kein eigener Block: der Satz dazu wird an
#: den Kopf gehängt, wenn die Einbettung ein Ergebnis-Schema erklärt.
#: ``last_shown`` (Paket C): was die Person zuletzt gesehen hat — nur, wenn es
#: etwas gibt (``agent_zugblock``).
JE_ZUG: Final = (
    "result_schema", "host_capabilities", "page_context", "host_instruction",
    "skill_hints", "history", "prefetch", "last_shown", "message",
)


def _master_skill_zustand(block: str | None, zustand: dict[str, Any]) -> str:
    if block:
        return "on"
    if not zustand.get("enabled"):
        return "off"
    return "failed" if zustand.get("node_id") else "no_node"


async def prompt_vorschau(sprache: Locale) -> dict[str, Any]:
    """Kopf und Master-Skill im Wortlaut, danach die Blöcke je Zug als Kennungen."""
    einstellung = load_engine()
    wissen = wissen_werkzeug(load_rag_config())
    kopf_text = kopf(einstellung.agent_rolle, sprache) + (WISSENS_REGEL if wissen else "")
    block = await master_skill.prompt_block(None)
    zustand = master_skill.zustand()
    werkzeuge = build_agent_tools(include_submit=False, include_dokument=True, wissen_tool=wissen)
    return {
        "locale": sprache,
        "chain": [
            {"id": "head", "text": kopf_text, "chars": len(kopf_text)},
            {
                "id": "master_skill",
                "state": _master_skill_zustand(block, zustand),
                "text": block,
                "chars": len(block) if block else 0,
                "node_id": zustand.get("node_id") or "",
                "sha256": zustand.get("sha256"),
                "error": zustand.get("last_error"),
            },
            *({"id": kennung} for kennung in JE_ZUG),
        ],
        # Die Beschreibungen gehen als Werkzeug-Liste mit, nicht als Text — aber
        # sie kosten Token wie Text, jede Runde.
        "tools": {
            "count": len(werkzeuge),
            "chars": len(json.dumps(werkzeuge, ensure_ascii=False)),
        },
    }
