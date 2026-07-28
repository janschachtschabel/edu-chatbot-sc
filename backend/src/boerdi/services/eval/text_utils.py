"""Shared eval text/marker helpers (port of ALT ``eval_text_utils.py``).

Persona markers are read from the persona definitions at call time (ALT Welle E,
2026-05-25): the ``## Positiv-Marker`` section of each persona MD feeds both the
classifier prompt and this module, so a marker the classifier is told about is
understood identically by the scenario generator and the drift telemetry. The
loader's own cache makes repeated calls effectively free.

Scope note: ALT's ``_detect_register`` and ``_repo_host`` are NOT here. They are
used only by the deterministic golden checks, which in NEU live in the
framework-free ``evals/run_golden.py`` (``detect_register``/``repo_host``);
duplicating them would create two copies of one rule.
"""

from __future__ import annotations

from boerdi.services.config_loader import load_persona_definitions


def _normalize_marker(s: str) -> str:
    """Lowercase + fold umlauts so that „fuer" and „für" both match."""
    if not s:
        return ""
    out = s.lower()
    for src, dst in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        out = out.replace(src, dst)
    return out


def _load_persona_markers() -> dict[str, list[str]]:
    """Persona-id → normalized markers, built from the persona definitions."""
    result: dict[str, list[str]] = {}
    for p in load_persona_definitions():
        pid = p.get("id", "")
        if not pid:
            continue
        hints = p.get("hints") or []
        result[pid] = [n for n in (_normalize_marker(h) for h in hints if h) if n]
    return result


def _has_persona_marker(text: str, persona_id: str) -> bool:
    """Deterministic check: does the user text carry a persona anchor?

    Flags LLM-generated scenarios that drifted to generic phrasing (telemetry
    since ALT 2026-05-23, not a filter). True if at least one marker of the
    expected persona is present (accent-folded substring), OR — for P-AND, which
    owns no markers — if no *other* persona's marker leaked in.

    An unknown persona or an empty marker list is permissive: a missing marker
    list is a config gap, and reporting it as drift would be a false signal.
    """
    markers_map = _load_persona_markers()
    t = _normalize_marker(text)
    if persona_id == "P-AND":
        for other_id, markers in markers_map.items():
            if other_id == "P-AND":
                continue
            if any(m in t for m in markers):
                return False
        return True
    markers = markers_map.get(persona_id, [])
    if not markers:
        return True
    return any(m in t for m in markers)


def _strip_id(decorated: str) -> str:
    """``"M03 (Schritt-für-Schritt)"`` → ``"M03"``.

    Debug strings are formatted ``"ID (Label)"``; confusion matrices need only
    the ID component.
    """
    if not decorated:
        return ""
    s = str(decorated).strip()
    return s.split(" ", 1)[0] if " " in s else s
