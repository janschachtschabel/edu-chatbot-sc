"""Ein Lauf des Strukturentwurfs: Frist, Plätze, Aufrufe und die Unterpunkte EINES Punkts —
aus ``strukturentwurf_dienst`` verschoben (Review Paket A, fünftes Review, MINOR 6; reine
Verschiebung). Der Dienst (``strukturentwurf_dienst``) ordnet die Ebenen, hier läuft je Punkt ein
Aufruf: auf dem Weg „gliederung“ mit moderiertem Auszug, auf dem Weg „ganz“ (Plan E1c) mit dem
ganzen Dokument (``strukturentwurf_ganz``, gleicher Anfang für das Prompt-Caching).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final

from boerdi.services import llm_parallel
from boerdi.services import strukturentwurf_ganz as ganz_teil
from boerdi.services import strukturentwurf_prompt as prompt
from boerdi.services import strukturentwurf_wiederholen as wiederholen
from boerdi.services.strukturentwurf_auszug import Auszuege, Moderieren
from boerdi.ui_module import strukturentwurf as se

if TYPE_CHECKING:
    from boerdi.services.dokumente.stand import DokumentStand

logger = logging.getLogger(__name__)

#: Höchstens so viele Aufrufe je Entwurf zugleich — bei einem kleinen Anbieter-Deckel weniger
#: (:func:`parallel`, Review U2, Befund 3).
PARALLEL: Final = 5
MINDEST_REST_S: Final = 8.0
AUFRUF_FRIST_S: Final = 40.0
#: Deckel der Dokument-Auszüge (U3-2b): Gliederung und Anfang für Ebene 1, Text je Punkt.
DOKUMENT_AUSZUG: Final = 6000
_TOKENS_KINDER: Final = 1600
#: Plan E1c: der Vorwärm-Aufruf braucht keine Antwort — nur den Cache des Anbieters.
_TOKENS_VORWAERMEN: Final = 32
#: Fünftes Review A, MINOR 2: eigene kurze Frist (und Platz-Geduld) des Vorwärmens — ein Hängen
#: kostet höchstens so viel, nie Ebene 2.
VORWAERMEN_FRIST_S: Final = 10.0
#: Kontroll-Durchgang, MINOR 1: so viel Zeit bleibt Ebene 2 nach dem Vorwärmen mindestens; bleibt
#: dem Vorwärmen danach weniger als :data:`VORWAERMEN_MIN_S`, entfällt es.
EBENE2_BUDGET_S: Final = 20.0
VORWAERMEN_MIN_S: Final = 2.0

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
    #: Plan E1c: auf dem Weg „ganz“ (der Aufrufer hat den ganzen Text moderiert, zweites Review A,
    #: MINOR 5) der ganze Text für Ebene 1 und Ebene 2, sonst ``None`` — die eine Quelle (NIT 7).
    text: str | None = None
    vorgewaermt: bool = False
    #: Fünftes Review A, NIT 9: das Vorwärmen unter eigener Phase (``None``: über ``llm``).
    llm_vorwaermen: LlmJson | None = None
    sperre: asyncio.Semaphore = field(default_factory=lambda: asyncio.Semaphore(parallel()))

    def rest(self) -> float:
        return self.frist_ende - _jetzt()

    async def rufe(self, nachrichten: list[dict[str, Any]], tokens: int) -> Any:
        """Ein Aufruf, der spätestens am Fristende endet — samt Warten auf den Platz: die Frist
        des Transports beginnt erst danach (Gegenreview U2, Befund 1)."""
        rest = max(self.rest() - 1.0, 0.0)
        async with asyncio.timeout_at(self.frist_ende):
            return await self.llm(nachrichten, tokens, min(rest, AUFRUF_FRIST_S), rest)

    async def _gesperrt(self, nachrichten: list[dict[str, Any]]) -> Any:
        """Ein Aufruf für Unterpunkte auf einem der :func:`parallel` Plätze des Entwurfs — nach dem
        Warten auf den Platz zählt die Restzeit (sonst ``TimeoutError`` → ``ausstehend``)."""
        async with self.sperre:
            if self.rest() < MINDEST_REST_S:
                raise TimeoutError
            return await self.rufe(nachrichten, _TOKENS_KINDER)

    async def vorwaermen(self) -> None:
        """Plan E1c: einmal je Lauf den gemeinsamen Anfang (Systemteil, Dokument) allein schicken —
        der Cache des Anbieters trifft danach bei allen Punkten (``strukturentwurf_ganz``). Ein
        Fehler oder eine abgeschnittene Antwort schadet nicht: es kostet dann nur den Cache."""
        # Kontroll-Durchgang, MINOR 1: die Frist hängt am Rest — Ebene 2 behält ihr Budget
        frist = min(VORWAERMEN_FRIST_S, self.rest() - EBENE2_BUDGET_S)
        if self.vorgewaermt or self.text is None or frist < VORWAERMEN_MIN_S:
            return
        self.vorgewaermt = True
        llm = self.llm_vorwaermen or self.llm
        try:
            # MINOR 2: eigene kurze Frist samt Platz-Geduld — hängt es, gehen die Punkte weiter
            async with asyncio.timeout(frist):
                await llm(ganz_teil.anfang(self.text, self.auftrag.vorgaben), _TOKENS_VORWAERMEN,
                          frist, frist)
        except Exception as e:  # noqa: BLE001 — nur der Cache fehlt, der Entwurf geht weiter
            logger.info("Strukturentwurf: Vorwärmen ohne Antwort (%s)", type(e).__name__)

    async def auszug(self, knoten: dict[str, Any]) -> str:
        """Der geprüfte Text des Dokuments zu ``knoten`` (``strukturentwurf_auszug``) — nur auf dem
        Weg „gliederung“ (auf dem Weg „ganz“ bekommt Ebene 2 den ganzen Text, Plan E1c)."""
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
        platz = min(se.HOECHSTENS_KNOTEN - self.zahl, se.HOECHSTENS_KINDER - len(vorhanden))
        # Review TW-1, Befund 2: ohne vorhandene Unterpunkte nie genau einen anfordern
        if (self.rest() < MINDEST_REST_S or platz <= 0
                or (not vorhanden and min(anzahl, platz) < 2)):
            knoten["ausstehend"] = True
            return
        # Fünftes Review A, MAJOR 1: das ganze Dokument nur für die oberen Punkte (Ebene 2) —
        # Ebene 3 wie bisher (ohne Dokument, höchstens die Planzahl)
        ganz = self.text is not None and not pfad
        try:
            auszug = ""
            if not ganz:
                # Nachprüfung Q4, Befund 1: das Warten auf die Moderation (ein Platz je Entwurf,
                # dahinter die geteilten Plätze) endet vor der Frist — sonst überzöge der Entwurf
                # sie und der Lauf bräche ihn samt Ebene 1 ab. ``TimeoutError`` → ``ausstehend``.
                async with asyncio.timeout_at(self.frist_ende - MINDEST_REST_S):
                    auszug = await self.auszug(knoten)
                if self.rest() < MINDEST_REST_S:
                    # Review Q4, Befund 1: die Zeit der Moderation zählt vor dem Modellaufruf.
                    knoten["ausstehend"] = True
                    return
            # Rückmeldung 16.11.: mit Text (Auszug oder E1c das ganze Dokument) ist die Schätzung
            # der oberen Ebene nur ein Hinweis — der Text bestimmt die Zahl, bis zur Grenze
            if auszug or ganz:
                anzahl = max(anzahl, prompt.UNTERTHEMEN_OBEN)
            gemeinsam = dict(
                entwurf=self.daten["titel"], thema=self.auftrag.thema,
                fach=self.daten.get("fach"), bildungsstufe=self.daten.get("bildungsstufe"),
                hinweise=self.auftrag.hinweise, pfad=pfad,
                knoten=knoten if self.sichtbar is None else {"titel": knoten["titel"]},
                geschwister=geschwister, anzahl=min(anzahl, platz), letzte_ebene=letzte,
                vorhanden=vorhanden_titel, vorgaben=self.auftrag.vorgaben)
            # Plan E1c: auf dem Weg „ganz“ das ganze Dokument (gleicher Anfang je Punkt)
            nachrichten = (ganz_teil.unterthemen(text=self.text, **gemeinsam)
                           if ganz and self.text is not None
                           else prompt.unterthemen(**gemeinsam, auszug=auszug))
            # Plan 2026-11-19, A1: ein 503 des Anbieters einmal wiederholen — die Pause dazwischen
            # hält keinen Platz des Entwurfs (Review A, NIT 13)
            antwort = await wiederholen.einmal_wiederholt(
                lambda: self._gesperrt(nachrichten), self.rest, MINDEST_REST_S)
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
