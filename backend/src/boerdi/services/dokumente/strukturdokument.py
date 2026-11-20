"""Der Leser der Strukturdokumente (Plan 2026-11-16, TG-3d): Verweis → Markdown-Text, je Quelle.

Datenmodell des Nutzers (16.11., Optimierungen 2 und 3): Der Teil ``strukturdokument`` trägt nur
Verweise (``strukturdokument_teil``); den Text holt dieser Leser bei Bedarf — der Lader des
Generators ruft :func:`staende` und muss die Quelle nicht kennen (die Einzel-Funktion ``text`` ist
seit der Nachprüfung TG-3d–f, NIT 5, gestrichen: unbenutzt, und sie hielt das Festschreiben vor dem
MCP nicht ein). Je Quelle gibt es genau eine
Stelle der Umwandlung:

- ``chatbot`` (anonym): die Umwandlung beim Hochladen (``dokumente/aufnahme``); der Text liegt an
  der Sitzung (``dokument_uploads``, 24 h). Gelesen über denselben Weg wie der Lader des Zugs
  (``ablage.alle_fuer_aufrufer``): eine Person, die sich nach dem Lesen anmeldet, übernimmt die
  anonym gelesenen Dokumente (TB-E1; Review TG-3d–f, M1).
- ``wlo``: der Volltext, den das Repositorium aus der abgelegten Datei erzeugt hat — gelesen über
  das MCP-Werkzeug ``get_wlo_content_text``, nur lesend und nur mit persönlicher Anmeldung (die
  Knoten liegen im persönlichen Bereich). Den Werkzeug-Cache liest der Leser nicht
  (``use_cache=False``: ein eben erzeugter Volltext soll gelten); das frische Ergebnis legt der
  Client wie sonst ab. **Nie selbst schreiben**: ein Volltext an einem Datensatz ersetzte die Datei.

Review TG-3d–f, MINOR 2: Die Sitzungsdokumente werden zuerst gelesen und berührt und
festgeschrieben, dann geht die Verbindung frei; erst danach laufen die WLO-Lesungen — parallel
(höchstens :data:`PARALLEL`) und mit einer Gesamtfrist. MINOR 3: Was ohne Text bleibt, fällt nicht
still weg — :class:`Lesung` nennt es mit Grund (ein fester Code des Servers, nie Text).

Ein Volltext aus WLO sah beim Lesen keine Moderation; sein Stand trägt ``ungeprueft`` — der Dienst
prüft Übersicht und Anfang vor dem ersten Modellaufruf, die Auszüge prüft er ohnehin.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Final

from boerdi.db.verbindung import verbindung_freigeben
from boerdi.domain.dokument_gliederung import bereinigen, gliederung
from boerdi.services.config_loader.upload import load_upload_config
from boerdi.services.dokumente import ablage
from boerdi.services.dokumente import strukturdokument_teil as sd
from boerdi.services.dokumente.stand import DokumentStand, TeilLader, aus_zeile
from boerdi.services.mcp.auth import aufrufer_kennung, has_personal_auth

logger = logging.getLogger(__name__)

#: So viel Volltext liest der Leser je Knoten höchstens (die Obergrenze des MCP-Werkzeugs).
VOLLTEXT_ZEICHEN: Final = 200_000
VOLLTEXT_WERKZEUG: Final = "get_wlo_content_text"
#: MINOR 2: so viele Volltexte gleichzeitig (Last am MCP) und so lange insgesamt ohne Frist des
#: Entwurfs. Review Paket E, MINOR 6: 50 statt 30 s — der MCP wartet beim ersten Lesen bis
#: ``WLO_TEXT_TIMEOUT_MS`` (25 s) auf das Repositorium; danach muss eine Wiederholung (E2) noch
#: passen. Der Dienst rechnet seine Frist (90 s) vor dem Lesen: ein langes Lesen kürzt den Entwurf.
PARALLEL: Final = 3
GESAMT_FRIST_S: Final = 50.0
#: MINOR 3: die Gründe ohne Text — die des Servers (``content-text.ts``) und eigene. Andere Werte
#: werden ``ohne_text``; nur diese Codes kommen ins Log.
GRUENDE: Final = frozenset({
    "not_extracted", "no_text_no_url", "extraction_failed", "access_denied", "node_not_found",
    "text_unreadable", "ohne_text", "ohne_anmeldung", "abruf_fehler", "frist",
})
#: Gründe, bei denen ein späterer Versuch helfen kann (Lesefehler, Frist). Plan 2026-11-20 §8, E1:
#: ``not_extracted`` gehört nicht dazu — gemessen (§7) erzeugt das Repositorium den Text synchron
#: beim ersten Lesen und wiederholt eine gescheiterte Extraktion nie.
SPAETER: Final = frozenset({"text_unreadable", "abruf_fehler", "frist"})
#: Aus der Datei kam kein Text, endgültig (Scan, Bild, Markdown, gescheiterte Extraktion im
#: Repositorium; das MCP liest ``ccm:fulltext_status`` noch nicht und unterscheidet das nicht).
NICHT_EXTRAHIERT: Final = "not_extracted"
#: Plan 2026-11-20 §8, E2: bei einem Grund aus :data:`SPAETER` liest der Leser im selben Zug noch
#: einmal — nach diesen Pausen, solange die Frist reicht (gemessen: erstes Lesen ≤ 10,5 s bei 8 MB).
WIEDERHOLEN_S: Final = (5.0, 10.0)
#: Nachprüfung, NIT 6: ein Sitzungsdokument, das nicht mehr lesbar ist (24 h vorbei, verdrängt).
ABGELAUFEN: Final = "abgelaufen"
#: Plan 2026-11-19, A3 (E5, Befund S2c): unter so vielen Wörtern ist ein Volltext aus WLO „kein
#: lesbarer Text“ (Seitenzahlen, OCR-Reste eines Scans) — Seitenzahlen kennt der WLO-Weg nicht.
#: Review A, MINOR 7: 30 statt 100 (echte kurze Systematiken), dazu der Anteil der Buchstaben.
KAUM_TEXT_WOERTER: Final = 30
#: Unter diesem Anteil an Buchstaben (ohne Leerraum) sind es Zahlen- und Zeichenreste.
KAUM_BUCHSTABEN: Final = 0.3
#: Ein Wort: mindestens zwei Buchstaben am Stück (Zahlen, Zeichen und einzelne Buchstaben nicht).
_WORT: Final = re.compile(r"[^\W\d_]{2,}")


def woerter(text: str) -> int:
    """Die Wörter eines Texts nach :data:`_WORT`."""
    return len(_WORT.findall(text))


def lesbar(text: str) -> bool:
    """Ist ``text`` lesbarer Text — mindestens :data:`KAUM_TEXT_WOERTER` Wörter und mindestens
    :data:`KAUM_BUCHSTABEN` Buchstaben unter den Zeichen ohne Leerraum?"""
    zeichen = "".join(text.split())
    buchstaben = sum(z.isalpha() for z in zeichen)
    return woerter(text) >= KAUM_TEXT_WOERTER and buchstaben >= KAUM_BUCHSTABEN * len(zeichen)


@dataclass
class Lesung:
    """Was der Leser fand: die lesbaren Stände (in der Reihenfolge des Teils) und die Dokumente
    ohne Text — je ``(Name, Grund)`` (MINOR 3; Sitzungsdokumente mit :data:`ABGELAUFEN`)."""

    staende: list[DokumentStand] = field(default_factory=list)
    fehlend: list[tuple[str, str]] = field(default_factory=list)


async def im_vorgang(teile: TeilLader) -> list[dict[str, str]]:
    """Die Einträge des Teils ``strukturdokument`` — fehlt der Teil (ein Vorgang, abgelegt vor
    TG-3d), die Strukturdokumente aus ``ablage``. Review Paket E, MINOR 2: nur dann; sonst kehrte
    ein Knoten zurück, den ein Ablauf verworfen hat (etwa nach „hier im Chat lesen lassen“), und
    jeder Entwurf fragte das MCP nach seinem Text. Neue Ablagen trägt ``mit_ablage`` in den Teil
    ein."""
    if (teil := await teile(sd.TEIL)) is not None:
        return sd.eintraege(teil)
    return sd.aus_ablage(await teile("ablage"))


def _aufrufer() -> str | None:
    return aufrufer_kennung() if has_personal_auth() else None


#: Review Paket E, MINOR 5: die Art eines gescheiterten MCP-Aufrufs → Grund. Keine Antwort
#: (Frist, Transport, ausgelastet) ist vorübergehend; eine abgewiesene Anmeldung nicht.
_ART_GRUND: Final = {"timeout": "abruf_fehler", "transport": "abruf_fehler",
                     "busy": "abruf_fehler", "auth": "ohne_anmeldung"}


async def volltext(node_id: str) -> tuple[str | None, str]:
    """Der Volltext eines Knotens als Markdown und ein Grund (``""`` mit Text). Ohne persönliche
    Anmeldung wird nicht gelesen (die Knoten liegen im persönlichen Bereich)."""
    from boerdi.services.mcp import client
    from boerdi.services.mcp.parsers import parse_content_text

    if not has_personal_auth():
        return None, "ohne_anmeldung"
    try:
        antwort = await client.call_mcp_tool_antwort(
            VOLLTEXT_WERKZEUG, {"nodeId": node_id, "maxChars": VOLLTEXT_ZEICHEN}, use_cache=False)
    except Exception as fehler:  # noqa: BLE001 — ein fehlender Text beendet den Zug nie
        logger.warning("Strukturdokument aus WLO: Volltext nicht lesbar (%s)",
                       type(fehler).__name__)
        return None, "abruf_fehler"
    if art := antwort.art:
        # MINOR 5: der Fehlertext des Clients ist keine Antwort des Werkzeugs (sonst ``ohne_text``
        # und der Satz „kein Zugriff“); abgelehnt (``tool``) nennt der Server einen Code
        grund = _ART_GRUND.get(art) or (antwort.code if antwort.code in GRUENDE else "ohne_text")
        logger.info("Strukturdokument aus WLO: Abruf gescheitert (%s, %s)", art, grund)
        return None, grund
    gelesen = parse_content_text(antwort.text)
    if inhalt := str(gelesen.get("text") or "").strip():
        if lesbar(bereinigen(inhalt)[0]):
            return inhalt, ""
        # A3 (E5): ein Scan mit Seitenzahlen ist kein Dokument — dieselben Texte wie ohne Text
        logger.info("Strukturdokument aus WLO: kaum Text (%s)", NICHT_EXTRAHIERT)
        return None, NICHT_EXTRAHIERT
    grund = str(gelesen.get("reason") or "")
    grund = grund if grund in GRUENDE else "ohne_text"
    logger.info("Strukturdokument aus WLO: kein Volltext (%s)", grund)
    return None, grund


async def _sitzungsdokumente(session: Any, session_id: str) -> dict[str, Any]:
    """M1: die lesbaren Dokumente der Sitzung je Kennung — über ``alle_fuer_aufrufer`` (mit
    Übernahme nach der Anmeldung), einmal je Lesung statt einer Abfrage je Eintrag."""
    return {z.id: z for z in await ablage.alle_fuer_aufrufer(session, session_id, _aufrufer())}


def _aus_volltext(e: dict[str, str], inhalt: str) -> DokumentStand:
    markdown, _ = bereinigen(inhalt)
    abschnitte, art = gliederung(markdown)
    return DokumentStand(upload_id=e["ref"], name=e["name"], format="md",
                         befund={"abschnitte": len(abschnitte), "gliederung_art": art},
                         abschnitte=abschnitte, markdown=markdown, ungeprueft=True)


#: Die Pause vor einer Wiederholung (Tests setzen eine Attrappe).
_schlafen = asyncio.sleep


async def _wlo_lesen(eintraege: list[dict[str, str]], frist_ende: float | None
                     ) -> dict[str, tuple[str | None, str]]:
    """MINOR 2: die Volltexte parallel (höchstens :data:`PARALLEL`), alle bis zur Frist. E2: ein
    vorübergehender Grund (:data:`SPAETER`) wird nach :data:`WIEDERHOLEN_S` wiederholt, solange die
    Pause vor der Frist endet; in der Pause hält der Knoten keinen Platz. Der letzte Grund bleibt
    stehen, falls die Frist den Versuch danach abbricht."""
    platz = asyncio.Semaphore(PARALLEL)
    ergebnis: dict[str, tuple[str | None, str]] = {}
    loop = asyncio.get_running_loop()
    ende = frist_ende if frist_ende is not None else loop.time() + GESAMT_FRIST_S

    async def eins(e: dict[str, str]) -> None:
        for pause in (0.0, *WIEDERHOLEN_S):
            if pause:
                if ergebnis[e["ref"]][1] not in SPAETER or loop.time() + pause >= ende:
                    return
                logger.info("Strukturdokument aus WLO: neuer Versuch in %.0f s (%s)", pause,
                            ergebnis[e["ref"]][1])
                await _schlafen(pause)
            async with platz:
                ergebnis[e["ref"]] = await volltext(e["ref"])

    aufgaben = [asyncio.ensure_future(eins(e)) for e in eintraege]
    try:
        async with asyncio.timeout_at(ende):
            await asyncio.gather(*aufgaben)
    except TimeoutError:
        logger.info("Strukturdokument aus WLO: Frist erreicht, %d ohne Volltext",
                    sum(1 for a in aufgaben if not a.done()))
    finally:
        for a in aufgaben:
            if not a.done():
                a.cancel()
    return {e["ref"]: ergebnis.get(e["ref"], (None, "frist")) for e in eintraege}


async def staende(eintraege: list[dict[str, str]], *, session: Any, session_id: str,
                  frist_ende: float | None = None) -> Lesung:
    """Die lesbaren Strukturdokumente als Stände (mit Gliederung), in der Reihenfolge des Teils,
    und was ohne Text blieb. Ein Sitzungsdokument nimmt seine gespeicherte Gliederung, und seine
    Frist beginnt neu; ein Volltext aus WLO wird hier gegliedert (``dokument_gliederung``)."""
    lesung = Lesung()
    wlo = [e for e in eintraege if e["quelle"] == sd.WLO]
    chatbot: dict[str, DokumentStand] = {}
    if any(sd.upload_id(e) for e in eintraege):
        zeilen = await _sitzungsdokumente(session, session_id)
        ttl_h = load_upload_config().aufbewahrung_h
        for e in eintraege:
            kennung = sd.upload_id(e)
            if kennung and (zeile := zeilen.get(kennung)) is not None and (
                    stand := aus_zeile(zeile)) is not None:
                await ablage.beruehren(session, zeile.id, ttl_h=ttl_h)
                chatbot[e["ref"]] = stand
        # MINOR 2: festschreiben, bevor das MCP gefragt wird — keine offene Transaktion darüber
        await session.commit()
    await verbindung_freigeben(session)
    gelesen = await _wlo_lesen(wlo, frist_ende) if wlo else {}
    for e in eintraege:
        if e["ref"] in chatbot:
            lesung.staende.append(chatbot[e["ref"]])
        elif sd.upload_id(e):
            # Nachprüfung, NIT 6: ein abgelaufenes oder verdrängtes Sitzungsdokument fehlt nicht
            # still — die KI kann um erneutes Lesen bitten
            lesung.fehlend.append((e["name"], ABGELAUFEN))
        elif e["ref"] in gelesen:
            inhalt, grund = gelesen[e["ref"]]
            if inhalt is not None:
                lesung.staende.append(_aus_volltext(e, inhalt))
            else:
                lesung.fehlend.append((e["name"], grund))
    return lesung
