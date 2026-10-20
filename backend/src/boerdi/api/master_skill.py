"""Master-Skill im Studio (AG-2): anzeigen und neu laden, nicht bearbeiten.

Nutzer-Entscheid 2026-09-26: der Master-Skill kommt aus dem edu-sharing-
Repositorium, „das ist so gewollt". Das Studio zeigt, was gilt; bearbeitet wird
im md-editor des Repositoriums, auf den ``edit_url`` führt (Paket F, Nutzer
2026-09-29), ``view_url`` zeigt den Knoten. Eigener Router mit Studio-Schlüssel
und NICHT unter ``/api/agent``: jener lässt sich mit ``AGENT_OPEN`` ohne
Anmeldung öffnen, und „Neu laden" löst einen MCP-Abruf aus.
"""

from __future__ import annotations

from fastapi import APIRouter, Security

from boerdi.api.deps import require_studio_key
from boerdi.api.schemas_agent import MasterSkillStatus
from boerdi.domain.repo_links import editor_url, render_url
from boerdi.services import master_skill
from boerdi.services.config_loader import get_repo_base_url

router = APIRouter(
    prefix="/api/master-skill", tags=["agent"],
    dependencies=[Security(require_studio_key)],
)


def _mit_links(anzeige: dict) -> MasterSkillStatus:
    kennung = anzeige.get("node_id") or ""
    if not kennung:
        return MasterSkillStatus(**anzeige)
    repo = get_repo_base_url()
    return MasterSkillStatus(**anzeige, edit_url=editor_url(kennung, repo),
                             view_url=render_url(kennung, repo))


@router.get("", response_model=MasterSkillStatus)
async def master_skill_anzeigen() -> MasterSkillStatus:
    """Zustand und Wortlaut; holt den Text, wenn keiner im Speicher ist."""
    return _mit_links(await master_skill.anzeige())


@router.post("/reload", response_model=MasterSkillStatus)
async def master_skill_neu_laden() -> MasterSkillStatus:
    """Speicher verwerfen und frisch holen — wirkt sofort auf allen Kopien (Paket 17, C3:
    geteilter Stand plus Signal; ohne Signal spätestens im nächsten Takt)."""
    return _mit_links(await master_skill.neu_laden())
