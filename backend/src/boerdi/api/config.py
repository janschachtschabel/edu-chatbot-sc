"""Generic config file CRUD + JSON-schema export + MCP registry read +
public guide-mode bundle (P2). Typed area editors live in config_areas.py
and config_elements.py; snapshots/backup in config_snapshots.py.

DB areas replace files (V2): the ``path`` parameter stays the area key
(with a ``.yaml``/``.md`` suffix for compatibility). GET /schema/{area}
is new (V3, JSON schema per area for the generic formly renderer).
"""

import asyncio

import yaml
from fastapi import APIRouter, HTTPException, Request, Response, Security
from pydantic import BaseModel

from boerdi.api.config_antworten import konflikt_antwort
from boerdi.api.config_documents import pruefe_kennung
from boerdi.api.config_guards import (
    _MCP_AREA,
    _assert_area_document_safe,
    _assert_servers_public,
    _resolve_area,
    is_restorable_area_key,
    modell_fehler,
    url_einwand,
)
from boerdi.api.deps import Lang, require_studio_key
from boerdi.api.schemas import ConfigFile
from boerdi.domain.anmelde_herkunft import anmeldung_erlaubt
from boerdi.domain.mcp_herkunft import mcp_herkunft
from boerdi.i18n import msg
from boerdi.services import config_loader as cl
from boerdi.services import seed_io
from boerdi.services.config_conflict import ConfigConflict
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
    """Raw file text plus its ``version`` — read from the database, so the
    version the raw editor saves against is the stored one (Paket 4, D5)."""
    try:
        key = cl._strip_ext(cl._validate_config_path(path))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid path") from None
    row = await cl.read_area(key)
    if row is None:
        raise HTTPException(status_code=404, detail="File not found")
    data, version = row
    return {"path": path, "content": cl.serialize_area(data), "version": version}


@router.put("/file")
async def update_config_file(file: ConfigFile, lang: Lang) -> dict:
    """Persist raw file text.

    Malformed YAML is the caller's mistake, not a server fault: ``safe_load``
    raises ``yaml.YAMLError`` (a subclass of neither ``ValueError`` nor
    anything else caught here), so before 9-3 a typo in the studio's raw editor
    produced a 500 with a stack trace instead of a message the editor could
    act on. The parser's own message names the line and column.

    The text is parsed BEFORE anything is persisted, so the document checks
    (MCP egress, reserved pattern id) and the model gate see exactly what would
    be stored. Since Paket 4 (D3, external audit F07) that gate is the one the
    form tab passes too (422), and the key follows the restore rule — one leaf
    per pattern or persona, no ``.`` segment.

    ``expected_version`` / ``create`` make the write conditional (D5): 409
    instead of overwriting a save made since the editor loaded the text.
    """
    try:
        key = cl._strip_ext(cl._validate_config_path(file.path))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid path") from None
    if not is_restorable_area_key(key):
        raise HTTPException(status_code=400, detail="Invalid path")
    try:
        key, data = cl.parse_config_file(file.path, file.content)
    except (yaml.YAMLError, ValueError) as e:
        raise HTTPException(400, msg(lang, "file.unreadable", error=e)) from e
    _assert_area_document_safe(key, data, lang)
    fehler = modell_fehler(key, data)
    if fehler:
        raise HTTPException(status_code=422, detail=fehler)
    await pruefe_kennung(key, data, lang)  # Paket 6, S1: eine Kennung je Ordner
    # Parses the same text the same way again — the request body cannot change
    # in between, so the stored document is the one just checked.
    try:
        version = await cl.write_config_file(
            file.path, file.content,
            expected_version=file.expected_version, create_only=file.create)
    except ConfigConflict as e:
        raise konflikt_antwort(e, lang, anlegen=file.create) from e
    return {"status": "saved", "path": file.path, "version": version}


# ── MCP registry (GET list + PUT replace + POST discover). GET enriches each
# enabled server with a tool_descriptions map (5-min TTL cache, A7 "don't cache
# errors"); the fetch + cache live in services/mcp/tool_descriptions.py — spec §4
# keeps the network I/O out of the router.
@router.get("/mcp-servers")
async def get_mcp_servers(response: Response) -> list[dict]:
    """The registry. Its version rides in ``X-Config-Version`` (Paket 4, D5):
    the body is a list, and the Studio saves against that version. The fresh
    read also refreshes the cache the list is built from."""
    row = await cl.read_area(_MCP_AREA)
    if row is not None:
        response.headers["X-Config-Version"] = str(row[1])
    return await tool_descriptions.load_mcp_servers_with_descriptions()


class AreaData(BaseModel):
    data: dict
    # Paket 4, D5 — both optional; see ``ConfigFile``.
    expected_version: int | None = None
    create: bool = False


class McpServerUpdate(BaseModel):
    servers: list[dict]
    expected_version: int | None = None


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
    try:
        version = await cl.save_mcp_servers(data.servers, expected_version=data.expected_version)
    except ConfigConflict as e:
        raise konflikt_antwort(e, lang) from e
    return {"status": "saved", "count": len(data.servers), "version": version}


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
        # Im Thread (Paket 4, C5): ``getaddrinfo`` blockierte sonst den
        # Event-Loop samt allen Chat-Zügen dieses Workers.
        await asyncio.to_thread(assert_public_url, url)
    except UnsafeUrlError as e:
        raise HTTPException(status_code=400, detail=url_einwand(e, lang)) from e
    try:
        tools = await transport.discover_server_tools(url)
        return {"url": url, "tools": tools}
    except Exception as e:
        raise HTTPException(502, msg(lang, "mcp.connectFailed", error=e)) from e


# backup / restore + snapshots + factory live in config_snapshots.py (P2-7).


# ── NEW (V3): JSON schema + JSON data per area, for the generic studio form ──
# The key and document rules these endpoints apply live in config_guards.py.
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

    ``version`` is what a save names as ``expected_version`` (Paket 4, D5),
    ``None`` while no row exists — then the save names ``create``. Read from
    the database, not the cache: after a conflict, "reload" must show the
    stored state even while another replica's NOTIFY is still on its way.
    """
    key, _ = _resolve_area(area, file_key=True)
    row = await cl.read_area(key)
    data, version = row if row is not None else ({}, None)
    return {"area": key, "data": data, "version": version,
            "type": "md" if seed_io.is_md_area(data) else "yaml"}


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
    key, _ = _resolve_area(area, file_key=True)
    _assert_area_document_safe(key, payload.data, lang)
    # One gate for the form, the raw text and the restore (Paket 4, D3).
    fehler = modell_fehler(key, payload.data)
    if fehler:
        raise HTTPException(status_code=422, detail=fehler)
    await pruefe_kennung(key, payload.data, lang)  # Paket 6, S1: eine Kennung je Ordner
    try:
        version = await cl.write_area(
            key, payload.data, updated_by="studio-form",
            expected_version=payload.expected_version, create_only=payload.create)
    except ConfigConflict as e:
        raise konflikt_antwort(e, lang, anlegen=payload.create) from e
    # ``type`` as in GET (Paket 4b, A2): without it the area editor fetched a
    # Markdown area's raw text as ``.yaml`` after a form save.
    return {"status": "saved", "area": key, "data": payload.data, "version": version,
            "type": "md" if seed_io.is_md_area(payload.data) else "yaml"}


def _mcp_auth_base() -> str:
    """Herkunft des MCP-Servers für die Anmeldung im Browser (C5-c2).

    Nur ``scheme://host[:port]``. Der Werkzeug-Pfad (``/mcp``) gehört nicht
    dazu: die Entdeckungs-Dokumente liegen unter ``/.well-known/…`` an der
    Wurzel. Und nur die Herkunft — der Rest der Server-Registrierung ist
    Betriebswissen und hat in einem öffentlichen Bündel nichts verloren.

    Leer bei fehlender oder unbrauchbarer Angabe; das Widget liest das als
    „diese Anlage bietet keine Anmeldung an" und bietet den Chip nicht an.
    Dieselbe Herkunft erlaubt die CSP der Studio-Seite (``domain/mcp_herkunft``).
    """
    return mcp_herkunft(get_settings().mcp_server_url)


# ── public: widget boot bundle (trusted_domains + header_nav + welcome) ────
@public_router.get("/guide-mode")
async def get_guide_mode(request: Request) -> dict:
    """Widget boot request (P2-8) — shape identical to ALT config_areas.py:
    guide-mode config + header_nav buttons + welcome, one round-trip."""
    cfg = cl.load_guide_mode_config()
    cfg["header_nav"] = cl.load_header_nav_config().get("buttons", [])
    cfg["welcome"] = cl.load_welcome_config()
    # C5-c2: neues Feld, KEIN Vertragsbruch — die Rückgabe ist ``dict``, im
    # Dokument also ein offenes Objekt. Eine eigene Route wäre einer gewesen.
    # Nutzer-Entscheid 2026-10-15 (A-2): eine geschlossene Anlage nennt die Anmeldung nur
    # Seiten, die sie bedient — ohne Adresse bietet das Widget weder Knopf noch Ticket-Tausch an.
    s = get_settings()
    erlaubt = anmeldung_erlaubt(
        request.headers.get("origin"), allow_all=s.cors_allow_all,
        origins=s.cors_origin_list, origin_regex=s.cors_origin_regex)
    cfg["mcp_auth_base"] = _mcp_auth_base() if erlaubt else ""
    return cfg
