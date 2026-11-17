"""Plan 2026-11-16, TG-5 (G-E8): feste Zuordnung der Antworten eines Laufs zum Auftrag des
Strukturentwurfs — im Code, nicht über die KI.

Bis TG-5 erreichten die Antworten auf die Leitfragen den Generator nur über die KI (Zeile
``[ABLAUFDATEN — …]``): „ausführlich“ wurde nicht in ``tiefe=3`` umgerechnet, die Stufe kam nur
an, wenn die KI sie weitergab. Jetzt belegt ein KI-Schritt mit ``agent.vorbelegen: true`` die
Argumente von ``ui_strukturentwurf`` selbst vor:

- ``umfang`` → ``tiefe`` (1/2/3) und ``anzahl_oben`` (6/10/12) — aus dem Label der Option (immer
  das deutsche, ``treiber.wahl_wert``) bzw. getipptem Text mit einem der Schlüsselwörter (ein
  verneintes zählt nicht); ein anderer Text geht als Zeile „Umfang: …“ in die Hinweise;
- ``stufe`` → ``bildungsstufe`` (die Labels des Ablaufs als WLO-Label, getippter Text wie er ist;
  „allgemein“ bzw. „für alle“ setzt nichts);
- ``thema`` → ``thema``;
- ``zweck``, ``publikum``, ``soll_ist`` und ``hinweise`` → je eine Zeile in ``hinweise`` (Vorsatz
  in der Sprache des Zugs; die Hinweise der Person bekommen den übrigen Platz).

Nur Teile, die in DIESEM Lauf beantwortet wurden (``lauf.antworten``, wie
``ki_schritt.daten_zeile``) — ein Neustart im selben Vorgang trüge sonst alte Antworten weiter.
Bestehende Abläufe ohne den Schalter ändern sich nicht.

**Vorrang (Entscheid TG-5): ein Argument der KI geht vor.** Die KI ruft ``ui_strukturentwurf`` wie
bisher mit Argumenten; die Vorbelegung füllt nur, was der Aufruf nicht setzt (:func:`vorbelegt`).
So kann die Person im Gespräch umentscheiden („doch nur eine Ebene“) — die KI gibt dann den neuen
Wert mit. ``tiefe`` und ``anzahl_oben`` gelten nur zusammen; ``""`` löscht einen vorbelegten Text
(Review TG-4–6, MINOR 5). Damit die KI die Antworten nicht aus Gewohnheit überschreibt, sagt ihr
die Zeile ``[VORBELEGT — …]`` (:func:`zeile`), welche Argumente der Ablauf setzt, und dass sie sie
nur bei einer Änderung im Gespräch nennt. Die Hinweise werden zusammengeführt: die Zeilen des
Ablaufs zuerst, dann die Wünsche aus dem Gespräch (die KI-Hinweise), gedeckelt auf die Länge des
Schemas. Rein, ohne I/O außer dem Lader der Teile.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from collections.abc import Awaitable, Callable, Iterable
from typing import Any, Final

from boerdi.domain.config_models.ablauf import Schritt

logger = logging.getLogger(__name__)

#: ``umfang`` → (``tiefe``, ``anzahl_oben``) nach Wortanfang (klein, ohne Akzente verglichen).
UMFANG: Final[dict[tuple[int, int], tuple[str, ...]]] = {
    (1, 6): ("kompakt", "compact", "knapp", "grob", "rough", "brief"),
    (2, 10): ("mittel", "medium"),
    (3, 12): ("ausfuhrlich", "ausfuehrlich", "detailliert", "detailed", "fein"),
}
#: Review TG-4–6, NIT 16: ein Schlüsselwort hinter einer Verneinung gilt nicht („nicht zu fein,
#: eher grob“ ist kompakt). Geprüft wird das Wort davor, bei „zu“/„so“ das davor.
_VERNEINUNG: Final = frozenset({"nicht", "kein", "keine", "nie", "not", "no", "never"})
_VERSTAERKER: Final = frozenset({"zu", "so", "allzu", "too"})
_WORT: Final = re.compile(r"\w+")
#: Die Stufen-Labels der Abläufe als WLO-Label (Beschreibung von ``bildungsstufe`` im Manifest).
#: ``None``: bewusst keine Stufe (für alle).
STUFEN: Final[dict[str, str | None]] = {
    "grundschule": "Primarstufe", "primarstufe": "Primarstufe",
    "sekundarstufe i": "Sekundarstufe I", "sek i": "Sekundarstufe I",
    "sekundarstufe ii": "Sekundarstufe II", "sek ii": "Sekundarstufe II",
    "berufliche bildung": "Berufliche Bildung", "beruf": "Berufliche Bildung",
    "hochschule": "Hochschule", "erwachsenenbildung": "Erwachsenenbildung",
    "allgemein": None, "alle, ohne bildungsstufe": None, "für alle": None,
}
#: Die Teile, die als Zeile in ``hinweise`` gehen, mit ihrem Vorsatz je Sprache (Review TG-4–6,
#: MINOR 11). Der Wert bleibt das deutsche Label der Wahl (``treiber.wahl_wert``) bzw. der Text der
#: Person — die englischen ``vorgaben`` nennen die deutschen Werte mit.
#: Zweites Review TG-4–6, E: ``publikum`` ohne Schritt entfällt („Für wen“ steckt in ``stufe``).
ZEILEN: Final[tuple[tuple[str, dict[str, str]], ...]] = (
    ("zweck", {"de": "Zweck", "en": "Purpose"}),
    ("soll_ist", {"de": "Soll oder Ist", "en": "Target or actual"}),
    ("hinweise", {"de": "Hinweise der Person", "en": "Notes from the person"}),
)
_UMFANG_VORSATZ: Final = {"de": "Umfang", "en": "Scope"}
#: E: eine getippte Stufe oder Zielgruppe („Klasse 7“, „Erwachsene“) ist kein WLO-Label — sie geht
#: als Zeile in die Hinweise, nicht in ``bildungsstufe``.
_STUFE_VORSATZ: Final = {"de": "Für wen/Stufe", "en": "Audience/level"}
#: E: der Teil der Grundlage — getippt (kein Label einer Option) ist er das Thema (NIT 15).
GRUNDLAGE: Final = "grundlage"
#: I: so viel Platz bleibt in ``hinweise`` für die Wünsche aus dem Gespräch (die KI-Hinweise).
_KI_PLATZ: Final = 150
#: Wie das Manifest von ``ui_strukturentwurf`` (``dienst.parameter``).
HINWEISE_ZEICHEN: Final = 600
_THEMA_ZEICHEN: Final = 200
#: Je Zeile höchstens so viel von einer kurzen Antwort (Zweck, für wen, Soll/Ist, Umfang) — die
#: Hinweise der Person bekommen den Rest bis :data:`HINWEISE_ZEICHEN` (MINOR 6).
_ZEILE_ZEICHEN: Final = 100
#: Was die Vorbelegung setzen kann (auch für :func:`zeile`).
ARGUMENTE: Final = ("thema", "bildungsstufe", "tiefe", "anzahl_oben", "hinweise")
#: MINOR 5: diese beiden gehören zusammen — setzt die KI eines, setzt der Ablauf keines.
_PAAR: Final = ("tiefe", "anzahl_oben")
#: MINOR 5: ``""`` von der KI löscht einen vorbelegten Text (``thema`` ist Pflicht, bleibt).
_LOESCHBAR: Final = ("bildungsstufe", "hinweise")


def _flach(text: str) -> str:
    """Klein, ohne Akzente und Umlaut-Punkte, Leerraum zusammengezogen — „Ausführlich“ wie
    „ausfuhrlich“."""
    zerlegt = unicodedata.normalize("NFKD", text.casefold())
    return " ".join("".join(z for z in zerlegt if not unicodedata.combining(z)).split())


def umfang(text: str) -> tuple[int, int] | None:
    """(``tiefe``, ``anzahl_oben``) für eine Antwort auf „Wie fein?“ — ``None`` ohne Schlüsselwort.
    Bei zwei Treffern (etwa „mittel bis ausführlich“) gilt der erste im Text; ein verneinter
    („nicht zu fein“) zählt nicht (NIT 16)."""
    woerter = _WORT.findall(_flach(text))
    for n, wort in enumerate(woerter):
        davor = woerter[n - 1] if n else ""
        vorvor = woerter[n - 2] if n > 1 else ""
        if davor in _VERNEINUNG or (davor in _VERSTAERKER and vorvor in _VERNEINUNG):
            continue
        for werte, schluessel in UMFANG.items():
            if any(wort.startswith(k) for k in schluessel):
                return werte
    return None


def bildungsstufe(text: str) -> tuple[bool, str | None]:
    """(bekannt, Wert) für eine Antwort auf „Stufe“: ein bekanntes Label wird ein WLO-Label (oder
    bewusst nichts, ``None``). Zweites Review E: getippter Text ist nicht bekannt — ``(False,
    None)``, er geht als Zeile in die Hinweise."""
    flach = _flach(text)
    for k, v in STUFEN.items():
        if _flach(k) == flach:
            return True, v
    return False, None


async def _thema_aus_daten(teile: Callable[[str], Awaitable[Any]]) -> str | None:
    """Plan 2026-11-16, Durchtest TG-7 (m1): ohne getippte Grundlage das Thema aus den Daten —
    sonst machte die KI den Zweck („Unterricht planen“) oder einen Platzhalter zum Thema.

    - Ordner-Weg (``ordnerweg``): der Name des Wurzelordners;
    - Datei-Weg (``metadaten`` ohne ``ordnerweg``): keins — das Thema leitet die KI aus den
      Inhalten ab (``vorgaben`` des Schritts);
    - Dokument-Weg: der Name des ersten Strukturdokuments (``strukturdokument``, sonst
      ``document``) ohne Endung.

    Die KI bleibt vorrangig (:func:`vorbelegt`). Ein Lesefehler heißt „kein Thema“."""
    from boerdi.services.dokumente import strukturdokument_teil as sd
    from boerdi.services.teil_verweise import stelle

    try:
        if await teile("ordnerweg") not in (None, ""):
            name = stelle(await teile("structure"), "struktur.name")
        elif await teile("metadaten") is not None:
            return None
        elif eintraege := sd.eintraege(await teile(sd.TEIL)):
            name = _ohne_endung(eintraege[0].get("name"))
        else:
            dok = await teile("document")
            name = _ohne_endung(dok.get("name")) if isinstance(dok, dict) else None
    except Exception as fehler:  # noqa: BLE001 — ohne Thema entscheidet die KI wie bisher
        logger.warning("Ablauf: Thema aus den Daten nicht lesbar (%s)", type(fehler).__name__)
        return None
    thema = _sauber(name, _THEMA_ZEICHEN) if isinstance(name, str) else ""
    return thema if len(thema) >= 2 else None


def _ohne_endung(name: Any) -> str | None:
    if not isinstance(name, str):
        return None
    return re.sub(r"\.[A-Za-z0-9]{1,5}\Z", "", name.strip()) or None


def _getippte_grundlage(ablauf: Any, wert: str) -> bool:
    """E: ist ``wert`` getippt — kein deutsches Label einer Option der Frage, die ``grundlage``
    schreibt? Ohne Ablauf (oder ohne solche Frage) nein."""
    labels = {(o.label.get("de") or "").strip()
              for s in (getattr(ablauf, "schritte", None) or [])
              if s.schreibt == GRUNDLAGE and s.optionen for o in s.optionen}
    return bool(labels) and wert.strip() not in labels


def _sauber(text: str, grenze: int) -> str:
    """Einzeilig, entschärft wie die Zeile ``[ABLAUFDATEN]`` (``ki_schritt._wert``) — Eingabe der
    Person, die in den Auftrag des Generators geht."""
    from boerdi.services.ablauf.ki_schritt import _wert

    return _wert(text, grenze)


def _vorsatz(texte: dict[str, str], sprache: str) -> str:
    return texte.get(sprache) or texte["de"]


async def vorbelegung(schritt: Schritt, teile: Callable[[str], Awaitable[Any]] | None,
                      in_diesem_lauf: Iterable[str], sprache: str = "de", *,
                      ablauf: Any = None) -> dict[str, Any]:
    """Die Argumente, die der Ablauf am KI-Schritt ``schritt`` vorbelegt — leer ohne
    ``agent.vorbelegen`` oder ohne beantwortete Teile. Ein Lesefehler beendet den Zug nie.
    ``ablauf`` (E): mit ihm wird eine getippte Grundlage das ``thema``."""
    if schritt.agent is None or not schritt.agent.vorbelegen or teile is None:
        return {}
    gilt = set(in_diesem_lauf)
    werte: dict[str, str] = {}
    try:
        for name in ("umfang", "stufe", GRUNDLAGE, *(n for n, _v in ZEILEN)):
            if name in gilt and isinstance(w := await teile(name), str) and w.strip():
                werte[name] = w.strip()
    except Exception as fehler:  # noqa: BLE001 — ohne Vorbelegung entscheidet die KI wie bisher
        logger.warning("Ablauf: Vorbelegung nicht lesbar (%s)", type(fehler).__name__)
        return {}
    aus: dict[str, Any] = {}
    zeilen: list[str] = []
    if "umfang" in werte:
        if (paar := umfang(werte["umfang"])) is not None:
            aus["tiefe"], aus["anzahl_oben"] = paar
        else:
            zeilen.append(f"{_vorsatz(_UMFANG_VORSATZ, sprache)}: "
                          f"{_sauber(werte['umfang'], _ZEILE_ZEICHEN)}")
    if "stufe" in werte:
        bekannt, stufe = bildungsstufe(werte["stufe"])
        if stufe:
            aus["bildungsstufe"] = stufe
        elif not bekannt:
            zeilen.append(f"{_vorsatz(_STUFE_VORSATZ, sprache)}: "
                          f"{_sauber(werte['stufe'], _ZEILE_ZEICHEN)}")
    if (GRUNDLAGE in werte and _getippte_grundlage(ablauf, werte[GRUNDLAGE])
            and len(thema := _sauber(werte[GRUNDLAGE], _THEMA_ZEICHEN)) >= 2):
        aus["thema"] = thema
    elif thema := await _thema_aus_daten(teile):
        aus["thema"] = thema
    for name, vorsatz in ZEILEN:
        if name not in werte:
            continue
        kopf = f"{_vorsatz(vorsatz, sprache)}: "
        # MINOR 6: die Hinweise der Person nicht auf eine kurze Zeile kürzen — sie bekommen den
        # Platz, der nach den anderen Zeilen bleibt
        bisher = sum(len(z) + 1 for z in zeilen)
        platz = (HINWEISE_ZEICHEN - bisher - len(kopf) if name == "hinweise"
                 else _ZEILE_ZEICHEN)
        if platz >= 20:
            zeilen.append(kopf + _sauber(werte[name], platz))
    if zeilen:
        aus["hinweise"] = "\n".join(zeilen)[:HINWEISE_ZEICHEN]
    return aus


def vorbelegt(args: dict[str, Any], vorbelegung: dict[str, Any] | None) -> dict[str, Any]:
    """Der Aufruf der KI mit der Vorbelegung: ein gesetztes Argument der KI geht vor (Entscheid
    TG-5), fehlende kommen aus dem Lauf; die Hinweise werden zusammengeführt (Ablauf zuerst).

    Review TG-4–6, MINOR 5: ``tiefe`` und ``anzahl_oben`` gelten nur zusammen — setzt die KI eines,
    bleibt das andere ihre Sache (sonst etwa „1 Ebene, 12 oben“). ``""`` löscht einen vorbelegten
    Text (``bildungsstufe``, ``hinweise``)."""
    if not vorbelegung or not isinstance(args, dict):
        return args
    fuellen = {k: v for k, v in vorbelegung.items() if k != "hinweise" and k not in args}
    if any(k in args for k in _PAAR):
        fuellen = {k: v for k, v in fuellen.items() if k not in _PAAR}
    neu = {**fuellen, **args}
    for k in _LOESCHBAR:
        if neu.get(k) == "":
            del neu[k]
    eigene = str(vorbelegung.get("hinweise") or "").strip()
    if eigene and args.get("hinweise") != "":
        von_ki = " ".join(str(args.get("hinweise") or "").split())
        if von_ki and von_ki not in eigene:
            # zweites Review I: für die Wünsche aus dem Gespräch bleibt Platz (bis zu
            # :data:`_KI_PLATZ`) — gekürzt wird zuerst die Zeile des Ablaufs
            eigene = eigene[:HINWEISE_ZEICHEN - min(len(von_ki), _KI_PLATZ) - 1].rstrip()
            rest = HINWEISE_ZEICHEN - len(eigene) - 1
            eigene = f"{eigene}\n{von_ki[:rest]}"
        neu["hinweise"] = eigene[:HINWEISE_ZEICHEN]
    return neu


_ZEILE: Final = {
    "de": ("[VORBELEGT — Diese Argumente von ui_strukturentwurf setzt der Ablauf aus den Antworten "
           "selbst: {namen}. Gib sie nur an, wenn die Person sie in diesem Gespräch ändert — tiefe "
           "und anzahl_oben dann beide; \"\" löscht bildungsstufe oder hinweise. Deine hinweise "
           "kommen zu denen des Ablaufs dazu.]"),
    "en": ("[VORBELEGT — The workflow sets these arguments of ui_strukturentwurf from the answers "
           "itself: {namen}. Only pass them if the person changes them in this conversation — then "
           "tiefe and anzahl_oben together; \"\" clears bildungsstufe or hinweise. Your hinweise "
           "are added to the workflow's.]"),
}


def zeile(vorbelegung: dict[str, Any] | None, sprache: str = "de") -> str:
    """``[VORBELEGT — …]`` für die KI: welche Argumente der Ablauf setzt — nur Namen und die Zahlen
    für Tiefe und Breite, keine Eingaben der Person (die stehen in ``[ABLAUFDATEN]``)."""
    if not vorbelegung:
        return ""
    namen = [f"{n}={vorbelegung[n]}" if n in _PAAR else n
             for n in ARGUMENTE if n in vorbelegung]
    return _ZEILE.get(sprache, _ZEILE["de"]).format(namen=", ".join(namen))
