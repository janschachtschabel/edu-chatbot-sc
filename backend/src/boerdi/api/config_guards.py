"""Checks a generic config write runs before anything is stored.

Split out of ``api/config.py`` (Paket 4, D3): the endpoints stay there, the
rules a document and its key must satisfy live here — shared by the Studio's
write paths (``config.py``) and the restore paths (``config_snapshots.py``).
Also the answer to a write that lost the race (409, Paket 4 D5).
"""

import re
from datetime import UTC
from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError

from boerdi.api.deps import request_locale
from boerdi.domain.config_models.patterns import ist_reservierte_kennung
from boerdi.i18n import Locale, msg
from boerdi.services import config_loader as cl
from boerdi.services.config_conflict import BereichNichtSpeicherbar, ConfigConflict
from boerdi.services.config_loader.mcp import _PRIMARY_ID
from boerdi.services.url_safety import UnsafeUrlError, assert_public_url

#: The area the MCP registry is stored in. Named here because three endpoints
#: can write it and only one of them is *about* MCP.
_MCP_AREA = "05-knowledge/mcp-servers"
#: One area per pattern below this prefix (``03-patterns/<name>``).
_PATTERN_PREFIX = "03-patterns/"
#: The guide rules: their ``message_rules`` patterns must compile (Paket 4, D6).
_GUIDE_RULES_AREA = "02-domain/guide-rules"


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
    """Per-area document checks the GENERIC write paths must not skip.

    ``PUT /config/data/{area}`` and ``PUT /config/file`` accept any area, so
    without this the guard on ``PUT /mcp-servers`` was only a guard against
    using that one endpoint — the studio's schema form and its raw-text tab
    reach the same document and neither is about MCP. Found while building the
    9-4 "Wissen" view; pinned by the two ``*_rejects_internal_url`` tests.

    Since review 2026-10-03 also the reserved pattern id ``AGENT``: the model
    rejects it on a typed write only, and the loader drops such a pattern
    silently — a write that reports "saved" must not end there. The restore
    paths (``config_snapshots``) run this check as well.

    Since Paket 4 (D6) also the guide rules' patterns: an invalid regular
    expression was stored and then skipped only at runtime.
    """
    if key == _MCP_AREA and isinstance(data, dict):
        _assert_servers_public(data.get("servers"), lang)
    if key.startswith(_PATTERN_PREFIX) and isinstance(data, dict):
        frontmatter = data.get("frontmatter")
        kennung = frontmatter.get("id") if isinstance(frontmatter, dict) else None
        if ist_reservierte_kennung(kennung):
            raise HTTPException(
                400, msg(lang, "patterns.idReserved", value=repr(str(kennung).strip()))
            )
    if key == _GUIDE_RULES_AREA and isinstance(data, dict):
        _assert_guide_patterns_compile(data.get("message_rules"), lang)


def _assert_guide_patterns_compile(rules: object, lang: Locale) -> None:
    """Every guide-rule pattern must compile — as the injector compiles it
    (stripped, case-insensitive). The 400 names the rule by position and label."""
    for nr, rule in enumerate(rules if isinstance(rules, list) else [], start=1):
        if not isinstance(rule, dict):
            continue
        pattern = str(rule.get("pattern") or "").strip()
        if not pattern:
            continue  # the loader drops a rule without a pattern
        try:
            re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            raise HTTPException(400, msg(
                lang, "guide.patternInvalid", nr=nr, label=rule.get("label") or "?", error=e,
            )) from e


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

    one_leaf = _single_group_leaf(key)
    if one_leaf is not None:
        return one_leaf
    return key in AREA_MODELS


def _single_group_leaf(key: str) -> bool | None:
    """Is ``key`` exactly one document below a grouped area? ``None`` when the
    key belongs to no group; the bare group key is no document, nor is a ``.``
    leaf (the form path took ``03-patterns/.``, the restore refused it)."""
    for group in _GROUPED_AREAS:
        if key == group:
            return False
        if key.startswith(f"{group}/"):
            leaf = key[len(group) + 1:]
            return bool(leaf) and "/" not in leaf and leaf not in (".", "..")
    return None


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


def is_restorable_area_key(key: str) -> bool:
    """May a restore write ``key``? The path rule of the raw file write
    (``PUT /config/file``), not the model allow-list of a typed write.

    Audit 2026-09-29, A-M7: ``../…`` from a crafted ZIP must not land in the
    store, ``export_tree`` would write it outside its folder. The model list is
    too narrow for a restore (review 2026-10-03): areas without a model exist —
    ``01-base/rag-retrieval`` is read but not registered — and must come back.

    Since Paket 4 (D3, external audit F07) also no ``.`` segment — it stored
    the same document under a second name — and below ``03-patterns/`` and
    ``04-personas/`` exactly one leaf, by the rule of ``_is_file_key``.
    """
    try:
        if cl._validate_config_path(key) != key:
            return False
    except ValueError:
        return False
    segments = key.split("/")
    if not all(segments) or "." in segments:
        return False
    return _single_group_leaf(key) is not False


def modell_fehler(key: str, data: object) -> list[dict[str, Any]]:
    """What the area model objects to in ``data`` — empty when nothing does or
    the area has no model (those pass, as on a restore).

    Validation is a gate, not a transform: callers store the raw document, never
    the model dump. Hand-built entries: pydantic's own carry ``input`` and
    ``url``, and the input is the submitted config content — no need to echo it
    back. ``ctx`` (the bound, the expected values) lets the Studio say
    „Mindestens 70" at the field (ST-2e) — plain values only.
    """
    from boerdi.domain.config_models import model_for

    model = model_for(key)
    if model is None:
        return []
    try:
        model.model_validate(data)
    except ValidationError as e:
        return [
            {"loc": list(err["loc"]), "msg": err["msg"], "type": err["type"],
             **_plain_ctx(err)}
            for err in e.errors()
        ]
    return []


def _plain_ctx(err: Any) -> dict[str, Any]:
    """``ctx`` of a validation error with plain values only (ST-2e).

    A ``value_error`` carries the raised exception there — neither JSON nor
    anything the Studio should show. Empty result: no ``ctx`` key at all.
    """
    ctx = {k: v for k, v in (err.get("ctx") or {}).items()
           if isinstance(v, (bool, int, float, str))}
    return {"ctx": ctx} if ctx else {}


async def nicht_speicherbar_antwort(request: Request, exc: Exception) -> JSONResponse:
    """400 for a value Postgres refuses to store (Paket 4b, A4).

    One handler for every config write — restore, seed apply, form and raw
    text. Before, such a write ended as a 500 without naming the area.

    The failed transaction writes nothing, but it is not always the whole
    request (review 4b): restore and seed apply write every area in one
    transaction, the ALT bulk routes (personas, patterns, tone modifiers) one
    per area, so earlier areas stay saved. The message says which case it is.
    """
    fehler = exc if isinstance(exc, BereichNichtSpeicherbar) else BereichNichtSpeicherbar("?")
    key = "config.notStorableAll" if fehler.ganzer_vorgang else "config.notStorable"
    text = msg(request_locale(request), key, area=fehler.area)
    return JSONResponse(status_code=400, content={"detail": text})


def konflikt_antwort(e: ConfigConflict, lang: Locale, *, anlegen: bool = False) -> HTTPException:
    """409 for a conditional write that found another state (Paket 4, D5).

    ``detail`` is an object: ``message`` for any client, and ``version``,
    ``updated_by``, ``updated_at`` (ISO, UTC) for the Studio, which names who
    changed what and when in the editor's own language.
    """
    cur = e.current or {}
    version = cur.get("version")
    updated_by = cur.get("updated_by")
    when = cur.get("updated_at")
    if anlegen and e.current is not None:
        text = msg(lang, "config.exists", area=e.area)
    elif e.current is None:
        text = msg(lang, "config.conflictGone")
    else:
        text = msg(lang, "config.conflict", version=version, who=updated_by or "?",
                   when=when.astimezone(UTC).strftime("%Y-%m-%d %H:%M") if when else "?")
    stamp = when.astimezone(UTC).isoformat() if when else None
    return HTTPException(status_code=409, detail={
        "message": text, "version": version, "updated_by": updated_by, "updated_at": stamp,
    })
