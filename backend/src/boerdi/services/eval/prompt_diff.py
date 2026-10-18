"""Text-Unterschied zweier Prompt-Fassungen (Paket 13, D4).

Der Vergleich (``vergleich_v2``) nennt je geändertem Baustein die Prüfsummen beider Läufe; hier
kommen die Texte aus ``prompt_versions`` (``prompt_ablage``) und werden als Unified Diff
gegenübergestellt — so sieht man, *was* sich am Master-Skill oder Agent-Kopf änderte.
"""

from __future__ import annotations

import difflib
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from boerdi.db.models import PromptVersion


def text_diff(alt: str, neu: str) -> list[str]:
    """Unified-Diff-Zeilen (3 Zeilen Kontext); gleiche Texte geben eine leere Liste."""
    return list(difflib.unified_diff(alt.splitlines(), neu.splitlines(),
                                     fromfile="a", tofile="b", lineterm=""))


def _kopf(row: PromptVersion) -> dict[str, Any]:
    return {"hash": row.hash, "art": row.art,
            "erstmals": row.erstmals.isoformat() if row.erstmals else None,
            "zuletzt": row.zuletzt.isoformat() if row.zuletzt else None}


async def prompt_diff(session: AsyncSession, a: str, b: str) -> dict[str, Any]:
    """Beide Fassungen (Kopfdaten) und ihr Unterschied; 404, wenn eine fehlt."""
    rows = (await session.execute(
        select(PromptVersion).where(PromptVersion.hash.in_([a, b])))).scalars().all()
    by_hash = {row.hash: row for row in rows}
    if a not in by_hash or b not in by_hash:
        raise HTTPException(404, "prompt version not found")
    alt, neu = by_hash[a], by_hash[b]
    return {"a": _kopf(alt), "b": _kopf(neu), "gleiche_art": alt.art == neu.art,
            "diff": text_diff(alt.text, neu.text)}
