"""Own site or somebody else's? — the host half of page-kind detection.

The widget's URL detector (``page-context-detector.ts``) recognises pages by
path and query. Everything it cannot place lands on ``other`` — our own start
page and a random third-party page alike. That distinction is what decides
whether the bot says "you are on our start page" or offers to add the page to
WLO, so it has to be made somewhere.

It is made HERE, and against a list the editorial team maintains, because a
hostname is an operational fact: it changes when a site moves, and the widget
bundle is only rebuilt on a deploy (the most frequent deploy mistake in this
project is a stale bundle). The widget therefore sends the bare hostname and
the backend decides.

Pure: the own-host list is a parameter, not a config read — the caller
(``page_context_enrich``) owns the I/O. Matching reuses ``guide_mode``'s
host helpers rather than growing a second, subtly different host matcher.
"""

from __future__ import annotations

from collections.abc import Sequence

from boerdi.domain.guide_mode import _normalize_host, host_matches_pattern

HOME = "home"
EXTERNAL = "external"


def classify_page_host(host: str | None, own_hosts: Sequence[str]) -> str:
    """``'home'`` for one of our own sites, ``'external'`` for anything else.

    Returns ``''`` when there is nothing to decide (no host) — the caller then
    keeps whatever page kind it already had. An unmaintained (empty) list makes
    every host ``external``: claiming "this is ours" without a list would be a
    guess, and the wrong guess offers to add WLO to WLO.

    ``own_hosts`` entries are exact hostnames or ``*.example.com`` wildcards;
    ``www.``, a port and letter case are normalised away on the host side.
    """
    normalized = _normalize_host(host)
    if not normalized:
        return ""
    for pattern in own_hosts:
        if host_matches_pattern(normalized, pattern):
            return HOME
    return EXTERNAL
