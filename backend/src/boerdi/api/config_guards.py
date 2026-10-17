"""Checks a generic config write runs before anything is stored.

Split out of ``api/config.py`` (Paket 4, D3): the endpoints stay there, the
rules a document and its key must satisfy live here — shared by the Studio's
write paths (``config.py``) and the restore paths (``config_snapshots.py``).
The answers to a write that failed (400 not storable, 409 conflict) moved to
``api/config_antworten.py`` (Paket 6).
"""

import logging
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, ValidationError

from boerdi.domain import regel_regex
from boerdi.domain.config_models.patterns import ist_reservierte_kennung
from boerdi.i18n import Locale, msg
from boerdi.services import config_loader as cl
from boerdi.services.config_loader.mcp import _PRIMARY_ID
from boerdi.services.url_safety import UnsafeUrlError, assert_public_url

logger = logging.getLogger(__name__)

#: The area the MCP registry is stored in. Named here because three endpoints
#: can write it and only one of them is *about* MCP.
_MCP_AREA = "05-knowledge/mcp-servers"
#: One area per pattern below this prefix (``03-patterns/<name>``).
_PATTERN_PREFIX = "03-patterns/"
#: The guide rules: their ``message_rules`` patterns must compile (Paket 4, D6).
_GUIDE_RULES_AREA = "02-domain/guide-rules"
#: The policy rules: their ``match.message_regex`` must compile (Paket 6, B1).
_POLICY_AREA = "01-base/policy"


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
            raise HTTPException(400, msg(lang, "mcp.serverRejected", id=srv.get("id") or "?",
                                         error=url_einwand(e, lang))) from e


def url_einwand(fehler: UnsafeUrlError, lang: Locale) -> str:
    """Warum eine Adresse abgewiesen wurde — in der Sprache des Studios statt im
    englischen Text des Wächters (Paket 9)."""
    if fehler.grund == "unbekannt":
        return msg(lang, "url.unknownHost", detail=fehler.host)
    return msg(lang, "url.notAllowed")


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
    expression was stored and then skipped only at runtime. Since Paket 6 (B1)
    the policy rules' ``message_regex`` as well, both with the engine the
    runtime uses (``domain/regel_regex``).
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
    if key == _POLICY_AREA and isinstance(data, dict):
        _assert_policy_patterns_compile(data.get("rules"), lang)


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
            regel_regex.uebersetze(pattern)
        except regel_regex.RegexFehler as e:
            raise HTTPException(400, msg(
                lang, "guide.patternInvalid", nr=nr, label=rule.get("label") or "?", error=e,
            )) from e


def _assert_policy_patterns_compile(rules: object, lang: Locale) -> None:
    """Every policy ``match.message_regex`` must compile — as ``assess_policy``
    compiles it (case-sensitive on the lowered message). Before, an invalid one
    was stored and the rule then silently never matched."""
    for nr, rule in enumerate(rules if isinstance(rules, list) else [], start=1):
        match = rule.get("match") if isinstance(rule, dict) else None
        pattern = match.get("message_regex") if isinstance(match, dict) else None
        if not pattern:
            continue
        # Kein Text (``2024``, eine Liste): die Laufzeit wirft daran einen
        # TypeError, nicht ``RegexFehler`` (Review Paket 6) — darum hier ab.
        if not isinstance(pattern, str):
            raise HTTPException(400, msg(
                lang, "policy.regexInvalid", nr=nr, id=rule.get("id") or "?",
                error=type(pattern).__name__,
            ))
        try:
            regel_regex.uebersetze(pattern, ignore_case=False)
        except regel_regex.RegexFehler as e:
            raise HTTPException(400, msg(
                lang, "policy.regexInvalid", nr=nr, id=rule.get("id") or "?", error=e,
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
    a hand-written one from the raw editor, say — and must come back.

    Since Paket 4 (D3, external audit F07) also no ``.`` segment — it stored
    the same document under a second name — and below ``03-patterns/`` and
    ``04-personas/`` exactly one leaf, by the rule of ``_is_file_key``. Since
    Paket 9 no retired area either: an old backup brought them back.
    """
    from boerdi.domain.config_models import GESTRICHENE_BEREICHE

    if key in GESTRICHENE_BEREICHE:
        return False
    try:
        if cl._validate_config_path(key) != key:
            return False
    except ValueError:
        return False
    segments = key.split("/")
    if not all(segments) or "." in segments:
        return False
    return _single_group_leaf(key) is not False


def pruefe_bereiche(areas: dict[str, dict], lang: Locale) -> dict[str, dict]:
    """Die Prüfung vor einem Schreiben vieler Bereiche — Wiederherstellen und
    Auslieferungsstand (Paket 6, W2) — über ALLE Bereiche, bevor etwas
    geschrieben wird. Gibt die schreibbaren Bereiche zurück.

    Drei Prüfungen: Schlüssel müssen gültige Bereichspfade sein (Audit
    2026-09-29, A-M7; andere werden mit Warnung übersprungen); Dokumente
    bestehen die Ausgangsprüfungen eines Studio-Schreibens
    (``_assert_area_document_safe``, Review 2026-10-03; ein Fehler antwortet
    400); und jeder Bereich mit Modell besteht es (Paket 4, D3; eine 422 mit
    allen Einwänden, jeder mit ``area``).
    """
    gueltig: dict[str, dict] = {}
    einwaende: list[dict] = []
    for key, data in areas.items():
        if not is_restorable_area_key(key):
            logger.warning("skipping %r, not a valid config area path", key)
            continue
        _assert_area_document_safe(key, data, lang)
        einwaende += [{"area": key, **f} for f in modell_fehler(key, data)]
        gueltig[key] = data
    if einwaende:
        raise HTTPException(status_code=422, detail=einwaende)
    return gueltig


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
