"""Argument-Modelle der kuratierenden MCP-Werkzeuge (E2).

Getrennt von ``schemas_mcp.py`` und nicht darin, aus zwei Gründen: die Lese-Datei
stünde sonst bei über 400 Zeilen, und die kuratierende Oberfläche hat ihren
eigenen Änderungsgrund — sie folgt dem Schreib-Schema des Servers, nicht dem
Such-Schema. Die Fassade ``boerdi.api.schemas`` reicht beide gemeinsam weiter.

**Feldnamen und Grenzen sind 2026-08-10 live von ``tools/list`` geholt**, nicht
abgetippt; die Enums (``contentFormat``, ``decision``, ``status``, das Feld eines
Vorschlags) stammen aus derselben Messung.

``confirmToken`` fehlt hier **absichtlich**. Er gehört nicht zu den Argumenten,
die ein Modell bestimmt: der Wall aus E1 (``domain/write_confirm``) entfernt
einen selbst gesetzten Schlüssel und setzt den echten erst im Folgezug ein. Ein
Modell, das ihn hier fände, würde ihn erfinden.

Zur Bedeutung der Grenzen siehe den Kopf von ``schemas_mcp.py``: ``ge``/``le``
heißt **klemmen**, nicht ablehnen.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_serializer, field_validator


# Die schreibbaren Metadatenfelder eines Materials. Einmal deklariert, von
# ``wlo_create_content`` und ``wlo_update_content`` geteilt — der Server führt
# für beide dieselbe Liste, und zwei Handkopien wären zwei Gelegenheiten zum
# Auseinanderlaufen.
class _ContentFields(BaseModel):
    title: str = ""
    description: str = ""
    keywords: list[str] = Field(default_factory=list)
    url: str = ""
    language: str = ""
    author: str = ""
    publisher: str = ""
    licenseKey: str = ""
    licenseVersion: str = ""
    contentType: str = ""
    educationalContext: str = ""
    discipline: str = ""
    userRole: str = ""
    content: str = ""
    # Leerstring statt ``None`` als „nicht angegeben": ``_export_non_empty``
    # entfernt ausschliesslich leere Strings. Ein ``None`` ueberlebt den Export
    # und ginge als ``"contentFormat": null`` an den Server, dessen Schema das
    # Feld als optionale Zeichenkette fuehrt — zod lehnt ``null`` dort ab.
    contentFormat: Literal["markdown", "text", ""] = ""
    fileBase64: str = ""


class ContentCreateArgs(_ContentFields):
    """``wlo_create_content`` — Pflichtfeld ist allein der Titel.

    ``addToCollectionId`` (Paket M3, MCP-Stand 2026-11-07): den neuen Datensatz unter DERSELBEN
    Bestätigung in eine Sammlung aufnehmen — eine Abnahme statt zwei. Gibt es zur ``url`` schon
    einen Datensatz, bietet die Vorschau an, diesen aufzunehmen."""

    addToCollectionId: str = Field(default="", max_length=200)


class ContentUpdateArgs(_ContentFields):
    """``wlo_update_content`` — vorhandenes Material ändern.

    ``commit`` steht auf dem Server-Standard ``False``: eine neue Version wird
    nur auf ausdrücklichen Wunsch angelegt.
    """
    nodeId: str
    commit: bool = False
    versionComment: str = ""


class NodeOnlyArgs(BaseModel):
    """``wlo_delete_content`` / ``wlo_delete_collection`` — nur die nodeId."""
    nodeId: str


class ContentSubmitArgs(BaseModel):
    """``wlo_submit_content`` — Material zur redaktionellen Prüfung einreichen."""
    nodeId: str
    comment: str = ""


class CollectionCreateArgs(BaseModel):
    """``wlo_create_collection`` — ohne ``parentId`` auf oberster Ebene."""
    title: str
    description: str = ""
    parentId: str = ""


class CollectionRenameArgs(BaseModel):
    """``wlo_rename_collection`` — Titel und Beschreibung einer Sammlung."""
    nodeId: str
    title: str
    description: str = ""


class CollectionTreeCreateArgs(BaseModel):
    """``wlo_create_collection_tree`` (Paket M5): ein Baum von Untersammlungen unter
    ``parentCollectionId`` — höchstens 250 Knoten, Tiefe 4, 15 Kinder je Knoten (prüft der Server
    und nennt jeden Grund). ``onExisting``: ``merge`` (Vorgabe: gleichnamige wird übernommen) oder
    ``fail``. ``continuationToken`` setzt einen bestätigten Plan fort."""

    parentCollectionId: str = Field(max_length=200)
    tree: list[dict[str, Any]]
    onExisting: Literal["merge", "fail", ""] = ""
    continuationToken: str = Field(default="", max_length=200)

    @field_validator("tree", mode="before")
    @classmethod
    def _nur_baumfelder(cls, wert):
        # Review 2026-11-07: der Server prüft jede Ebene streng — ein fremdes Feld (``keywords``,
        # ``nodeId``) in einem tieferen Knoten kippte den ganzen Aufruf. Nur title/description/
        # children bleiben; Grenzen (250 Knoten, Tiefe 4, 15 Kinder) prüft und nennt der Server.
        def knoten(k):
            if not isinstance(k, dict):
                return k
            aus = {f: k[f] for f in ("title", "description") if f in k}
            if isinstance(k.get("children"), list):
                aus["children"] = [knoten(c) for c in k["children"]]
            return aus
        return [knoten(k) for k in wert] if isinstance(wert, list) else wert


class CollectionsAddArgs(BaseModel):
    """``wlo_add_to_collections`` (Paket M5): bis zu 200 Paare ``{nodeId, collectionId}``."""

    pairs: list[dict[str, str]]
    continuationToken: str = Field(default="", max_length=200)

    @field_validator("pairs", mode="before")
    @classmethod
    def _nur_paarfelder(cls, wert):
        # Wie beim Baum: nur nodeId/collectionId — der Server lehnt fremde Felder ab.
        if not isinstance(wert, list):
            return wert
        return [{f: p[f] for f in ("nodeId", "collectionId") if f in p} if isinstance(p, dict)
                else p for p in wert]


#: Paket K2d-3: woher ein Volltext kommt (``wlo_attach_fulltext(s)``, Schema des Servers).
VolltextQuelle = Literal["binary", "website", "manual"]
_VOLLTEXT_FELDER = ("nodeId", "markdown", "source", "sourceUrl", "language")
#: Die Felder eines Eintrags von ``wlo_update_contents`` — die Metadatenfelder von
#: :class:`_ContentFields` ohne Inhalt und Datei (dafür bleibt ``wlo_update_content``), dazu
#: ``reason`` (Begründung der Vorschläge, die der Server statt eines Schreibens hinterlegt).
_METADATEN_FELDER = ("nodeId", "reason", *(f for f in _ContentFields.model_fields
                                          if f not in ("content", "contentFormat", "fileBase64")))


def _nur(felder: tuple[str, ...], wert: Any) -> Any:
    """Jeder Eintrag nur mit diesen Feldern und ohne leere Werte. Unbekannte Felder entfernt der
    Server still; ein leeres Feld dagegen („kein Wert angegeben“) weist bei ``wlo_update_contents``
    den GANZEN Aufruf ab (Review K2d-3, Befund 1) — ``_export_non_empty`` räumt nur die oberste
    Ebene auf."""
    if not isinstance(wert, list):
        return wert
    return [{f: v for f in felder if f in e and not _leer(v := _ohne_leere(e[f]))}
            if isinstance(e, dict) else e for e in wert]


def _ohne_leere(wert: Any) -> Any:
    """Zweites Review K2d-3, Befund 3: aus einer Liste fallen leere Einträge (``""``, ``"  "``)."""
    return [x for x in wert if not _leer(x)] if isinstance(wert, list) else wert


def _leer(wert: Any) -> bool:
    """Leer wie beim Server (er kürzt Leerzeichen): ``None``, ``""``, nur Leerzeichen, ``[]``."""
    return wert is None or wert == [] or (isinstance(wert, str) and not wert.strip())


class FulltextAttachArgs(BaseModel):
    """``wlo_attach_fulltext`` (Paket K2d-3, W1): ein Volltext (Markdown) in den ``textContent``
    eines vorhandenen Datensatzes. ``replace`` ersetzt einen vorhandenen. Ein Datensatz mit Datei
    lehnt der Server ab (``would_replace_file``, dauerhaft seit dem 14.11.2026)."""

    nodeId: str = Field(max_length=200)
    markdown: str
    source: VolltextQuelle
    sourceUrl: str = Field(default="", max_length=2000)
    language: str = Field(default="", max_length=10)
    replace: bool = False


class FulltextsAttachArgs(BaseModel):
    """``wlo_attach_fulltexts`` (Paket K2d-3, W2): bis zu 200 Volltexte als Plan."""

    items: list[dict[str, Any]]
    replace: bool = False
    continuationToken: str = Field(default="", max_length=200)

    @field_validator("items", mode="before")
    @classmethod
    def _nur_volltextfelder(cls, wert):
        return _nur(_VOLLTEXT_FELDER, wert)


class ContentsUpdateArgs(BaseModel):
    """``wlo_update_contents`` (Paket K2d-3, W3): Metadaten für bis zu 200 Datensätze als Plan.
    Der Server entscheidet je Feld, ob er schreibt oder einen Vorschlag hinterlegt."""

    items: list[dict[str, Any]]
    continuationToken: str = Field(default="", max_length=200)

    @field_validator("items", mode="before")
    @classmethod
    def _nur_metadatenfelder(cls, wert):
        return _nur(_METADATEN_FELDER, wert)


class CollectionMembershipArgs(BaseModel):
    """``wlo_add_to_collection`` / ``wlo_remove_from_collection``.

    Eine Sammlung enthält Verweise: hier wird nichts kopiert und beim Entfernen
    nichts gelöscht.
    """
    collectionId: str
    nodeId: str


class CompendiumUpdateArgs(BaseModel):
    """``wlo_update_compendium`` — die Übersichts-Prosa einer Sammlung.

    ``remove=True`` löscht den Text; ohne ``text`` und ohne ``remove`` gibt es
    nichts zu ändern, was der Server als leere Änderungsmenge beantwortet.
    """
    nodeId: str
    text: str = ""
    remove: bool = False


class TopicPageSetArgs(BaseModel):
    """``wlo_set_topic_page`` — Sammlung als Themenseiten-Variante setzen."""
    collectionId: str
    variantId: str


class MetadataSuggestion(BaseModel):
    """Ein einzelner Metadaten-Vorschlag.

    ``reason`` ist Pflicht, weil genau daran die prüfende Person entscheidet —
    ein Vorschlag ohne Begründung ist im Redaktions-Postfach wertlos.
    ``confidence`` bleibt optional: ohne Angabe des Modells wäre jeder Ersatzwert
    eine Sicherheit, die niemand behauptet hat.
    """
    field: Literal[
        "title", "description", "keywords", "url", "language", "author",
        "publisher", "licenseKey", "licenseVersion", "contentType",
        "educationalContext", "discipline", "userRole",
    ]
    value: str
    reason: str
    confidence: float | None = Field(default=None, ge=0, le=1)


class MetadataSuggestArgs(BaseModel):
    """``wlo_suggest_metadata`` — Vorschläge zur redaktionellen Entscheidung."""
    nodeId: str
    suggestions: list[MetadataSuggestion]

    @field_serializer("suggestions")
    def _ohne_ungesetzte_sicherheit(self, items: list[MetadataSuggestion]) -> list[dict]:
        """Nicht angegebene ``confidence`` fällt raus statt als ``null`` zu reisen.

        ``_export_non_empty`` in ``tool_defs`` räumt nur die OBERSTE Ebene auf —
        eine verschachtelte Liste sieht es nicht. Ohne diesen Schritt ginge
        ``"confidence": null`` an den Server, der das Feld als optionale Zahl
        führt; damit scheiterte jeder Vorschlag, für den das Modell keine
        Sicherheit angibt — also der Regelfall.
        """
        return [i.model_dump(exclude_none=True) for i in items]


class SuggestionsListArgs(BaseModel):
    """``wlo_list_suggestions`` — das einzige lesende Werkzeug der Gruppe."""
    nodeId: str
    # Leerstring statt ``None``, gleiche Begründung wie bei ``contentFormat``.
    status: Literal["PENDING", "ACCEPTED", "DECLINED", ""] = ""


class SuggestionDecideArgs(BaseModel):
    """``wlo_decide_suggestion`` — einen Vorschlag annehmen oder ablehnen."""
    nodeId: str
    suggestionId: str
    decision: Literal["accept", "decline"]
