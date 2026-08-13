"""Store binding + generic area file-API (P2-3, port of ALT _core.py).

The ALT loaders are SYNC (chat hot path). Here they read the ConfigStore's
process cache (preloaded at startup, refreshed via NOTIFY) through
``area()`` — a pure dict lookup. The bound store is a per-process infra
singleton (like the OTel provider); its DATA is cluster-synchronized.

Deliberate deviation from ALT: the write path (``write_config_file``) is
ASYNC because it persists to Postgres. ALT's mtime semantics map to
version/NOTIFY; ``invalidate_yaml_cache`` clears the process cache.
"""

from __future__ import annotations

import logging
from typing import Any

from boerdi.services import seed_io
from boerdi.services.config_store import ConfigStore

logger = logging.getLogger(__name__)

_store: ConfigStore | None = None


def bind_store(store: ConfigStore | None) -> None:
    """Bind the process ConfigStore (app lifespan / tests; None unbinds)."""
    global _store
    _store = store


def area(key: str) -> dict[str, Any]:
    """Cached area data — ``{}`` when unbound/missing (ALT `_load_yaml` default).

    **Nur lesen.** Zurück kommt das Objekt AUS DEM CACHE, kein Klon — und alle
    Lader dieser Fassade reichen Teile davon unverändert weiter
    (``load_intents()`` ist ``area(...)["intents"]``). Wer hineinschreibt,
    ändert den Bereich für den ganzen Prozess: das Studio zeigt den Zusatz dann
    als unbekannten Schlüssel an, und ein Speichern schreibt ihn fest
    (Befund 2026-08-13, ``config_elements``). Wer etwas anhängen will, kopiert:
    ``[{**e, "extra": …} for e in load_…()]``.
    """
    if _store is None:
        return {}
    return _store.get_cached(key) or {}


def cached_keys(prefix: str = "") -> list[str]:
    if _store is None:
        return []
    return sorted(k for k in _store.cached_areas() if k.startswith(prefix))


def area_exists(key: str) -> bool:
    return _store is not None and key in _store.cached_areas()


async def write_area(area_key: str, data: dict[str, Any], updated_by: str = "studio") -> int:
    """Persist a config area as a dict (typed-endpoint write path, P2-5).
    Counterpart to write_config_file, which takes raw file TEXT."""
    if _store is None:
        raise RuntimeError("config store not bound")
    return await _store.put(area_key, data, updated_by=updated_by)


async def delete_area(area_key: str) -> bool:
    if _store is None:
        raise RuntimeError("config store not bound")
    return await _store.delete(area_key)


def store_engine():
    """The bound store's async engine (snapshots-table SQL, P2-7)."""
    if _store is None:
        raise RuntimeError("config store not bound")
    return _store.engine


def current_config() -> dict[str, dict[str, Any]]:
    """All loaded config areas as {key: data} — the snapshot/backup source."""
    return {key: area(key) for key in cached_keys()}


def invalidate_yaml_cache(rel_path: str | None = None) -> None:
    """ALT-compatible cache drop (None = everything)."""
    if _store is not None:
        _store.clear_cache(_strip_ext(rel_path) if rel_path else None)


def _strip_ext(rel_path: str) -> str:
    for ext in (".yaml", ".yml", ".md"):
        if rel_path.endswith(ext):
            return rel_path[: -len(ext)]
    return rel_path


def _validate_config_path(rel_path: str) -> str:
    """Path-traversal guard (ALT contract: raises ValueError)."""
    p = rel_path.replace("\\", "/")
    if p.startswith("/") or ".." in p.split("/") or ":" in p:
        raise ValueError(f"invalid config path: {rel_path!r}")
    return p


def read_config_file(rel_path: str) -> str:
    """Serialize an area back to file text — ``""`` when missing (ALT)."""
    key = _strip_ext(_validate_config_path(rel_path))
    data = area(key)
    if not data:
        return ""
    if seed_io.is_md_area(data):
        return seed_io.join_frontmatter(data["frontmatter"], data["body"])
    import yaml as _yaml

    return _yaml.safe_dump(data, allow_unicode=True, sort_keys=False)


async def write_config_file(rel_path: str, content: str) -> None:
    """Parse + persist raw file text as an area (ASYNC — DB write)."""
    key = _strip_ext(_validate_config_path(rel_path))
    if _store is None:
        raise RuntimeError("config store not bound")
    if rel_path.endswith(".md") or seed_io.is_md_area(area(key)):
        frontmatter, body = seed_io.split_frontmatter(content)
        data: dict[str, Any] = {
            "frontmatter": seed_io.normalize_json_keys(frontmatter),
            "body": body,
        }
    else:
        import yaml as _yaml

        parsed = _yaml.safe_load(content) or {}
        if not isinstance(parsed, dict):
            raise ValueError("YAML root must be a mapping")
        data = seed_io.normalize_json_keys(parsed)
    await _store.put(key, data, updated_by="config-file-api")


def list_config_files() -> list[dict[str, str]]:
    """ALT shape: {path, full_path, name, type} per area (from cache)."""
    out: list[dict[str, str]] = []
    for key in cached_keys():
        data = area(key)
        ext = "md" if seed_io.is_md_area(data) else "yaml"
        path = f"{key}.{ext}"
        out.append({
            "path": path,
            "full_path": path,  # no filesystem in NEU — key IS the address
            "name": path.rsplit("/", 1)[-1],
            "type": ext,
        })
    return out
