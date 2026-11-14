"""MCP tool-argument models (validated before calling the MCP server) —
ported 1:1 from ALT ``app/models/schemas.py``. Part of the facade
``boerdi.api.schemas``. Canonical arg names + legacy aliases per spec §5.2.

Bounds note (W10, 2026-08-01): ``Field(ge=…, le=…)`` here means **clamp**, not
reject. ``validate_tool_args`` catches the ValidationError and sets the field to
the violated bound before revalidating; only errors it cannot repair (missing
required field, unparsable value) fall back to forwarding the raw arguments.
Until that repair step existed the bounds were decorative — an oversized
``maxResults`` travelled to the server unchanged, the exact case they exist for.

**Only numeric bounds are repaired.** ``max_length`` and ``extra="forbid"`` are
NOT: they raise an error the repair step cannot fix, so the fail-open path
forwards the raw arguments and the server rejects them. String bounds here
therefore document the server's limit and produce a log line; they do not cap.
Truncating a URL or an id would silently address something else, which is worse
than a rejection — so this is deliberate, not an oversight (R5, 2026-08-11).

Size (R6, 2026-08-11): past the ~300-line threshold and deliberately kept as one
unit. It is a flat table of argument models with exactly ONE reason to change —
a tool's schema on the MCP server changed — so a split would cut along no seam
and cost the facade a second import for nothing. The threshold is a smoke
detector, and the smoke here has a known source: the file grows by one small
model per server tool we adopt. Split it when a model starts carrying logic
beyond field bounds and alias normalisation; the sibling
``services/response_tool_selection.py`` documents its own exception the same way.
"""

from __future__ import annotations

import logging
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_logger = logging.getLogger(__name__)


class SearchWloArgs(BaseModel):
    """Arguments for search_wlo_collections and search_wlo_content.

    NOTE: These parameter names match the WLO MCP server schema EXACTLY.
    Historical mismatches (resourceType, educationalLevel, maxItems) caused
    the server to silently ignore our filters; those legacy names are now
    accepted via pre-validator aliases but always exported as the server's
    canonical names (learningResourceType, educationalContext, maxResults).
    """
    query: str = ""
    discipline: str = ""
    educationalContext: str = ""  # educationalLevel is a legacy alias
    learningResourceType: str = ""  # resourceType is a legacy alias
    userRole: str = ""
    publisher: str = ""
    parentNodeId: str = ""  # only valid for search_wlo_collections
    maxResults: int = Field(default=5, ge=1, le=20)  # maxItems is a legacy alias
    # V4 (Server 2026-08-20): bereits gezeigte IDs überspringen — der
    # dokumentierte Weg für „zeig mehr davon" statt skipCount-Paging.
    excludeNodeIds: list[str] = Field(default_factory=list, max_length=200)

    #: Felder, die das Server-Schema DIESES Werkzeugs nicht kennt
    #: (``additionalProperties: false`` — mitreisen hieße Server-Fehler).
    #: Die Sammlungs-Suche kennt weder ``license`` noch ``skipCount``.
    _SERVER_UNBEKANNT: ClassVar[tuple[str, ...]] = ("license", "skipCount")

    @model_validator(mode="before")
    @classmethod
    def _accept_legacy_names(cls, data):
        """Accept old param names we used in prompts and UI history."""
        if not isinstance(data, dict):
            return data
        data = dict(data)
        # educationalLevel → educationalContext
        if "educationalContext" not in data and "educationalLevel" in data:
            data["educationalContext"] = data.pop("educationalLevel")
        # resourceType → learningResourceType
        if "learningResourceType" not in data and "resourceType" in data:
            data["learningResourceType"] = data.pop("resourceType")
        # maxItems → maxResults
        if "maxResults" not in data and "maxItems" in data:
            data["maxResults"] = data.pop("maxItems")
        for feld in cls._SERVER_UNBEKANNT:
            data.pop(feld, None)
        return data


class ContentSearchArgs(SearchWloArgs):
    """Arguments for search_wlo_content — kennt zusätzlich ``license``.

    Server 2026-08-20: exakter Lizenzfilter ("CC BY 4.0", "gemeinfrei", …)
    oder das Bündel "OER" (CC0/gemeinfrei/CC BY/CC BY-SA). ``skipCount``
    kennt der Server hier zwar auch, bleibt aber bewusst undeklariert:
    Folgeseiten laufen über ``excludeNodeIds`` — beim Lizenzbündel ist
    Paging laut Server-Doku keine saubere Partition.
    """
    license: str = ""

    _SERVER_UNBEKANNT: ClassVar[tuple[str, ...]] = ("skipCount",)


class CollectionContentsArgs(BaseModel):
    """Arguments for get_collection_contents.

    Matches MCP schema: nodeId, query, contentFilter, includeSubcollections,
    maxResults, skipCount. Legacy name maxItems accepted via pre-validator.

    N3 (MCP-Stand 2026-11-14): statt ``nodeId`` der Titel der Sammlung als ``collection``, dazu
    ``discipline`` für gleichnamige. Die Kennung ist deshalb hier keine Pflicht mehr; fehlt
    beides, sagt es der Server (``invalid_input``).
    """
    nodeId: str = ""
    collection: str = Field(default="", max_length=200)
    discipline: str = Field(default="", max_length=200)
    query: str = ""
    contentFilter: str = ""  # "files" | "folders" | "both"
    # Server 2026-08-18: liefert die Skills DIESES Arbeitszusammenhangs samt
    # der Anweisung der Redaktion mit der Sammlungsantwort — der
    # get_skill_registry-Zwischenschritt entfällt. Ein Name, der nicht trifft,
    # liefert den vollen Katalog samt vorhandener Namen, nie einen Fehler.
    # Nutzungsregel (2026-08-20): nur auf ausdrücklichen Wunsch verengen
    # (Nutzer/Einbettung) — Vorgabe ist der volle Katalog.
    skillContext: str = ""
    includeSubcollections: bool = False
    maxResults: int = Field(default=5, ge=1, le=100)
    skipCount: int = Field(default=0, ge=0)

    @model_validator(mode="before")
    @classmethod
    def _accept_legacy_names(cls, data):
        if not isinstance(data, dict):
            return data
        data = dict(data)
        if "maxResults" not in data and "maxItems" in data:
            data["maxResults"] = data.pop("maxItems")
        return data


class NodeDetailsArgs(BaseModel):
    """Arguments for get_node_details (MCP server v2)."""
    nodeId: str
    includeTextContent: bool = False
    includeParents: bool = False
    includeRaw: bool = False
    skillContext: str = ""  # wie CollectionContentsArgs (Server 2026-08-18)


class SearchTopicPagesArgs(BaseModel):
    """Arguments for search_wlo_topic_pages."""
    query: str = ""
    collectionId: str = ""
    targetGroup: str = ""  # teacher | learner | general
    educationalContext: str = ""
    mergeVariants: bool = True
    sort: str = ""  # "alpha" | "relevance"
    maxResults: int = Field(default=5, ge=1, le=20)


class SubjectPortalsArgs(BaseModel):
    """Arguments for get_subject_portals (Fachportale)."""
    educationalContext: str = ""
    includeContentCounts: bool = False


class CollectionTreeArgs(BaseModel):
    """Arguments for browse_collection_tree.

    W9c (2026-08-01): ``nodeId`` is no longer required — the server resolves a
    subject-portal name (``subject="Mathematik"``) on its own, which saves the
    ``get_subject_portals`` round trip the old two-step flow needed. Exactly one
    of the two is expected; the server rejects a call with neither, and its
    error message is clearer than anything we could raise here (a raised
    ValidationError would be swallowed by ``validate_tool_args`` anyway).
    """
    nodeId: str = ""
    subject: str = ""
    # N3 (MCP-Stand 2026-11-14): der Titel einer Sammlung statt ihrer Kennung; ``discipline``
    # unterscheidet gleichnamige. ``subject`` bleibt der Name eines Fachportals.
    collection: str = Field(default="", max_length=200)
    discipline: str = Field(default="", max_length=200)
    depth: int = Field(default=1, ge=1, le=3)  # Paket M4: bis 3 (MCP-Stand 2026-11-07)
    includeContentCounts: bool = False
    maxResults: int = Field(default=50, ge=1, le=100)


class HealthCheckArgs(BaseModel):
    """Arguments for wlo_health_check."""
    pass


class FindByUrlArgs(BaseModel):
    """``find_content_by_url`` (Paket M3, MCP-Stand 2026-11-07): gibt es zu diesen Adressen schon
    Datensätze? Der Server nimmt höchstens 20 — mehr werden gekappt statt abgelehnt."""

    urls: list[str]
    includeCollections: bool = False

    @model_validator(mode="before")
    @classmethod
    def _kappen(cls, data):
        if isinstance(data, dict) and isinstance(data.get("urls"), str):
            data = {**data, "urls": [data["urls"]]}
        if isinstance(data, dict) and isinstance(data.get("urls"), list):
            # Über 2000 Zeichen lehnte der Server den GANZEN Aufruf ab (Review M3, Befund 5).
            urls = [u.strip() for u in data["urls"]
                    if isinstance(u, str) and u.strip() and len(u.strip()) <= 2000]
            data = {**data, "urls": urls[:20]}
        return data


def _kappe(wert, vorgabe: int, unten: int, oben: int) -> int:
    try:
        return max(unten, min(oben, int(wert)))
    except (TypeError, ValueError):
        return vorgabe


_UEBERSICHT_TEILE = ("breadcrumb", "compendium", "stats", "skills", "subcollections", "contents")


class CollectionOverviewArgs(BaseModel):
    """``get_collection_overview`` (Paket M4, MCP-Stand 2026-11-07): eine Sammlung auf einen Blick.
    Unbekannte Teile fallen weg, Zahlen werden auf die Grenzen des Servers gekappt."""

    # N3 (MCP-Stand 2026-11-14): die Kennung oder der Titel als ``collection`` (mit ``discipline``).
    collectionId: str = Field(default="", max_length=200)
    collection: str = Field(default="", max_length=200)
    discipline: str = Field(default="", max_length=200)
    include: list[str] = Field(default_factory=list)
    maxContents: int = 10
    maxSubcollections: int = 30

    @model_validator(mode="before")
    @classmethod
    def _grenzen(cls, data):
        if not isinstance(data, dict):
            return data
        data = dict(data)
        # Review M4, Befund 15: die Kennung unter dem Namen der Nachbarwerkzeuge, ein Teil als
        # Zeichenkette — beides lehnte der Server sonst als Ganzes ab.
        if not data.get("collectionId") and data.get("nodeId"):
            data["collectionId"] = data.pop("nodeId")
        data.pop("nodeId", None)
        if isinstance(data.get("include"), str):
            data["include"] = [data["include"]]
        if isinstance(data.get("include"), list):
            data["include"] = [t for t in data["include"] if t in _UEBERSICHT_TEILE]
        if "maxContents" in data:
            data["maxContents"] = _kappe(data["maxContents"], 10, 0, 50)
        if "maxSubcollections" in data:
            data["maxSubcollections"] = _kappe(data["maxSubcollections"], 30, 0, 100)
        return data


#: Die Filter der Zählung (Server ``tools/content-count.ts``) und ihre Altnamen wie bei
#: :class:`SearchWloArgs`.
_ZAEHL_FILTER = ("educationalContext", "discipline", "userRole", "learningResourceType")
_ZAEHL_ALTNAMEN = {"educationalLevel": "educationalContext", "subject": "discipline",
                   "resourceType": "learningResourceType"}


def _zaehl_anfrage(q: object) -> dict[str, Any] | None:
    """Eine Anfrage in der Form des Servers — oder ``None``, wenn sie nicht gezählt werden darf
    (Review M4, Befund 3). Der Server lehnt den GANZEN Aufruf ab, wenn eine Anfrage nicht passt;
    und einen fremden Filterschlüssel verwürfe er still — gezählt würde dann ohne den Filter, die
    Zahl wäre zu hoch. Beides trifft hier nur die eine Anfrage."""
    if not isinstance(q, dict):
        return None
    kennung = str(q.get("id") if q.get("id") is not None else "").strip()
    anfrage = str(q.get("query") or "").strip()
    if not kennung or not anfrage or len(kennung) > 100 or len(anfrage) > 500:
        return None
    filter_ = q.get("filters")
    if filter_ is None:
        return {"id": kennung, "query": anfrage}
    if not isinstance(filter_, dict):
        return None
    sauber: dict[str, str] = {}
    for schluessel, wert in filter_.items():
        schluessel = _ZAEHL_ALTNAMEN.get(schluessel, schluessel)
        if wert is None or wert == "":
            continue
        if schluessel not in _ZAEHL_FILTER or not isinstance(wert, str) or len(wert) > 200:
            return None
        sauber[schluessel] = wert
    return {"id": kennung, "query": anfrage, **({"filters": sauber} if sauber else {})}


class ContentCountArgs(BaseModel):
    """``count_wlo_content_matches`` (Paket M4): Trefferzahlen für bis zu 30 Anfragen
    ``{id, query, filters?}`` zugleich; ``top`` 0–3 beste Treffer je Anfrage. Eine Anfrage, die
    der Server nicht annähme, fällt einzeln weg (:func:`_zaehl_anfrage`)."""

    queries: list[dict[str, Any]]
    top: int = 2

    @model_validator(mode="before")
    @classmethod
    def _grenzen(cls, data):
        if not isinstance(data, dict):
            return data
        data = dict(data)
        if isinstance(data.get("queries"), list):
            sauber = [a for a in map(_zaehl_anfrage, data["queries"]) if a is not None]
            if len(sauber) < len(data["queries"]):
                _logger.info("count_wlo_content_matches: %d von %d Anfragen nicht annehmbar — "
                             "weggelassen", len(data["queries"]) - len(sauber),
                             len(data["queries"]))
            data["queries"] = sauber[:30]
        if "top" in data:
            data["top"] = _kappe(data["top"], 2, 0, 3)
        return data


_MANY_FILTER = ("educationalContext", "discipline", "userRole", "learningResourceType",
                "publisher", "license")


def _many_wert(wert: Any) -> Any:
    """Ein Filterwert: Text in der Schranke des Servers (200 Zeichen); eine Liste mit genau einem
    Text ist dieser Text. Alles andere bleibt, wie es ist — der Server lehnt es ab."""
    if isinstance(wert, list) and len(wert) == 1 and isinstance(wert[0], str):
        wert = wert[0]
    return wert.strip()[:200] if isinstance(wert, str) else wert


def _many_filter(roh: Any) -> Any:
    """Die Filter einer Anfrage: leere Werte fallen weg (wie am Server), die alten Namen
    (``educationalLevel``, ``resourceType``, ``subject``) werden übersetzt. Ein Wert, der kein
    Text ist (mehrere Werte als Liste, eine Zahl), bleibt stehen, ebenso ein ``filters``, das
    kein Objekt ist: Der Server lehnt den Aufruf ab und sagt es. Auch ein fremder Schlüssel
    bleibt stehen: Den ließe der Server still weg, deshalb lehnt der Client den Aufruf ab
    (``suche_mehrfach.nicht_moeglich``). Fiele der Filter still weg, liefe die Suche ungefiltert
    und sähe gefiltert aus (Review N4, M3; Review 2, Befund 4)."""
    if not isinstance(roh, dict):
        return roh
    werte = {n: w for n, w in roh.items() if n not in _ZAEHL_ALTNAMEN}
    for alt, neu in _ZAEHL_ALTNAMEN.items():
        if alt in roh and werte.get(neu) in (None, "", []):
            werte[neu] = roh[alt]
    werte = {n: (_many_wert(w) if n in _MANY_FILTER else w)
             for n, w in werte.items() if w is not None}
    return {n: w for n, w in werte.items() if w not in ("", [])}


def _many_anfrage(roh: Any) -> Any:
    """Eine Anfrage ``{id, query, filters?}`` in den Schranken des Servers (``id`` 1–40, ``query``
    1–200 Zeichen), ohne fremde Felder und leere Filter. Was keine Anfrage sein kann, bleibt, wie
    es ist: Der Server lehnt den Aufruf dann ab und sagt es — fiele die Anfrage hier still weg,
    bliebe ein Schritt ohne Suche und sähe aus wie „keine Treffer“. Dasselbe gilt für einen
    Filter, der keiner sein kann (:func:`_many_filter`)."""
    if not isinstance(roh, dict) or not isinstance(roh.get("query"), str) or not roh[
            "query"].strip():
        return roh
    kennung = roh.get("id")
    if not isinstance(kennung, str | int) or isinstance(kennung, bool) or not str(kennung).strip():
        return roh
    anfrage: dict[str, Any] = {"id": str(kennung).strip()[:40], "query": roh["query"].strip()[:200]}
    if filter_ := _many_filter(roh.get("filters")):
        anfrage["filters"] = filter_
    return anfrage


class ContentSearchManyArgs(BaseModel):
    """``search_wlo_content_many`` (N4, MCP-Stand 2026-11-14): bis zu acht Inhaltssuchen
    ``{id, query, filters?}`` in einem Aufruf, je bis zu fünf Treffer in Kurzform. Gemeinsame
    Filter gelten für alle Anfragen. Mehr als acht Anfragen lehnt der Client mit einem Satz ab
    (``services/mcp/suche_mehrfach.nicht_moeglich``), er kürzt nicht."""

    queries: list[Any]
    educationalContext: str = Field(default="", max_length=200)
    discipline: str = Field(default="", max_length=200)
    userRole: str = Field(default="", max_length=200)
    learningResourceType: str = Field(default="", max_length=200)
    publisher: str = Field(default="", max_length=200)
    license: str = Field(default="", max_length=200)
    maxResults: int = Field(default=3, ge=1, le=5)
    distinct: bool = False

    @field_validator("queries", mode="before")
    @classmethod
    def _anfragen(cls, wert):
        return [_many_anfrage(a) for a in wert] if isinstance(wert, list) else wert

    @model_validator(mode="before")
    @classmethod
    def _altnamen(cls, data):
        """Die alten Filternamen, gemeinsam für alle Anfragen — wie bei der Einzelsuche."""
        if not isinstance(data, dict):
            return data
        data = dict(data)
        for alt, neu in _ZAEHL_ALTNAMEN.items():
            if alt in data and data.get(neu) in (None, "", []):
                data[neu] = data.pop(alt)
        return data

    @field_validator(*_MANY_FILTER, mode="before")
    @classmethod
    def _ein_wert(cls, wert):
        """Eine Liste mit genau einem Text ist dieser Text; ``null`` und eine leere Liste heißen
        „nicht angegeben“ (wie je Anfrage). Mehrere Werte lässt das Modell nicht zu: Die
        Argumente gehen dann roh hinaus, und der Server lehnt sie ab."""
        if wert is None or wert == []:
            return ""
        return wert[0] if (isinstance(wert, list) and len(wert) == 1
                           and isinstance(wert[0], str)) else wert


class NodesDetailsArgs(BaseModel):
    """Arguments for get_nodes_details (bulk metadata)."""
    nodeIds: list[str]


class CollectionStatsArgs(BaseModel):
    """Arguments for get_collection_stats (W9a).

    Server schema (fetched 2026-08-01): ``nodeId`` required, nothing else the
    model needs to steer. The breakdown counts up to 100 direct child files —
    a sample, not the whole subtree; the server's own output says so.

    ``outputFormat`` seit 2026-08-14 — nicht fürs Modell, sondern damit ein
    interner Aufrufer JSON verlangen KANN. Ein Feld, das dieses Modell nicht
    kennt, wirft Pydantic STILL weg: ``context_facts`` bat um ``json``, bekam
    Markdown, ``json.loads`` scheiterte, und die Kontext-Bestätigung blieb ohne
    Zahlen — ohne dass irgendwo ein Fehler stand. Vorgabe ``markdown`` ist der
    Server-Standard, der Aufruf also unverändert.
    """
    nodeId: str
    outputFormat: Literal["markdown", "json"] = "markdown"


class NodeBreadcrumbArgs(BaseModel):
    """Arguments for get_node_breadcrumb (W9a).

    Collection nodes only — file nodes (``ccm:io``) return an empty path.
    """
    nodeId: str


class CompendiumTextArgs(BaseModel):
    """Arguments for get_compendium_text (W9a).

    ``nodeIds`` (V6) ergänzt ``nodeId`` um weitere Sammlungen — der Server
    vereinigt beide Angaben und nähme bis zu 25. Wir bieten 9: die Antwort
    läuft ungedeckelt durch die Redaktion (Langform-Pfad), und der
    Server-Deckel gilt JE Kompendium — 25 auf einmal multiplizierten ihn auf
    >100 KB Prompt (Review 2026-08-20). Der frühere Verzicht auf die Liste
    stützte sich darauf, dass der Export-Filter nur leere Strings strippte;
    seit V4 strippt er auch leere Listen.

    ``query`` (Server 2026-08-18): nur die per BM25 passenden Absätze samt
    Inhaltsverzeichnis statt des ganzen Texts — gemessen ~5 KB statt ~21 KB am
    größten Kompendium. Die Antwort nennt Suchwörter ohne Treffer ausdrücklich.
    ``max_length`` spiegelt die Server-Schranke.

    N3 (MCP-Stand 2026-11-14): statt der Kennung der Titel als ``collection`` (mit ``discipline``).
    """
    nodeId: str = ""
    collection: str = Field(default="", max_length=200)
    discipline: str = Field(default="", max_length=200)
    nodeIds: list[str] = Field(default_factory=list, max_length=9)
    query: str = Field(default="", max_length=200)


class PublishersLookupArgs(BaseModel):
    """Arguments for lookup_wlo_publishers (W9a).

    ``maxResults`` is **clamped, not rejected** — see the module note on bounds.
    """
    query: str = ""
    discipline: str = ""
    educationalContext: str = ""
    maxResults: int = Field(default=20, ge=1, le=50)


class WithinCollectionArgs(BaseModel):
    """Arguments for search_wlo_within_collection (W9b).

    Same filter vocabulary as the global content search, but scoped to one
    collection. Server schema fetched 2026-08-01.

    N3 (MCP-Stand 2026-11-14): statt ``nodeId`` der Titel als ``collection``. Das Fach der
    Sammlung heißt hier ``collectionDiscipline`` — ``discipline`` filtert die Inhalte.
    """
    nodeId: str = ""
    collection: str = Field(default="", max_length=200)
    collectionDiscipline: str = Field(default="", max_length=200)
    query: str = ""
    educationalContext: str = ""
    discipline: str = ""
    userRole: str = ""
    learningResourceType: str = ""
    publisher: str = ""
    maxResults: int = Field(default=10, ge=1, le=20)
    skillContext: str = ""  # wie CollectionContentsArgs (Server 2026-08-18)
    license: str = ""  # wie ContentSearchArgs (Server 2026-08-20)
    # Paket M1 (MCP-Stand 2026-11-07): ``excludeNodeIds`` wirkt hier jetzt — schon Gesehenes
    # fällt vor dem Blättern weg, auch über das Original einer Verknüpfung. ``skipCount``
    # bleibt für „die nächsten n“.
    excludeNodeIds: list[str] = Field(default_factory=list, max_length=200)
    skipCount: int = Field(default=0, ge=0)

    @model_validator(mode="before")
    @classmethod
    def _normalize(cls, data):
        if not isinstance(data, dict):
            return data
        data = dict(data)
        # Dieselben Alt-Namen, die die globale Suche akzeptiert — das Modell
        # unterscheidet die beiden Werkzeuge beim Benennen der Filter nicht.
        if "educationalContext" not in data and "educationalLevel" in data:
            data["educationalContext"] = data.pop("educationalLevel")
        if "learningResourceType" not in data and "resourceType" in data:
            data["learningResourceType"] = data.pop("resourceType")
        if "maxResults" not in data and "maxItems" in data:
            data["maxResults"] = data.pop("maxItems")
        return data


class RelatedContentArgs(BaseModel):
    """Arguments for get_related_content (W9b) — „mehr wie dieses".

    ``includeSiblings`` bleibt beim Server-Default False: Geschwister aus
    derselben Sammlung sind oft dasselbe Material in Varianten, und die Karten
    wären dann Dubletten der Liste, aus der der Nutzer gerade kommt.
    """
    nodeId: str
    maxResults: int = Field(default=8, ge=1, le=20)
    includeSiblings: bool = False
    skillContext: str = ""  # wie CollectionContentsArgs (Server 2026-08-18)


class NodeCollectionsArgs(BaseModel):
    """Arguments for get_node_collections (A2) — „wo ist das eingeordnet?".

    Gegenstück zu ``NodeBreadcrumbArgs``: dieses hier nimmt die nodeId eines
    MATERIALS und nennt die Sammlungen, die es führen; jenes nimmt die nodeId
    einer SAMMLUNG und nennt ihren Pfad im Themenbaum. Der Server hat nur
    diesen einen Parameter (``outputFormat`` setzt ``call_mcp_tool`` zentral).
    """
    nodeId: str


class LookupVocabularyArgs(BaseModel):
    """Arguments for lookup_wlo_vocabulary.

    NOTE: The upstream MCP server expects the parameter name ``vocabulary``
    (not ``field``). Historically this project used ``field``; we accept
    either via the pre-validator for backwards compatibility, but the
    exported argument is always ``vocabulary``.

    ``query`` (N2, MCP-Stand 2026-11-14): grenzt die große Liste ``contentType`` (Inhaltstypen
    zum Schreiben) auf Einträge nahe einem Begriff ein.
    """
    vocabulary: str
    query: str = Field(default="", max_length=100)

    @model_validator(mode="before")
    @classmethod
    def _accept_legacy_field(cls, data):
        if isinstance(data, dict) and "vocabulary" not in data and "field" in data:
            data = {**data, "vocabulary": data["field"]}
        # Review N2 (M2): ``query`` ist jetzt angeboten — ``null`` oder ein zu langer Wert darf
        # nicht den ganzen Aufruf roh hinausschicken.
        if isinstance(data, dict) and "query" in data:
            q = data["query"]
            data = {**data, "query": q.strip()[:100] if isinstance(q, str) else ""}
        return data


class SkillSearchArgs(BaseModel):
    """Arguments for search_skill (D1) — redaktionell gepflegte Anleitungen finden.

    Grenzen aus dem Live-Schema des Servers geholt (``tools/list`` am
    2026-08-10), nicht geraten. Ohne Argumente listet der Server den ganzen
    Katalog auf — deshalb ist nichts Pflicht.

    ``outputFormat`` wie bei :class:`SkillRegistryArgs`: nicht fürs Modell,
    sondern für die Skill-Suche des Studios (``agent_skill_directory``).
    ``search_skill`` steht NICHT in ``_JSON_CAPABLE_TOOLS`` — das Modell liest
    den Markdown-Katalog —, und ein Feld, das hier fehlt, verwirft
    ``validate_tool_args`` still (Review 2026-09-29: jede Suche endete
    „unlesbar“).

    ``includeSubcollections`` bleibt ungesetzt, wenn niemand es nennt: die
    Vorgabe des Servers hängt davon ab, woher die Sammlung kommt (genannt → nur
    diese; die konfigurierte Skills-Sammlung → mit ihren Skillsets). Ein festes
    ``False`` hob sie auf, und die Skillsets fielen aus jeder Suche.
    """
    query: str = ""
    collectionId: str = ""
    discipline: str = ""
    educationalContext: str = ""
    includeSubcollections: bool | None = None
    maxResults: int = Field(default=10, ge=1, le=25)
    outputFormat: Literal["markdown", "json"] = "markdown"


class SkillGetArgs(BaseModel):
    """Arguments for get_skill (D1) — die Anleitung zu einer nodeId laden.

    ``includeFiles`` steht auf dem Server-Standard ``True``: die Begleitdateien
    kommen als blosse Liste (Name + nodeId, kein Inhalt) und kosten einen
    Aufruf. Ohne sie wüsste das Modell nicht, dass es zu einer Anleitung eine
    Vorlage gibt.
    """
    nodeId: str
    includeFiles: bool = True


class UrlTextArgs(BaseModel):
    """Arguments for get_url_text (H5) — the text behind an arbitrary web URL.

    The server declares this tool **unsafe**: it hands a caller-supplied URL to
    an extraction service that fetches it in its own process, so a redirect
    after the server's own check is invisible there. Two consequences we honour
    here rather than discover at runtime:

    * ``url`` carries the server's 2000-character limit. Note what that does and
      does not do: string bounds are NOT repaired (see the module note — only
      ``ge``/``le`` are), so an over-long value is logged and then forwarded
      unchanged for the server to reject. Truncating a URL would produce a
      *different* address, which is worse than a rejection. The bound documents
      the limit and makes the case visible in the log; it does not cap.
    * ``method`` has exactly two values. On ``extraction_failed`` the other one
      is the one sensible retry (protected pages, crawl blocks, pure media) —
      the tool description tells the model so.

    Operators can switch the tool off entirely (``WLO_DISABLE_UNSAFE_TOOLS``),
    and it needs ``WLO_TEXT_EXTRACTION_URL``. Both show up as a refusal with a
    ``reason``, not as an exception.
    """
    url: str = Field(max_length=2000)
    method: Literal["browser", "simple"] = "browser"
    #: KEIN Default (2026-08-21): ein Feld-Default reist bei JEDEM Aufruf mit
    #: — unser altes ``8000`` kappte damit jede fremde Seite, ohne dass es
    #: jemand sah (Befund der Plugin-Entwickler: 59 398 Zeichen Wikipedia
    #: kamen als 8000 an). Ohne Angabe schickt der Client nichts, dann gilt die
    #: Server-Vorgabe 200000 = ganzer Text. ``le`` ist die Server-Obergrenze,
    #: keine eigene Politik: eine kleinere Kopie hier veraltet still, sobald
    #: der Server sie anhebt.
    maxChars: int | None = Field(default=None, ge=500, le=200000)


class WikipediaSummaryArgs(BaseModel):
    """Arguments for get_wikipedia_summary (H5).

    The deterministic caller (``services/wikipedia_service``) has used this tool
    since P4-5; H5 additionally offers it to the model, for the two cases the
    use-case list names: checking a generated text against an outside source,
    and clearing up a term before searching.
    """
    query: str


class AuthStatusArgs(BaseModel):
    """Arguments for wlo_auth_status (H5) — none; the server takes an empty object.

    Kept as an explicit empty model rather than left out: ``validate_tool_args``
    passes raw arguments through when no model is registered, so without one an
    invented argument would reach the server.

    ``extra="ignore"`` (the pydantic default, stated here because it is the whole
    point of the class) DROPS such an argument: validation succeeds and the export
    is ``{}``. ``extra="forbid"`` was measured to do the opposite — it raises,
    ``validate_tool_args`` cannot repair a non-bound error, and the fail-open path
    then forwards the raw arguments including the invented one (R5, 2026-08-11).
    """
    model_config = ConfigDict(extra="ignore")


class SkillRegistryArgs(BaseModel):
    """Arguments for get_skill_registry (H9) — which skills a COLLECTION approves.

    The other direction from ``search_skill``: not "which skills exist in the
    repository" but "which are approved for this one collection". The server
    registers it unconditionally and needs no configuration — a collection
    without a registry simply says so, which is why this works before a single
    skill exists.

    ``max_length`` mirrors the server's bound and is not enforced here — same
    reason as ``UrlTextArgs.url``.

    ``outputFormat`` wie bei :class:`CollectionStatsArgs` (2026-08-14). Die
    Vorgabe bleibt bewusst ``markdown``: der Agent-Vorabruf (P4) legt diese
    Antwort dem Modell vor, und dort ist der Registry-Text mit den
    Verwendungshinweisen der Redaktion mehr wert als ein JSON-Baum. Nur wer
    zählen will — ``context_facts`` — verlangt JSON.

    ``context`` (Server 2026-08-18): eine Überschrift des Registry-Dokuments —
    dann kommt nur dieser Arbeitszusammenhang zurück. Gemessen am deployten
    Server: 28 Skills/~14 KB ohne, 1 Skill/~2 KB mit ``context``. Ein Name, der
    nicht trifft, liefert den vollen Katalog samt der vorhandenen Namen — nie
    einen Fehler. Leer = alles (der Export-Filter strippt leere Strings).
    Nutzungsregel (Nutzer-Entscheid 2026-08-20): nur auf ausdrücklichen
    Wunsch verengen (Nutzer oder Einbettung) — Vorgabe ist der volle Katalog.
    """
    collectionId: str = Field(max_length=64)
    context: str = Field(default="", max_length=120)
    #: Paket M4 (MCP-Stand 2026-11-07): die anstehende Aufgabe — der Server wählt den passenden
    #: Skill und liefert dessen Anleitung gleich mit (``task.match = found``).
    task: str = Field(default="", max_length=300)
    outputFormat: Literal["markdown", "json"] = "markdown"

    @model_validator(mode="before")
    @classmethod
    def _aufgabe_kuerzen(cls, data):
        # Review M4, Befund 15: Freitext — gekürzt statt den ganzen Aufruf zu verlieren.
        if isinstance(data, dict) and isinstance(data.get("task"), str):
            data = {**data, "task": data["task"].strip()[:300]}
        return data
