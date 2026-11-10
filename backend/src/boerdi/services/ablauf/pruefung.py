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
  Modell selbst), keine unbekannten Werkzeuge, schreibende nur mit Freigabe (Paket S), keine
  fest eingetragenen Schlüssel, Teile nur an Dienste (nicht an
  lesende WLO-Werkzeuge — Review A1, Befund 9; einzige Ausnahme eine Kennung aus den Startdaten
  der Gastseite als ganzes Argument, ``_ohne_start_kennungen``), gültige Teilnamen, bekannte
  Voraussetzungen und Auslöser.

Die Befunde folgen der Sprache des Studios (``lang``).
"""

from __future__ import annotations

from typing import Any, Final
from urllib.parse import urlsplit

from boerdi.domain import seiten_muster
from boerdi.domain.config_models.ablauf import AblaufArea, Schritt
from boerdi.domain.write_confirm import SCHLUESSEL_FELDER
from boerdi.services.ablauf import platzhalter, startdaten, typen, vergleich, werkzeuge
from boerdi.services.ablauf.pruefung_texte import t as _t
from boerdi.services.teil_verweise import (
    NAME,
    PFAD,
    TIEFE,
    alle_verweise,
    auswahl_fehler,
    ist_auswahl,
    verweis,
)
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
#: AS-3a: so viele Schnellantworten zeigt ein Schritt höchstens (Chips unter der Antwort).
MAX_OPTIONEN: Final = 8
_MODI: Final = frozenset({"vorschlagen"})


#: Review K2c-1, Befund 8 (älter): tiefer sucht die Prüfung keine Verweise — eine sehr tief
#: geschachtelte ``daten``/``argumente`` brach sonst mit ``RecursionError`` (500).
_VERWEIS_TIEFE: Final = 32


def _verweise_mit_tiefe(wert: Any) -> list[tuple[str, str | None, int]]:
    """Name, Pfad und Tiefe jedes Verweises (die oberste Ebene hat Tiefe 0, wie im Treiber)."""
    return [(n, p, t) for n, p, _w, t in alle_verweise(wert, bis=_VERWEIS_TIEFE)]


def _verweise_mit_pfad(wert: Any, *, ohne_auswahl: bool = False) -> list[tuple[str, str | None]]:
    """``ohne_auswahl``: die ``liste`` einer Auswahl nicht als Pfad (die prüft ``auswahl_fehler``
    — Review AS-Da, Befund 4: sonst derselbe Fehler zweimal)."""
    if ohne_auswahl:
        return [(n, None if ist_auswahl(w) else pfad) for n, pfad, w in _verweise_mit_wert(wert)]
    return [(name, pfad) for name, pfad, _tiefe in _verweise_mit_tiefe(wert)]


def _verweise_mit_wert(wert: Any) -> list[tuple[str, str | None, Any]]:
    return [(n, p, w) for n, p, w, _t in alle_verweise(wert, bis=_VERWEIS_TIEFE)]


def _alle_verweis_namen(wert: Any) -> list[str]:
    """Die Namen der Teile, auf die ``wert`` verweist (K2d-1: auch mit ``pfad``) — bis
    ``_VERWEIS_TIEFE``, für Formprüfungen. Was der Treiber einsetzt (bis ``TIEFE``), liefert
    ``typen.verweise`` (Querschnitts-Review AS-D, Befund 6)."""
    return [name for name, _pfad in _verweise_mit_pfad(wert)]


#: Die Schrittarten, an denen der Treiber ``bei_fehler`` nimmt (``nachricht`` und
#: ``verzweigung`` scheitern nie, ``ende`` hat keinen Nachfolger) — Review K2c-1 (älter).
MIT_BEI_FEHLER: Final = frozenset({"modul", "werkzeug", "agent", "auftrag"})


def mit_wahl(s: Schritt) -> bool:
    """AS-3a: wartet der Schritt auf eine Schnellantwort oder Freitext?"""
    return s.typ in ("nachricht", "modul") and bool(s.optionen or s.freitext)


def wahl_ziele(s: Schritt) -> list[str]:
    """Die Ziele der Schnellantworten und des Freitexts, in ihrer Reihenfolge."""
    return [o.ziel for o in s.optionen or []] + ([s.freitext.ziel] if s.freitext else [])


def _normal(ablauf: AblaufArea, i: int) -> list[str]:
    """Die regulären nächsten Schritte (ohne ``bei_fehler``; ``""`` = läuft ohne ``ende`` aus).
    Eine Liste in ``weiter`` sind Regeln nur an einer Verzweigung; an jedem anderen Schritt (die
    Prüfung meldet sie) gilt sie wie kein ``weiter`` — sonst nähme der Treiber bei ``weiter: []``
    im Erfolgsfall ``bei_fehler`` (Review K2c-4, älter)."""
    s = ablauf.schritte[i]
    if s.typ == "ende":
        return []
    if mit_wahl(s):
        # AS-3a: die Wahl entscheidet — ``weiter`` gilt dort nicht (eigener Befund)
        return wahl_ziele(s)
    if isinstance(s.weiter, list) and s.typ == "verzweigung":
        return [r.dann or r.sonst or "" for r in s.weiter]
    if isinstance(s.weiter, list):
        return [ablauf.schritte[i + 1].id if i + 1 < len(ablauf.schritte) else ""]
    folgender = ablauf.schritte[i + 1].id if i + 1 < len(ablauf.schritte) else ""
    return [s.weiter or folgender]


def regulaere_nachfolger(ablauf: AblaufArea, i: int) -> list[str]:
    """Die regulären nächsten Schritte (ohne ``bei_fehler``) — für „Schritt n von m“
    (``fortschritt``, AS-Ua)."""
    return _normal(ablauf, i)


def nachfolger(ablauf: AblaufArea, i: int) -> list[str]:
    """Die möglichen nächsten Schritte von Schritt ``i`` — der reguläre zuerst, dann
    ``bei_fehler``."""
    ziele = _normal(ablauf, i)
    s = ablauf.schritte[i]
    if s.bei_fehler and s.typ in MIT_BEI_FEHLER:
        ziele.append(s.bei_fehler)
    return ziele


def _wartet(s: Schritt) -> bool:
    if s.typ in ("agent", "auftrag") or schreibt_mit_freigabe(s) or mit_wahl(s):
        return True
    # Review AS-7a, Befund 4: ``seite`` ist kein sicherer Halt — steht die Person schon dort, läuft
    # der Schritt durch; ein Kreis über ihn wäre sonst unbemerkt
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
        bedingung = (r.wenn_teil is not None or r.wenn_gewaehlt is not None
                     or r.wenn_wert is not None or r.wenn_seite is not None)
        if r.wenn_wert is not None and (r.wenn_teil is not None or r.wenn_gewaehlt is not None):
            # AS-3c: ein Vergleich steht allein (zwei Bedingungen wären unklar: und oder oder?)
            b.append(_t(lang, "wert_allein", s=s.id))
            break
        if r.wenn_seite is not None and (r.wenn_teil is not None or r.wenn_gewaehlt is not None
                                         or r.wenn_wert is not None):
            b.append(_t(lang, "seite_allein", s=s.id))
            break
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
    # nur Verweise, die der Treiber einsetzt — ein zu tiefer schaltet die Vertragsprüfung nicht
    # ab (Querschnitts-Review AS-D, Befund 6; ``zu_tief`` meldet ihn)
    if s.modul in werkzeuge.MODUL_DIENST_OHNE_MODELL or typen.verweise(s.daten):
        return []
    if fehler := katalog.daten_fehler(manifest, s.daten or {}):
        return [_t(lang, "daten", s=s.id, m=s.modul, f="; ".join(fehler)[:160])]
    return []


def _schritt(s: Schritt, module: dict[str, Any], lang: str,
             kennungsfelder: frozenset[str] = frozenset()) -> list[str]:
    b: list[str] = []
    # Review AS-7a, Befund 6: ohne Text bliebe die Antwort auf den Seiten-Ping leer und unsichtbar
    if (s.typ == "nachricht" and not (s.text or {}).get("de")) or (
            s.typ == "seite" and not ((s.text or {}).get("de") or "").strip()):
        b.append(_t(lang, "text", s=s.id))
    if s.typ == "modul":
        b += _modul(s, module, lang)
    if s.typ == "werkzeug":
        name = s.werkzeug or ""
        if werkzeuge.schreibend(name):
            b += _schreibend(s, name, lang)
        elif s.freigabe is not None and werkzeuge.bekannt(name):
            b.append(_t(lang, "freigabe_lesend", s=s.id, w=name))
        elif not werkzeuge.bekannt(name):
            b.append(_t(lang, "werkzeug", s=s.id, w=name))
        elif name in werkzeuge.DIENSTE:
            b += _dienst_argumente(s, name, lang)
        elif name in werkzeuge.LESENDE_MCP and _alle_verweis_namen(
                _ohne_start_kennungen(s.argumente, kennungsfelder)):
            b.append(_t(lang, "mcp_teil", s=s.id))
    if s.typ == "agent":
        b += _agent(s, module, lang)
    if s.typ == "auftrag":
        b += _auftrag(s, lang)
    elif s.warten == "gesperrt":
        b.append(_t(lang, "warten", s=s.id))
    if s.bei_fehler and s.typ not in MIT_BEI_FEHLER:
        b.append(_t(lang, "bei_fehler_typ", s=s.id, typ=s.typ))
    if s.typ != "auftrag" and s.dateien_holen:
        b.append(_t(lang, "dateien_holen", s=s.id))
    if s.typ != "werkzeug" and s.freigabe is not None:
        b.append(_t(lang, "freigabe_typ", s=s.id))
    if s.typ in ("werkzeug", "auftrag") and (fest := sorted(
            set(s.argumente or {}) & SCHLUESSEL_FELDER)):
        # Paket S (Review S1, Befund 1): ein fest eingetragener Schlüssel schriebe ohne Vorschau —
        # und über ``$teil`` setzte ihn womöglich ein Modell (die Ausgabe eines agent-Schritts).
        b.append(_t(lang, "schluessel_fest", s=s.id, f=", ".join(fest)))
    b += _regeln(s, lang)
    b += _seite(s, lang)
    b += _wahl(s, module, lang)
    teile = _alle_verweis_namen(s.daten) + _alle_verweis_namen(s.argumente)
    if s.freitext is not None:
        teile.append(s.freitext.schreibt)
    teile += [n for n in (s.schreibt, s.agent.ausgabe if s.agent else None) if n is not None]
    if isinstance(s.weiter, list):
        teile += [r.wenn_teil for r in s.weiter if r.wenn_teil is not None]
    # Review K2d-1 (2), Befund 4: gekürzt — ein langer Name ginge sonst ganz in die 422-Antwort
    b += [_t(lang, "teil", s=s.id, t=n[:40]) for n in teile if not NAME.match(n)]
    # K2d-1: ob die Stelle im Teil entsteht, weiß erst der Lauf — geprüft wird ihre Form
    b += [_t(lang, "pfad", s=s.id, t=n[:40], p=p[:80])
          for n, p in _verweise_mit_pfad(s.daten, ohne_auswahl=True)
          + _verweise_mit_pfad(s.argumente, ohne_auswahl=True)
          if p is not None and not PFAD.match(p)]
    b += _nicht_eingesetzt(s, lang)
    b += _auswahl(s, lang)
    b += _auswahl_ziele(s, lang)
    return b


def muster_befunde(muster: list[str] | None, wo: str, lang: str) -> list[str]:
    """AS-7a (F-3): Anzahl und Form einer Musterliste — leer ist hier kein Befund (der Aufrufer
    entscheidet, ob Muster Pflicht sind)."""
    if not muster:
        return []
    b = ([_t(lang, "seite_anzahl", wo=wo, max=seiten_muster.MAX_MUSTER)]
         if len(muster) > seiten_muster.MAX_MUSTER else [])
    b += [_t(lang, "seite_muster", wo=wo, m=m[:60], f=_t(lang, f"muster_{f}"))
          for m in muster if (f := seiten_muster.fehler(m))]
    return b


def url_ok(url: str | None) -> bool:
    """AS-7a (F-2): ein Pfad mit ``/`` (nicht ``//``) oder ``https://host…`` ohne Zugangsdaten."""
    url = (url or "").strip()
    # ``|`` trennt die Teile des Chips (``seite_zug.knopf``); ``\`` machen Browser zu ``/``
    # (``/\host`` wäre fremd, Review AS-7a, Befund 5); Steuerzeichen gehören nicht in Adressen
    if "|" in url or "\\" in url or any(ord(c) < 32 or ord(c) == 127 for c in url):
        return False
    if url.startswith("/"):
        return not url.startswith("//") and not any(c.isspace() for c in url)
    try:
        teile = urlsplit(url)
    except ValueError:
        return False
    return (teile.scheme == "https" and bool(teile.hostname) and "@" not in teile.netloc
            and not any(c.isspace() for c in url))


def _seite(s: Schritt, lang: str) -> list[str]:
    """AS-7a: der Schritt ``seite`` (F-1, F-2) und ``wenn_seite`` einer Verzweigung (F-6)."""
    wo = _t(lang, "schritt_wo", s=s.id)
    b: list[str] = []
    if s.typ == "seite":
        if not url_ok(s.url):
            b.append(_t(lang, "seite_url", s=s.id))
        if not ((s.label or {}).get("de") or "").strip():
            b.append(_t(lang, "seite_label", s=s.id))
        b += muster_befunde(s.ankunft, wo, lang)
        # Zweites Review AS-7a, Befund 1: führt der eigene Chip nie auf eine passende Seite, wartet
        # der Lauf still für immer
        if (s.ankunft and url_ok(s.url) and not muster_befunde(s.ankunft, wo, lang)
                and not seiten_muster.passt(s.url, s.ankunft)):
            b.append(_t(lang, "seite_unerreichbar", s=s.id))
    elif s.url is not None or s.label is not None or s.ankunft is not None:
        b.append(_t(lang, "seite_felder", s=s.id))
    for r in s.weiter if isinstance(s.weiter, list) else []:
        b += muster_befunde(r.wenn_seite, wo, lang)
    return b


def _dienst_argumente(s: Schritt, name: str, lang: str) -> list[str]:
    """Ein Dienst nennt seine Argumente (``typen.DIENST_EINGABE``) — ein Tippfehler fiel sonst
    erst im Lauf auf (``bei_fehler``; Querschnitts-Review AS-D). Alle sind Pflicht."""
    erwartet = typen.DIENST_EINGABE.get(name, {})
    da = set(s.argumente or {})
    b = [_t(lang, "dienst_argument", s=s.id, w=name, a=a[:40], e=", ".join(sorted(erwartet)))
         for a in sorted(da - set(erwartet))]
    b += [_t(lang, "dienst_argument_fehlt", s=s.id, w=name, a=a)
          for a in sorted(set(erwartet) - da)]
    return b


def _ohne_start_kennungen(argumente: dict[str, Any] | None,
                          felder: frozenset[str]) -> dict[str, Any]:
    """Entscheid zu AS-4a, Befund 10 (Option 2): Eine Kennung aus den Startdaten der Gastseite
    (Feld vom Typ ``nodeid``) darf als ganzes Argument an ein lesendes WLO-Werkzeug — sie ist eine
    geprüfte UUID, kein Inhalt des Arbeitsstands. Alles andere bleibt verwehrt (``mcp_teil``)."""
    return {k: v for k, v in (argumente or {}).items()
            if startdaten.kennung_verweis(felder, v) is None}


def _argument_typen(werkzeug: str) -> dict[str, str]:
    """Argument → JSON-Typ eines schreibenden WLO-Werkzeugs (lokale Werkzeugdefinition)."""
    from boerdi.services.mcp.tool_defs_curation import CURATION_TOOL_DEFINITIONS

    for d in CURATION_TOOL_DEFINITIONS:
        f = d.get("function") or {}
        if f.get("name") == werkzeug:
            felder = (f.get("parameters") or {}).get("properties") or {}
            return {k: v["type"] for k, v in felder.items()
                    if isinstance(v, dict) and isinstance(v.get("type"), str)}
    return {}


def _auswahl_ziele(s: Schritt, lang: str) -> list[str]:
    """Querschnitts-Review AS-D: eine Auswahl ist immer eine Liste — an einem Argument, das ein
    Objekt (Dienst, Befund 2c) oder einen einzelnen Wert nimmt (schreibendes Werkzeug, Befund 4a),
    scheiterte der Schritt in jedem Lauf."""
    b = [_t(lang, "dienst_auswahl", s=s.id, a=a[:40], w=s.werkzeug)
         for a in typen.auswahl_an_objekt(s)]
    if s.typ == "werkzeug" and werkzeuge.schreibend(s.werkzeug or ""):
        arten = _argument_typen(s.werkzeug or "")
        b += [_t(lang, "auswahl_einzeln", s=s.id, a=a[:40], w=s.werkzeug)
              for a, wert in (s.argumente or {}).items()
              if ist_auswahl(wert) and arten.get(a) not in (None, "array")]
    return b


def _kaputte_verweise(wert: Any, tiefe: int = 0) -> list[Any]:
    """Objekte mit ``$teil``, die kein Verweis sind — sie blieben still als wörtlicher Wert stehen
    (AS-Da)."""
    if tiefe > _VERWEIS_TIEFE:
        return []
    if isinstance(wert, dict):
        if "$teil" in wert and verweis(wert) is None:
            return [wert]
        return [x for v in wert.values() for x in _kaputte_verweise(v, tiefe + 1)]
    if isinstance(wert, list):
        return [x for v in wert for x in _kaputte_verweise(v, tiefe + 1)]
    return []


def _alle_auswahlen(wert: Any, tiefe: int = 0) -> list[Any]:
    if tiefe > _VERWEIS_TIEFE:
        return []
    if ist_auswahl(wert):
        return [wert]
    if isinstance(wert, dict):
        return [x for v in wert.values() for x in _alle_auswahlen(v, tiefe + 1)]
    if isinstance(wert, list):
        return [x for v in wert for x in _alle_auswahlen(v, tiefe + 1)]
    return []


def _auswahl(s: Schritt, lang: str) -> list[str]:
    """AS-Da: Form der Auswahlen und Objekte mit ``$teil``, die kein Verweis sind."""
    b = [_t(lang, "verweis_form", s=s.id, t=str(w.get("$teil"))[:40])
         for w in _kaputte_verweise(s.daten) + _kaputte_verweise(s.argumente)]
    for w in _alle_auswahlen(s.daten) + _alle_auswahlen(s.argumente):
        if fehler := auswahl_fehler(w):
            b.append(_t(lang, "auswahl_form", s=s.id, t=str(w.get("$teil"))[:40],
                        f=", ".join(fehler)[:80]))
    return list(dict.fromkeys(b))


def _wahl(s: Schritt, module: dict[str, Any], lang: str) -> list[str]:
    """AS-3a: Schnellantworten — Anzahl, Kennungen, Beschriftung, kein ``weiter`` daneben, kein
    abfragendes Modul (das wartet schon selbst auf seine Antwort)."""
    if (s.optionen or s.freitext) and s.typ not in ("nachricht", "modul"):
        return [_t(lang, "wahl_typ", s=s.id)]
    if not mit_wahl(s):
        return []
    b: list[str] = []
    optionen = s.optionen or []
    if len(optionen) > MAX_OPTIONEN:
        b.append(_t(lang, "optionen_anzahl", s=s.id, max=MAX_OPTIONEN))
    ids = [o.id for o in optionen]
    if doppelt := sorted({i for i in ids if ids.count(i) > 1}):
        b.append(_t(lang, "optionen_doppelt", s=s.id, ids=", ".join(doppelt)))
    b += [_t(lang, "optionen_label", s=s.id, o=o.id) for o in optionen
          if not (o.label.get("de") or "").strip()]
    # Querschnitts-Review AS-3, Befund 7: zwei gleich beschriftete Chips — getippter Text träfe
    # immer den ersten
    for sprache in sorted({k for o in optionen for k in o.label}):
        labels = [wendung(o.label.get(sprache) or "") for o in optionen]
        if gleich := sorted({x for x in labels if x and labels.count(x) > 1}):
            b.append(_t(lang, "optionen_label_doppelt", s=s.id, l=", ".join(gleich)[:80]))
    if s.weiter not in (None, ""):
        b.append(_t(lang, "wahl_weiter", s=s.id))
    if s.typ == "modul" and (module.get(s.modul or "") or {}).get("art") == "abfragen":
        b.append(_t(lang, "wahl_abfragend", s=s.id, m=s.modul))
    return b


def _schreibt_je_schritt(ablauf: AblaufArea, module: dict[str, Any], i: int) -> set[str]:
    """Die Teile, die Schritt ``i`` hinterlässt (``i == -1``: was vor dem Start da ist) — aus der
    einen Quelle ``typen`` (Review AS-Db, Befund 6)."""
    if i < 0:
        return set(typen.start_teile(ablauf, module))
    return set(typen.schritt_ausgaben(ablauf.schritte[i], module))


def _teile_davor(ablauf: AblaufArea, module: dict[str, Any]) -> dict[int, set[str]]:
    """Je Schritt die Teile, die auf irgendeinem Weg VOR ihm entstehen (D3: „den kein Schritt
    davor schreibt“, Review AS-3b, Befund 3) — über die Kanten von :func:`nachfolger`. Was vor dem
    Start da ist (Modul-Auslöser), gilt an jedem Schritt."""
    index = {s.id: i for i, s in enumerate(ablauf.schritte)}
    start = _schreibt_je_schritt(ablauf, module, -1)
    davor: dict[int, set[str]] = {i: set(start) for i in range(len(ablauf.schritte))}
    for w in range(len(ablauf.schritte)):
        if not (namen := _schreibt_je_schritt(ablauf, module, w)):
            continue
        offen = [index[z] for z in nachfolger(ablauf, w) if z in index]
        gesehen: set[int] = set()
        while offen:
            j = offen.pop()
            if j in gesehen:
                continue
            gesehen.add(j)
            davor[j] |= namen
            offen += [index[z] for z in nachfolger(ablauf, j) if z in index]
    return davor


def _platzhalter(s: Schritt, davor: set[str], geschrieben: set[str], lang: str,
                 startfelder: frozenset[str] = frozenset()) -> list[str]:
    """AS-3b: Platzhalter in ``text`` und ``freigabe`` — gültige Form, ein Teil, der VOR dem
    Schritt entsteht; ``{start.<feld>}`` (AS-4a) ein Feld des Startschemas. Teile, die vor dem
    Start im Vorgang liegen, nur über ``$teil`` — bewusst. In Beschriftungen von Schnellantworten
    wirken sie nicht (die Chips entstehen ohne die Teile)."""
    b: list[str] = []
    texte = [*(s.text or {}).values(), *(s.freigabe or {}).values()]
    for art, name, pfad, gueltig in (f for t in texte for f in platzhalter.finden(t)):
        roh = "{" + (f"{art}.{name}" + (f".{pfad}" if pfad else "") if gueltig else name) + "}"
        if not gueltig:
            b.append(_t(lang, "platzhalter_form", s=s.id, p=roh[:80]))
        elif art == "start" or name == typen.START_TEIL:
            # Review AS-4a, Befund 8: auch ``{teil.start.feld}``
            feld = name if art == "start" else (pfad or "").split(".")[0]
            if feld and feld not in startfelder:
                b.append(_t(lang, "platzhalter_start", s=s.id, p=roh[:80], t=feld[:40]))
        elif name not in geschrieben:
            b.append(_t(lang, "platzhalter_teil", s=s.id, p=roh[:80], t=name))
        elif name not in davor:
            b.append(_t(lang, "platzhalter_spaeter", s=s.id, p=roh[:80], t=name))
    if any(platzhalter.finden(label) for o in s.optionen or [] for label in o.label.values()):
        b.append(_t(lang, "platzhalter_label", s=s.id))
    return list(dict.fromkeys(b))


def _wenn_wert(s: Schritt, davor: set[str], geschrieben: set[str], lang: str) -> list[str]:
    """AS-3c: Quelle in Form, ein Teil, der vor der Verzweigung entsteht, ein Wert, wo der
    Vergleich einen braucht (bei ``groesser``/``kleiner`` eine Zahl), keiner bei ``vorhanden`` und
    ``leer``."""
    if s.typ != "verzweigung" or not isinstance(s.weiter, list):
        return []
    b: list[str] = []
    for r in s.weiter:
        if (w := r.wenn_wert) is None:
            continue
        q = vergleich.quelle(w.quelle)
        if q is None:
            b.append(_t(lang, "wert_quelle", s=s.id, q=w.quelle[:80]))
        elif q[0] not in geschrieben:
            b.append(_t(lang, "wert_teil", s=s.id, q=w.quelle[:80], t=q[0]))
        elif q[0] not in davor:
            b.append(_t(lang, "wert_spaeter", s=s.id, q=w.quelle[:80], t=q[0]))
        hat_wert = bool((w.wert or "").strip())
        if w.vergleich in vergleich.MIT_WERT and not hat_wert:
            b.append(_t(lang, "wert_fehlt", s=s.id, v=w.vergleich))
        elif w.vergleich not in vergleich.MIT_WERT and hat_wert:
            b.append(_t(lang, "wert_ohne", s=s.id, v=w.vergleich))
        elif w.vergleich in vergleich.ZAHL_NOETIG and vergleich.zahl(w.wert) is None:
            b.append(_t(lang, "wert_zahl", s=s.id, v=w.vergleich))
    return list(dict.fromkeys(b))


def _verweis_namen(s: Schritt) -> list[str]:
    """Die ``$teil``-Namen des Schritts — aus der einen Quelle ``typen`` (Review AS-Dc,
    Befund 2)."""
    return typen.verweis_namen(s)


def _datenfluss(s: Schritt, geschrieben: set[str], ausgaben: dict[str, set[str | None]],
                gespraech: typen.Typen, lang: str) -> list[str]:
    """AS-Db: ``$teil`` auf einen Teil, den weder der Ablauf noch irgendein Modul schreibt, und
    ein ganzer Teil, dessen Typen nicht zum erwarteten passen. Typen kommen von den Schreibern im
    Ablauf, sonst aus dem Gespräch (Review AS-Db, Befund 5); ein Schreiber mit unbekanntem Typ
    (``None``) hebt den Vergleich auf."""
    b: list[str] = []
    irgendwo = geschrieben | set(gespraech)
    b += [_t(lang, "verweis_teil", s=s.id, t=n[:40]) for n in _verweis_namen(s)
          if NAME.match(n) and n not in irgendwo]
    # Querschnitts-Review AS-D, Befund 2a: in einem Text findet ein Pfad oder eine Auswahl nichts
    # (der Lauf liest Text nicht als JSON)
    im_text = [n for n, pfad, wert in typen.schritt_verweise(s)
               if (pfad is not None or ist_auswahl(wert)) and ausgaben.get(n) == {typen.TEXT}]
    b += [_t(lang, "verweis_text", s=s.id, t=n[:40]) for n in dict.fromkeys(im_text)]
    for name, erwartet in typen.erwartete_eingaben(s):
        bekannt = ausgaben.get(name) or ({gespraech[name]} if name in gespraech else set())
        if not bekannt or None in bekannt or erwartet in bekannt:
            continue
        b.append(_t(lang, "verweis_typ", s=s.id, t=name[:40], e=erwartet,
                    i=", ".join(sorted(t for t in bekannt if t))[:80]))
    return b


def warnungen(ablauf: AblaufArea, lang: str = "de") -> list[str]:
    """AS-Db: Hinweise, die das Speichern nicht sperren — ein ``$teil`` auf einen Teil, der im
    Ablauf erst nach dem Schritt entsteht, oder den nur ein Modul im Gespräch hinterlässt. Er muss
    dann schon im Vorgang liegen, sonst scheitert der Schritt. Einen Teil, den gar nichts schreibt,
    meldet die Prüfung als Befund — hier steht er nicht noch einmal (Review AS-Db, Befund 4)."""
    if not 1 <= len(ablauf.schritte) <= MAX_SCHRITTE:
        return []
    module = katalog.katalog()
    davor = _teile_davor(ablauf, module)
    ausgaben = typen.ausgaben(ablauf, module)
    im_ablauf = set(ausgaben)
    gespraech_typen = typen.teile_aus_dem_gespraech(module)
    gespraech = set(gespraech_typen)
    w: list[str] = []
    rueckfrage = False
    for i, s in enumerate(ablauf.schritte):
        w += _auswahl_listen(s, ausgaben, gespraech_typen, lang)
        if (s.typ == "auftrag" and not rueckfrage
                and typen.START_TEIL in typen.verweis_namen(s)):
            # Review AS-4a, Befund 11: Daten der Gastseite gingen ungesehen in einen Auftrag
            w.append(_t(lang, "start_auftrag", s=s.id))
        rueckfrage = rueckfrage or s.typ == "modul" or bool(s.optionen) or s.freitext is not None
        rueckfrage = rueckfrage or (s.typ == "werkzeug" and s.freigabe is not None)
        for n in _verweis_namen(s):
            if not NAME.match(n) or n in davor.get(i, set()) or n not in im_ablauf | gespraech:
                continue
            # schreibt ihn der Ablauf selbst, nur später — oder gar nicht (dann aus dem Gespräch)
            schluessel = "verweis_spaeter" if n in im_ablauf else "verweis_gespraech"
            w.append(_t(lang, schluessel, s=s.id, t=n[:40]))
    return list(dict.fromkeys(w))


def _auswahl_listen(s: Schritt, ausgaben: dict[str, set[str | None]], gespraech: typen.Typen,
                    lang: str) -> list[str]:
    """Querschnitts-Review AS-D, Befund 2b: eine Auswahl sucht eine Liste, die kein bekannter Typ
    des Teils trägt (:data:`typen.LISTEN`) — ein Hinweis, denn ein Teil kann im Vorgang anders
    aussehen; mit einem Schreiber unbekannten Typs keiner."""
    w: list[str] = []
    for name, _pfad, wert in typen.schritt_verweise(s):
        if not ist_auswahl(wert) or (liste := typen.auswahl_liste(wert)) is None:
            continue
        bekannt = ausgaben.get(name) or ({gespraech[name]} if name in gespraech else set())
        if not bekannt or not all(t in typen.LISTEN for t in bekannt):
            continue
        listen = set().union(*(typen.LISTEN[t] for t in bekannt if t))
        if liste not in listen:
            w.append(_t(lang, "auswahl_liste", s=s.id, t=name[:40], l=liste[:40],
                        k=", ".join(sorted(listen))))
    return w


def _nicht_eingesetzt(s: Schritt, lang: str) -> list[str]:
    """Review K2d-1 (2), Befunde 1–2: Verweise, die der Treiber stehen ließe — der Schritt bekäme
    sonst das wörtliche ``{"$teil": …}``. ``argumente`` als Ganzes setzt er nie ein (nur ``daten``,
    ``treiber._daten``), tiefer als ``teil_verweise.TIEFE`` sucht er nicht."""
    b: list[str] = []
    if verweis(s.argumente) is not None:
        b.append(_t(lang, "argumente_ganz", s=s.id))
    if ist_auswahl(s.daten):
        # Review AS-Da, Befund 1: eine Auswahl ergibt eine Liste, Moduldaten sind ein Objekt
        b.append(_t(lang, "daten_auswahl", s=s.id))
    tief = {n for n, _p, t in _verweise_mit_tiefe(s.daten) + _verweise_mit_tiefe(s.argumente)
            if t > TIEFE}
    b += [_t(lang, "zu_tief", s=s.id, t=n[:40], max=TIEFE) for n in sorted(tief)]
    return b


def _schreibend(s: Schritt, name: str, lang: str) -> list[str]:
    """Paket S: ein schreibendes Werkzeug nur, wenn es freigebbar ist und der Schritt den Satz über
    der Vorschau trägt (``freigabe.de``)."""
    if not werkzeuge.freigebbar(name):
        return [_t(lang, "schreibend", s=s.id, w=name)]
    if not (s.freigabe or {}).get("de", "").strip():
        return [_t(lang, "freigabe_fehlt", s=s.id, w=name)]
    return []


def schreibt_mit_freigabe(s: Schritt) -> bool:
    """Ein ``werkzeug``-Schritt, der eine Änderung vorlegt und auf die Freigabe wartet."""
    return (s.typ == "werkzeug" and s.freigabe is not None
            and werkzeuge.freigebbar(s.werkzeug or ""))


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
    mit Agent-Freigabe im Manifest — nie schreibende (die gibt es nur im werkzeug-Schritt mit
    Freigabe, Paket S)."""
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


#: Ein Befund und der Index des Schritts, an dem er steht (``None``: der ganze Ablauf) — für das
#: Studio. Der Index, nicht die Kennung: doppelte Kennungen meldet die Prüfung selbst (Review K2c-1,
#: Befund 4).
Befund = tuple[int | None, str]


def _laeufe(ablauf: AblaufArea, lang: str) -> list[Befund]:
    """Erreichbarkeit, Auslaufen ohne ``ende`` und die Länge bis zum nächsten Halt."""
    index = {s.id: i for i, s in enumerate(ablauf.schritte)}
    erreicht, offen = {0}, [0]
    while offen:
        for z in nachfolger(ablauf, offen.pop()):
            if z in index and index[z] not in erreicht:
                erreicht.add(index[z])
                offen.append(index[z])
    b: list[Befund] = [(i, _t(lang, "unerreichbar", s=s.id))
                       for i, s in enumerate(ablauf.schritte) if i not in erreicht]
    b += [(i, _t(lang, "auslaufen", s=ablauf.schritte[i].id))
          for i in sorted(erreicht) if "" in _normal(ablauf, i)]
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

    if zu_lang := [i for i in range(len(ablauf.schritte))
                   if laenge(i, frozenset()) > RECHENSCHRITTE]:
        b.append((zu_lang[0], _t(lang, "zu_lang", s=ablauf.schritte[zu_lang[0]].id,
                                 max=RECHENSCHRITTE)))
    return b


def pruefe(ablauf: AblaufArea, lang: str = "de") -> list[str]:
    """Die Befunde als Liste — beim Speichern (``config_guards``)."""
    return [text for _schritt_id, text in pruefe_gegliedert(ablauf, lang)]


def pruefe_gegliedert(ablauf: AblaufArea, lang: str = "de") -> list[Befund]:
    """Paket K2c-1: dieselben Befunde in derselben Reihenfolge, je mit dem Index des Schritts, an
    dem sie stehen (``None``: der ganze Ablauf) — für „Prüfen“ im Studio."""
    if not 1 <= len(ablauf.schritte) <= MAX_SCHRITTE:
        return [(None, _t(lang, "anzahl", max=MAX_SCHRITTE, n=len(ablauf.schritte)))]
    befunde: list[Befund] = []
    ids = [s.id for s in ablauf.schritte]
    if doppelt := sorted({i for i in ids if ids.count(i) > 1}):
        befunde.append((None, _t(lang, "doppelt", ids=", ".join(doppelt))))
    bekannt = set(ids)
    module = katalog.katalog()
    davor = _teile_davor(ablauf, module)
    ausgaben = typen.ausgaben(ablauf, module)
    gespraech = typen.teile_aus_dem_gespraech(module)
    geschrieben = set().union(*davor.values(), _schreibt_je_schritt(ablauf, module, -1))
    startfelder = frozenset(f.name for f in ablauf.start or [])
    # Querschnitts-Review RB, Befund 3: die Ausnahme für Kennungen der Gastseite gilt nur, wo die
    # Gastseite starten kann — sonst ginge der Schritt im Betrieb still zu ``bei_fehler``.
    kennungen = (startdaten.kennungsfelder(ablauf)
                 if any(a.art == "extern" for a in ablauf.ausloeser) else frozenset())
    for i, s in enumerate(ablauf.schritte):
        befunde += [(i, text) for text in _schritt(s, module, lang, kennungen)]
        befunde += [(i, text) for text in _platzhalter(s, davor.get(i, set()), geschrieben,
                                                       lang, startfelder)]
        # AS-4a: ``start`` tragen nur die Startdaten
        if typen.START_TEIL in typen.schritt_ausgaben(s, module):
            befunde.append((i, _t(lang, "start_reserviert", s=s.id)))
        # Review AS-4a, Befund 8: ``$teil: start`` mit Pfad nennt ein Feld des Schemas
        befunde += [(i, _t(lang, "start_feld", s=s.id, f=f[:40])) for f in dict.fromkeys(
            (pfad or "").split(".")[0] for n, pfad, _w in typen.schritt_verweise(s)
            if n == typen.START_TEIL and pfad) if f and f not in startfelder]
        befunde += [(i, text) for text in _wenn_wert(s, davor.get(i, set()), geschrieben, lang)]
        befunde += [(i, text) for text in _datenfluss(s, geschrieben, ausgaben, gespraech, lang)]
        ziele = nachfolger(ablauf, i)
        if s.bei_fehler and s.typ not in MIT_BEI_FEHLER and s.typ != "ende":
            ziele.append(s.bei_fehler)   # wirkt nicht (eigener Befund), ein Tippfehler zeigt sich
        befunde += [(i, _t(lang, "ziel", s=s.id, z=z)) for z in dict.fromkeys(ziele)
                    if z and z not in bekannt]
    if not any(s.typ == "ende" for s in ablauf.schritte):
        befunde.append((None, _t(lang, "ende")))
    if _schleife_ohne_halt(ablauf):
        befunde.append((None, _t(lang, "schleife")))
    elif not doppelt:
        befunde += _laeufe(ablauf, lang)
    befunde += [(None, _t(lang, "voraussetzung", v=v)) for v in ablauf.voraussetzungen
                if v not in VORAUSSETZUNGEN]
    if (any(s.typ == "auftrag" for s in ablauf.schritte)
            and "anmeldung" not in ablauf.voraussetzungen):
        befunde.append((None, _t(lang, "auftrag_anmeldung")))
    if (any(s.typ == "werkzeug" and werkzeuge.schreibend(s.werkzeug or "")
            for s in ablauf.schritte) and "anmeldung" not in ablauf.voraussetzungen):
        # Paket S (FS-5): geschrieben wird nur unter der eigenen Anmeldung
        befunde.append((None, _t(lang, "freigabe_anmeldung")))
    for a in ablauf.ausloeser:
        befunde += [(None, text) for text in _ausloeser(ablauf, a, module, lang)]
    befunde += [(None, text) for text in _startschema(ablauf, lang)]
    return befunde


def _startschema(ablauf: AblaufArea, lang: str) -> list[str]:
    """AS-4a: doppelte Felder (Review, Befund 6); Pflichtfelder ohne Gastseite oder neben einem
    Auslöser, der nie Daten bringt (Befund 1 — der wählt den Ablauf gar nicht erst)."""
    b: list[str] = []
    namen = [f.name for f in ablauf.start or []]
    if doppelt := sorted({n for n in namen if namen.count(n) > 1}):
        b.append(_t(lang, "start_doppelt", f=", ".join(doppelt)))
    arten = [a.art for a in ablauf.ausloeser]
    # AS-5a: die Beschreibung wird Teil des Werkzeugs der KI — ohne sie rät das Modell
    if "agent" in arten:
        b += [_t(lang, "start_beschreibung", f=f.name) for f in ablauf.start or []
              if not any((t or "").strip() for t in f.beschreibung.values())]
    if not any(f.pflicht for f in ablauf.start or []):
        return b
    if not set(arten) & _MIT_DATEN:
        b.append(_t(lang, "start_pflicht"))
    else:
        b += [_t(lang, "start_pflicht_ausloeser", a=art) for art in dict.fromkeys(arten)
              if art not in _MIT_DATEN]
    return b


#: Auslöser, die Startdaten bringen (wie ``ausloeser._MIT_DATEN``).
_MIT_DATEN: Final = frozenset({"extern", "agent"})


def wendung(text: str) -> str:
    """Die Vergleichsform einer Wendung bzw. Nachricht: klein, Leerraum zusammengezogen."""
    return " ".join(text.casefold().split())


def wendungs_warnungen(
    ablauf: AblaufArea, andere: list[AblaufArea], lang: str = "de",
) -> list[str]:
    """AS-0: Wendungen dieses (aktiven) Ablaufs, die sich mit denen eines anderen aktiven Ablaufs
    überschneiden — gleich oder ineinander enthalten, wie ``ausloeser.per_text`` sucht (Review AS-0,
    Befund 5: „themenbaum“ startet auch bei „themenbaum aus meinem ordner“). Je Wendung eine Warnung
    mit den anderen. Es startet dann der Ablauf mit dem kleinsten Schlüssel; das ist selten gewollt,
    aber kein Fehler (kein Befund, der das Speichern sperrt)."""
    if not ablauf.aktiv:
        return []
    fremde: list[tuple[str, str]] = [
        (w, anderer.id) for anderer in andere if anderer.id != ablauf.id and anderer.aktiv
        for a in anderer.ausloeser if a.art == "text" for roh in a.wendungen if (w := wendung(roh))]
    eigene = dict.fromkeys(w for a in ablauf.ausloeser if a.art == "text"
                           for roh in a.wendungen if (w := wendung(roh)))
    warnungen: list[str] = []
    for w in eigene:
        treffer = sorted({kennung for f, kennung in fremde if w in f or f in w})
        if treffer:
            warnungen.append(_t(lang, "wendung_doppelt", w=w, andere=", ".join(treffer)))
    return warnungen


#: Wie ``vorschlag.MAX_WERKZEUGE`` (ohne Import: ``vorschlag`` hängt an den Auslösern).
_MAX_KI_ABLAEUFE: Final = 6


def agent_warnungen(ablauf: AblaufArea, andere: list[AblaufArea], lang: str = "de") -> list[str]:
    """AS-5a (Review, Befund 8): Mehr aktive Abläufe mit Auslöser ``agent``, als ein Agent-Zug
    als Werkzeug bekommt — die übrigen schlägt die KI nie vor. Ein Hinweis, kein Befund."""
    if not ablauf.aktiv or not any(a.art == "agent" for a in ablauf.ausloeser):
        return []
    zahl = 1 + sum(1 for x in andere if x.id != ablauf.id and x.aktiv
                   and any(a.art == "agent" for a in x.ausloeser))
    if zahl <= _MAX_KI_ABLAEUFE:
        return []
    return [_t(lang, "agent_zu_viele", n=zahl, m=_MAX_KI_ABLAEUFE)]


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
    if a.art == "seite":
        if not a.muster:
            b.append(_t(lang, "seite_ausloeser", max=seiten_muster.MAX_MUSTER))
        b += muster_befunde(a.muster, _t(lang, "ausloeser_wo"), lang)
    return b
