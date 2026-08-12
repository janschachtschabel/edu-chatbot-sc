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

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
        # Drop fields the real MCP schema doesn't know
        data.pop("license", None)
        data.pop("skipCount", None)
        return data


class CollectionContentsArgs(BaseModel):
    """Arguments for get_collection_contents.

    Matches MCP schema: nodeId, query, contentFilter, includeSubcollections,
    maxResults, skipCount. Legacy name maxItems accepted via pre-validator.
    """
    nodeId: str
    query: str = ""
    contentFilter: str = ""  # "files" | "folders" | "both"
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
    depth: int = Field(default=1, ge=1, le=2)
    includeContentCounts: bool = False
    maxResults: int = Field(default=50, ge=1, le=100)


class HealthCheckArgs(BaseModel):
    """Arguments for wlo_health_check."""
    pass


class NodesDetailsArgs(BaseModel):
    """Arguments for get_nodes_details (bulk metadata)."""
    nodeIds: list[str]


class CollectionStatsArgs(BaseModel):
    """Arguments for get_collection_stats (W9a).

    Server schema (fetched 2026-08-01): ``nodeId`` required, nothing else the
    model needs to steer. The breakdown counts up to 100 direct child files —
    a sample, not the whole subtree; the server's own output says so.
    """
    nodeId: str


class NodeBreadcrumbArgs(BaseModel):
    """Arguments for get_node_breadcrumb (W9a).

    Collection nodes only — file nodes (``ccm:io``) return an empty path.
    """
    nodeId: str


class CompendiumTextArgs(BaseModel):
    """Arguments for get_compendium_text (W9a).

    The server also accepts ``nodeIds`` for a bulk fetch. We deliberately
    expose only the single-node form: the export filter in
    ``validate_tool_args`` strips empty *strings* only, so an unused list would
    travel as ``nodeIds: []``. One compendium per call costs a round trip and
    saves a special case.
    """
    nodeId: str


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
    """
    nodeId: str
    query: str = ""
    educationalContext: str = ""
    discipline: str = ""
    userRole: str = ""
    learningResourceType: str = ""
    publisher: str = ""
    maxResults: int = Field(default=10, ge=1, le=20)

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
    """
    vocabulary: str

    @model_validator(mode="before")
    @classmethod
    def _accept_legacy_field(cls, data):
        if isinstance(data, dict) and "vocabulary" not in data and "field" in data:
            data = {**data, "vocabulary": data["field"]}
        return data


class SkillSearchArgs(BaseModel):
    """Arguments for search_skill (D1) — redaktionell gepflegte Anleitungen finden.

    Grenzen aus dem Live-Schema des Servers geholt (``tools/list`` am
    2026-08-10), nicht geraten. Ohne Argumente listet der Server den ganzen
    Katalog auf — deshalb ist nichts Pflicht.

    ``outputFormat`` fehlt bewusst: das setzt ``call_mcp_tool`` zentral
    (gleiche Begründung wie bei ``NodeCollectionsArgs``).
    """
    query: str = ""
    collectionId: str = ""
    discipline: str = ""
    educationalContext: str = ""
    includeSubcollections: bool = False
    maxResults: int = Field(default=10, ge=1, le=25)


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
    maxChars: int = Field(default=8000, ge=500, le=50000)


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
    """
    collectionId: str = Field(max_length=64)
