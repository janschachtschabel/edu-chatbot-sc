"""Die Strukturdokumente für einen Zug (Paket U3-2b, Plan 2026-11-04 §16.6; TG-3d/TG-3e).

Der Strukturentwurf liest sie serverseitig — ihr Text läuft nie durch die KI-Antwort des Zugs,
nur gedeckelte Auszüge gerahmt in die eigenen Aufrufe des Dienstes. :func:`lader` gibt eine
Funktion, die beim ersten Bedarf lädt (und sich das Ergebnis merkt): ein Zug ohne
``aus_dokument`` zahlt keine Abfrage, und die zwei Millionen Zeichen liegen nicht in jedem Zug.

Plan 2026-11-16, TG-3d/TG-3e: Welche Dokumente gelten, sagt der Teil ``strukturdokument`` des
Vorgangs (Quelle ``chatbot`` oder ``wlo``, gelesen über ``dokumente/strukturdokument``); ohne ihn
alle lesbaren Dokumente der Sitzung. Mehrere werden zu einem :class:`DokumentStand`
zusammengeführt (``dokument_gliederung.zusammenfuehren``: je Dokument ein Abschnitt oberster
Ebene, Kennungen ``d1-a3``) — Gliederung, Anfang und Auszüge haben so insgesamt dieselben Deckel
wie ein Dokument. Mit einem Dokument bleibt alles wie vorher.

Beim Laden beginnt die Frist eines Sitzungsdokuments neu (``beruehren``, „24 h nach letzter
Nutzung“). Danach geht die Verbindung in den Pool zurück — es folgen LLM-Aufrufe
(``db/verbindung``).
"""

from __future__ import annotations

import dataclasses
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Final

from sqlalchemy.exc import SQLAlchemyError

from boerdi.db.verbindung import verbindung_freigeben
from boerdi.domain.dokument_gliederung import Abschnitt, zusammenfuehren
from boerdi.services.config_loader.upload import load_upload_config
from boerdi.services.dokumente import ablage
from boerdi.services.mcp.auth import aufrufer_kennung, has_personal_auth

logger = logging.getLogger(__name__)

#: TG-3e: der Anfang für Ebene 1 — insgesamt so lang wie bei einem Dokument
#: (``strukturentwurf_dokument.DOKUMENT_ANFANG``), bei mehreren gleich verteilt.
ANFANG_ZEICHEN: Final = 1500


@dataclass(frozen=True)
class DokumentStand:
    upload_id: str
    name: str
    format: str
    befund: dict[str, Any]
    abschnitte: list[Abschnitt]
    markdown: str
    #: TG-3e: der Anfang für Ebene 1, wenn er nicht der Anfang von ``markdown`` ist (mehrere
    #: Dokumente: je Dokument ein Stück).
    anfang: str | None = None
    #: TG-3e: so viele Dokumente stecken darin (``> 1``: Kennungen mit Präfix ``d1-``).
    dokumente: int = 1
    #: TG-3d: ein Text, den beim Lesen keine Moderation sah (Volltext aus WLO) — der Dienst prüft
    #: Übersicht und Anfang vor Ebene 1 (``ui_module/dienst._ebene_eins_pruefen``).
    ungeprueft: bool = False
    #: Review TG-3d–f, MINOR 3: Strukturdokumente aus WLO, die (noch) keinen Volltext haben — je
    #: ``(Name, Grund)``. Die KI bekommt dazu eine Zeile, statt dass sie still fehlen.
    fehlend: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class OhneVolltext:
    """MINOR 3: Es gibt nur Strukturdokumente aus WLO, und keins hat (schon) einen Volltext — der
    Dienst sagt das mit eigenem Code statt „kein Dokument“: ``volltext_endgueltig`` (WLO gewann
    keinen Text, Plan 2026-11-20 §8, E1), sonst ``volltext_fehlt``."""

    fehlend: tuple[tuple[str, str], ...]


DokumentLader = Callable[[], Awaitable[DokumentStand | OhneVolltext | None]]
TeilLader = Callable[[str], Awaitable[Any]]


def _abschnitte(roh: Any) -> list[Abschnitt] | None:
    if not isinstance(roh, list):
        return None
    try:
        return [Abschnitt(**a) for a in roh]
    except TypeError:
        return None


def aus_zeile(zeile: Any) -> DokumentStand | None:
    """Ein gespeichertes Sitzungsdokument als Stand — ``None`` mit unlesbarer Gliederung."""
    abschnitte = _abschnitte(zeile.gliederung)
    if abschnitte is None:
        logger.warning("Dokument der Sitzung: Gliederung unlesbar, wird nicht genutzt")
        return None
    return DokumentStand(upload_id=zeile.id, name=zeile.name, format=zeile.format,
                         befund=dict(zeile.befund or {}), abschnitte=abschnitte,
                         markdown=zeile.markdown)


def vereint(staende: list[DokumentStand],
            fehlend: list[tuple[str, str]] | None = None) -> DokumentStand | None:
    """TG-3e: mehrere Stände als einer (je Dokument ein Abschnitt oberster Ebene); einer bleibt,
    wie er ist; keiner → ``None``. MINOR 3: ``fehlend`` reist mit."""
    if len(staende) <= 1:
        if staende and fehlend:
            return dataclasses.replace(staende[0], fehlend=tuple(fehlend))
        return staende[0] if staende else None
    abschnitte, markdown = zusammenfuehren([(d.name, d.abschnitte, d.markdown) for d in staende])
    je = ANFANG_ZEICHEN // len(staende)
    anfang = "\n\n".join(f"# {d.name}\n{d.markdown[:je]}" for d in staende)[:ANFANG_ZEICHEN]
    namen = ", ".join(d.name for d in staende)
    return DokumentStand(
        upload_id=staende[0].upload_id, name=namen[:200], format=staende[0].format,
        befund={"abschnitte": len(abschnitte), "dokumente": len(staende)},
        abschnitte=abschnitte, markdown=markdown, anfang=anfang, dokumente=len(staende),
        ungeprueft=any(d.ungeprueft for d in staende), fehlend=tuple(fehlend or ()))


async def _sitzungsdokumente(session: Any, session_id: str, rolle: str | None = "struktur"
                             ) -> list[DokumentStand]:
    """Paket U: ``rolle`` wie ``ablage.alle_lesbaren`` (Vorgabe Strukturdokumente; ``None`` = auch
    die hier gelesenen Inhalte, für ``dokument_lesen``)."""
    aufrufer = aufrufer_kennung() if has_personal_auth() else None
    # TB-E1 (N2): anonym gelesen, dann angemeldet — die Dokumente gehen an diese Person
    zeilen = await ablage.alle_fuer_aufrufer(session, session_id, aufrufer, rolle)
    ttl_h = load_upload_config().aufbewahrung_h
    staende = []
    for zeile in zeilen:
        if (stand := aus_zeile(zeile)) is not None:
            await ablage.beruehren(session, zeile.id, ttl_h=ttl_h)
            staende.append(stand)
    await session.commit()
    return staende


#: Plan 2026-11-16, Durchtest TG-7 (M2): ``dokument_lesen`` liest die Sitzungsdokumente einzeln
#: (je Dokument ein Stand, nicht vereint) — derselbe Leseweg samt Frist.
sitzungsdokumente = _sitzungsdokumente


async def laden(session: Any, session_id: str, teile: TeilLader | None = None
                ) -> DokumentStand | OhneVolltext | None:
    """Die Strukturdokumente als ein Stand — oder ``None``: keins da, abgelaufen, unlesbar, gerade
    nicht erlaubt (das Studio hat abgeschaltet, die Anmeldung fehlt; Review U3-2 Befund 7) oder die
    Datenbank streikt (dann sagt der Dienst ``kein_dokument`` statt den Werkzeugaufruf zu
    beenden). TG-3d: mit ``teile`` zuerst die Einträge des Teils ``strukturdokument``."""
    from boerdi.services.dokumente import strukturdokument
    from boerdi.ui_module.dienst_upload import dokument_erlaubt

    try:
        if teile is not None and (eintraege := await strukturdokument.im_vorgang(teile)):
            # Ein Dokument aus WLO braucht den Schalter des Chat-Lesens nicht (das Repositorium
            # wandelt um); ein Sitzungsdokument schon
            lesung = await strukturdokument.staende(
                [e for e in eintraege if e["quelle"] != "chatbot" or dokument_erlaubt()],
                session=session, session_id=session_id)
            if not lesung.staende:
                # Nachprüfung, NIT 6: nur abgelaufene Sitzungsdokumente sind „kein Dokument“;
                # fehlt einem aus WLO der Volltext, sagt das der eigene Fall
                wlo = tuple(f for f in lesung.fehlend if f[1] != strukturdokument.ABGELAUFEN)
                return OhneVolltext(wlo) if wlo else None
            return vereint(lesung.staende, lesung.fehlend)
        if not dokument_erlaubt():
            return None
        return vereint(await _sitzungsdokumente(session, session_id))
    except SQLAlchemyError as fehler:
        logger.warning("Dokument der Sitzung nicht lesbar (%s)", type(fehler).__name__)
        try:
            await session.rollback()
        except SQLAlchemyError:
            logger.debug("Rollback nach Lesefehler gescheitert", exc_info=True)
        return None
    finally:
        await verbindung_freigeben(session)


def lader(session: Any, session_id: str, teile: TeilLader | None = None) -> DokumentLader:
    """Lädt beim ersten Aufruf, danach dasselbe Ergebnis (auch ``None``)."""
    gemerkt: list[DokumentStand | OhneVolltext | None] = []

    async def holen() -> DokumentStand | OhneVolltext | None:
        if not gemerkt:
            gemerkt.append(await laden(session, session_id, teile))
        return gemerkt[0]

    return holen
