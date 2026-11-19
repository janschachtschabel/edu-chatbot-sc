"""Vorgänge: Teile aufräumen, wenn ein Sitzungsdokument geht (aus ``vorgaenge`` gelöst, zweites
Review Paket U, MINOR 6 — verhaltensgleich verschoben).

Geht ein hier gelesenes Dokument (Löschen, Ersetzen, Ablauf der Frist, „Arbeitsstand löschen“,
Kaskade der Sitzung), gehen seine Spuren in jedem Vorgang mit: der Teil ``document``, der Eintrag im
Teil ``strukturdokument`` (TG-3d) und die Kurzangaben im Teil ``metadaten`` (Review U, MAJOR 2).
Gesperrt gelesen und unter der Sperre noch einmal geprüft (Review Q3); der Aufrufer schreibt fest.
"""

from __future__ import annotations

import copy
from typing import Any, Final

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from boerdi.db.models import DokumentUpload, Vorgang, VorgangAblage
from boerdi.services.vorgaenge import INLINE_BYTES, _ablegen, _aus_ablage, _groesse, _jetzt, _weg


async def dokument_teile_entfernen(s: AsyncSession, upload_ids: list[str]) -> int:
    """Den Teil ``document`` aus jedem Vorgang, der auf eines dieser Dokumente zeigt (Querschnitts-
    Review 2026-11-06, Datenschutz): Name und Befund überdauerten sonst die 24 h des Dokuments und
    dessen Löschen. Auch eine große Fassung in der Ablage geht mit. Der Aufrufer schreibt fest.
    Gibt die Zahl der betroffenen Vorgänge zurück."""
    refs = [f"dokument:{i}" for i in upload_ids if isinstance(i, str) and i]
    if not refs:
        return 0
    inline = select(Vorgang.id).where(
        Vorgang.akte[("teile", "document", "wert", "ref")].astext.in_(refs))
    abgelegt = select(VorgangAblage.vorgang_id).where(
        VorgangAblage.schluessel.like("document@%"), VorgangAblage.inhalt["ref"].astext.in_(refs))
    ids = set((await s.execute(inline)).scalars()) | set((await s.execute(abgelegt)).scalars())
    # Plan 2026-11-16, TG-3d: auch der Eintrag im Teil ``strukturdokument`` geht mit — sein Name
    # überdauerte sonst das Dokument wie früher der Teil ``document``.
    ids |= await _mit_strukturdokument(s, refs)
    # Review Paket U (19.11.), MAJOR 2: und die Kurzangaben eines hier im Chat gelesenen Inhalts
    # im Teil ``metadaten`` (``_metadaten_bereinigen``)
    ids |= await _mit_metadaten(s, [r.removeprefix("dokument:") for r in refs])
    return sum([await _entfernen_unter_sperre(s, vid, set(refs)) for vid in sorted(ids)])


#: So viele Verweise prüft eine Abfrage auf ``strukturdokument`` höchstens (der Aufbewahrungslauf
#: kann viele Dokumente auf einmal löschen).
_REFS_JE_ABFRAGE: Final = 100


async def _mit_strukturdokument(s: AsyncSession, refs: list[str]) -> set[str]:
    """TG-3d: Vorgänge, deren Teil ``strukturdokument`` auf eines dieser Dokumente verweist."""
    from sqlalchemy import or_

    from boerdi.services.dokumente.strukturdokument_teil import FELD, TEIL

    ids: set[str] = set()
    for i in range(0, len(refs), _REFS_JE_ABFRAGE):
        bedingungen = [Vorgang.akte.contains({"teile": {TEIL: {"wert": {FELD: [{"ref": r}]}}}})
                       for r in refs[i:i + _REFS_JE_ABFRAGE]]
        ids |= set((await s.execute(select(Vorgang.id).where(or_(*bedingungen)))).scalars())
    return ids


async def _strukturdokument_bereinigen(s: AsyncSession, v: Vorgang, refs: set[str]
                                       ) -> dict[str, Any] | None:
    """TG-3d: die Akte ohne die Einträge dieser Dokumente im Teil ``strukturdokument`` — ``None``,
    wenn keiner darauf zeigt. Bleibt keiner, geht der ganze Teil."""
    from boerdi.services.dokumente import strukturdokument_teil as sd

    alt = ((v.akte or {}).get("teile") or {}).get(sd.TEIL)
    if not isinstance(alt, dict):
        return None
    wert = await _aus_ablage(s, v.id, alt["ref"]) if alt.get("ref") else alt.get("wert")
    vorher = sd.eintraege(wert)
    if not any(e["ref"] in refs for e in vorher):
        return None
    akte = copy.deepcopy(v.akte)
    for weg in [*([alt["ref"]] if alt.get("ref") else []),
                *(akte.get("historie") or {}).pop(sd.TEIL, [])]:
        await _weg(s, v.id, weg)
    neu = sd.ohne(wert, refs)
    if not neu[sd.FELD]:
        akte["teile"].pop(sd.TEIL, None)
        return akte
    # Klein (höchstens zehn Verweise) — der Teil steht danach in der Akte selbst.
    akte["teile"][sd.TEIL] = {
        **{k: w for k, w in alt.items() if k != "ref"}, "wert": neu,
        "version": int(alt.get("version") or 0) + 1,
        "zusammenfassung": sd.zusammenfassung(neu[sd.FELD]), "geaendert": _jetzt().isoformat()}
    return akte


async def _mit_metadaten(s: AsyncSession, kennungen: list[str]) -> set[str]:
    """Review U, MAJOR 2: Vorgänge, deren Teil ``metadaten`` auf einen dieser Inhalte verweist
    (``upload_id``) — in der Akte oder, groß, in der Ablage."""
    from sqlalchemy import or_

    ids: set[str] = set()
    for i in range(0, len(kennungen), _REFS_JE_ABFRAGE):
        stueck = kennungen[i:i + _REFS_JE_ABFRAGE]
        inline = [Vorgang.akte.contains(
            {"teile": {"metadaten": {"wert": {"inhalte": [{"upload_id": k}]}}}}) for k in stueck]
        ids |= set((await s.execute(select(Vorgang.id).where(or_(*inline)))).scalars())
        abgelegt = [VorgangAblage.inhalt.contains({"inhalte": [{"upload_id": k}]}) for k in stueck]
        ids |= set((await s.execute(select(VorgangAblage.vorgang_id).where(
            VorgangAblage.schluessel.like("metadaten@%"), or_(*abgelegt)))).scalars())
    return ids


async def _wert_aus(s: AsyncSession, vid: str, eintrag: Any) -> Any:
    if not isinstance(eintrag, dict):
        return None
    return await _aus_ablage(s, vid, eintrag["ref"]) if eintrag.get("ref") else eintrag.get("wert")


async def _metadaten_bereinigen(s: AsyncSession, vid: str, akte: dict[str, Any],
                                kennungen: set[str]) -> bool:
    """Review Paket U (19.11.), MAJOR 2 (Datenschutz): im Teil ``metadaten`` fallen die Einträge
    dieser Inhalte auf „nur Name“ zurück (``metadaten_lokal.ohne_uploads``) — Titel, Beschreibung
    und Schlagworte des LLM überdauerten sonst das Dokument. Ändert ``akte``; ``True``, wenn ein
    Eintrag betroffen war. ``metadaten`` führt keine Historie (:data:`MIT_HISTORIE`); eine
    dennoch vorhandene geht mit, wie beim Teil ``strukturdokument``."""
    from boerdi.services.dokumente import metadaten_lokal as ml

    teile = akte.get("teile") or {}
    alt = teile.get("metadaten")
    neu = ml.ohne_uploads(await _wert_aus(s, vid, alt), kennungen,
                          await _wert_aus(s, vid, teile.get("struktur")))
    if neu is None:
        return False
    for weg in [*([alt["ref"]] if alt.get("ref") else []),
                *(akte.get("historie") or {}).pop("metadaten", [])]:
        await _weg(s, vid, weg)
    version = int(alt.get("version") or 0) + 1
    eintrag = {**{k: w for k, w in alt.items() if k not in ("ref", "wert")},
               "version": version, "zusammenfassung": ml.zusammenfassung(neu)[:200],
               "geaendert": _jetzt().isoformat()}
    if (groesse := _groesse(neu)) > INLINE_BYTES:
        eintrag["ref"] = f"metadaten@{version}"
        await _ablegen(s, vid, eintrag["ref"], str(alt.get("typ") or ""), neu, groesse)
    else:
        eintrag["wert"] = neu
    teile["metadaten"] = eintrag
    return True


async def _entfernen_unter_sperre(s: AsyncSession, vid: str, refs: set[str]) -> bool:
    """Review Q3, Befund 6: gesperrt gelesen — sonst überschriebe das Zurückschreiben ein
    gleichzeitiges ``teil_setzen`` zwischen Lesen und Schreiben (aufsteigend: keine Verklemmung).
    Unter der Sperre noch einmal geprüft (Nachprüfung, Befund 5): ``document`` geht nur, wenn es
    noch auf eines der Dokumente zeigt — ein inzwischen neues bleibt. TG-3d: ebenso die Einträge
    im Teil ``strukturdokument``; Review U, MAJOR 2: die des Teils ``metadaten``."""
    v = await s.get(Vorgang, vid, populate_existing=True, with_for_update=True)
    if v is None:
        return False
    geaendert = await _strukturdokument_bereinigen(s, v, refs)
    akte = geaendert if geaendert is not None else copy.deepcopy(v.akte)
    angaben_weg = await _metadaten_bereinigen(
        s, vid, akte, {r.removeprefix("dokument:") for r in refs})
    alt = ((v.akte or {}).get("teile") or {}).get("document")
    wert = None
    if isinstance(alt, dict):
        wert = await _aus_ablage(s, vid, alt["ref"]) if alt.get("ref") else alt.get("wert")
    if isinstance(wert, dict) and wert.get("ref") in refs:
        akte["teile"].pop("document", None)
        for weg in [*([alt["ref"]] if alt.get("ref") else []),
                    *(akte.get("historie") or {}).pop("document", [])]:
            await _weg(s, vid, weg)
    elif geaendert is None and not angaben_weg:
        return False
    await s.execute(update(Vorgang).where(Vorgang.id == vid)
                    .values(akte=akte, akte_version=Vorgang.akte_version + 1)
                    .execution_options(synchronize_session=False))
    return True


async def verwaiste_dokument_teile_entfernen(s: AsyncSession) -> int:
    """Den Teil ``document`` aus jedem Vorgang, dessen Dokument nicht mehr da ist — gelöscht auf
    einem Weg ohne :func:`dokument_teile_entfernen` (die Sitzung ging, Kaskade; Review Q3,
    Befund 7). Für den Aufbewahrungslauf; der Aufrufer schreibt fest."""
    ref = Vorgang.akte[("teile", "document", "wert", "ref")].astext
    inline = select(ref).where(ref.like("dokument:%"))
    abgelegt = select(VorgangAblage.inhalt["ref"].astext).where(
        VorgangAblage.schluessel.like("document@%"))
    refs = set((await s.execute(inline)).scalars()) | set((await s.execute(abgelegt)).scalars())
    refs |= await _strukturdokument_refs(s)
    ids = {r.removeprefix("dokument:") for r in refs if isinstance(r, str)}
    ids |= await _metadaten_kennungen(s)
    if not ids:
        return 0
    da = set((await s.execute(select(DokumentUpload.id).where(DokumentUpload.id.in_(ids))))
             .scalars())
    return await dokument_teile_entfernen(s, sorted(ids - da))


async def _strukturdokument_refs(s: AsyncSession) -> set[str]:
    """TG-3d: die Verweise auf Sitzungsdokumente in allen Teilen ``strukturdokument`` (in der Akte
    — der Teil ist klein und liegt nie in der Ablage, ``_strukturdokument_bereinigen``)."""
    from boerdi.services.dokumente import strukturdokument_teil as sd

    werte = (await s.execute(select(Vorgang.akte[("teile", sd.TEIL, "wert")]).where(
        Vorgang.akte["teile"].has_key(sd.TEIL)))).scalars()
    return {e["ref"] for w in werte for e in sd.eintraege(w) if sd.upload_id(e)}


async def _metadaten_kennungen(s: AsyncSession) -> set[str]:
    """Review U, MAJOR 2: die Kennungen hier im Chat gelesener Inhalte in allen Teilen
    ``metadaten`` (``quelle: chatbot``) — in der Akte und, groß, in der Ablage."""
    from boerdi.services.dokumente import metadaten_lokal as ml

    inline = (await s.execute(select(Vorgang.akte[("teile", "metadaten", "wert")]).where(
        Vorgang.akte[("teile", "metadaten", "wert", "quelle")].astext == ml.QUELLE))).scalars()
    abgelegt = (await s.execute(select(VorgangAblage.inhalt).where(
        VorgangAblage.schluessel.like("metadaten@%"),
        VorgangAblage.inhalt["quelle"].astext == ml.QUELLE))).scalars()
    return {k for wert in [*inline, *abgelegt] for k in ml.upload_ids(wert)}
