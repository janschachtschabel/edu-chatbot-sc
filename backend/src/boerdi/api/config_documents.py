"""Ordner-Dokumente — Muster und Personas anlegen, duplizieren, löschen (Paket 6, S1).

``03-patterns`` und ``04-personas`` sind Ordner: ein Dokument je Eintrag
(ST-3d). Drei Regeln stehen hier an einer Stelle:

* **Der Server leitet den Schlüssel ab.** Eine Persona wird zur Laufzeit über
  ``_persona_slug(id)`` gefunden; lag sie unter einem anderen Schlüssel, lief
  ihr Prompt ins Leere (Muster findet der Lader über die Kennung, ihr Schlüssel
  ist nur der Speicherort).
* **Eine Kennung je Gruppe**, ohne Rücksicht auf Groß/Klein, und in der Form,
  die die Laufzeit liest — beim Anlegen und beim Speichern über Formular und
  Rohtext (``pruefe_kennung``). Vorher prüfte das Studio nur den Schlüssel.
* **Löschen lässt die feste Konfiguration stehen.** ``DELETE /api/config/file``
  löschte jeden Bereich, auch ``01-base/policy``; das Studio rief es nie. Jetzt
  nimmt es Muster, Personas und Bereiche ohne Modell (etwa Tippfehler) — nicht
  die Muster, die Krise und Bedrohung erzwingen, und auf Wunsch nur den Stand,
  den das Studio geladen hat (``expected_version``, sonst 409 wie beim Speichern).
"""

import copy

from fastapi import APIRouter, HTTPException, Security
from pydantic import BaseModel

from boerdi.api.config_antworten import konflikt_antwort
from boerdi.api.config_guards import (
    _GROUPED_AREAS,
    _assert_area_document_safe,
    is_restorable_area_key,
    modell_fehler,
)
from boerdi.api.config_kennungen import (
    KENNUNG,
    gruppe_von,
    ist_fest,
    ist_sicherheitsmuster,
    kennung_von,
    kennungs_einwand,
    schluessel_fuer,
    sicherheits_kennungen,
)
from boerdi.api.deps import Lang, require_studio_key
from boerdi.domain.config_models.patterns import ist_reservierte_kennung
from boerdi.i18n import Locale, msg
from boerdi.services import config_loader as cl
from boerdi.services import seed_sync
from boerdi.services.config_conflict import ConfigConflict
from boerdi.services.config_store import EigeneFassungLiegtStill
from boerdi.settings import get_settings

router = APIRouter(
    prefix="/api/config", tags=["config"], dependencies=[Security(require_studio_key)],
)

GRUPPEN = _GROUPED_AREAS
_NAME_MAX = 200


class DocumentCreate(BaseModel):
    """Ein neues Dokument — leer oder als Kopie von ``source`` (demselben Ordner)."""

    group: str
    id: str
    label: str
    source: str | None = None


async def pruefe_kennung(
    key: str, data: object, lang: Locale, *, vergeben_status: int = 400,
) -> None:
    """Die Kennung eines Ordner-Dokuments: in der Form, die die Laufzeit liest
    (400), bei einer Persona passend zum Schlüssel (400) und frei in der Gruppe.
    Die Regel steht in ``config_kennungen`` — dieselbe prüft das Wiederherstellen.

    „Vergeben“ ist auf den Speicher-Routen 400: dort heißt 409 „inzwischen
    gespeichert“, und das Studio zeigte sonst den Konflikt-Kasten ohne Grund
    (Review Paket 6). ``POST /documents`` meldet es als 409. Andere Bereiche
    passieren. Der Bestand kommt aus der Datenbank, nicht aus dem Prozess-Cache,
    der einer anderen Replika hinterherlaufen kann (Paket 4, D2).
    """
    # Auch ohne Kennung geprüft (Review Paket 9): ein geleertes Sicherheitsmuster.
    if gruppe_von(key) is None:
        return
    einwand = kennungs_einwand(
        {key: data}, await cl.current_config(), await sicherheits_kennungen())
    if einwand:
        status = vergeben_status if einwand.art == "vergeben" else 400
        raise HTTPException(status, msg(lang, einwand.meldung, **einwand.werte))


@router.post("/documents", status_code=201)
async def create_document(body: DocumentCreate, lang: Lang) -> dict:
    """Ein Muster oder eine Persona anlegen — leer oder als Kopie (ST-3d).

    Die Kopie übernimmt das ganze Dokument der Vorlage und setzt nur Kennung und
    Name neu. Angelegt wird bedingt (409, wenn es den Schlüssel schon gibt), mit
    denselben Prüfungen wie ein Speichern.
    """
    group = body.group.strip()
    kennung = body.id.strip()
    name = body.label.strip()
    if group not in GRUPPEN:
        raise HTTPException(400, msg(lang, "documents.groupInvalid", group=group))
    if not KENNUNG.fullmatch(kennung):
        raise HTTPException(400, msg(lang, "documents.idInvalid", id=kennung))
    if group == "03-patterns" and ist_reservierte_kennung(kennung):
        raise HTTPException(400, msg(lang, "patterns.idReserved", value=repr(kennung)))
    if not name or len(name) > _NAME_MAX:
        raise HTTPException(400, msg(lang, "documents.labelMissing", max=_NAME_MAX))

    data: dict = {"frontmatter": {}, "body": ""}
    if body.source is not None:
        vorlage = await cl.read_area(body.source) if gruppe_von(body.source) == group else None
        if vorlage is None:
            raise HTTPException(400, msg(lang, "documents.sourceMissing", source=body.source))
        data = copy.deepcopy(vorlage[0])
    alt = data.get("frontmatter") if isinstance(data.get("frontmatter"), dict) else {}
    data["frontmatter"] = {"id": kennung, "label": name,
                           **{k: v for k, v in alt.items() if k not in ("id", "label")}}

    key = schluessel_fuer(group, kennung)
    if not is_restorable_area_key(key) or gruppe_von(key) != group:
        # „P-“ ergab ``04-personas/`` — eine Zeile ohne Blatt (Review Paket 6).
        raise HTTPException(400, msg(lang, "documents.idInvalid", id=kennung))
    _assert_area_document_safe(key, data, lang)
    fehler = modell_fehler(key, data)
    if fehler:
        raise HTTPException(status_code=422, detail=fehler)
    await pruefe_kennung(key, data, lang, vergeben_status=409)
    try:
        version = await cl.write_area(key, data, updated_by="studio-document", create_only=True)
    except ConfigConflict as e:
        raise konflikt_antwort(e, lang, anlegen=True) from e
    return {"status": "created", "key": key, "version": version}


@router.delete("/file")
async def delete_config_file(path: str, lang: Lang, expected_version: int | None = None) -> dict:
    """Ein Muster, eine Persona oder einen Bereich ohne Modell löschen (Paket 6, S1).

    Ein fester Bereich der Registry (``01-base/policy`` …) bleibt: ohne ihn fiele
    der Lader still auf Vorgaben zurück — zurücksetzen geht über „Werksfassung
    verwenden“ (Sicherung → „Werk und eigene Fassung“, Paket 12). Ein Bereich
    ohne Modell (etwa ein Tippfehler aus dem Rohtext) bleibt löschbar.

    Ein gelöschtes Dokument aus der Werksfassung bleibt gelöscht: der Löschvermerk
    (``config_werk_entfernt``, Paket 12) hält den Werksabgleich beim nächsten Start
    davon ab, es wieder anzulegen. Zurück holt es „Werksfassung verwenden“ unter
    Sicherung → „Werk und eigene Fassung“; das Studio sagt das in der Rückfrage.
    Die Muster, die Krise und Bedrohung erzwingen (M01, M02,
    ``crisis_pattern``/``threat_pattern``), bleiben stehen (400). Mit
    ``expected_version`` wird nur dieser Stand gelöscht — sonst 409 wie beim
    bedingten Speichern (Review Paket 6).
    """
    try:
        key = cl._strip_ext(cl._validate_config_path(path))
    except ValueError:
        raise HTTPException(400, msg(lang, "documents.deleteOnly", path=path)) from None
    if ist_fest(key) or not is_restorable_area_key(key):
        raise HTTPException(400, msg(lang, "documents.deleteOnly", path=path))
    if gruppe_von(key) == "03-patterns":
        gelesen = await cl.read_area(key)
        if gelesen and ist_sicherheitsmuster(key, gelesen[0], await sicherheits_kennungen()):
            raise HTTPException(400, msg(lang, "documents.deleteSafety",
                                         id=kennung_von(gelesen[0])))
    werksbereich = key in await seed_sync.werk_bereiche(get_settings().config_seed_dir)
    try:
        geloescht = await cl.delete_area(key, expected_version=expected_version,
                                         werksbereich=werksbereich)
    except ConfigConflict as e:
        raise konflikt_antwort(e, lang) from e
    except EigeneFassungLiegtStill:
        raise HTTPException(400, msg(lang, "fassung.loeschenMitEigener", area=key)) from None
    if not geloescht:
        raise HTTPException(404, msg(lang, "documents.notFound", path=path))
    return {"status": "deleted", "path": path}
