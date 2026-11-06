"""Ein Ablauf vor dem Speichern prüfen (Paket A1, Plan 2026-11-05 §9) — Liste der Befunde, leer =
gut.

Abgewiesen wird, was der lokale Treiber nicht so ausführen kann, wie es dasteht:

- Form: 1–40 Schritte, eindeutige IDs, Ziele (``weiter``, ``dann``, ``sonst``, ``bei_fehler``),
  die es gibt; ``nachricht`` mit Text; Regeln nur bei ``verzweigung`` und dort Pflicht — jede
  Bedingung mit ``dann``, ``sonst`` genau einmal und zuletzt.
- Lauf: jeder Schritt erreichbar, kein Weg läuft ohne ``ende`` aus, keine Schleife ohne wartenden
  Schritt, höchstens :data:`RECHENSCHRITTE` Schritte bis zum nächsten Halt (so viele rechnet der
  Treiber je Zug).
- Inhalt: bekannte Module (feste Daten passend zum Vertrag, außer das Modul baut seinen Block ohne
  Modell selbst), keine schreibenden oder unbekannten Werkzeuge, Teile nur an Dienste (nicht an
  lesende WLO-Werkzeuge — Review A1, Befund 9), gültige Teilnamen, bekannte Voraussetzungen und
  Auslöser.

Die Befunde folgen der Sprache des Studios (``lang``).
"""

from __future__ import annotations

from typing import Any, Final

from boerdi.domain.config_models.ablauf import AblaufArea, Schritt
from boerdi.services.ablauf import werkzeuge
from boerdi.services.ablauf.pruefung_texte import t as _t
from boerdi.services.teil_verweise import NAME, SCHLUESSEL
from boerdi.ui_module import katalog

MAX_SCHRITTE: Final = 40
#: So viele Schritte rechnet der Treiber höchstens je Zug, bis ein Schritt wartet oder endet.
RECHENSCHRITTE: Final = 25
VORAUSSETZUNGEN: Final = frozenset({"anmeldung"})
MAX_WENDUNGEN: Final = 10
MAX_AGENT_WERKZEUGE: Final = 10
MAX_AGENT_ZUEGE: Final = 20
#: Wie ``ki_schritt.HINWEIS_ZEICHEN`` — länger würde in der Zeile abgeschnitten.
MAX_AGENT_HINWEIS: Final = 200
_MODI: Final = frozenset({"vorschlagen"})


def _verweise(wert: Any) -> list[str]:
    if isinstance(wert, dict):
        if len(wert) == 1 and isinstance(wert.get(SCHLUESSEL), str):
            return [wert[SCHLUESSEL]]
        return [n for v in wert.values() for n in _verweise(v)]
    if isinstance(wert, list):
        return [n for v in wert for n in _verweise(v)]
    return []


def _normal(ablauf: AblaufArea, i: int) -> list[str]:
    """Die regulären nächsten Schritte (ohne ``bei_fehler``; ``""`` = läuft ohne ``ende`` aus)."""
    s = ablauf.schritte[i]
    if s.typ == "ende":
        return []
    if isinstance(s.weiter, list):
        return [r.dann or r.sonst or "" for r in s.weiter]
    folgender = ablauf.schritte[i + 1].id if i + 1 < len(ablauf.schritte) else ""
    return [s.weiter or folgender]


def nachfolger(ablauf: AblaufArea, i: int) -> list[str]:
    """Die möglichen nächsten Schritte von Schritt ``i`` — der reguläre zuerst, dann
    ``bei_fehler``."""
    ziele = _normal(ablauf, i)
    s = ablauf.schritte[i]
    if s.bei_fehler and s.typ != "ende":
        ziele.append(s.bei_fehler)
    return ziele


def _wartet(s: Schritt) -> bool:
    if s.typ in ("agent", "auftrag"):
        return True
    if s.typ != "modul" or not s.modul:
        return False
    return (katalog.katalog().get(s.modul) or {}).get("art") == "abfragen"


def _regeln(s: Schritt, lang: str) -> list[str]:
    if s.typ != "verzweigung":
        return [_t(lang, "regeln_falsch", s=s.id)] if isinstance(s.weiter, list) else []
    if not isinstance(s.weiter, list) or not s.weiter:
        return [_t(lang, "regeln_fehlen", s=s.id)]
    b: list[str] = []
    for r in s.weiter:
        bedingung = r.wenn_teil is not None or r.wenn_gewaehlt is not None
        if (r.sonst is not None) == bedingung or (bedingung and not r.dann) or (
                r.sonst is not None and r.dann):
            b.append(_t(lang, "regel_dann", s=s.id))
            break
    sonst = [i for i, r in enumerate(s.weiter) if r.sonst is not None]
    if sonst != [len(s.weiter) - 1]:
        b.append(_t(lang, "sonst", s=s.id))
    return b


def _modul(s: Schritt, module: dict[str, Any], lang: str) -> list[str]:
    manifest = module.get(s.modul or "")
    if manifest is None:
        return [_t(lang, "modul", s=s.id, m=s.modul)]
    if s.modul in werkzeuge.MODUL_DIENST_OHNE_MODELL or _verweise(s.daten):
        return []
    if fehler := katalog.daten_fehler(manifest, s.daten or {}):
        return [_t(lang, "daten", s=s.id, m=s.modul, f="; ".join(fehler)[:160])]
    return []


def _schritt(s: Schritt, module: dict[str, Any], lang: str) -> list[str]:
    b: list[str] = []
    if s.typ == "nachricht" and not (s.text or {}).get("de"):
        b.append(_t(lang, "text", s=s.id))
    if s.typ == "modul":
        b += _modul(s, module, lang)
    if s.typ == "werkzeug":
        name = s.werkzeug or ""
        if werkzeuge.schreibend(name):
            b.append(_t(lang, "schreibend", s=s.id, w=name))
        elif not werkzeuge.bekannt(name):
            b.append(_t(lang, "werkzeug", s=s.id, w=name))
        elif name in werkzeuge.LESENDE_MCP and _verweise(s.argumente):
            b.append(_t(lang, "mcp_teil", s=s.id))
    if s.typ == "agent":
        b += _agent(s, module, lang)
    if s.typ == "auftrag":
        b += _auftrag(s, lang)
    b += _regeln(s, lang)
    teile = _verweise(s.daten) + _verweise(s.argumente)
    teile += [n for n in (s.schreibt, s.agent.ausgabe if s.agent else None) if n is not None]
    if isinstance(s.weiter, list):
        teile += [r.wenn_teil for r in s.weiter if r.wenn_teil is not None]
    b += [_t(lang, "teil", s=s.id, t=n) for n in teile if not NAME.match(n)]
    return b


def _auftrag(s: Schritt, lang: str) -> list[str]:
    from boerdi.services.auftraege import client

    b: list[str] = []
    if not s.flow:
        b.append(_t(lang, "auftrag_flow", s=s.id))
    elif not client.erlaubt(s.flow):
        b.append(_t(lang, "auftrag_frei", s=s.id, f=s.flow))
    if not s.schreibt:
        b.append(_t(lang, "auftrag_schreibt", s=s.id))
    return b


def agent_werkzeug(name: str, module: dict[str, Any]) -> bool:
    """Darf ein ``agent``-Schritt der KI dieses Werkzeug lassen? Lesende WLO-Werkzeuge und UI-Module
    mit Agent-Freigabe im Manifest — nie schreibende (die kämen erst mit Freigabe, Paket S)."""
    if werkzeuge.schreibend(name):
        return False
    return name in werkzeuge.LESENDE_MCP or bool((module.get(name) or {}).get("agent"))


def _agent(s: Schritt, module: dict[str, Any], lang: str) -> list[str]:
    if s.agent is None:
        return [_t(lang, "agent_fehlt", s=s.id)]
    b: list[str] = []
    if not 1 <= len(s.agent.werkzeuge) <= MAX_AGENT_WERKZEUGE:
        b.append(_t(lang, "agent_werkzeuge", s=s.id, max=MAX_AGENT_WERKZEUGE))
    for name in s.agent.werkzeuge:
        if werkzeuge.schreibend(name):
            b.append(_t(lang, "schreibend", s=s.id, w=name))
        elif not agent_werkzeug(name, module):
            b.append(_t(lang, "agent_werkzeug", s=s.id, w=name))
    if any(len(t or "") > MAX_AGENT_HINWEIS for t in (s.agent.hinweis or {}).values()):
        b.append(_t(lang, "agent_hinweis", s=s.id, max=MAX_AGENT_HINWEIS))
    if not 1 <= s.agent.zuege <= MAX_AGENT_ZUEGE:
        b.append(_t(lang, "agent_zuege", s=s.id, max=MAX_AGENT_ZUEGE))
    return b


def _schleife_ohne_halt(ablauf: AblaufArea) -> bool:
    """Gibt es einen Kreis, auf dem kein Schritt wartet?"""
    index = {s.id: i for i, s in enumerate(ablauf.schritte)}
    nachbarn = {i: [index[z] for z in nachfolger(ablauf, i) if z in index]
                for i in range(len(ablauf.schritte)) if not _wartet(ablauf.schritte[i])}
    farbe: dict[int, int] = {}

    def besuche(i: int) -> bool:
        farbe[i] = 1
        for j in nachbarn.get(i, []):
            if j not in nachbarn:
                continue
            if farbe.get(j) == 1 or (farbe.get(j) is None and besuche(j)):
                return True
        farbe[i] = 2
        return False

    return any(farbe.get(i) is None and besuche(i) for i in nachbarn)


def _laeufe(ablauf: AblaufArea, lang: str) -> list[str]:
    """Erreichbarkeit, Auslaufen ohne ``ende`` und die Länge bis zum nächsten Halt."""
    index = {s.id: i for i, s in enumerate(ablauf.schritte)}
    erreicht, offen = {0}, [0]
    while offen:
        for z in nachfolger(ablauf, offen.pop()):
            if z in index and index[z] not in erreicht:
                erreicht.add(index[z])
                offen.append(index[z])
    b = [_t(lang, "unerreichbar", s=s.id) for i, s in enumerate(ablauf.schritte)
         if i not in erreicht]
    b += [_t(lang, "auslaufen", s=ablauf.schritte[i].id) for i in sorted(erreicht)
          if "" in _normal(ablauf, i)]
    lang_bis_halt: dict[int, int] = {}

    def laenge(i: int, weg: frozenset[int]) -> int:
        """Schritte, die der Treiber ab ``i`` höchstens in einem Zug rechnet (Halt mitgezählt)."""
        if i in weg:
            return RECHENSCHRITTE + 1
        if i not in lang_bis_halt:
            s = ablauf.schritte[i]
            ziele = ([s.bei_fehler] if s.bei_fehler else []) if _wartet(s) else nachfolger(
                ablauf, i)
            weiter = [laenge(index[z], weg | {i}) for z in ziele if z in index]
            lang_bis_halt[i] = 1 + max(weiter, default=0)
        return lang_bis_halt[i]

    if zu_lang := [s.id for i, s in enumerate(ablauf.schritte)
                   if laenge(i, frozenset()) > RECHENSCHRITTE]:
        b.append(_t(lang, "zu_lang", s=zu_lang[0], max=RECHENSCHRITTE))
    return b


def pruefe(ablauf: AblaufArea, lang: str = "de") -> list[str]:
    if not 1 <= len(ablauf.schritte) <= MAX_SCHRITTE:
        return [_t(lang, "anzahl", max=MAX_SCHRITTE, n=len(ablauf.schritte))]
    befunde: list[str] = []
    ids = [s.id for s in ablauf.schritte]
    if doppelt := sorted({i for i in ids if ids.count(i) > 1}):
        befunde.append(_t(lang, "doppelt", ids=", ".join(doppelt)))
    bekannt = set(ids)
    module = katalog.katalog()
    for i, s in enumerate(ablauf.schritte):
        befunde += _schritt(s, module, lang)
        befunde += [_t(lang, "ziel", s=s.id, z=z) for z in nachfolger(ablauf, i)
                    if z and z not in bekannt]
    if not any(s.typ == "ende" for s in ablauf.schritte):
        befunde.append(_t(lang, "ende"))
    if _schleife_ohne_halt(ablauf):
        befunde.append(_t(lang, "schleife"))
    elif not doppelt:
        befunde += _laeufe(ablauf, lang)
    befunde += [_t(lang, "voraussetzung", v=v) for v in ablauf.voraussetzungen
                if v not in VORAUSSETZUNGEN]
    if (any(s.typ == "auftrag" for s in ablauf.schritte)
            and "anmeldung" not in ablauf.voraussetzungen):
        befunde.append(_t(lang, "auftrag_anmeldung"))
    for a in ablauf.ausloeser:
        befunde += _ausloeser(ablauf, a, module, lang)
    return befunde


def wendung(text: str) -> str:
    """Die Vergleichsform einer Wendung bzw. Nachricht: klein, Leerraum zusammengezogen."""
    return " ".join(text.casefold().split())


def modul_start(ablauf: AblaufArea, modul: str | None) -> int | None:
    """Ab welchem Schritt ein Modul-Auslöser startet: dem regulären Nachfolger des ersten Schritts
    mit ``modul`` — wie das Fortsetzen nach einer Antwort (Review A2a, Befund 3)."""
    index = {s.id: i for i, s in enumerate(ablauf.schritte)}
    for i, s in enumerate(ablauf.schritte):
        if s.typ == "modul" and s.modul == modul:
            return index.get((nachfolger(ablauf, i) or [""])[0])
    return None


def _ausloeser(ablauf: AblaufArea, a: Any, module: dict[str, Any], lang: str) -> list[str]:
    b: list[str] = []
    if a.modus not in _MODI:
        b.append(_t(lang, "modus", m=a.modus))
    if a.art == "text" and not (1 <= len(a.wendungen) <= MAX_WENDUNGEN and all(
            4 <= len(wendung(w)) <= 80 for w in a.wendungen)):
        b.append(_t(lang, "wendung", max=MAX_WENDUNGEN))
    if a.art == "modul":
        if a.modul not in module:
            b.append(_t(lang, "ausloeser", m=a.modul))
        elif modul_start(ablauf, a.modul) is None:
            b.append(_t(lang, "modul_schritt", m=a.modul))
    if a.wenn_teil is not None and not NAME.match(a.wenn_teil):
        b.append(_t(lang, "ausloeser_teil", t=a.wenn_teil))
    return b
