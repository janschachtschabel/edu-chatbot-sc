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
#: Entwurfs.
PARALLEL: Final = 3
GESAMT_FRIST_S: Final = 30.0
#: MINOR 3: die Gründe ohne Text — die des Servers (``content-text.ts``) und eigene. Andere Werte
#: werden ``ohne_text``; nur diese Codes kommen ins Log.
GRUENDE: Final = frozenset({
    "not_extracted", "no_text_no_url", "extraction_failed", "access_denied", "node_not_found",
    "text_unreadable", "ohne_text", "ohne_anmeldung", "abruf_fehler", "frist",
})
#: Gründe, bei denen ein späterer Versuch helfen kann (der Volltext entsteht noch).
SPAETER: Final = frozenset({"not_extracted", "text_unreadable", "abruf_fehler", "frist"})
#: Plan 2026-11-16, Durchtest TG-7 (m3): aus der Datei kam (noch) kein Text — „noch nicht“ oder
#: „nie“ (Scan, Bild); das MCP unterscheidet beides nicht (``get_wlo_content_text``).
NICHT_EXTRAHIERT: Final = "not_extracted"
#: Nachprüfung, NIT 6: ein Sitzungsdokument, das nicht mehr lesbar ist (24 h vorbei, verdrängt).
ABGELAUFEN: Final = "abgelaufen"

@dataclass
class Lesung:
    """Was der Leser fand: die lesbaren Stände (in der Reihenfolge des Teils) und die Dokumente
    ohne Text — je ``(Name, Grund)`` (MINOR 3; Sitzungsdokumente mit :data:`ABGELAUFEN`)."""

    staende: list[DokumentStand] = field(default_factory=list)
    fehlend: list[tuple[str, str]] = field(default_factory=list)


async def im_vorgang(teile: TeilLader) -> list[dict[str, str]]:
    """Die Einträge des Teils ``strukturdokument`` — dazu Strukturdokumente aus ``ablage``, die
    darin (noch) fehlen (ein Vorgang, abgelegt vor TG-3d)."""
    eintraege = sd.eintraege(await teile(sd.TEIL))
    bekannt = {e["ref"] for e in eintraege}
    knoten = [e for e in sd.aus_ablage(await teile("ablage")) if e["ref"] not in bekannt]
    return sd.eintraege({sd.FELD: [*eintraege, *knoten]})


def _aufrufer() -> str | None:
    return aufrufer_kennung() if has_personal_auth() else None


async def volltext(node_id: str) -> tuple[str | None, str]:
    """Der Volltext eines Knotens als Markdown und ein Grund (``""`` mit Text). Ohne persönliche
    Anmeldung wird nicht gelesen (die Knoten liegen im persönlichen Bereich)."""
    from boerdi.services.mcp.client import call_mcp_tool
    from boerdi.services.mcp.parsers import parse_content_text

    if not has_personal_auth():
        return None, "ohne_anmeldung"
    try:
        roh = await call_mcp_tool(VOLLTEXT_WERKZEUG,
                                  {"nodeId": node_id, "maxChars": VOLLTEXT_ZEICHEN},
                                  use_cache=False)
    except Exception as fehler:  # noqa: BLE001 — ein fehlender Text beendet den Zug nie
        logger.warning("Strukturdokument aus WLO: Volltext nicht lesbar (%s)",
                       type(fehler).__name__)
        return None, "abruf_fehler"
    gelesen = parse_content_text(roh)
    if inhalt := str(gelesen.get("text") or "").strip():
        return inhalt, ""
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


async def _wlo_lesen(eintraege: list[dict[str, str]], frist_ende: float | None
                     ) -> dict[str, tuple[str | None, str]]:
    """MINOR 2: die Volltexte parallel (höchstens :data:`PARALLEL`), alle bis zur Frist."""
    platz = asyncio.Semaphore(PARALLEL)
    ergebnis: dict[str, tuple[str | None, str]] = {}

    async def eins(e: dict[str, str]) -> None:
        async with platz:
            ergebnis[e["ref"]] = await volltext(e["ref"])

    ende = frist_ende if frist_ende is not None else (
        asyncio.get_running_loop().time() + GESAMT_FRIST_S)
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
