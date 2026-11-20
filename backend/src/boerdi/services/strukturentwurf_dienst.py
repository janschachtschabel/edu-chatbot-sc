"""Der Dienst „Strukturentwurf“ (Paket U2, Plan 2026-11-04 T-5 … T-7): Auftrag → Gliederung.

**Top-down** (Vorgabe Nutzer 2026-11-04): Ebene 1 in einem LLM-Aufruf, Ebene 2 je Punkt mit
``unterthemen > 0`` (parallel), Ebene 3 nur bei ``tiefe = 3`` und nur für Punkte, die das Modell
dafür vorsieht (höchstens :data:`EBENE3_HOECHSTENS` Aufrufe). Je Entwurf laufen höchstens
:data:`PARALLEL` Aufrufe zugleich — darüber liegt der Anbieter-Deckel des Chats
(``llm.chat_completion`` → ``llm_parallel.platz("live")``, ``LLM_MAX_CONCURRENCY``), ein Entwurf
belegt also nie alle Plätze.

**Frist:** ``frist_ende`` ist ein Zeitpunkt der Ereignisschleife (wie ``agent_frist``). Vor jedem
Aufruf weniger als :data:`MINDEST_REST_S` übrig → er entfällt; je Aufruf höchstens
:data:`AUFRUF_FRIST_S`. Ohne Ebene 1 kein Entwurf; fehlt eine tiefere, trägt der Punkt
``ausstehend`` — „liefern, was da ist“, vertieft wird später (``vorlage`` + ``vertiefen``).

**Vorlage** (T-5): der Entwurf, den die Person mit dieser Nachricht geschickt hat. Seine Punkte
bleiben samt Kennungen; neue Unterpunkte bekommen die genannten Punkte (``vertiefen``, über den
Titel) oder alle Blätter oberhalb von ``tiefe``. Umstellen und Umbenennen macht die Person.

**Dokument** (U3-2b, ``aus_dokument``): Ebene 1 sieht die Gliederung des Dokuments der Person mit
Kennungen (≤ :data:`DOKUMENT_GLIEDERUNG` Zeichen) und seinen Anfang; jeder Punkt nennt seine
``abschnitte``, der erste ergibt die ``fundstelle``. Ebene 2 bekommt den Text dieser Abschnitte
samt Unterabschnitten (≤ :data:`DOKUMENT_AUSZUG`). Plan 2026-11-19, A4: bis
``strukturentwurf_dokument.GANZTEXT_ZEICHEN`` sieht Ebene 1 statt des Anfangs den ganzen Text
(vorher moderiert), und E1c: auch jeder Aufruf für Ebene 2 bekommt den ganzen Text
(``strukturentwurf_ganz``, gleicher Anfang für das Prompt-Caching); A5: ``unterthemen: 0`` an
einem Punkt mit Text heißt „nicht angegeben“. A1: vorübergehende Fehler des Anbieters werden
einmal wiederholt.

Eine **reine Funktion** Auftrag → Struktur mit ersetzbarer LLM-Naht (``llm``): so kann sie später
als Job hinter der B-API laufen (Konzept §16.15, „Dienste sind reine Funktionen“).
"""

from __future__ import annotations

import asyncio
import copy
import json
import logging
from collections.abc import Iterator
from dataclasses import dataclass
from itertools import zip_longest
from typing import TYPE_CHECKING, Any, Final

from boerdi.services import strukturentwurf_dokument as dokument_teil
from boerdi.services import strukturentwurf_lauf as lauf_teil
from boerdi.services import strukturentwurf_prompt as prompt
from boerdi.services import strukturentwurf_wiederholen as wiederholen
from boerdi.services.llm_parallel import LlmAusgelastet
from boerdi.services.strukturentwurf_auszug import Moderieren
from boerdi.services.strukturentwurf_dokument import (  # noqa: F401 — wie bisher
    DOKUMENT_ANFANG,
    DOKUMENT_GLIEDERUNG,
)

# Review A (fünftes), MINOR 6: der Lauf in ``strukturentwurf_lauf`` (die alten Namen bleiben)
from boerdi.services.strukturentwurf_lauf import (  # noqa: F401 — Re-Export
    AUFRUF_FRIST_S,
    DOKUMENT_AUSZUG,
    MINDEST_REST_S,
    PARALLEL,
    Auftrag,
    LlmJson,
    _jetzt,
    _Lauf,
    parallel,
)

# Review A (zweites), MINOR 7: das Platzhalter-Thema in eigenem Modul (der alte Name bleibt)
from boerdi.services.strukturentwurf_platzhalter import platzhalter_thema  # noqa: F401
from boerdi.ui_module import strukturentwurf as se
from boerdi.ui_module import strukturentwurf_text as st

if TYPE_CHECKING:
    from boerdi.services.dokumente.stand import DokumentStand

logger = logging.getLogger(__name__)

EBENE3_HOECHSTENS: Final = 24
#: Frist ohne Lauf-Frist (Muster-Weg, Brücke): so lange wartet die Person höchstens.
GESAMT_FRIST_S: Final = 90.0
#: Unterpunkte je Punkt beim Vertiefen einer Vorlage (das Modell kennt dort keine Planzahl).
VORLAGE_UNTERTHEMEN: Final = 4
PHASE: Final = "strukturentwurf"
PHASE_VORWAERMEN: Final = "strukturentwurf_vorwaermen"
_TOKENS_OBEN: Final = 2500
#: Felder der Block-Daten, die aus einer Vorlage übernommen werden (ohne die Antwort-Merker).
_WURZEL_FELDER: Final = ("titel", "quelle", "thema", "fach", "bildungsstufe", "wurzel_wlo_id",
                         "gekuerzt", "quelle_block", "knoten", se.RESTE)



@dataclass(frozen=True, slots=True)
class Erzeugt:
    """Die Block-Daten — oder ``None`` mit ``grund`` (``fehler``, ``ausgelastet``, ``frist``,
    ``leer``, ``voruebergehend``)."""

    daten: dict[str, Any] | None
    grund: str | None = None


def llm_json(usage_acc: dict[str, Any] | None, phase: str = PHASE) -> LlmJson:
    """Die echte Naht: ein JSON-Aufruf über den Transport, gebucht im Zähler des Zugs (unter
    ``phase``; das Vorwärmen unter :data:`PHASE_VORWAERMEN`, fünftes Review A, NIT 9)."""

    async def rufe(nachrichten: list[dict[str, Any]], max_tokens: int, frist_s: float,
                   platz_frist_s: float) -> Any:
        from boerdi.services import llm

        # Eigene Platz-Geduld (Review U2, Befund 3): läuft sie ab, scheitert nur dieser Aufruf —
        # der Zug gilt nicht als ausgelastet (``llm_parallel._anstellen``).
        resp = await llm.chat_completion(
            messages=nachrichten, temperature=0.4, max_tokens=max_tokens,
            response_format={"type": "json_object"}, usage_acc=usage_acc, phase=phase,
            frist_s=frist_s, platz_frist_s=platz_frist_s)
        return json.loads(resp.choices[0].message.content or "{}")

    return rufe


def _mit_pfad(knoten: list[dict[str, Any]], ebene: int = 1, pfad: tuple[str, ...] = ()
              ) -> Iterator[tuple[dict[str, Any], int, list[str], list[str]]]:
    """Jeder Punkt mit Ebene, Titeln der Vorfahren und Titeln der Geschwister."""
    for k in knoten:
        geschwister = [g["titel"] for g in knoten if g is not k]
        yield k, ebene, list(pfad), geschwister
        yield from _mit_pfad(k.get("kinder") or [], ebene + 1, (*pfad, k["titel"]))


async def _ebene(lauf: _Lauf, ziele: list[tuple[dict[str, Any], int, list[str], list[str]]],
                 *, letzte: bool) -> None:
    if lauf.text is not None and ziele and not ziele[0][2]:
        await lauf.vorwaermen()              # Plan E1c: nur vor den oberen Punkten (Ebene 2)
    await asyncio.gather(*(lauf.kinder(k, n, pfad, g, letzte=letzte) for k, n, pfad, g in ziele))


async def _obere_ebene(lauf: _Lauf) -> str | None:
    """Ebene 1 in die Daten; ``None`` oder der Grund, warum es keinen Entwurf gibt."""
    a = lauf.auftrag
    if lauf.rest() < lauf_teil.MINDEST_REST_S:   # eine Quelle (Tests setzen sie dort)
        return "frist"
    try:
        nachrichten = dokument_teil.aufforderung_oben(lauf.auftrag, lauf.daten, lauf.dokument,
                                                      text=lauf.text or "")
        # Plan 2026-11-19, A1 (E3): ein 503 des Anbieters einmal wiederholen
        antwort = await wiederholen.einmal_wiederholt(
            lambda: lauf.rufe(nachrichten, _TOKENS_OBEN), lauf.rest, lauf_teil.MINDEST_REST_S)
    except LlmAusgelastet:
        return "ausgelastet"
    except TimeoutError:
        return "frist"
    except Exception as e:  # noqa: BLE001 — Grund ins Log, an die KI nur „ließ sich nicht erzeugen“
        logger.info("Strukturentwurf: obere Ebene nicht erzeugt (%s)", type(e).__name__)
        # A1, Befund S1: ein vorübergehender Fehler ist keine Sackgasse — „gleich nochmal“
        return "voruebergehend" if wiederholen.voruebergehend(e) else "fehler"
    d = lauf.daten
    if isinstance(antwort, dict):
        if isinstance(antwort.get("titel"), str) and (
                titel := " ".join(antwort["titel"].split())[:se.TITEL_ZEICHEN]):
            d["titel"] = titel
        for feld, form in (("fach", se.fach), ("bildungsstufe", se.bildungsstufe)):
            if feld not in d and (wert := form(antwort.get(feld))):
                d[feld] = wert
    # Review TW-1, Befund 1: aus einem Dokument je Ordnungselement ein Punkt (bis zum Deckel) —
    # ein Lehrplan mit 13 Lernfeldern verlöre sonst drei
    oben = se.HOECHSTENS_OBEN if lauf.dokument is not None else a.anzahl_oben
    paare: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for p in prompt.punkte(antwort)[:oben]:
        if k := se.knoten_aus(p, se.neue_kennung(None, lauf.vergeben), wurzel=d):
            paare.append((k, p))
            d["knoten"].append(k)
            lauf.plaene[k["id"]] = prompt.zahl_unterthemen(p, prompt.UNTERTHEMEN_OBEN)
    if lauf.dokument is not None:
        # Review A (zweites), MINOR 7: Fundstelle und Plan in ``strukturentwurf_dokument``
        dokument_teil.nacharbeit(paare, lauf.plaene, lauf.dokument, ganz=lauf.text is not None)
    lauf.zahl = len(d["knoten"])
    return None if d["knoten"] else "leer"


async def _neu(lauf: _Lauf) -> Erzeugt:
    if grund := await _obere_ebene(lauf):
        return Erzeugt(None, grund)
    if lauf.auftrag.tiefe >= 2:
        ziele = [(k, lauf.plaene[k["id"]], p, g) for k, _, p, g in _mit_pfad(lauf.daten["knoten"])
                 if lauf.plaene.get(k["id"])]
        await _ebene(lauf, ziele, letzte=lauf.auftrag.tiefe == 2)
    if lauf.auftrag.tiefe >= 3:
        # Review 16.11., MAJOR: reihum über die oberen Punkte (erst je das erste Kind, dann das
        # zweite …) — in Baumreihenfolge reichte der Deckel bei 5 bis 8 Kindern je Punkt nur für
        # die ersten drei oberen Punkte.
        reihen = [[(k, lauf.plaene[k["id"]], p, g) for k, ebene, p, g in _mit_pfad([oben])
                   if ebene == 2 and lauf.plaene.get(k["id"])] for oben in lauf.daten["knoten"]]
        ziele = [z for runde in zip_longest(*reihen) for z in runde if z is not None]
        # Drittes Review U2, Befund 3: was über den Deckel geht, ist vorgesehen, aber nicht erzeugt
        # — ``ausstehend`` (die Quittung zählt es), nicht still weg.
        for k, *_ in ziele[EBENE3_HOECHSTENS:]:
            k["ausstehend"] = True
        await _ebene(lauf, ziele[:EBENE3_HOECHSTENS], letzte=True)
    return Erzeugt(lauf.daten)


async def _vertiefen(lauf: _Lauf) -> Erzeugt:
    gesucht = {" ".join(t.split()).casefold() for t in lauf.auftrag.vertiefen}
    sichtbar = lauf.sichtbar or set()
    sichtbare_titel = {k["titel"] for k, _ in se.alle(lauf.daten["knoten"]) if k["id"] in sichtbar}
    ziele = []
    for k, ebene, pfad, g in _mit_pfad(lauf.daten["knoten"]):
        if ebene >= se.HOECHSTE_TIEFE or k["id"] not in sichtbar:
            continue
        # Geschwister nur aus dem sichtbaren Teil (Gegenreview U2, Befund 3); der Pfad liegt davor
        # (die Kompaktfassung steht in Lesereihenfolge) und ist damit sichtbar.
        g = [t for t in g if t in sichtbare_titel]
        passt = (" ".join(k["titel"].split()).casefold() in gesucht if gesucht
                 else not k.get("kinder") and ebene < lauf.auftrag.tiefe)
        if passt and len(k.get("kinder") or []) < se.HOECHSTENS_KINDER:
            ziele.append((k, VORLAGE_UNTERTHEMEN, pfad, g))
    if not ziele:
        # Review U2, Befund 5: kein passender Titel, kein Blatt über der Tiefe, kein Platz — kein
        # Erfolg mit unverändertem Entwurf, sondern ein Grund für die KI.
        return Erzeugt(None, "nichts_zu_vertiefen")
    # Eine Ebene je Vertiefung: die neuen Punkte sind Blätter (die Person sieht sie zuerst).
    await _ebene(lauf, ziele, letzte=True)
    return Erzeugt(lauf.daten)


async def erzeugen(auftrag: Auftrag, *, llm: LlmJson, frist_ende: float,
                   vorlage: dict[str, Any] | None = None,
                   dokument: DokumentStand | None = None,
                   moderieren: Moderieren | None = None,
                   ganz_moderiert: bool = False,
                   llm_vorwaermen: LlmJson | None = None) -> Erzeugt:
    """Einen Entwurf erzeugen — aus dem ``dokument`` der Person oder frei — oder eine ``vorlage``
    vertiefen. Block-Daten nach ``ui-strukturentwurf/manifest.json`` (``eingabe``); geprüft wird
    beim Aufrufer. Mit ``dokument`` gehört ``moderieren`` dazu (``ui_module/dienst._moderation``):
    ohne gehen die Auszüge für Ebene 2 ungeprüft ans Modell.

    ``ganz_moderiert`` (zweites Review A, MINOR 5): der Aufrufer hat den GANZEN Text des Dokuments
    moderiert (``ui_module/dienst_ganztext``) — nur dann sehen Ebene 1 und (Plan E1c) jeder Aufruf
    für Ebene 2 ihn ganz (bis ``GANZTEXT_ZEICHEN``), ohne zweite Moderation. Ohne die Zusage gilt
    der Weg „gliederung“ mit moderierten Auszügen. ``llm_vorwaermen``: die Naht für den
    Vorwärm-Aufruf (eigene Phase, fünftes Review A, NIT 9); ohne sie ``llm``."""
    if vorlage is not None:
        daten = {f: copy.deepcopy(vorlage[f]) for f in _WURZEL_FELDER if f in vorlage}
        # Plan 2026-11-16, Durchtest TG-7 (m2): der Kopf der Vorlage (etwa aus den Ordnern) bekommt
        # Stufe und Fach des Auftrags (die Antworten des Laufs, ``vorbelegung``) und ein Thema, wo
        # er keins hat — Titel, Quelle und Punkte bleiben die der Vorlage
        for feld, form in (("fach", se.fach), ("bildungsstufe", se.bildungsstufe)):
            if wert := form(getattr(auftrag, feld)):
                daten[feld] = wert
        if not str(daten.get("thema") or "").strip() and auftrag.thema.strip():
            daten["thema"] = " ".join(auftrag.thema.split())[:200]
        lauf = _Lauf(auftrag, llm, frist_ende, daten, sichtbar=st.sichtbare_ids(daten))
        lauf.vergeben = {k["id"] for k, _ in se.alle(daten.get("knoten") or [])}
        lauf.zahl = len(lauf.vergeben)
        return await _vertiefen(lauf)
    daten: dict[str, Any] = {"titel": " ".join(auftrag.thema.split())[:se.TITEL_ZEICHEN],
                             "quelle": "ki" if dokument is None else "dokument",
                             "thema": auftrag.thema[:200]}
    for feld, form in (("fach", se.fach), ("bildungsstufe", se.bildungsstufe)):
        if wert := form(getattr(auftrag, feld)):
            daten[feld] = wert
    daten["knoten"] = []
    if gelesen := dokument_teil.gelesen(dokument, ganz=ganz_moderiert):
        daten["gelesen"] = gelesen          # Plan 2026-11-19, A6 (E7): nur Anzeige, nie an die KI
    text = dokument_teil.ganzer_text(dokument) if ganz_moderiert else None
    return await _neu(_Lauf(auftrag, llm, frist_ende, daten, dokument=dokument,
                            moderieren=moderieren, text=text, llm_vorwaermen=llm_vorwaermen))
