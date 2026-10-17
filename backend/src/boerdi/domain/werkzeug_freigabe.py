"""Welche MCP-Werkzeuge das Modell nicht bekommt — je Server gepflegt (Paket 7, S5).

Jeder Server der Registry (``05-knowledge/mcp-servers``) trägt ``werkzeuge_aus``.
Ohne Eintrag gilt die Vorgabe des Aufrufers (``search_skill`` verborgen: Skills
kommen über die Freigabeliste der Sammlung, nicht über eine freie Suche); eine
gepflegte Liste ersetzt sie, eine leere schaltet alles ein. Die Vorgabe des
Primärservers gilt auch, wenn er in der Registry fehlt — ein Werkzeug ohne
Eintrag wird über ihn geroutet (``mcp/client._get_server_url_for_tool``).

Rein: keine I/O; die Registry reicht der Aufrufer herein.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Final

#: Werkzeuge, die im Katalog stehen, aber ohne Pflege KEINEM Lauf angeboten werden.
#:
#: ``search_skill`` (Nutzer-Entscheid 2026-08-13): der Weg zu einer Anleitung
#: fuehrt ueber die Sammlung, die sie freigegeben hat. Die Definition bleibt im
#: Katalog — sie beschreibt ein Werkzeug, das der MCP-Server hat, und ein
#: Bestands-Waechter nennt sie. Seit Paket 7 (S5, Nutzer-Entscheid 2026-10-09)
#: nur noch die Vorgabe: im Studio je MCP-Server einschaltbar. Hier statt in
#: ``services/agent_tools``, seit auch das Speichern der Registry sie kennt
#: (Review A-10) — von dort aus wäre der Weg zirkulär.
VORGABE_AUS: Final = frozenset({"search_skill"})


def _gepflegt(server: Mapping[str, Any]) -> frozenset[str] | None:
    """Die gepflegte Liste — ``None`` ohne Eintrag oder bei falscher Form.

    Eine Zeichenkette statt einer Liste fiele als Folge von Buchstaben durch
    jede Prüfung und schaltete still alles frei; deshalb zählt nur eine Liste.
    """
    liste = server.get("werkzeuge_aus")
    if not isinstance(liste, list | tuple):
        return None
    return frozenset(str(name) for name in liste if name)


def wirksam_aus(server: Mapping[str, Any], *, primaer: bool,
                vorgabe: frozenset[str]) -> list[str]:
    """Die Werkzeuge, die dieser Server dem Modell vorenthält — für das Studio."""
    gepflegt = _gepflegt(server)
    if gepflegt is not None:
        return sorted(gepflegt)
    if primaer:
        return sorted(vorgabe)
    # Review Paket 11, #5: übernommene Werkzeuge eines weiteren Servers haben keine Vorgabe —
    # wie zur Laufzeit (``domain/fremdwerkzeug``).
    return sorted(vorgabe & (set(server.get("tools") or ()) - uebernommen(server)))


def uebernommen(server: Mapping[str, Any]) -> set[str]:
    """Die Namen, die ein fremder Server über „Server prüfen“ übernommen hat."""
    return {str(e.get("name")) for e in server.get("tool_schemas") or []
            if isinstance(e, Mapping) and e.get("name")}


def verborgen(servers: Iterable[Mapping[str, Any]], *, primaer_id: str,
              vorgabe: frozenset[str]) -> frozenset[str]:
    """Alle Werkzeugnamen, die kein Pfad dem Modell reicht — seit Paket 9 auch der
    Vorabruf und der Medientyp-Zweig nicht (Review Paket 7, MAJOR 11)."""
    aus: set[str] = set()
    primaer_gesehen = False
    for server in servers:
        primaer = server.get("id") == primaer_id
        primaer_gesehen = primaer_gesehen or primaer
        # Paket 11 (E): übernommene Werkzeuge eines fremden Servers stehen im eigenen
        # Namensraum (``domain/fremdwerkzeug``); ihr Schalter gilt dort, nicht hier —
        # sonst verbärge er ein gleichnamiges WLO-Werkzeug.
        eigene = set() if primaer else uebernommen(server)
        aus.update(n for n in wirksam_aus(server, primaer=primaer, vorgabe=vorgabe)
                   if n not in eigene)
    if not primaer_gesehen:
        aus.update(vorgabe)
    return frozenset(aus)


def ohne_vorgabe(server: Mapping[str, Any], *, primaer: bool,
                 vorgabe: frozenset[str]) -> dict[str, Any]:
    """``server`` ohne ``werkzeuge_aus``, wenn die Liste genau die Vorgabe ist — fürs
    Speichern (Review Paket 7, A-10).

    Das Studio zeigt die Vorgabe als Liste (:func:`wirksam_aus`). Ginge sie beim
    Speichern mit, hieße sie gepflegt: „fehlt = Vorgabe“ gälte nach dem ersten
    Speichern nicht mehr, und eine spätere Änderung der Vorgabe erreichte die
    Anlage nie. Eine leere Liste (alles eingeschaltet) bleibt — sie ist eine
    Entscheidung, keine Vorgabe.
    """
    gepflegt = _gepflegt(server)
    ohne = {k: v for k, v in server.items() if k != "werkzeuge_aus"}
    if gepflegt is None or gepflegt != frozenset(wirksam_aus(ohne, primaer=primaer,
                                                             vorgabe=vorgabe)):
        return dict(server)
    return ohne

