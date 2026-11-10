"""Arbeitsstand im Gespräch (Paket V1, Plan 2026-11-05 §3): Modul-Antworten → Teile des Vorgangs.

Ohne Ablauf: Liefert ein Modul etwas Bleibendes — erfasste Ordner (``ui_upload``), ein gelesenes
Dokument, einen übernommenen Entwurf (``ui_strukturentwurf``) —, wird es nach der Prüfung
des Zugs als **Teil** des aktiven Vorgangs gespeichert (:func:`uebernehmen`). Die Sitzung hält nur
einen **Verweis** (:data:`VERWEIS`: Kennung, Titel, je Teil Version und Kurztext, Frist); die
KI sieht davon je Zug die :func:`kennzeile`, nie die Daten. Dienste lesen den Vorgang über
:func:`lader` (einmal je Zug, erst bei Bedarf).

Besitzerin ist die bestätigte Person, sonst die Sitzung (``sitzung:<id>``). Meldet sich die Person
später an, gehört ihr der anonyme Vorgang nicht — sie bekommt beim nächsten Teil einen eigenen.
Fehler beim Speichern beenden nie den Zug: zurückrollen, protokollieren (ohne Inhalte), weiter.

simplify: V1 verdrahtet die drei Module fest (:func:`teile_aus_antwort`); V2 liest dasselbe aus dem
Manifest (``vorgang.schreibt``).
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any, Final

from sqlalchemy.exc import SQLAlchemyError

from boerdi.db.models import Vorgang
from boerdi.db.verbindung import verbindung_freigeben
from boerdi.services import probe, vorgaenge

# Querschnitts-Review 2026-11-06 (Q4): Normalform und Verweis in eigenen Modulen —
# hier weiter erreichbar, wie bisher genutzt.
from boerdi.services.arbeitsstand_teile import (  # noqa: F401
    Teil,
    _titel,
    teile_aus_antwort,
)
from boerdi.services.arbeitsstand_verweis import (  # noqa: F401
    VERWEIS,
    _besitz,
    kennzeile,
    verweis,
    verweis_fuer,
    verweis_weg,
)
from boerdi.services.config_loader._store import area
from boerdi.services.mcp.auth import aufrufer_kennung, has_personal_auth
from boerdi.services.vorgaenge import VorgangKonflikt
from boerdi.ui_module.rahmen import zeile

logger = logging.getLogger(__name__)

#: Die Frist nach letzter Nutzung pflegt das Studio (``logging.vorgang_tage``, Paket A2a).
FRIST_BEREICH: Final = "01-base/privacy-config"


def tage() -> int:
    """Die Frist eines Vorgangs in Tagen — aus dem rohen Bereich, gelesen wie im Studio. Was das
    Modell nicht annimmt (0, über 30, ``true``), gilt als Vorgabe: eine kaputte Frist verlängert
    nichts."""
    from pydantic import ValidationError

    from boerdi.domain.config_models.base_governance import PrivacyLoggingBlock

    logging_ = (area(FRIST_BEREICH) or {}).get("logging") or {}
    if not isinstance(logging_, dict) or "vorgang_tage" not in logging_:
        return PrivacyLoggingBlock().vorgang_tage
    try:
        return PrivacyLoggingBlock.model_validate(
            {"vorgang_tage": logging_["vorgang_tage"]}).vorgang_tage
    except ValidationError:
        logger.warning("Vorgang: vorgang_tage=%r ist keine Frist — Vorgabe gilt",
                       logging_["vorgang_tage"])
        return PrivacyLoggingBlock().vorgang_tage


VorgangLader = Callable[[], Awaitable[Vorgang | None]]


def aufrufer_fuer(session_id: str, entities: dict[str, Any] | None = None) -> str:
    """Wem gehören die Vorgänge dieses Zuges? Der Person, sonst der Sitzung. Eine Probe der
    Studio-Vorschau hat eine eigene Kennung je Sitzung (Review AS-8a, Befund 1): sie findet keinen
    echten Vorgang der Person, und ihre Läufe tauchen in keiner echten Sitzung auf. Endpunkte
    außerhalb des Graphen (ohne Zug-Merker) geben ``entities`` der Sitzung mit."""
    if probe.aktiv() or probe.in_sitzung(entities):
        return f"probe:{session_id}"
    return aufrufer_kennung() if has_personal_auth() else f"sitzung:{session_id}"


def ist_persoenlich(aufrufer: str) -> bool:
    """Gehört der Vorgang einer angemeldeten Person (nicht der Sitzung, nicht einer Probe)? Nur dann
    hängt er an der Anmeldung (Leiste nur mit Zugangsblock, Z-8; zweites Review AS-8a, Befund 2)."""
    return not aufrufer.startswith(("sitzung:", "probe:"))


_verweis_aus = verweis_fuer


async def auffrischen(s: Any, session_id: str, entities: dict[str, Any]) -> None:
    """Der Verweis folgt einmal je Zug dem Vorgang — im Preflight, vor den Prüfungen, die nur ihn
    lesen (wartet ein Lauf? Auslöser?; Querschnitts-Review 2026-11-06, Review Q3, Befund 10): Frist,
    Teile und Lauf aus der Datenbank, denn eine zweite Sitzung derselben Person kann ihn bewegt
    haben; ein abgelaufener oder abgeschlossener eigener Vorgang fällt weg. Ohne Verweis findet eine
    angemeldete Person ihren jüngsten offenen Vorgang wieder — auch aus einer neuen Sitzung (Review
    V1, Befund 1). Wirft nie; die Verbindung geht danach frei."""
    aufrufer = aufrufer_fuer(session_id)
    try:
        roh = entities.get(VERWEIS)
        if isinstance(roh, dict) and roh.get("b") == _besitz(aufrufer) \
                and isinstance(roh.get("id"), str):
            v = await vorgaenge.lesen(s, roh["id"], aufrufer)
            if v is None or v.status in vorgaenge.ABGESCHLOSSEN:
                entities.pop(VERWEIS, None)
            else:
                entities[VERWEIS] = _verweis_aus(v, aufrufer)
        else:
            verweis_weg(entities, aufrufer)
        if verweis(entities, aufrufer) is None and has_personal_auth():
            if (v := await vorgaenge.juengster(s, aufrufer)) is not None:
                entities[VERWEIS] = _verweis_aus(v, aufrufer)
    except Exception as fehler:  # noqa: BLE001 — der Arbeitsstand beendet den Zug nie
        logger.warning("Arbeitsstand nicht lesbar (%s)", type(fehler).__name__)
    finally:
        await verbindung_freigeben(s)


async def _dokument_bestaetigt(s: Any, session_id: str, wert: dict[str, Any]
                               ) -> tuple[dict[str, Any], str] | None:
    """Das Dokument der Sitzung statt der Angaben des Widgets (Review V1, Befund 9): nur wenn die
    Kennung zum gespeicherten Dokument passt, als ``dokument:<id>`` mit Befund des Servers."""
    from boerdi.services.dokumente import ablage as dokumente

    zeile_db = await dokumente.aktuelles(s, session_id,
                                         aufrufer_kennung() if has_personal_auth() else None)
    if zeile_db is None or zeile_db.id != wert.get("upload_id"):
        return None
    befund = dict(zeile_db.befund or {})
    return ({"ref": f"dokument:{zeile_db.id}", "name": zeile_db.name, "format": zeile_db.format,
             "befund": befund},
            f"{zeile(zeile_db.name, 80)}, {int(befund.get('abschnitte') or 0)} Abschnitte")


async def _speichern(s: Any, session_id: str, entities: dict[str, Any], teile: list[Teil],
                     nur_dieser: bool = False) -> Vorgang | None:
    aufrufer = aufrufer_fuer(session_id)
    vw = verweis(entities, aufrufer)
    v = await vorgaenge.lesen(s, vw["id"], aufrufer) if vw else None
    if v is not None and v.status in vorgaenge.ABGESCHLOSSEN:
        v = None          # M6: ein abgeschlossenes Vorhaben nimmt keine neuen Teile
    if v is None and nur_dieser:
        return None
    if v is None and has_personal_auth():
        v = await vorgaenge.juengster(s, aufrufer)
    if v is None:
        v = await vorgaenge.anlegen(s, aufrufer=aufrufer, session_id=session_id,
                                    titel=_titel(teile), zweck="sammlungsstruktur", tage=tage())
    for name, typ, wert, zusammenfassung in teile:
        if name == "document":
            if (bestaetigt := await _dokument_bestaetigt(s, session_id, wert)) is None:
                logger.info("Arbeitsstand: Dokument der Antwort passt nicht zur Sitzung")
                continue
            wert, zusammenfassung = bestaetigt
        v = await vorgaenge.teil_setzen(s, v, name, typ=typ, wert=wert,
                                        zusammenfassung=zusammenfassung, tage=tage())
    return v


async def uebernehmen(s: Any, session_id: str, entities: dict[str, Any],
                      geprueft: dict[str, Any] | None, *, nur_dieser: bool = False) -> bool:
    """Die Teile einer geprüften Antwort speichern und den Verweis setzen (schreibt selbst fest).
    Jeder Versuch läuft in einem Savepoint (Review V1, Befund 4) — ein Fehlschlag verwirft nur ihn.
    Ein Konflikt mit einem gleichzeitigen Zug wird einmal mit frischem Stand wiederholt; jeder
    andere Fehler wird protokolliert und beendet den Zug nicht (Befund 5). ``True``, wenn nichts zu
    speichern war oder es gespeichert ist — ein Ablauf rechnet sonst nicht auf altem Stand weiter
    (Querschnitts-Review 2026-11-06). ``nur_dieser`` wie bei :func:`teile_speichern` — ein Ablauf
    speichert nur in den Vorgang seines Laufs (Review Q3, Nachprüfung, Befund 3)."""
    teile = teile_aus_antwort(geprueft)
    if not teile:
        return True
    return await teile_speichern(s, session_id, entities, teile, nur_dieser=nur_dieser)


async def teile_speichern(s: Any, session_id: str, entities: dict[str, Any],
                          teile: list[Teil], *,
                          neu: Callable[[], Awaitable[list[Teil] | None]] | None = None,
                          nur_dieser: bool = False) -> bool:
    """Teile in den aktiven Vorgang (sonst einen neuen) und den Verweis setzen — wie
    :func:`uebernehmen`, für Teile, die kein Modul geschickt hat (U3-3a: ``ablage``). ``True``, wenn
    gespeichert.

    ``neu`` (Querschnitts-Review 2026-11-06, V-3; Review Q1, Befund 3): wer liest, ändert und
    zurückschreibt, rechnet in **jedem** Versuch unter der Zeilensperre des Vorgangs neu — so liegt
    kein gleichzeitiger Schreiber zwischen Lesen und Schreiben. ``teile`` gilt dann nicht.
    ``None`` aus dem Rückruf = nichts schreiben.

    ``nur_dieser`` (Review Q3, Befund 8): nur in den Vorgang des Verweises — ist er abgeschlossen
    oder weg, wird nichts gespeichert. Der Stand einer Datei nach „neues Vorhaben“ landete sonst in
    einem anderen Vorgang, ohne den Stapel, zu dem er gehört."""
    for versuch in (1, 2):
        try:
            async with s.begin_nested():
                if neu is not None:
                    vw = verweis(entities, aufrufer_fuer(session_id))
                    if vw is not None:
                        await vorgaenge.sperren(s, vw["id"], aufrufer_fuer(session_id))
                    frisch = await neu()
                    if frisch is None:
                        return False
                    teile = frisch
                v = await _speichern(s, session_id, entities, teile, nur_dieser)
                if v is None:
                    return False
            await s.commit()
            entities[VERWEIS] = _verweis_aus(v, aufrufer_fuer(session_id))
            return True
        except VorgangKonflikt:
            if versuch == 2:
                logger.warning("Arbeitsstand: Vorgang gleichzeitig geändert, Teil verworfen")
        except Exception as fehler:  # noqa: BLE001 — ein Hilfsschritt beendet den Zug nicht
            logger.warning("Arbeitsstand nicht gespeichert (%s)", type(fehler).__name__)
            try:
                await s.rollback()
            except SQLAlchemyError:
                logger.debug("Rollback nach Arbeitsstand gescheitert", exc_info=True)
            return False
    return False


async def laden(s: Any, session_id: str, entities: dict[str, Any]) -> Vorgang | None:
    """Der aktive Vorgang; ein Lesen zählt als Nutzung (die Frist beginnt neu, Befund 14)."""
    aufrufer = aufrufer_fuer(session_id)
    vw = verweis(entities, aufrufer)
    if vw is None:
        return None
    try:
        v = await vorgaenge.lesen(s, vw["id"], aufrufer)
        if v is not None:
            await vorgaenge.beruehren(s, v.id, tage=tage())
        return v
    except Exception as fehler:  # noqa: BLE001 — ein Lesefehler beendet den Zug nie
        logger.warning("Arbeitsstand nicht lesbar (%s)", type(fehler).__name__)
        return None
    finally:
        await verbindung_freigeben(s)


def lader(s: Any, session_id: str, entities: dict[str, Any]) -> VorgangLader:
    """Lädt den aktiven Vorgang beim ersten Aufruf, danach dasselbe Ergebnis (auch ``None``)."""
    gemerkt: list[Vorgang | None] = []

    async def holen() -> Vorgang | None:
        if not gemerkt:
            gemerkt.append(await laden(s, session_id, entities))
        return gemerkt[0]

    return holen


TeilLader = Callable[[str], Awaitable[Any]]


def teil_lader(s: Any, session_id: str, entities: dict[str, Any]) -> TeilLader:
    """Liest einen Teil des aktiven Vorgangs per Name (für Dienste, nie aus KI-Argumenten); der
    Vorgang wird einmal je Zug geladen, ``None`` ohne Vorgang oder Teil."""
    vorgang = lader(s, session_id, entities)

    async def teil(name: str) -> Any:
        v = await vorgang()
        if v is None:
            return None
        try:
            return await vorgaenge.teil_wert(s, v, name)
        except Exception as fehler:  # noqa: BLE001 — ein Lesefehler beendet den Zug nie
            logger.warning("Teil des Arbeitsstands nicht lesbar (%s)", type(fehler).__name__)
            return None
        finally:
            await verbindung_freigeben(s)

    return teil
