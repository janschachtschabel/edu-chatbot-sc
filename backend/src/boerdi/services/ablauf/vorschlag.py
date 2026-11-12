"""Auslöser ``agent`` (A2a, AS-5a): die KI schlägt einen Ablauf vor — gestartet wird per Knopf.

- :func:`werkzeuge`: je aktivem Ablauf mit Auslöser ``agent`` ein virtuelles Werkzeug
  ``ablauf-<id>`` (Plan §5g, A5-1/A5-2: ein Bindestrich, weil ``__`` ein Fremdwerkzeug kennzeichnet
  und Ablauf-Kennungen nie ``-`` enthalten). Seine Parameter sind das Startschema
  (``startdaten.werkzeug_schema``); Titel, ``wann`` und ``nicht_wann`` stehen in der Beschreibung.
- Die Schleife ruft nichts: :func:`merken` prüft die Daten wie jeder Start
  (``startdaten.pruefen``) und merkt den Vorschlag (:data:`MAX_JE_ZUG`,
  ``AgentRun.ablauf_vorschlaege``). :func:`schnellantworten` macht daraus beim Zusammenstellen den
  Knopf ``__action__|<Titel>|ablauf_starten|{"ablauf": id, "start": {…}, "start_quelle": "ki"}``.
  So formuliert die KI nie selbst einen Knopf; der Start läuft wie jeder Knopf durch Preflight und
  Sicherheitsprüfung, und Daten der KI tragen nie die Rechte der Gastseite (A5-3).

``direkt`` (Plan 2026-11-10, TB-E3, Nutzer-Entscheid N4): kein Treiber mitten in der Antwort —
der Knopf entsteht wie beim Vorschlag, die Zusammenstellung merkt ihn (:data:`DIREKT_KEY`), die
Antwort trägt ihn in ``ui.direkt_start`` (:func:`direkt_fuer_antwort`) und das Widget drückt ihn
nach dem Zug. Nur für Abläufe, die nicht selbst schreiben (``werkzeuge.ablauf_schreibt_selbst``;
seit TW-6 zählt ein Upload-Feld nicht — es überträgt nur nach eigenem Klick).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Collection
from typing import Any, Final

from boerdi.domain.ablauf_werkzeug import MUSTER_KEY, PRAEFIX, ist_ablauf_werkzeug, kennung
from boerdi.domain.antwort_werkzeug import RESPOND_TO_USER
from boerdi.domain.host_capabilities import MODI, VOLL
from boerdi.domain.werkzeug_angebot import NICHT_ANGEBOTEN
from boerdi.services.ablauf import ausloeser, startdaten
from boerdi.services.ablauf import werkzeuge as werkzeuge_mod
from boerdi.ui_module.antwort import NACH_DER_FRAGE

logger = logging.getLogger(__name__)

# Re-Exporte (die Namensregel liegt rein in ``domain/ablauf_werkzeug``).
_REEXPORT = (MUSTER_KEY, PRAEFIX, ist_ablauf_werkzeug, kennung)

#: Im ``session_state``: die Vorschläge dieses Zugs (``{ablauf, start?}``), gelesen (und entfernt)
#: beim Zusammenstellen.
SITZUNG_KEY: Final = "_ablauf_vorschlaege"
#: TB-E3: im ``session_state`` der Knopf, den das Widget nach diesem Zug selbst drückt.
DIREKT_KEY: Final = "_ablauf_direkt"
MAX_JE_ZUG: Final = 1
#: A5-7: die Schemas reisen in jedem Agent-Zug mit (Kosten, Cache).
MAX_WERKZEUGE: Final = 6
_BESCHREIBUNG_ZEICHEN: Final = 800
#: A5-7: so lang dürfen die Daten im Knopf werden (als JSON) — sonst kein Knopf.
MAX_DATEN_ZEICHEN: Final = 2000
_MAX_SCHNELLANTWORTEN: Final = 4
_LABEL_ZEICHEN: Final = 60

QUITTUNG: Final = ("Vorschlag angenommen: unter deiner Antwort erscheint ein Knopf, mit dem die "
                   "Person den Ablauf startet. Sag ihr in einem Satz, was er tut und mit welchen "
                   "Angaben (A5-8); starte selbst nichts und beschreibe keine Schritte im Voraus.")
#: TB-E3: der Ablauf startet nach der Antwort von selbst.
QUITTUNG_DIREKT: Final = ("Angenommen: der Ablauf startet gleich nach deiner Antwort von selbst. "
                          "Sag der Person in einem Satz, was jetzt passiert und mit welchen "
                          "Angaben (A5-8); beschreibe keine Schritte im Voraus.")
SCHON_VORGESCHLAGEN: Final = "Ein Ablauf ist in diesem Zug schon vorgeschlagen."
UNBEKANNT: Final = "Diesen Ablauf gibt es nicht (mehr) — schlage ihn nicht vor."
#: Review AS-5a, Befund 7: die Abweichungen vom Schema der Angaben (nicht „das Ergebnis“).
ANGABEN_FALSCH: Final = "Die Angaben passen nicht zum Ablauf: {abweichungen}"
#: AS-5b (A5-8): in derselben Runde wie die Antwort kein Vorschlag mit Angaben.
NEBEN_DER_ANTWORT: Final = ("Nicht ausgeführt: Die Antwort steht in derselben Runde — ein "
                            "Ablauf mit Angaben braucht einen Satz danach.")
ZU_LANG: Final = "Die Angaben sind zu lang für einen Knopf — kürze sie oder schlage nichts vor."
DATEN_FALSCH: Final = "Die Angaben passen nicht zum Ablauf ({codes}) — korrigiere sie oder lass es."


def _titel(ablauf: Any, lang: str) -> str:
    return ((ablauf.titel.get(lang) or "").strip() or (ablauf.titel.get("de") or "").strip()
            or ablauf.id)


#: Plan 2026-11-11, TW-3 (Nutzer N16): ein passender Ablauf geht einzelnen Modulen und
#: Werkzeugen vor — er stellt die Fragen, die ein gutes Ergebnis braucht.
_VORRANG: Final = (". Passt er, geht er einzelnen Modulen und Werkzeugen vor; ohne ihn nur auf "
                   "Wunsch der Person")
_SCHLUSS: Final = (_VORRANG + ". Das Werkzeug startet nichts: unter deiner Antwort erscheint ein "
                   "Knopf, und die Person entscheidet. Höchstens ein Ablauf je Antwort. Mit "
                   "Angaben: rufe das Werkzeug allein auf und antworte erst nach der Quittung.")
#: Review TB-E3, Befund 1: ein direkter Ablauf startet von selbst — die Beschreibung sagt es, sonst
#: kündigte das Modell einen Knopf an, und der Ablauf liefe ohne Klick.
_SCHLUSS_DIREKT: Final = (_VORRANG + ". Der Ablauf startet gleich nach deiner Antwort von "
                          "selbst. Höchstens ein Ablauf je Antwort. Rufe das Werkzeug allein auf "
                          "und sag erst nach der Quittung in einem Satz, was jetzt passiert.")


def _beschreibung(a: Any, lang: str) -> str:
    """Titel und Schlusssatz bleiben immer ganz; ``wann``/``nicht_wann`` teilen sich den Rest —
    jedes höchstens die Hälfte, damit die Einschränkungen nie ganz wegfallen (Review AS-5a,
    Befund 4)."""
    direkt = _direkt(a)
    kopf = (f"Starte für die Person den festen Ablauf „{_titel(a, lang)}“" if direkt
            else f"Schlage der Person den festen Ablauf „{_titel(a, lang)}“ vor")
    schluss = _SCHLUSS_DIREKT if direkt else _SCHLUSS
    rest = max(0, _BESCHREIBUNG_ZEICHEN - len(kopf) - len(schluss))
    listen = [(m, liste) for m, liste in (("passt, wenn: ", a.wann),
                                          ("nicht, wenn: ", a.nicht_wann)) if liste]
    teile = [kopf]
    for marke, liste in listen:
        # Review TW-3, Befund 1: ohne ``nicht_wann`` bekommt ``wann`` den ganzen Rest
        teile.append(_gekuerzt(marke + "; ".join(liste), max(0, rest // len(listen) - 3)))
    return " — ".join(teile) + schluss


def _gekuerzt(text: str, hoechstens: int) -> str:
    """An der Wortgrenze kürzen, mit „…“ — ein halbes Wort („ohne ei“) führte das Modell irre."""
    if len(text) <= hoechstens:
        return text
    stueck = text[:max(0, hoechstens - 1)]
    return (stueck.rsplit(" ", 1)[0] if " " in stueck else stueck) + "…"


def _schreibt(ablauf: Any) -> bool:
    return werkzeuge_mod.ablauf_schreibt(ablauf)


def _direkt(ablauf: Any) -> bool:
    """TB-E3: startet die KI diesen Ablauf direkt? Nur mit ``modus: direkt`` am Auslöser ``agent``
    und nur, wenn er nicht selbst schreibt (TW-6: ein Upload-Feld allein zählt nicht)."""
    return (any(a.art == "agent" and a.modus == "direkt" for a in ablauf.ausloeser)
            and not werkzeuge_mod.ablauf_schreibt_selbst(ablauf))


def werkzeuge(lang: str, nur: Collection[str] | None = None,
              tool_mode: str | None = None, ohne: str | None = None) -> list[dict[str, Any]]:
    """Je vorschlagbarem Ablauf ein Werkzeug, höchstens :data:`MAX_WERKZEUGE`.

    - ``nur``: nur diese Namen (``tools:`` eines Musters) — gefiltert **vor** der Kürzung, sonst
      fiele ein genannter Ablauf ab Platz 7 still weg (Review AS-5b, Befund 1).
    - ``tool_mode`` (Erlaubnis der Einbettung): ohne „full“ keine Abläufe, die schreiben — die KI
      wäre sonst ein Einstieg an der Vorgabe des Gastgebers vorbei (Querschnitt AS-5, Befund 6).
    """
    # Wie ``host_capabilities.erlaubt``: normalisiert; ein unbekannter Wert gilt als voll
    # (zweites Review AS-5, Befund 1).
    modus = (tool_mode or "").strip().lower()
    voll = modus not in MODI or modus == VOLL
    # ``ohne`` (Review TW-4, Befund 2): der Ablauf, aus dem die Person eben ausgestiegen ist
    passend = [a for a in ausloeser.vorschlaege()
               if (nur is None or PRAEFIX + a.id in nur) and (voll or not _schreibt(a))
               and a.id != ohne]
    return [{"type": "function", "function": {
        "name": PRAEFIX + a.id, "description": _beschreibung(a, lang),
        "parameters": startdaten.werkzeug_schema(a, lang)}}
        for a in passend[:MAX_WERKZEUGE]]


#: TW-6: Argumente, die eine Arbeitsgrundlage nennen — dann nie umlenken (Weiterbearbeiten,
#: Bestand, Dokument, eigene Inhalte, erneut zeigen).
_MIT_GRUNDLAGE: Final = ("vorlage", "vertiefen", "wurzel_wlo_id", "aus_dokument", "aus_inhalten",
                         "erneut_zeigen")
#: TW-6: welche Module ein Ablauf statt der KI anbietet.
UMLENKBAR: Final = frozenset({"ui_strukturentwurf", "ui_upload"})
#: Im ``session_state`` (nur dieser Zug): eine Arbeitsgrundlage liegt vor (``respond`` setzt es)
#: bzw. ein Modul wurde in diesem Zug schon einmal umgelenkt.
GRUNDLAGE_KEY: Final = "_ablauf_grundlage"
UMGELENKT_KEY: Final = "_ablauf_umgelenkt"


def arbeitsgrundlage(entities: dict[str, Any], aufrufer: str) -> bool:
    """TW-6 (Review, Befund 2): hat die Sitzung schon etwas, woran die KI weiterarbeitet — einen
    gemerkten Entwurf oder im Vorgang einen Teil ``draft`` oder ``document`` (auch Tage später,
    Paket V1)? Dann lenkt :func:`umlenkung` nie um."""
    from boerdi.services.arbeitsstand_verweis import verweis
    from boerdi.ui_module import strukturentwurf_merken

    if strukturentwurf_merken.vorlage(entities) is not None:
        return True
    vw = verweis(entities, aufrufer)
    teile = vw.get("teile") if isinstance(vw, dict) and isinstance(vw.get("teile"), dict) else {}
    return bool({"draft", "document"} & set(teile))


def umlenkung(modul: str, args: Any, angeboten: Collection[str],
              session_state: dict[str, Any] | None, *, merken: bool = True,
              lang: str = "de") -> str | None:
    """TW-6 (Durchtest 12.11.): die KI griff trotz Regel meist direkt zum Modul. Ruft sie
    ``ui_strukturentwurf`` oder ``ui_upload`` **ohne Arbeitsgrundlage** auf, während ein passender
    Ablauf angeboten ist, läuft das Modul nicht — die Antwort sagt ihr, welchen Ablauf sie nehmen
    soll. ``None``: ausführen.

    Nie umgelenkt (Review TW-6, Befunde 1–3): nach einem Ausstieg („Ohne Ablauf“), mit
    Arbeitsgrundlage (:func:`arbeitsgrundlage`, Argumente wie ``vorlage`` oder
    ``wurzel_wlo_id``), und beim zweiten Versuch im selben Zug — ein Fluchtweg: die KI entscheidet
    ihn, etwa weil die Nachricht dieses Zugs ausdrücklich „ohne Ablauf“ sagt (zweites Review
    TW-6, Befund 8). Für ``ui_strukturentwurf`` zählen nur Abläufe ohne Upload-Schritt (ein
    Thema), für ``ui_upload`` die mit. ``merken=False`` prüft nur (ohne den Versuch zu zählen).
    """
    from boerdi.services.ablauf.zug_basis import abgelehnt

    zustand = session_state if isinstance(session_state, dict) else {}
    if modul not in UMLENKBAR or zustand.get(GRUNDLAGE_KEY) or abgelehnt(None, zustand):
        return None
    if isinstance(args, dict) and any(args.get(k) for k in _MIT_GRUNDLAGE):
        return None
    if modul in (zustand.get(UMGELENKT_KEY) or []):
        return None
    katalog = {a.id: a for a in ausloeser.vorschlaege()}
    ziele: list[str] = []
    for name in angeboten:
        if not ist_ablauf_werkzeug(name) or (a := katalog.get(kennung(name))) is None:
            continue
        mit_upload = any(s.typ == "modul" and s.modul == "ui_upload" for s in a.schritte)
        nutzt = any((s.typ == "modul" and s.modul == modul)
                    or (s.typ == "agent" and s.agent and modul in s.agent.werkzeuge)
                    for s in a.schritte)
        if nutzt and (modul == "ui_upload") == mit_upload:
            ziele.append(f"{name} („{_titel(a, lang)}“)")
    if not ziele:
        return None
    if merken:
        zustand.setdefault(UMGELENKT_KEY, []).append(modul)
    # Durchtest 12.11.: ohne klare Anweisung schrieb die KI danach Prosa („wähle hier aus“) ohne
    # Feld — deshalb ausdrücklich: jetzt einen Ablauf aufrufen, nichts versprechen
    return ("Nicht ausgeführt: Für diese Bitte gibt es einen geführten Ablauf — rufe JETZT "
            + " oder ".join(sorted(ziele)) + " auf (der nächstliegende, wenn keiner genau passt); "
            "er fragt selbst nach, was fehlt. Versprich kein Auswahlfeld ohne Aufruf. Nur wenn die "
            "Person ausdrücklich ohne Ablauf arbeiten will, rufe das Modul noch einmal auf.")


def ist_quittung(text: str) -> bool:
    return text in (QUITTUNG, QUITTUNG_DIREKT)


def merken(vorgeschlagen: list[dict[str, Any]], name: str, args: dict[str, Any] | None) -> str:
    """Einen Vorschlag merken — die Daten geprüft wie jeder Start; Quittung für das Modell."""
    if len(vorgeschlagen) >= MAX_JE_ZUG:
        return SCHON_VORGESCHLAGEN
    ablauf = next((a for a in ausloeser.vorschlaege() if a.id == kennung(name)), None)
    if ablauf is None:
        return UNBEKANNT
    start, fehler = startdaten.pruefen(ablauf, args or None)
    if fehler:
        return DATEN_FALSCH.format(codes=", ".join(fehler)[:200])
    if start and len(json.dumps(start, ensure_ascii=False)) > MAX_DATEN_ZEICHEN:
        return ZU_LANG
    vorgeschlagen.append({"ablauf": ablauf.id, **({"start": start} if start else {})})
    return QUITTUNG_DIREKT if _direkt(ablauf) else QUITTUNG


def _vorschlag(eintrag: Any) -> tuple[str, dict[str, Any] | None] | None:
    """``(Kennung, Daten)`` — auch die Form vor AS-5a (bloße Kennung) einer laufenden Sitzung."""
    if isinstance(eintrag, str):
        return eintrag, None
    if isinstance(eintrag, dict) and isinstance(eintrag.get("ablauf"), str):
        start = eintrag.get("start")
        return eintrag["ablauf"], start if isinstance(start, dict) and start else None
    return None


def schnellantworten(vorschlaege: list[Any] | None, lang: str) -> list[str]:
    """Knopf-Schnellantworten für die Vorschläge — nur, was noch vorschlagbar ist. Daten der KI
    reisen mit der Herkunft ``ki`` (A5-3)."""
    vorschlagbar = {a.id: a for a in ausloeser.vorschlaege()}
    aus: list[str] = []
    for eintrag in vorschlaege or []:
        if (v := _vorschlag(eintrag)) is None or (a := vorschlagbar.get(v[0])) is None:
            continue
        # Querschnitts-Review AS-5, Befund 1: jeder KI-Knopf trägt die Marke — auch ohne Angaben;
        # ``zug.starten`` fragt damit, bevor er einen laufenden Lauf ersetzt.
        params: dict[str, Any] = {"ablauf": a.id, **({"start": v[1]} if v[1] else {}),
                                  "start_quelle": startdaten.QUELLE_KI}
        label = _titel(a, lang).replace("|", "/")[:_LABEL_ZEICHEN]
        aus.append(f"__action__|{label}|ablauf_starten|" + json.dumps(params, ensure_ascii=False))
    return aus


def direkt_knopf(vorschlaege: list[Any] | None, lang: str) -> str | None:
    """TB-E3: der Knopf des (einen) Vorschlags, wenn sein Ablauf direkt startet — sonst ``None``."""
    vorschlagbar = {a.id: a for a in ausloeser.vorschlaege()}
    for eintrag in vorschlaege or []:
        if (v := _vorschlag(eintrag)) and (a := vorschlagbar.get(v[0])) and _direkt(a):
            [knopf] = schnellantworten([eintrag], lang)
            return knopf
    return None


def direkt_fuer_antwort(session_state: Any, quick_replies: list[str] | None) -> str | None:
    """TB-E3: der gemerkte Direktknopf für ``ui.direkt_start`` — nur, wenn er nach der letzten
    Kürzung noch unter den Schnellantworten steht (sonst startete etwas, das die Person nicht
    sieht). Gilt nur für diesen Zug."""
    knopf = session_state.pop(DIREKT_KEY, None) if isinstance(session_state, dict) else None
    return knopf if isinstance(knopf, str) and knopf in (quick_replies or []) else None


def grenze(hoechstens: int | None) -> int:
    """Wie viele Schnellantworten unter einer Antwort stehen: vier, höchstens die Zahl des
    Gastgebers."""
    return min(_MAX_SCHNELLANTWORTEN, hoechstens) if hoechstens else _MAX_SCHNELLANTWORTEN


def anhaengen(quick_replies: list[str] | None, vorschlaege: list[str] | None, *,
              hoechstens: int | None = None, alle: bool = False) -> list[str]:
    """Die Knöpfe zuerst, insgesamt höchstens vier (wie der Relevanz-Rückfall) bzw. die Höchstzahl
    des Gastgebers. ``alle`` (Review AS-3a, Befund 2): die Knöpfe selbst werden nie gekürzt — die
    Schnellantworten eines wartenden Schritts sind der einzige Weg zurück in den Ablauf; nur
    andere Vorschläge fallen dann weg."""
    if not vorschlaege:
        return list(quick_replies or [])
    platz = grenze(hoechstens)
    if alle:
        platz = max(platz, len(vorschlaege))
    rest = [q for q in quick_replies or [] if q not in vorschlaege]
    return [*vorschlaege, *rest][:platz]


def nimm_an(tool_calls: Any, angeboten: Any, session_state: dict[str, Any],
            messages: list[dict[str, Any]], *, mit_frage: bool = False,
            abgewiesen: set[str] | None = None) -> tuple[set[str], bool]:
    """AS-5b: die Ablauf-Aufrufe einer Runde der Muster-Schleife — virtuell, in der Vorrunde (wie
    die UI-Module): nur Angebotenes, die Angaben geprüft wie jeder Start, der Vorschlag im
    ``session_state`` (den Knopf setzt die Zusammenstellung). Steht ``respond_to_user`` in
    derselben Runde, gibt es keinen Vorschlag mit Angaben (A5-8); unter einer Frage keinen
    (Querschnitt AS-5, Befund 10). ``abgewiesen`` (die Schleife hält es über die Runden):
    derselbe abgewiesene Vorschlag ein zweites Mal ist Stillstand (Review AS-5b, Befund 5).

    Rückgabe: die erledigten Aufruf-Kennungen und ob ein Stillstand vorliegt (dann nimmt die
    Schleife die Ablauf-Werkzeuge für den Rest des Zugs weg)."""
    aufrufe = [tc for tc in tool_calls or [] if ist_ablauf_werkzeug(tc.function.name)]
    if not aufrufe:
        return set(), False
    stillstand = False
    mit_antwort = any(tc.function.name == RESPOND_TO_USER for tc in tool_calls)
    vorgeschlagen = session_state.setdefault(SITZUNG_KEY, [])
    for tc in aufrufe:
        name = tc.function.name
        try:
            args = json.loads(tc.function.arguments or "{}")
        except ValueError:
            args = None
        if name not in angeboten:
            text = NICHT_ANGEBOTEN
        elif not isinstance(args, dict):
            text = DATEN_FALSCH.format(codes="form")
        elif mit_frage:
            text = NACH_DER_FRAGE
        elif mit_antwort and args:
            text = NEBEN_DER_ANTWORT
        else:
            text = merken(vorgeschlagen, name, args)
        angenommen = ist_quittung(text)   # Review TB-E3, Befund 2: auch QUITTUNG_DIREKT
        if not angenommen and abgewiesen is not None:
            schluessel = name + "|" + (tc.function.arguments or "")
            stillstand = stillstand or schluessel in abgewiesen
            abgewiesen.add(schluessel)
        # Review AS-5b, Kleinigkeit 8: eine Spur ohne die Angaben; zweites Review, Befund 3: ein
        # Vorschlag mit Angaben neben der Antwort geht verloren — wie oft, zeigt der Grund.
        grund = ("angenommen" if angenommen
                 else "neben_der_antwort" if text == NEBEN_DER_ANTWORT else "abgewiesen")
        logger.info("Ablauf-Vorschlag (Muster): %s → %s", name, grund)
        messages.append({"role": "tool", "tool_call_id": tc.id, "content": text})
    return {tc.id for tc in aufrufe}, stillstand
