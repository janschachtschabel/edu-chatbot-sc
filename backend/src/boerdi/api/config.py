"""Generic config file CRUD + JSON-schema export + MCP registry read +
public guide-mode bundle (P2). Typed area editors live in config_areas.py
and config_elements.py; snapshots/backup in config_snapshots.py.

DB areas replace files (V2): the ``path`` parameter stays the area key
(with a ``.yaml``/``.md`` suffix for compatibility). GET /schema/{area}
is new (V3, JSON schema per area for the generic formly renderer).
"""

from urllib.parse import urlparse

import yaml
from fastapi import APIRouter, HTTPException, Security
from pydantic import BaseModel, ValidationError

from boerdi.api.deps import Lang, require_studio_key
from boerdi.api.schemas import ConfigFile
from boerdi.i18n import Locale, msg
from boerdi.services import config_loader as cl
from boerdi.services import seed_io
from boerdi.services.config_loader.mcp import _PRIMARY_ID
from boerdi.services.mcp import tool_descriptions, transport
from boerdi.services.url_safety import UnsafeUrlError, assert_public_url
from boerdi.settings import get_settings

router = APIRouter(
    prefix="/api/config", tags=["config"],
    dependencies=[Security(require_studio_key)],
)
public_router = APIRouter(prefix="/api/config", tags=["config"])


# ── generic area CRUD (ALT: file-based; NEU: DB areas, key = path sans ext) ──
@router.get("/files")
async def list_config_files() -> list[dict]:
    return cl.list_config_files()


@router.get("/file")
async def get_config_file(path: str) -> dict:
    try:
        cl._validate_config_path(path)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid path") from None
    if not cl.area_exists(cl._strip_ext(path)):
        raise HTTPException(status_code=404, detail="File not found")
    return {"path": path, "content": cl.read_config_file(path)}


@router.put("/file")
async def update_config_file(file: ConfigFile, lang: Lang) -> dict:
    """Persist raw file text.

    Malformed YAML is the caller's mistake, not a server fault: ``safe_load``
    raises ``yaml.YAMLError`` (a subclass of neither ``ValueError`` nor
    anything else caught here), so before 9-3 a typo in the studio's raw editor
    produced a 500 with a stack trace instead of a message the editor could
    act on. The parser's own message names the line and column.
    """
    try:
        cl._validate_config_path(file.path)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid path") from None
    key = cl._strip_ext(file.path)
    if key == _MCP_AREA:
        # Parsed here rather than after the write, because the check has to
        # happen BEFORE anything is persisted. Only this one area pays for it.
        try:
            parsed = yaml.safe_load(file.content) or {}
        except yaml.YAMLError as e:
            raise HTTPException(400, msg(lang, "file.unreadable", error=e)) from e
        _assert_area_document_safe(key, parsed, lang)
    try:
        await cl.write_config_file(file.path, file.content)
    except (yaml.YAMLError, ValueError) as e:
        raise HTTPException(400, msg(lang, "file.unreadable", error=e)) from e
    return {"status": "saved", "path": file.path}


@router.delete("/file")
async def delete_config_file(path: str) -> dict:
    try:
        cl._validate_config_path(path)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid path") from None
    if not await cl.delete_area(cl._strip_ext(path)):
        raise HTTPException(status_code=404, detail="File not found")
    return {"status": "deleted", "path": path}


# ── MCP registry (GET list + PUT replace + POST discover). GET enriches each
# enabled server with a tool_descriptions map (5-min TTL cache, A7 "don't cache
# errors"); the fetch + cache live in services/mcp/tool_descriptions.py — spec §4
# keeps the network I/O out of the router.
@router.get("/mcp-servers")
async def get_mcp_servers() -> list[dict]:
    return await tool_descriptions.load_mcp_servers_with_descriptions()


class AreaData(BaseModel):
    data: dict


class McpServerUpdate(BaseModel):
    servers: list[dict]


#: The area the MCP registry is stored in. Named here because three endpoints
#: can write it and only one of them is *about* MCP.
_MCP_AREA = "05-knowledge/mcp-servers"


def _assert_servers_public(servers: object, lang: Locale) -> None:
    """Reject a registry that would point the backend at an internal address.

    Stored SSRF (ALT audit T8): the backend POSTs to every enabled server on
    each chat turn, so one accepted ``http://169.254.169.254`` fires once per
    conversation.

    The primary (``wlo-mcp``) is exempt: its URL comes from ``MCP_SERVER_URL``
    and may deliberately point inside the network — ``save_mcp_servers`` strips
    it before writing regardless.
    """
    for srv in servers if isinstance(servers, list) else []:
        if not isinstance(srv, dict) or srv.get("id") == _PRIMARY_ID:
            continue
        srv_url = (srv.get("url") or "").strip()
        if not srv_url:
            continue
        try:
            assert_public_url(srv_url)
        except UnsafeUrlError as e:
            raise HTTPException(
                400, msg(lang, "mcp.serverRejected", id=srv.get("id") or "?", error=e)
            ) from e


def _assert_area_document_safe(key: str, data: object, lang: Locale) -> None:
    """Per-area egress checks the GENERIC write paths must not skip.

    ``PUT /config/data/{area}`` and ``PUT /config/file`` accept any area, so
    without this the guard on ``PUT /mcp-servers`` was only a guard against
    using that one endpoint — the studio's schema form and its raw-text tab
    reach the same document and neither is about MCP. Found while building the
    9-4 "Wissen" view; pinned by the two ``*_rejects_internal_url`` tests.
    """
    if key == _MCP_AREA and isinstance(data, dict):
        _assert_servers_public(data.get("servers"), lang)


@router.put("/mcp-servers")
async def update_mcp_servers(data: McpServerUpdate, lang: Lang) -> dict:
    """Replace the MCP server registry.

    Every non-primary URL is SSRF-checked before anything is persisted (ALT audit
    T8, stored SSRF): the backend POSTs to each enabled server on every chat turn,
    so an internal URL accepted here would fire once per conversation.

    The primary (``wlo-mcp``) is exempt: its URL comes from ``MCP_SERVER_URL`` and
    may deliberately point inside the network, and ``save_mcp_servers`` strips it
    before writing regardless.
    """
    _assert_servers_public(data.servers, lang)
    await cl.save_mcp_servers(data.servers)
    return {"status": "saved", "count": len(data.servers)}


@router.post("/mcp-servers/discover")
async def discover_mcp_tools(lang: Lang, url: str = "") -> dict:
    """Handshake an MCP server once and list its tools, without registering it.

    The SSRF guard sits in *front* of the egress, not behind a stored value like
    the PUT above: this endpoint dials whatever URL it is handed, so an internal
    URL must be rejected before the handshake fires rather than before a later
    write (ALT audit T8/T9). A transport failure is a 502 — the server is
    reachable-or-not from here, it is not the caller's bad request.
    """
    if not url:
        raise HTTPException(status_code=400, detail=msg(lang, "mcp.urlRequired"))
    try:
        assert_public_url(url)
    except UnsafeUrlError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    try:
        tools = await transport.discover_server_tools(url)
        return {"url": url, "tools": tools}
    except Exception as e:
        raise HTTPException(502, msg(lang, "mcp.connectFailed", error=e)) from e


# backup / restore + snapshots + factory live in config_snapshots.py (P2-7).


# ── NEW (V3): JSON schema + JSON data per area, for the generic studio form ──
#: The two areas whose model covers a whole DIRECTORY of files. They are legal
#: as a schema target (one model describes every file) but never as a document
#: key — no row is stored under them.
_GROUPED_AREAS = ("03-patterns", "04-personas")


def _is_file_key(key: str) -> bool:
    """Does this key address exactly one stored document?

    ``model_for`` answers for *any* ``03-patterns/…`` key, so on its own it
    accepts ``03-patterns/``, ``03-patterns/a/b/c`` and the bare group key —
    each of which would create a junk row that then shows up in the area list
    and, for a `03-patterns/`-shaped one, in pattern classification.
    """
    from boerdi.domain.config_models import AREA_MODELS

    for group in _GROUPED_AREAS:
        if key.startswith(f"{group}/"):
            leaf = key[len(group) + 1:]
            return bool(leaf) and "/" not in leaf
    return key in AREA_MODELS and key not in _GROUPED_AREAS


def _resolve_area(area: str, *, file_key: bool = False) -> tuple[str, type[BaseModel]]:
    """Area key -> (validated key, area model), or the matching HTTP error.

    ``model_for`` is an allow-list and would be guard enough on its own, except
    for the two grouped prefixes: it answers for *any* ``03-patterns/…`` key,
    so ``03-patterns/../../evil`` would pass and create a junk row.

    ``file_key=True`` additionally demands a key that addresses one document —
    required for reading and writing, not for the schema, which is per model.
    """
    from boerdi.domain.config_models import model_for

    try:
        key = cl._validate_config_path(area)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid path") from None
    model = model_for(key)
    if model is None or (file_key and not _is_file_key(key)):
        raise HTTPException(status_code=404, detail=f"unknown config area: {area}")
    return key, model


@router.get("/schema/{area:path}")
async def get_area_schema(area: str) -> dict:
    """JSON schema of the area's pydantic model (P2-6) — grouped file keys
    (03-patterns/*, 04-personas/*) resolve to their group model."""
    return _resolve_area(area)[1].model_json_schema()


@router.get("/data/{area:path}")
async def get_area_data(area: str) -> dict:
    """The area's stored document as JSON — the counterpart /schema needs.

    ``/config/file`` returns YAML *text*, which a form cannot bind to. An area
    that has a model but no row yields ``{}`` rather than 404: the schema is
    there, so the form renders defaults and the first save creates it.

    ``type`` says which file the raw editor must ask for, served from the same
    ``seed_io.is_md_area`` predicate ``read_config_file`` uses to decide how to
    serialize. The studio therefore never guesses it from the document shape,
    and the two sides cannot disagree about a document.
    """
    key, _ = _resolve_area(area, file_key=True)
    data = cl.area(key)
    return {"area": key, "data": data, "type": "md" if seed_io.is_md_area(data) else "yaml"}


@router.put("/data/{area:path}")
async def update_area_data(area: str, payload: AreaData, lang: Lang) -> dict:
    """Replace the area's document (9-3a). ``data`` is the WHOLE document.

    GET/PUT are a read-modify-write pair, and that is deliberate. The area
    models pin only part of the tree — measured against the ALT config, 357
    data paths sit below or beside a pinned key without being pinned
    themselves (``01-base/policy`` -> ``rules[*].effect.disclaimer``,
    ``01-base/classify-overrides`` -> ``pattern_disambiguators_legacy[*]``).
    A schema-driven form therefore edits a *copy of the whole document* and
    submits it whole; the unpinned parts ride along untouched.

    Merging server-side was the other candidate and is worse: a deep merge
    cannot express deletion (dropping a list entry or a whole section would be
    impossible), and a shallow one would only have protected the top level —
    which is not where the unpinned keys are. Replace also matches every typed
    area endpoint, so the store has one write semantic, not two.

    Validation is a gate, not a transform: the submitted *raw* dict is
    persisted, never the model dump — dumping would inject defaults for every
    absent optional field and rewrite the document the editor saw.
    """
    key, model = _resolve_area(area, file_key=True)
    _assert_area_document_safe(key, payload.data, lang)
    try:
        model.model_validate(payload.data)
    except ValidationError as e:
        # Hand-built detail: pydantic's own carries `input` and `url`, and the
        # input is the submitted config content — no need to echo it back.
        raise HTTPException(status_code=422, detail=[
            {"loc": list(err["loc"]), "msg": err["msg"], "type": err["type"]}
            for err in e.errors()
        ]) from e
    await cl.write_area(key, payload.data, updated_by="studio-form")
    return {"status": "saved", "area": key, "data": payload.data}


def _mcp_auth_base() -> str:
    """Herkunft des MCP-Servers für die Anmeldung im Browser (C5-c2).

    Nur ``scheme://host[:port]``. Der Werkzeug-Pfad (``/mcp``) gehört nicht
    dazu: die Entdeckungs-Dokumente liegen unter ``/.well-known/…`` an der
    Wurzel. Und nur die Herkunft — der Rest der Server-Registrierung ist
    Betriebswissen und hat in einem öffentlichen Bündel nichts verloren.

    Leer bei fehlender oder unbrauchbarer Angabe; das Widget liest das als
    „diese Anlage bietet keine Anmeldung an" und bietet den Chip nicht an.
    """
    roh = (get_settings().mcp_server_url or "").strip()
    if not roh:
        return ""
    teile = urlparse(roh)
    if teile.scheme not in ("http", "https") or not teile.netloc:
        return ""
    return f"{teile.scheme}://{teile.netloc}"


# ── public: widget boot bundle (trusted_domains + header_nav + welcome) ────
@public_router.get("/guide-mode")
async def get_guide_mode() -> dict:
    """Widget boot request (P2-8) — shape identical to ALT config_areas.py:
    guide-mode config + header_nav buttons + welcome, one round-trip."""
    cfg = cl.load_guide_mode_config()
    cfg["header_nav"] = cl.load_header_nav_config().get("buttons", [])
    cfg["welcome"] = cl.load_welcome_config()
    # C5-c2: neues Feld, KEIN Vertragsbruch — die Rückgabe ist ``dict``, im
    # Dokument also ein offenes Objekt. Eine eigene Route wäre einer gewesen.
    cfg["mcp_auth_base"] = _mcp_auth_base()
    return cfg
