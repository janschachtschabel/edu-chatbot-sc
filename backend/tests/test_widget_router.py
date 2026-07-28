"""C4a: widget bundle delivery — the public route a host page embeds.

The router is PUBLIC (``main.py`` mounts it without an auth dependency): the
bundle must load from a foreign host page without a key.

Boundary = the filesystem. Every test points ``WIDGET_DIST_DIR`` at a tmp_path
and writes exactly the files it needs, so each existence branch is visible in
the test rather than depending on whether someone ran ``npm run build:widget``.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from boerdi.main import create_app
from boerdi.settings import get_settings

STABLE = "/widget/boerdi-widget.js"


@pytest.fixture()
def dist(tmp_path, monkeypatch):
    """An (empty) widget dist directory the app will serve from."""
    monkeypatch.setenv("WIDGET_DIST_DIR", str(tmp_path))
    get_settings.cache_clear()
    return tmp_path


@pytest.fixture()
def client(dist):
    return TestClient(create_app())


def _bundle(dist, body: str = "// bundle") -> None:
    (dist / "main.js").write_text(body, encoding="utf-8")


# ── GET /widget/boerdi-widget.js — the stable path ───────────────────────


def test_stable_path_503_when_the_bundle_was_never_built(client):
    # 503, not 404: the route exists and the deploy is incomplete. The detail
    # names the command, because "not found" sends people looking for a typo.
    r = client.get(STABLE)
    assert r.status_code == 503
    assert "build:widget" in r.json()["detail"]


def test_stable_path_503_when_the_directory_exists_but_the_bundle_does_not(client, dist):
    (dist / "styles.css").write_text("body{}", encoding="utf-8")
    assert client.get(STABLE).status_code == 503


def test_stable_path_redirects_to_the_hashed_url(client, dist):
    _bundle(dist)
    r = client.get(STABLE, follow_redirects=False)
    assert r.status_code == 302
    location = r.headers["location"]
    assert location.startswith("/widget/boerdi-widget.")
    assert location.endswith(".js")
    # The pointer itself must never be cached, or a deploy would keep handing
    # out the previous bundle's URL for as long as the redirect lives.
    assert r.headers["cache-control"] == "no-store, must-revalidate"
    assert r.headers["access-control-allow-origin"] == "*"


def test_the_hashed_url_changes_when_the_bundle_changes(client, dist):
    _bundle(dist, "// one")
    first = client.get(STABLE, follow_redirects=False).headers["location"]
    _bundle(dist, "// two — a different build")
    second = client.get(STABLE, follow_redirects=False).headers["location"]
    assert first != second


def test_the_hashed_url_is_stable_for_unchanged_content(client, dist):
    _bundle(dist)
    a = client.get(STABLE, follow_redirects=False).headers["location"]
    b = client.get(STABLE, follow_redirects=False).headers["location"]
    assert a == b


def test_following_the_redirect_serves_the_bundle_immutably(client, dist):
    _bundle(dist, "// the real bundle")
    r = client.get(STABLE)  # follows the redirect
    assert r.status_code == 200
    assert r.text == "// the real bundle"
    assert "javascript" in r.headers["content-type"]
    # This is the point of V1: a year of no revalidation, safe because the URL
    # carries the content hash.
    assert "immutable" in r.headers["cache-control"]
    assert "max-age=31536000" in r.headers["cache-control"]
    assert r.headers["access-control-allow-origin"] == "*"


# ── GET /widget/{asset_name} — auxiliary files ───────────────────────────


def test_plain_asset_is_served_but_not_immutable(client, dist):
    # An unhashed name says nothing about its content, so it must be
    # revalidated — only the hashed URL earns `immutable`.
    (dist / "extra.js").write_text("// chunk", encoding="utf-8")
    r = client.get("/widget/extra.js")
    assert r.status_code == 200
    assert "javascript" in r.headers["content-type"]
    assert r.headers["cache-control"] == "no-store, must-revalidate"


@pytest.mark.parametrize(
    ("name", "expected"),
    [("a.css", "text/css"), ("a.map", "application/json"), ("a.js", "javascript")],
)
def test_asset_media_types(client, dist, name, expected):
    (dist / name).write_text("x", encoding="utf-8")
    r = client.get(f"/widget/{name}")
    # The status assertion is not decoration: an error response is JSON too, so
    # without it the `.map` case would pass against a 501 stub.
    assert r.status_code == 200
    assert expected in r.headers["content-type"]


def test_missing_asset_404_names_it(client, dist):
    r = client.get("/widget/chunk-404.js")
    assert r.status_code == 404
    assert "chunk-404.js" in r.json()["detail"]


def test_a_directory_is_404_not_a_listing(client, dist):
    (dist / "assets").mkdir()
    assert client.get("/widget/assets").status_code == 404


# ── The path guard, tested directly ─────────────────────────────────────
#
# At the HTTP layer a traversal never even reaches the handler — the client
# normalises `..` away and the router does not match a name containing `/`.
# The guard is therefore tested where it runs, the way ALT tested it: a future
# caller that passes an unchecked name must still be refused.


def test_guard_refuses_parent_traversal_before_looking_the_file_up(dist):
    # 400 rather than 404 on purpose: answering "not found" for a path outside
    # the directory would turn the endpoint into an existence oracle for the
    # host filesystem. The guard runs first, so both cases look the same.
    from fastapi import HTTPException

    from boerdi.api import widget

    with pytest.raises(HTTPException) as exc:
        widget._resolve("../does-not-exist-anywhere.js")
    assert exc.value.status_code == 400
    assert exc.value.detail == "invalid path"


def test_guard_refuses_an_absolute_path(dist, tmp_path):
    # pathlib: `base / "<absolute path>"` replaces the base entirely, so the
    # join alone is no protection — only the relative_to check is.
    from fastapi import HTTPException

    from boerdi.api import widget

    outside = tmp_path.parent / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    with pytest.raises(HTTPException) as exc:
        widget._resolve(str(outside))
    assert exc.value.status_code == 400


# ── The three demo pages (C4b) ──────────────────────────────────────────
#
# They are demo *pages*, not a copy of ALT's 942-line integration guide: its
# attribute table lists 17 of the 18 host attributes (measured — the missing one
# is `inline-result-grouping`, the very attribute 8-7 found dead), and the studio
# already documents the full contract from a source a test pins. A third,
# untested copy in a Python string is what this project keeps finding drifted.

DEMOS = ["/widget/", "/widget/inline", "/widget/classic"]

#: Exactly what the widget dispatches — `host-events.ts` and `chat-shell`.
WIDGET_EVENTS = [
    "badboerdi:guide-suggestion",
    "badboerdi:routing-debug",
    "badboerdi:query-meta",
    "badboerdi:page-action",
]


@pytest.mark.parametrize("path", DEMOS)
def test_demo_pages_embed_the_element_through_the_stable_path(client, path):
    r = client.get(path)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert "<boerdi-chat" in r.text
    # The stable path, never the hashed one: a demo page must exercise exactly
    # what a host page does, redirect included.
    assert 'src="/widget/boerdi-widget.js"' in r.text


@pytest.mark.parametrize("path", DEMOS)
def test_demo_pages_never_reference_the_missing_static_mount(client, path):
    # ALT's pages loaded a logo from /api/static/boerdi.svg. That mount does not
    # exist here and nothing needs it, so referencing it would be a guaranteed
    # 404 in every demo.
    r = client.get(path)
    assert r.status_code == 200  # or the negative assertion holds for free
    assert "/api/static" not in r.text


def test_the_embed_demo_hides_the_two_operator_buttons(client):
    # What actually distinguishes ALT's inline demo: language + debug buttons off.
    body = client.get("/widget/inline").text
    assert 'show-language-buttons="false"' in body
    assert 'show-debug-button="false"' in body


def test_classic_is_the_real_a_b_against_inline(client):
    # ALT could no longer show this: it had forced `inline-result-grouping` to
    # true and its /classic page was /inline plus a banner saying so. Here the
    # attribute is live (the 18th, restored in 8-7), so the page can be what it
    # claims — the same embed with the grouping boxes off.
    classic = client.get("/widget/classic").text
    inline = client.get("/widget/inline").text
    assert 'inline-result-grouping="false"' in classic
    assert 'inline-result-grouping="false"' not in inline


@pytest.mark.parametrize("path", DEMOS)
def test_the_event_inspector_listens_to_exactly_what_the_widget_emits(client, path):
    body = client.get(path).text
    for event in WIDGET_EVENTS:
        assert event in body, f"{event} fehlt auf {path}"
    # Nothing else: a panel for an event that is never dispatched reads as a
    # broken widget, not as an unused feature.
    import re as _re

    listed = set(_re.findall(r"badboerdi:[a-z-]+", body))
    assert listed == set(WIDGET_EVENTS), listed


def test_a_demo_route_wins_over_a_file_of_the_same_name(client, dist):
    # ALT's documented trap: declared after the catch-all, `/widget/inline`
    # would look for a file called `inline` in the dist directory.
    (dist / "inline").write_text("not the page", encoding="utf-8")
    r = client.get("/widget/inline")
    assert r.headers["content-type"].startswith("text/html")
    assert "not the page" not in r.text
