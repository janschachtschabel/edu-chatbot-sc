"""Deterministische UX-Hinweise aus MCP-``_queryMeta`` (Port von ALT ``chat_facets``).

Zwei zustandslose, gut testbare Ableitungen aus den akkumulierten
``_queryMeta``-Blöcken einer Such-Runde — beide OHNE LLM:

- :func:`narrowing_quick_replies_from_metas` — aus ``_queryMeta.facets``
  (``includeFacets``) klickbare „Nur <Typ> (N)"-Eingrenzungen bauen.
- :func:`unresolved_filter_note` — aus ``_queryMeta.unresolvedFilters`` einen
  kurzen Hinweis bauen, wenn der MCP einen angefragten Filter nicht auflösen
  konnte und ihn still verworfen hat.

Verbatim-Port: ALT hatte keine ``app.``-Importe (nur ``typing``). **C1-f2b6a hat
diese Byte-Gleichheit beendet** — beide Ausgaben folgen jetzt der Widget-Sprache
(``lang``); der deutsche Wortlaut ist unverändert und in
``tests/test_facets.py`` gepinnt. Home = ``domain/`` (framework-frei, kein
Config/DB/LLM). Der ``persist``-Node konsumiert beide und reicht die Sprache
durch.
"""

from __future__ import annotations

from typing import Any

from boerdi.i18n import DEFAULT, Locale, bot_text


def narrowing_quick_replies_from_metas(
    metas: list[dict[str, Any]] | None,
    *,
    dimension: str = "learningResourceType",
    max_options: int = 3,
    min_count: int = 1,
    lang: Locale = DEFAULT,
) -> list[str]:
    """Baut Eingrenzungs-Quick-Replies (z.B. ``['Nur Video (1203)', …]``) aus den
    akkumulierten ``_queryMeta``-Facetten einer Such-Runde.

    - ``dimension``: welche Facette (Default ``learningResourceType`` = Medientyp,
      die natürlichste Eingrenzung im Chat).
    - Gibt eine **leere** Liste zurück, wenn es nichts zu verengen gibt (weniger
      als 2 sinnvolle Buckets) — dann bietet der Bot keine Eingrenzung an.
    """
    # Reichste Bucket-Liste über alle Metas nehmen (mehrere Sub-Suchen möglich).
    best: list[dict[str, Any]] = []
    for m in metas or []:
        buckets = ((m or {}).get("facets") or {}).get(dimension) or []
        if isinstance(buckets, list) and len(buckets) > len(best):
            best = buckets

    meaningful = [
        b for b in best
        if isinstance(b, dict)
        and int(b.get("count") or 0) >= min_count
        and str(b.get("label") or "").strip()
    ]
    # Mit nur einem Typ gibt es nichts einzugrenzen.
    if len(meaningful) < 2:
        return []

    top = sorted(meaningful, key=lambda b: int(b.get("count") or 0), reverse=True)[:max_options]
    # Das Label ist WLO-Vokabular („Video", „Arbeitsblatt") und bleibt, wie der
    # MCP es liefert — übersetzt wird nur das Wort, das wir davorsetzen.
    return [
        bot_text(lang, "facets.narrowChip",
                 label=b["label"], count=int(b["count"]))
        for b in top
    ]


def unresolved_filter_note(
    metas: list[dict[str, Any]] | None,
    *,
    max_shown: int = 2,
    lang: Locale = DEFAULT,
) -> str:
    """Kurzer, ehrlicher Hinweis, wenn der MCP einen angefragten Vokabular-Filter
    NICHT auf eine URI auflösen konnte und ihn deshalb still verworfen hat
    (``_queryMeta.unresolvedFilters`` = ``[{field, value}]``).

    Leerer String, wenn alles auflöste — dann gibt es nichts zu melden. Werte
    werden dedupliziert (``search_wlo_all`` emittiert sie in content- UND
    collections-Meta) und auf ``max_shown`` gekürzt.
    """
    seen: dict[str, str] = {}
    for m in metas or []:
        for uf in ((m or {}).get("unresolvedFilters") or []):
            if not isinstance(uf, dict):
                continue
            value = str(uf.get("value") or "").strip()
            if value and value not in seen:
                seen[value] = str(uf.get("field") or "").strip()
    if not seen:
        return ""
    quoted = ", ".join(
        bot_text(lang, "facets.quotedValue", value=v)
        for v in list(seen.keys())[:max_shown]
    )
    return bot_text(lang, "facets.unresolvedFilter", values=quoted)
