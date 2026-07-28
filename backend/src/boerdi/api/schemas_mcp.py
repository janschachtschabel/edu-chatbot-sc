"""MCP tool-argument models (validated before calling the MCP server) —
ported 1:1 from ALT ``app/models/schemas.py``. Part of the facade
``boerdi.api.schemas``. Canonical arg names + legacy aliases per spec §5.2.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


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
    """Arguments for browse_collection_tree."""
    nodeId: str
    depth: int = Field(default=1, ge=1, le=2)
    includeContentCounts: bool = False
    maxResults: int = Field(default=50, ge=1, le=100)


class HealthCheckArgs(BaseModel):
    """Arguments for wlo_health_check."""
    pass


class NodesDetailsArgs(BaseModel):
    """Arguments for get_nodes_details (bulk metadata)."""
    nodeIds: list[str]


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
