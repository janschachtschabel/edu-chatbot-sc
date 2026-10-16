"""Die Werkzeugliste des Agenten mit ihren Sperren — für das Studio (ST-8b).

Bis hier stand nirgends, welche Werkzeuge der Agent in einem Chat-Zug bekommt
und was ihm eines davon nehmen kann. Einzelne Werkzeuge nehmen ihm drei Stellen:
das Regex-Gate bei persönlichen Daten in der Nachricht, die Policy-Regeln
(``block_tools``) und der ``tool-mode`` der Einbettung. Diese Liste setzt sie
nebeneinander, gebaut aus denselben Quellen wie der Zug: dem Katalog von
``build_agent_tools``, der Sperrliste des Gates und den gepflegten Bereichen. Sie
ändert nichts und hat keine eigene Einstellung — jede Sperre wird weiter dort
gepflegt, wo sie wirkt.

**Krise, Drohung und die harte Sperre der Moderation stehen nicht darin**
(Review-Befund 2026-09-27). Sie erzwingen ein Schutzmuster, und dann antwortet
nicht die Schleife (SF-1, ``engine_choice.zug_laeuft_ueber_die_schleife``) — der
Zug hat gar kein Agent-Werkzeug. Ihre Sperrlisten (``SPERRE_KRISE``,
``crisis_blocked_tools``) daneben zu nennen hieße, die Schleife liefe mit dem
Rest weiter. Das Studio sagt es über der Tabelle.

**„Angeboten" meint einen gewöhnlichen Chat-Zug:** ohne Sicherheitsbefund, ohne
Policy-Treffer, ohne Einschränkung der Einbettung. Die Sperren sagen, was
davon abweichen kann; ob eine davon in einem bestimmten Zug griff, steht in
dessen Spur (``safety.blocked_tools`` im Debug-Block).

Nicht dabei: ``submit_result``. Es gehört dem Auftrags-Endpunkt ``/api/agent``;
ein Chat-Zug bekommt es nie.
"""

from __future__ import annotations

from typing import Any

from boerdi.domain.host_capabilities import KURATIEREND, LESEND, erlaubt
from boerdi.domain.inline_documents import dokument_werkzeug
from boerdi.domain.result_delivery import ergebnis_werkzeug
from boerdi.services.agent_knowledge import WISSEN_SUCHEN, wissen_werkzeug
from boerdi.services.agent_tools import build_agent_tools, verborgene_werkzeuge
from boerdi.services.config_loader import load_policy_config, load_rag_config
from boerdi.services.mcp import fremdwerkzeuge
from boerdi.services.mcp.tool_defs import TOOL_DEFINITIONS
from boerdi.services.mcp.tool_defs_curation import CURATION_TOOL_DEFINITIONS
from boerdi.services.safety.regex_gate import SPERRE_PERSOENLICH
from boerdi.services.schreibrecht import schreiben_erlaubt


def _policy_sperren(cfg: dict[str, Any]) -> dict[str, list[str]]:
    """Werkzeug → Kennungen der Regeln, die es sperren (Reihenfolge der Datei).

    Ohne ``id`` heißt eine Regel wie in ``domain/policy.assess_policy``.
    """
    sperren: dict[str, list[str]] = {}
    for regel in cfg.get("rules") or []:
        wirkung = (regel or {}).get("effect") or {}
        for name in wirkung.get("block_tools") or []:
            sperren.setdefault(name, []).append(str(regel.get("id") or "policy-rule"))
    return sperren


def _sperren(name: str, art: str, policy: dict[str, list[str]],
             verborgen: frozenset[str]) -> list[dict]:
    if name in verborgen:
        # Paket 7 (S5): im Studio je MCP-Server abgeschaltet — von Haus aus
        # ``search_skill``. Dort ist es auch wieder einzuschalten.
        return [{"code": "hidden"}]
    sperren: list[dict[str, Any]] = []
    if art == "curation":
        sperren.append({"code": "needs_access"})
    modi = [modus for modus in (LESEND, KURATIEREND) if not erlaubt(name, modus)]
    if modi:
        sperren.append({"code": "tool_mode", "modes": modi})
    if name in SPERRE_PERSOENLICH or art == "external":
        sperren.append({"code": "safety_fixed", "signals": ["pii"]})
    if name in policy:
        sperren.append({"code": "policy", "rules": policy[name]})
    return sperren


def _virtuell(werkzeug: dict[str, Any] | None, name: str, angeboten: set[str],
              bedingung: str | None) -> dict[str, Any]:
    """Nicht sperrbar: ``build_agent_tools`` hängt sie nach dem Sperrfilter an."""
    return {
        "name": name, "kind": "virtual",
        "description": werkzeug["function"]["description"] if werkzeug else "",
        "offered": name in angeboten,
        "locks": [{"code": bedingung}] if bedingung else [],
    }


def werkzeugliste() -> dict[str, Any]:
    """Alle Werkzeuge eines Chat-Zugs im Agent-Modus, je mit Art und Sperren."""
    wissen = wissen_werkzeug(load_rag_config())
    # Wie im Chat-Zug (Paket 7, S4): schreibend nur mit Schreibrecht. Eine
    # Studio-Anfrage trägt keine persönliche Anmeldung — die Liste zeigt also,
    # was ein Zug ohne Anmeldung bekommt; mit Anmeldung kämen sie dazu.
    angeboten = {t["function"]["name"] for t in build_agent_tools(
        include_submit=False, include_dokument=True, wissen_tool=wissen,
        allow_curation=schreiben_erlaubt())}
    policy = _policy_sperren(load_policy_config())
    verborgen = verborgene_werkzeuge()

    zeilen: list[dict[str, Any]] = []
    # Paket 11 (E): lesende Werkzeuge fremder MCP-Server als eigene Art.
    for art, katalog in (("read", TOOL_DEFINITIONS), ("curation", CURATION_TOOL_DEFINITIONS),
                         ("external", fremdwerkzeuge.definitionen())):
        for definition in katalog:
            name = definition["function"]["name"]
            zeilen.append({
                "name": name, "kind": art,
                "description": definition["function"]["description"],
                "offered": name in angeboten,
                "locks": _sperren(name, art, policy, verborgen),
            })
    dokument = dokument_werkzeug()
    ergebnis = ergebnis_werkzeug(None)
    zeilen += [
        _virtuell(wissen, WISSEN_SUCHEN, angeboten, "knowledge_areas"),
        _virtuell(dokument, dokument["function"]["name"], angeboten, None),
        # Nur wenn der Gastgeber ein ``result_schema`` erklärt (J1).
        _virtuell(ergebnis, ergebnis["function"]["name"], angeboten, "host_schema"),
    ]
    return {"tools": zeilen}
