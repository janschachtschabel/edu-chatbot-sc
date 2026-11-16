"""Arbeitsstand im Gespräch (Paket V1, Plan 2026-11-05 §3): Modul-Antworten → Teile des Vorgangs.

Ohne Ablauf: Liefert ein Modul etwas Bleibendes — erfasste Ordner (``ui_upload``), ein gelesenes
Dokument, einen übernommenen Entwurf (``ui_strukturentwurf``) —, wird es nach der Prüfung
des Zugs als **Teil** des aktiven Vorgangs gespeichert (:func:`uebernehmen`). Die Sitzung hält nur
einen **Verweis** (:data:`VERWEIS`: Kennung, Titel, je Teil Version und Kurztext, Frist); die
KI sieht davon je Zug die :func:`kennzeile`, nie die Daten. Dienste lesen den Vorgang über
:func:`lader` (einmal je Zug, erst bei Bedarf).

Besitzerin ist die bestätigte Person, sonst die Sitzung (``sitzung:<id>``). Meldet sich die Person
später an, geht der offene Vorgang des Verweises dieser Sitzung auf sie über (Paket R2-d,
:func:`anonymen_uebernehmen`); andere anonyme Vorgänge bleiben der Sitzung.
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
from boerdi.services.dokumente import strukturdokument_teil as sd
from boerdi.services.mcp.auth import aufrufer_kennung, has_personal_auth
from boerdi.services.vorgaenge import VorgangKonflikt
from boerdi.ui_module.namen import ZWECK_BEREITSTELLEN
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


async def anonymen_uebernehmen(s: Any, session_id: str, entities: dict[str, Any],
                               aufrufer: str) -> bool:
    """Paket R2-d: zeigt der Verweis auf den Vorgang der anonymen Sitzung und ist die Person jetzt
    angemeldet, gehört er ab hier ihr (nur derselben Sitzung, nur ein offener). ``True``: übernommen
    (der Verweis in ``entities`` ist neu — der Aufrufer speichert die Sitzung, wenn nötig)."""
    anonym = f"sitzung:{session_id}"
    roh = entities.get(VERWEIS)
    if (aufrufer == anonym or not ist_persoenlich(aufrufer) or not isinstance(roh, dict)
            or roh.get("b") != _besitz(anonym) or not isinstance(roh.get("id"), str)):
        return False
    if (v := await vorgaenge.uebernehmen(s, roh["id"], von=anonym, an=aufrufer)) is None:
        return False
    await s.commit()
    entities[VERWEIS] = _verweis_aus(v, aufrufer)
    logger.info("Arbeitsstand: anonymer Vorgang nach der Anmeldung übernommen")
    return True


async def auffrischen(s: Any, session_id: str, entities: dict[str, Any]) -> None:
    """Der Verweis folgt einmal je Zug dem Vorgang — im Preflight, vor den Prüfungen, die nur ihn
    lesen (wartet ein Lauf? Auslöser?; Querschnitts-Review 2026-11-06, Review Q3, Befund 10): Frist,
    Teile und Lauf aus der Datenbank, denn eine zweite Sitzung derselben Person kann ihn bewegt
    haben; ein abgelaufener oder abgeschlossener eigener Vorgang fällt weg. Ohne Verweis findet eine
    angemeldete Person ihren jüngsten offenen Vorgang wieder — auch aus einer neuen Sitzung (Review
    V1, Befund 1). Wirft nie; die Verbindung geht danach frei."""
    aufrufer = aufrufer_fuer(session_id)
    try:
        await anonymen_uebernehmen(s, session_id, entities, aufrufer)
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


async def lesbares_dokument(s: Any, session_id: str) -> str | None:
    """Zweites Review TG-2 (MINOR 5): die Kennung des Dokuments, das diese Sitzung gerade lesen
    kann (derselbe Leseweg wie der Lader) — ``None`` ohne eins. Ein Lesefehler gilt als keins."""
    from boerdi.services.dokumente import ablage as dokumente

    try:
        zeile_db = await dokumente.fuer_aufrufer(
            s, session_id, aufrufer_kennung() if has_personal_auth() else None)
    except SQLAlchemyError as fehler:
        logger.warning("Lesbares Dokument nicht feststellbar (%s)", type(fehler).__name__)
        return None
    finally:
        await verbindung_freigeben(s)
    return None if zeile_db is None else str(zeile_db.id)


async def _lesbare_zeilen(s: Any, session_id: str, merk: dict[str, Any] | None) -> list[Any]:
    """Review TG-3d–f, NIT: die lesbaren Dokumente der Sitzung — mit ``merk`` einmal je Speichern
    gelesen, nicht je Teil bzw. Eintrag."""
    from boerdi.services.dokumente import ablage as dokumente

    if merk is not None and "zeilen" in merk:
        return merk["zeilen"]
    zeilen = list(await dokumente.alle_fuer_aufrufer(
        s, session_id, aufrufer_kennung() if has_personal_auth() else None))
    if merk is not None:
        merk["zeilen"] = zeilen
    return zeilen


async def _dokument_bestaetigt(s: Any, session_id: str, wert: dict[str, Any],
                               merk: dict[str, Any] | None = None
                               ) -> tuple[dict[str, Any], str] | None:
    """Das Dokument der Sitzung statt der Angaben des Widgets (Review V1, Befund 9): nur wenn die
    Kennung zum gespeicherten Dokument passt, als ``dokument:<id>`` mit Befund des Servers."""
    # Review TB-E1, Befund 1: derselbe Leseweg wie der Lader — mit Übernahme nach der Anmeldung.
    # TG-3e: eines der lesbaren Dokumente (das erste gelesene ist nicht immer das jüngste)
    zeile_db = next((z for z in await _lesbare_zeilen(s, session_id, merk)
                     if z.id == wert.get("upload_id")), None)
    if zeile_db is None:
        return None
    befund = dict(zeile_db.befund or {})
    return ({"ref": f"dokument:{zeile_db.id}", "name": zeile_db.name, "format": zeile_db.format,
             "befund": befund},
            f"{zeile(zeile_db.name, 80)}, {int(befund.get('abschnitte') or 0)} Abschnitte")


async def lesbare_dokumente(s: Any, session_id: str) -> list[tuple[str, str]]:
    """Plan 2026-11-16, TG-3e: ``(Kennung, Name)`` aller Dokumente, die diese Sitzung gerade lesen
    kann (derselbe Leseweg wie der Lader), in Lesereihenfolge; leer ohne. Ein Lesefehler gilt als
    keins."""
    from boerdi.services.dokumente import ablage as dokumente

    try:
        zeilen = await dokumente.alle_fuer_aufrufer(
            s, session_id, aufrufer_kennung() if has_personal_auth() else None)
    except Exception as fehler:  # noqa: BLE001 — ein Lesefehler heißt „keins“, nie Abbruch
        logger.warning("Lesbare Dokumente nicht feststellbar (%s)", type(fehler).__name__)
        return []
    finally:
        await verbindung_freigeben(s)
    return [(str(z.id), str(z.name)) for z in zeilen]


async def lesbare_dokument_ids(s: Any, session_id: str) -> list[str]:
    """TG-3e: nur die Kennungen von :func:`lesbare_dokumente`."""
    return [kennung for kennung, _ in await lesbare_dokumente(s, session_id)]


async def _strukturdokumente_bestaetigt(s: Any, session_id: str, wert: Any, alt: Any,
                                        merk: dict[str, Any] | None = None
                                        ) -> tuple[dict[str, Any], str] | None:
    """TG-3d: je Eintrag dieselbe Prüfung wie :func:`_dokument_bestaetigt` — nur Einträge, deren
    Dokument diese Sitzung lesen kann, mit dem Namen des Servers; die ``wlo``-Einträge des Vorgangs
    (nach der Ablage) bleiben. ``None``, wenn keiner der gelesenen passt."""
    gelesen = []
    for e in sd.eintraege(wert):
        if (kennung := sd.upload_id(e)) is None:
            continue
        bestaetigt = await _dokument_bestaetigt(s, session_id,
                                                {"upload_id": kennung, "name": e["name"]}, merk)
        if bestaetigt is not None:
            gelesen.append(sd.chatbot(kennung, bestaetigt[0]["name"]))
    if not gelesen:
        return None
    neu = sd.mit_chatbot(alt, gelesen)
    return neu, sd.zusammenfassung(neu[sd.FELD])


async def _entwurf_mit_knoten(s: Any, v: Vorgang, wert: dict[str, Any]) -> dict[str, Any]:
    """MINOR 8: der Entwurf mit den node_ids seiner Inhalte — nie die, die der Client mitschickte.

    Nachprüfung TG-3d–f, MINOR 2: Der Entwurf nennt seine Auswahl (``quelle_block``). Aus
    ``ablage`` kommen node_ids nur, wenn ``struktur`` und ``ablage`` gebunden sind UND zu dieser
    Auswahl gehören — eine neue Auswahl im selben Vorgang vergibt die Nummern ``i`` anders. Sonst
    bleiben die node_ids des zuletzt gespeicherten Entwurfs derselben Auswahl (sie stammen vom
    Server)."""
    from boerdi.services.arbeitsstand_teile import gebunden
    from boerdi.ui_module.strukturentwurf import knoten_ids_im_entwurf, mit_knoten_ids
    from boerdi.ui_module.strukturentwurf_ordner import knoten_ids

    if not _hat_inhalte(wert):
        return wert
    quelle = wert.get("quelle_block")
    struktur = await vorgaenge.teil_wert(s, v, "struktur")
    ablage = await vorgaenge.teil_wert(s, v, "ablage")
    if (isinstance(quelle, str) and quelle and gebunden(struktur, ablage)
            and struktur.get("block_id") == quelle):
        return mit_knoten_ids(wert, knoten_ids(ablage))
    alt = await vorgaenge.teil_wert(s, v, "draft")
    gleiche_quelle = isinstance(alt, dict) and quelle and alt.get("quelle_block") == quelle
    return mit_knoten_ids(wert, knoten_ids_im_entwurf(alt) if gleiche_quelle else {})


def _hat_inhalte(wert: dict[str, Any]) -> bool:
    from boerdi.ui_module.strukturentwurf import alle

    return any(k.get("inhalte") for k, _ in alle(wert.get("knoten") or []))


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
        # Plan 2026-11-16, TG-2: ohne Ablauf ist der Zweck neutral — das Upload-Feld stellt nur
        # bereit (gelesen wird ``zweck`` nur als Kennung eines Ablaufs, ``api/ui_vorgaenge``)
        v = await vorgaenge.anlegen(s, aufrufer=aufrufer, session_id=session_id,
                                    titel=_titel(teile), zweck=ZWECK_BEREITSTELLEN, tage=tage())
    merk: dict[str, Any] = {}
    for name, typ, wert, zusammenfassung in teile:
        if name == "document":
            if (bestaetigt := await _dokument_bestaetigt(s, session_id, wert, merk)) is None:
                logger.info("Arbeitsstand: Dokument der Antwort passt nicht zur Sitzung")
                continue
            wert, zusammenfassung = bestaetigt
        elif name == sd.TEIL and typ == sd.TYP and not sd.hat_wlo(wert):
            # TG-3d: Einträge aus einer Antwort (nur gelesene Dokumente) prüft der Server; was die
            # Ablage schreibt (mit ``wlo``-Einträgen, ``vorgang_teil``), stammt aus dem Vorgang
            alt = await vorgaenge.teil_wert(s, v, name)
            bestaetigt = await _strukturdokumente_bestaetigt(s, session_id, wert, alt, merk)
            if bestaetigt is None:
                logger.info("Arbeitsstand: kein Strukturdokument der Antwort passt zur Sitzung")
                continue
            wert, zusammenfassung = bestaetigt
        elif name == "draft" and isinstance(wert, dict):
            # Review TG-3d–f, MINOR 8: node_ids eines Entwurfs nie vom Client — neu aus der Ablage
            # über ``i``, nur wenn Auswahl und Ablage zum selben Upload-Feld gehören
            wert = await _entwurf_mit_knoten(s, v, wert)
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
