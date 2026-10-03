"""Token-Streaming im Chat-Zug: Strom öffnen oder sperren (Plan
``docs/plans/2026-10-01-token-streaming.md``, T11 und T22).

``on_token`` ist ein :class:`~boerdi.services.token_stream.TokenStrom`, wenn
``api/chat._stream_turn`` mit eingeschaltetem ``CHAT_TOKEN_STREAMING`` läuft —
sonst ``None`` (``POST /api/chat``, Eval, Tests). Vor der Antwortrunde entscheidet
:func:`~boerdi.domain.stream_gate.sperrgrund`, ob der Zug streamt.

Die Umformung der Vorschau folgt der Endverarbeitung der jeweiligen Maschine,
soweit sie nur vom Text abhängt und schon vor der Antwortrunde feststeht. Alles
Weitere richtet ``result`` am Ende.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from boerdi.domain.antwort_werkzeug import inline_anzahl
from boerdi.domain.skill_ansagen import mit_master_ansage
from boerdi.domain.skill_precedence import mit_ladehinweis, mit_ladehinweisen
from boerdi.domain.stream_gate import sperrgrund
from boerdi.domain.url_helpers import _extract_web_links_from_text
from boerdi.graph.state import TurnContext
from boerdi.services.token_stream import TokenStrom
from boerdi.settings import get_settings


def _links_zu_labels(ctx: TurnContext, text: str) -> str:
    """Links → Label nur, wo die Endverarbeitung es auch tut: mit Ergebnis-Gruppen
    (``services/turn_links``, ``_grouping_on_impl`` — das ist genau
    ``inline_result_grouping is not False``). Sonst bleiben sie Links (Review L3)."""
    if getattr(ctx.req.environment, "inline_result_grouping", None) is False:
        return text
    return _extract_web_links_from_text(text, cards=None)[0]


def _oeffnen_oder_sperren(strom: TokenStrom, ctx: TurnContext, *, antwort_werkzeug: bool,
                          muster: str, umformen: Callable[[str], str]) -> TokenStrom | None:
    grund = sperrgrund(
        eingeschaltet=get_settings().chat_token_streaming,
        antwort_werkzeug=antwort_werkzeug,
        muster_id=muster,
        risiko=ctx.safety.risk_level,
    )
    if grund:
        strom.sperren(grund, muster=muster)
        return None
    strom.oeffnen(umformen, muster=muster)
    return strom


def strom_fuer_muster_zug(on_token: Any, ctx: TurnContext,
                          pattern_output: dict[str, Any]) -> TokenStrom | None:
    """Der Strom für die Antwortrunde des Muster-Zugs — oder ``None``.

    Umformung wie die Endverarbeitung: die Ansage-Zeile einer in diesem Zug
    geholten Anleitung (``respond``, ``mit_ladehinweis``), dann Links → Label
    (``services/turn_links``).
    """
    if not isinstance(on_token, TokenStrom):
        return None
    session_state = ctx.session_state

    def umformen(text: str) -> str:
        # ``entities`` bei jedem Aufruf gelesen: eine in der Schleife geholte
        # Anleitung steht so rechtzeitig vorne.
        mit_ansage = mit_ladehinweis(
            text, session_state.get("entities"), session_state.get("turn_count"))
        return _links_zu_labels(ctx, mit_ansage)

    return _oeffnen_oder_sperren(
        on_token, ctx, antwort_werkzeug=inline_anzahl(pattern_output) > 0,
        muster=ctx.winner_id or "", umformen=umformen)


def strom_fuer_agent_zug(on_token: Any, ctx: TurnContext, *,
                         antwort_werkzeug: bool) -> TokenStrom | None:
    """Der Strom für den Agent-Zug — oder ``None``.

    ``antwort_werkzeug``: ob ``respond_to_user`` im Angebot ist (nur mit
    ``AGENT_INLINE_QUICK_REPLIES``). Umformung wie der Abschluss in
    ``respond_agent``: Modell-Ansagen weg, die Master-Ansage voran, Links → Label.
    """
    if not isinstance(on_token, TokenStrom):
        return None
    zeile = ctx.master_skill_zeile
    entities = (ctx.session_state or {}).get("entities")

    def umformen(text: str) -> str:
        # simplify: die Anleitungs-Ansagen DIESES Laufs fehlen hier — ihre Liste
        # entsteht erst im Lauf (``AgentRun.anleitungen``). Folge: Drift am Ende,
        # sichtbar in der Logzeile. Upgrade-Pfad: die Schleife reicht die Liste
        # an die Umformung weiter.
        ohne_modell_ansagen = mit_ladehinweisen(text, [])
        # Eine Kopie: ``mit_master_ansage`` merkt sich in ``entities``, dass
        # angesagt wurde. Die Vorschau darf das der Endverarbeitung nicht
        # vorwegnehmen — sonst fehlte die Zeile in der fertigen Antwort.
        kopie = dict(entities) if isinstance(entities, dict) else entities
        mit_master = mit_master_ansage(ohne_modell_ansagen, zeile, kopie)
        return _links_zu_labels(ctx, mit_master)

    return _oeffnen_oder_sperren(on_token, ctx, antwort_werkzeug=antwort_werkzeug,
                                 muster="AGENT", umformen=umformen)
