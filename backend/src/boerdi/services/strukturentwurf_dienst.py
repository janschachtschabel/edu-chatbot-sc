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
samt Unterabschnitten (≤ :data:`DOKUMENT_AUSZUG`). Das ganze Dokument sieht das Modell nie.

Eine **reine Funktion** Auftrag → Struktur mit ersetzbarer LLM-Naht (``llm``): so kann sie später
als Job hinter der B-API laufen (Konzept §16.15, „Dienste sind reine Funktionen“).
"""

from __future__ import annotations

import asyncio
import copy
import json
import logging
from collections.abc import Awaitable, Callable, Iterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final

from boerdi.services import llm_parallel
from boerdi.services import strukturentwurf_dokument as dokument_teil
from boerdi.services import strukturentwurf_prompt as prompt
from boerdi.services.llm_parallel import LlmAusgelastet
from boerdi.services.strukturentwurf_auszug import Auszuege, Moderieren
from boerdi.services.strukturentwurf_dokument import (  # noqa: F401 — wie bisher
    DOKUMENT_ANFANG,
    DOKUMENT_GLIEDERUNG,
)
from boerdi.ui_module import strukturentwurf as se
from boerdi.ui_module import strukturentwurf_text as st

if TYPE_CHECKING:
    from boerdi.services.dokumente.stand import DokumentStand

logger = logging.getLogger(__name__)

#: Höchstens so viele Aufrufe je Entwurf zugleich — bei einem kleinen Anbieter-Deckel weniger
#: (:func:`parallel`, Review U2, Befund 3).
PARALLEL: Final = 5
MINDEST_REST_S: Final = 8.0
AUFRUF_FRIST_S: Final = 40.0
EBENE3_HOECHSTENS: Final = 24
#: Frist ohne Lauf-Frist (Muster-Weg, Brücke): so lange wartet die Person höchstens.
GESAMT_FRIST_S: Final = 90.0
#: Unterpunkte je Punkt beim Vertiefen einer Vorlage (das Modell kennt dort keine Planzahl).
VORLAGE_UNTERTHEMEN: Final = 4
PHASE: Final = "strukturentwurf"
_TOKENS_OBEN: Final = 2500
#: Deckel der Dokument-Auszüge (U3-2b): Gliederung und Anfang für Ebene 1, Text je Punkt.
DOKUMENT_AUSZUG: Final = 6000
_TOKENS_KINDER: Final = 1600
#: Felder der Block-Daten, die aus einer Vorlage übernommen werden (ohne die Antwort-Merker).
_WURZEL_FELDER: Final = ("titel", "quelle", "thema", "fach", "bildungsstufe", "wurzel_wlo_id",
                         "gekuerzt", "knoten")

#: (Nachrichten, max_tokens, frist_s, platz_frist_s) → geparstes JSON; wirft bei jedem Fehler.
LlmJson = Callable[[list[dict[str, Any]], int, float, float], Awaitable[Any]]


def parallel() -> int:
    """Eigene Parallelität: höchstens :data:`PARALLEL`, höchstens die Hälfte des Anbieter-Deckels
    (``LLM_MAX_CONCURRENCY``, AcademicCloud 2) — ein Entwurf belegt nie alle Plätze des Chats."""
    return min(PARALLEL, max(1, llm_parallel.anbieter_deckel() // 2))


@dataclass(frozen=True, slots=True)
class Auftrag:
    thema: str
    fach: str | None = None
    bildungsstufe: str | None = None
    anzahl_oben: int = 10
    tiefe: int = 2
    hinweise: str = ""
    vertiefen: tuple[str, ...] = ()
    #: TW-2: Vorgaben der Redaktion aus dem Ablauf (Systemteil, nie Daten der Person).
    vorgaben: str = ""


@dataclass(frozen=True, slots=True)
class Erzeugt:
    """Die Block-Daten — oder ``None`` mit ``grund`` (``fehler``, ``ausgelastet``, ``frist``,
    ``leer``)."""

    daten: dict[str, Any] | None
    grund: str | None = None


def llm_json(usage_acc: dict[str, Any] | None) -> LlmJson:
    """Die echte Naht: ein JSON-Aufruf über den Transport, gebucht im Zähler des Zugs."""

    async def rufe(nachrichten: list[dict[str, Any]], max_tokens: int, frist_s: float,
                   platz_frist_s: float) -> Any:
        from boerdi.services import llm

        # Eigene Platz-Geduld (Review U2, Befund 3): läuft sie ab, scheitert nur dieser Aufruf —
        # der Zug gilt nicht als ausgelastet (``llm_parallel._anstellen``).
        resp = await llm.chat_completion(
            messages=nachrichten, temperature=0.4, max_tokens=max_tokens,
            response_format={"type": "json_object"}, usage_acc=usage_acc, phase=PHASE,
            frist_s=frist_s, platz_frist_s=platz_frist_s)
        return json.loads(resp.choices[0].message.content or "{}")

    return rufe


def _jetzt() -> float:
    return asyncio.get_running_loop().time()


@dataclass
class _Lauf:
    auftrag: Auftrag
    llm: LlmJson
    frist_ende: float
    daten: dict[str, Any]
    vergeben: set[str] = field(default_factory=set)
    zahl: int = 0
    #: Kennung → vom Modell vorgesehene Zahl der Unterpunkte.
    plaene: dict[str, int] = field(default_factory=dict)
    #: Mit Vorlage: nur diese Punkte (die Kompaktfassung, die KI und Prüfung sahen) gehen an den
    #: Dienst, und nur ihre Titel (Gegenreview U2, Befund 3); ``None`` ohne Vorlage.
    sichtbar: set[str] | None = None
    dokument: DokumentStand | None = None
    #: Querschnitts-Review: der Auszug für Ebene 2 geht erst nach der Moderation hin.
    moderieren: Moderieren | None = None
    auszuege: Auszuege | None = None
    sperre: asyncio.Semaphore = field(default_factory=lambda: asyncio.Semaphore(parallel()))

    def rest(self) -> float:
        return self.frist_ende - _jetzt()

    async def rufe(self, nachrichten: list[dict[str, Any]], tokens: int) -> Any:
        """Ein Aufruf, der spätestens am Fristende endet — samt Warten auf den Platz: die Frist
        des Transports beginnt erst danach (Gegenreview U2, Befund 1)."""
        rest = max(self.rest() - 1.0, 0.0)
        async with asyncio.timeout_at(self.frist_ende):
            return await self.llm(nachrichten, tokens, min(rest, AUFRUF_FRIST_S), rest)

    async def auszug(self, knoten: dict[str, Any]) -> str:
        """Der geprüfte Text des Dokuments zu ``knoten`` (``strukturentwurf_auszug``)."""
        if self.auszuege is None:
            self.auszuege = Auszuege(self.dokument, DOKUMENT_AUSZUG, self.moderieren)
        return await self.auszuege.fuer(knoten)

    async def kinder(self, knoten: dict[str, Any], anzahl: int, pfad: list[str],
                     geschwister: list[str], *, letzte: bool) -> None:
        """Unterpunkte EINES Punkts erzeugen und an seine vorhandenen anhängen (Review U2,
        Befund 2: beim Vertiefen bleiben Bearbeitungen) — sonst ``ausstehend``."""
        vorhanden = list(knoten.get("kinder") or [])
        # Mit Vorlage nur, was in der Kompaktfassung stand (Gegenreview U2, Befund 3).
        vorhanden_titel = [k["titel"] for k in vorhanden
                           if self.sichtbar is None or k.get("id") in self.sichtbar]
        async with self.sperre:
            platz = min(se.HOECHSTENS_KNOTEN - self.zahl, se.HOECHSTENS_KINDER - len(vorhanden))
            # Review TW-1, Befund 2: ohne vorhandene Unterpunkte nie genau einen anfordern
            if (self.rest() < MINDEST_REST_S or platz <= 0
                    or (not vorhanden and min(anzahl, platz) < 2)):
                knoten["ausstehend"] = True
                return
            try:
                # Nachprüfung Q4, Befund 1: das Warten auf die Moderation (ein Platz je Entwurf,
                # dahinter die geteilten Plätze) endet vor der Frist — sonst überzöge der Entwurf
                # sie und der Lauf bräche ihn samt Ebene 1 ab. ``TimeoutError`` → ``ausstehend``.
                async with asyncio.timeout_at(self.frist_ende - MINDEST_REST_S):
                    auszug = await self.auszug(knoten)
                if self.rest() < MINDEST_REST_S:
                    # Review Q4, Befund 1: die Zeit der Moderation zählt vor dem Modellaufruf.
                    knoten["ausstehend"] = True
                    return
                antwort = await self.rufe(prompt.unterthemen(
                    entwurf=self.daten["titel"], thema=self.auftrag.thema,
                    fach=self.daten.get("fach"), bildungsstufe=self.daten.get("bildungsstufe"),
                    hinweise=self.auftrag.hinweise, pfad=pfad,
                    knoten=knoten if self.sichtbar is None else {"titel": knoten["titel"]},
                    geschwister=geschwister, anzahl=min(anzahl, platz), letzte_ebene=letzte,
                    vorhanden=vorhanden_titel, auszug=auszug, vorgaben=self.auftrag.vorgaben),
                    _TOKENS_KINDER)
            except Exception as e:  # noqa: BLE001 — ein Zweig fehlt, der Entwurf bleibt
                logger.info("Strukturentwurf: Unterpunkte nicht erzeugt (%s)", type(e).__name__)
                knoten["ausstehend"] = True
                return
        neu = []
        for p in prompt.punkte(antwort)[:min(anzahl, platz)]:
            if self.zahl >= se.HOECHSTENS_KNOTEN:
                break
            if kind := se.knoten_aus(p, se.neue_kennung(knoten["id"], self.vergeben),
                                     wurzel=self.daten):
                neu.append(kind)
                self.zahl += 1
                self.plaene[kind["id"]] = 0 if letzte else prompt.zahl_unterthemen(
                    p, prompt.UNTERTHEMEN_TIEF)
        if neu:
            knoten["kinder"] = vorhanden + neu
            knoten.pop("ausstehend", None)
        else:
            knoten["ausstehend"] = True


def _mit_pfad(knoten: list[dict[str, Any]], ebene: int = 1, pfad: tuple[str, ...] = ()
              ) -> Iterator[tuple[dict[str, Any], int, list[str], list[str]]]:
    """Jeder Punkt mit Ebene, Titeln der Vorfahren und Titeln der Geschwister."""
    for k in knoten:
        geschwister = [g["titel"] for g in knoten if g is not k]
        yield k, ebene, list(pfad), geschwister
        yield from _mit_pfad(k.get("kinder") or [], ebene + 1, (*pfad, k["titel"]))


async def _ebene(lauf: _Lauf, ziele: list[tuple[dict[str, Any], int, list[str], list[str]]],
                 *, letzte: bool) -> None:
    await asyncio.gather(*(lauf.kinder(k, n, pfad, g, letzte=letzte) for k, n, pfad, g in ziele))


async def _obere_ebene(lauf: _Lauf) -> str | None:
    """Ebene 1 in die Daten; ``None`` oder der Grund, warum es keinen Entwurf gibt."""
    a = lauf.auftrag
    if lauf.rest() < MINDEST_REST_S:
        return "frist"
    try:
        antwort = await lauf.rufe(
            dokument_teil.aufforderung_oben(lauf.auftrag, lauf.daten, lauf.dokument),
            _TOKENS_OBEN)
    except LlmAusgelastet:
        return "ausgelastet"
    except TimeoutError:
        return "frist"
    except Exception as e:  # noqa: BLE001 — Grund ins Log, an die KI nur „ließ sich nicht erzeugen“
        logger.info("Strukturentwurf: obere Ebene nicht erzeugt (%s)", type(e).__name__)
        return "fehler"
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
    for p in prompt.punkte(antwort)[:oben]:
        if k := se.knoten_aus(p, se.neue_kennung(None, lauf.vergeben), wurzel=d):
            if lauf.dokument is not None:
                dokument_teil.fundstelle(k, p, lauf.dokument)
            d["knoten"].append(k)
            lauf.plaene[k["id"]] = prompt.zahl_unterthemen(p, prompt.UNTERTHEMEN_OBEN)
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
        ziele = [(k, lauf.plaene[k["id"]], p, g)
                 for k, ebene, p, g in _mit_pfad(lauf.daten["knoten"])
                 if ebene == 2 and lauf.plaene.get(k["id"])]
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
                   moderieren: Moderieren | None = None) -> Erzeugt:
    """Einen Entwurf erzeugen — aus dem ``dokument`` der Person oder frei — oder eine ``vorlage``
    vertiefen. Block-Daten nach ``ui-strukturentwurf/manifest.json`` (``eingabe``); geprüft wird
    beim Aufrufer. Mit ``dokument`` gehört ``moderieren`` dazu (``ui_module/dienst._moderation``):
    ohne gehen die Auszüge für Ebene 2 ungeprüft ans Modell."""
    if vorlage is not None:
        daten = {f: copy.deepcopy(vorlage[f]) for f in _WURZEL_FELDER if f in vorlage}
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
    return await _neu(_Lauf(auftrag, llm, frist_ende, daten, dokument=dokument,
                            moderieren=moderieren))
