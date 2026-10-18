"""Werk und eigene Fassung je Konfigurationsbereich (Paket 12) — die Studio-Endpunkte.

Die Werksfassung ist der Seed im Image (``CONFIG_SEED_DIR``), die gelebte steht in
``config_areas``. Status und Regeln: ``services/werkfassung``. Hier:

* ``GET  /api/config/fassungen`` — alle Bereiche (Seed ∪ Datenbank) mit Status.
* ``POST /api/config/fassungen/werksabgleich`` — Fehlendes anlegen, Unberührtes anheben,
  Angepasstes lassen (derselbe Ablauf wie ``boerdi import-config --werksabgleich``).
* ``POST /api/config/fassungen/umschalten`` — ``werk``: die gelebte Fassung stilllegen und die
  Werksfassung schreiben (ein gelöschter Werksbereich kommt so zurück); ``eigen``: die
  stillgelegte Fassung zurückholen. Bedingt auf ``expected_version`` wie jedes Speichern (409).
* ``GET  /api/config/fassungen/vergleich?area=…`` — Werk gegen gelebt als Zeilen (``difflib``)
  und je Feld (``felder``, Paket 16).

Der Bereich steht im Body bzw. in der Abfrage, nicht im Pfad: Bereichsnamen enthalten ``/``.
Kein Lesepfad im Chat ändert sich — die Endpunkte lesen den Seed bei Bedarf (wenige ms).
"""

from __future__ import annotations

import difflib
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Security
from pydantic import BaseModel

from boerdi.api.config_antworten import konflikt_antwort
from boerdi.api.config_guards import pruefe_bereiche
from boerdi.api.config_kennungen import (
    kennungs_einwand,
    kennungs_kollisionen,
    sicherheits_kennungen,
)
from boerdi.api.deps import Lang, require_studio_key
from boerdi.i18n import Locale, msg
from boerdi.services import config_loader as cl
from boerdi.services import seed_sync, werkfassung
from boerdi.services.config_conflict import ConfigConflict
from boerdi.services.feld_unterschiede import feld_unterschiede
from boerdi.settings import get_settings

router = APIRouter(
    prefix="/api/config/fassungen", tags=["config-fassungen"],
    dependencies=[Security(require_studio_key)],
)


class Umschalten(BaseModel):
    area: str
    ziel: Literal["werk", "eigen", "geprueft"]
    #: Die Version, die das Studio zeigt — fehlt nur, wenn es den Bereich nicht gibt.
    expected_version: int | None = None


async def _seed(lang: Locale | None = None) -> dict[str, dict[str, Any]] | None:
    """Die Werksfassung — ``None`` ohne Seed-Baum, mit ``lang`` dann 404."""
    pfad = seed_sync.seed_pfad(get_settings().config_seed_dir)
    if pfad is None:
        if lang is not None:
            raise HTTPException(404, msg(lang, "seed.missing"))
        return None
    return await seed_sync.seed_lesen(pfad)


@router.get("")
async def liste() -> dict:
    seed = await _seed()
    if seed is None:
        return {"available": False, "bereiche": []}
    store = cl.bound_store()
    zeilen = {z["area"]: z for z in await store.fassungen()}
    entfernt = await store.entfernte()
    bereiche = []
    for area in sorted(seed.keys() | zeilen.keys()):
        zeile = zeilen.get(area) or {}
        bereiche.append({
            "area": area,
            "status": werkfassung.status(
                data=zeile.get("data"), werk_hash=zeile.get("werk_hash"), werk=seed.get(area),
                entfernt=area in entfernt, updated_by=zeile.get("updated_by") or ""),
            "version": zeile.get("version"),
            "hat_eigene_fassung": bool(zeile.get("hat_eigene_fassung")),
        })
    return {"available": True, "bereiche": bereiche}


@router.post("/werksabgleich")
async def werksabgleich(lang: Lang) -> dict:
    pfad = seed_sync.seed_pfad(get_settings().config_seed_dir)
    if pfad is None:
        raise HTTPException(404, msg(lang, "seed.missing"))
    store = cl.bound_store()

    async def schreiben(eintraege: dict) -> dict[str, int]:
        return await store.werk_schreiben(eintraege, updated_by="werksabgleich")

    return await seed_sync.werksabgleich(
        pfad, pruefen=lambda seed: pruefe_bereiche(seed, lang), lesen=store.fassungen,
        entfernte=store.entfernte, schreiben=schreiben, zuordnen=store.werk_hashes_setzen,
        kollisionen=kennungs_kollisionen)


@router.post("/umschalten")
async def umschalten(payload: Umschalten, lang: Lang) -> dict:
    seed = await _seed(lang)
    store = cl.bound_store()
    area = payload.area
    zeile = await store.fassung(area) or {}
    vorher = werkfassung.Fassung(zeile.get("data"), zeile.get("werk_hash"),
                                 zeile.get("eigene_fassung"), zeile.get("eigene_basis"))
    try:
        neu = werkfassung.umschalten(payload.ziel, vorher, werk=seed.get(area))
    except werkfassung.UmschaltEinwand as e:
        status = 404 if e.meldung == "fassung.keinWerk" else 400
        raise HTTPException(status, msg(lang, e.meldung, area=area)) from None
    pruefe_bereiche({area: neu.data}, lang)
    einwand = kennungs_einwand({area: neu.data}, await cl.current_config(),
                               await sicherheits_kennungen())
    if einwand:
        raise HTTPException(400, msg(lang, einwand.meldung, **einwand.werte))
    wer = {"werk": "werkfassung", "eigen": "eigene-fassung", "geprueft": "werk-geprueft"}[
        payload.ziel]
    if vorher.data is None:
        # Gelöscht oder nie angelegt: anlegen — nur, wenn ihn nicht inzwischen jemand anlegte
        # (Review #5; dann 409 wie jedes bedingte Schreiben).
        geschrieben = await store.werk_schreiben(
            {area: (neu.data, neu.werk_hash, None, None)}, updated_by=wer, trotz_entfernt=True)
        if area not in geschrieben:
            raise HTTPException(409, msg(lang, "fassung.inzwischenDa", area=area))
        return {"status": "ok", "area": area, "version": geschrieben[area]}
    if payload.expected_version is None:
        raise HTTPException(400, msg(lang, "fassung.versionFehlt"))
    try:
        version = await store.umschalten(
            area, neu, expected_version=payload.expected_version, updated_by=wer)
    except ConfigConflict as e:
        raise konflikt_antwort(e, lang) from e
    return {"status": "ok", "area": area, "version": version}


@router.get("/vergleich")
async def vergleich(area: str, lang: Lang) -> dict:
    seed = await _seed(lang)
    fassung = await cl.bound_store().fassung(area)
    werk = seed.get(area)
    if werk is None and fassung is None:
        raise HTTPException(404, msg(lang, "fassung.unbekannt", area=area))
    werk_text = cl.serialize_area(werk) if werk else ""
    gelebt_text = cl.serialize_area(_nach_vorbild(fassung["data"], werk)) if fassung else ""
    eigene = (fassung or {}).get("eigene_fassung")
    zeilen = list(difflib.unified_diff(
        werk_text.splitlines(), gelebt_text.splitlines(), "werk", "gelebt", lineterm="", n=3))
    eigene_text = None if eigene is None else cl.serialize_area(_nach_vorbild(eigene, werk))
    # Review 2 #10: die stillgelegte Fassung gegen das Werk — vor „Eigene Fassung verwenden“.
    zeilen_eigene = [] if eigene_text is None else list(difflib.unified_diff(
        werk_text.splitlines(), eigene_text.splitlines(), "werk", "eigene", lineterm="", n=3))
    # Paket 16, C6: dieselben Unterschiede je Feld — die Tabelle in der Sicherung.
    felder, felder_gesamt = feld_unterschiede(werk or {}, (fassung or {}).get("data") or {})
    felder_eigene, felder_eigene_gesamt = ([], 0) if eigene is None else feld_unterschiede(
        werk or {}, eigene)
    return {"area": area, "werk": werk_text, "gelebt": gelebt_text, "eigene": eigene_text,
            "zeilen": zeilen, "zeilen_eigene": zeilen_eigene,
            "felder": felder, "felder_gesamt": felder_gesamt,
            "felder_eigene": felder_eigene, "felder_eigene_gesamt": felder_eigene_gesamt}


def _nach_vorbild(data: Any, vorbild: Any) -> Any:
    """``data`` mit der Schlüsselfolge von ``vorbild`` (der Werksfassung), rekursiv.

    ``jsonb`` ordnet Schlüssel selbst (Länge, dann Bytes); die Werksfassung behält die Folge der
    Datei. Ohne Angleichen zeigte der Vergleich eines unveränderten Bereichs ganze Blöcke als
    verschoben (Browser-Abnahme 2026-10-16). Schlüssel, die das Vorbild nicht kennt, folgen am
    Ende in ihrer eigenen Folge; Listen behalten ihre Reihenfolge.
    """
    if isinstance(data, dict) and isinstance(vorbild, dict):
        folge = [k for k in vorbild if k in data] + [k for k in data if k not in vorbild]
        return {k: _nach_vorbild(data[k], vorbild.get(k)) for k in folge}
    if isinstance(data, list) and isinstance(vorbild, list):
        return [_nach_vorbild(d, vorbild[i] if i < len(vorbild) else None)
                for i, d in enumerate(data)]
    return data
