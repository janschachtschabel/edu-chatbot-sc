"""C4a: widget bundle delivery — the public route a host page embeds.

The router is PUBLIC (``main.py`` mounts it without an auth dependency): the
bundle must load from a foreign host page without a key.

Boundary = the filesystem. Every test points ``WIDGET_DIST_DIR`` at a tmp_path
and writes exactly the files it needs, so each existence branch is visible in
the test rather than depending on whether someone ran ``npm run build:widget``.
"""

from __future__ import annotations

import json
import re
from html import unescape

import pytest
from fastapi.testclient import TestClient

from boerdi.api import widget_demo_controls
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
    [
        ("a.css", "text/css"),
        ("a.map", "application/json"),
        ("a.js", "javascript"),
        # C5-c1: die OAuth-Rückruf-Seite reist als Datei im Bündel und wird
        # über genau diesen Sammelpfad ausgeliefert — deshalb KEINE neue Route
        # und damit kein neuer Pfad im eingefrorenen Vertrag. Als HTML muss sie
        # ankommen, sonst zeigt der Browser Quelltext statt sie auszuführen.
        # ``.html`` steht bewusst NICHT in ``_MEDIA_TYPES``: gemessen 2026-08-10
        # war dieser Fall ohne jede Codeänderung grün, weil ``FileResponse`` bei
        # ``media_type=None`` aus dem Dateinamen rät. Der Eintrag wäre ein
        # Zusatz ohne Wirkung; dieser Wächter hält die Verlässlichkeit fest.
        ("oauth-callback.html", "text/html"),
    ],
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

DEMOS = ["/widget/", "/widget/inline", "/widget/classic", "/widget/frameless"]

#: Die Seiten, die das Element wirklich zeigen. ``/widget/`` gehört seit der
#: Umwidmung (2026-08-13) NICHT dazu: es ist die Übersicht und trägt bewusst
#: kein Widget. Vorher war es die dritte Seite mit demselben schwebenden Knopf —
#: genau das las sich für den Nutzer als „alle machen dasselbe".
LIVE_DEMOS = ["/widget/inline", "/widget/classic", "/widget/frameless"]

#: Exactly what the widget dispatches — `host-events.ts` and `chat-shell`.
#: New `boerdi:` prefix since U5a (2026-08-09). The widget additionally fires
#: each event under its old `badboerdi:` name during the P11 transition; the
#: demo inspector deliberately does NOT listen to those (it would show every
#: event twice), which is what the strict comparison below pins.
WIDGET_EVENTS = [
    "boerdi:guide-suggestion",
    "boerdi:routing-debug",
    "boerdi:query-meta",
    "boerdi:page-action",
]


@pytest.mark.parametrize("path", LIVE_DEMOS)
def test_demo_pages_embed_the_element_through_the_stable_path(client, path):
    r = client.get(path)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert "<boerdi-chat" in r.text
    # The stable path, never the hashed one: a demo page must exercise exactly
    # what a host page does, redirect included.
    assert 'src="/widget/boerdi-widget.js"' in r.text


def test_the_index_shows_no_widget_and_loads_no_bundle(client):
    # Die Übersicht ist ein Verzeichnis, kein vierter Einbau. Lüde sie das
    # Bundle ohne Element, zahlte jeder Besuch 400 kB für nichts.
    body = client.get("/widget/").text
    assert not _ELEMENT_TAG.search(body)
    assert '<script src="/widget/boerdi-widget.js"' not in body
    # Das Einbau-Schnipsel steht sehr wohl da — maskiert, als Text zum Kopieren.
    assert "&lt;boerdi-chat" in body


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


#: Das Start-Tag des ECHTEN Elements. ``_element()`` schreibt es immer
#: mehrzeilig (eine Zeile je Attribut), und daran hängt dieser Ausdruck.
#:
#: Die naive Fassung — auf ``<boerdi-chat`` teilen — war erst grün und dann
#: falsch: das Bedienpult trägt in einem JS-Kommentar den Text
#: ``` `<boerdi-chat>` ``` (die Erklärung, warum das Pult ÜBER dem Element
#: steht). Der stand früher im Dokument, also traf der Split ihn, lieferte einen
#: leeren Tag — und jede Zusicherung „Attribut X steht NICHT im Tag" war
#: geschenkt.
_ELEMENT_TAG = re.compile(r"<boerdi-chat\n[^>]*>")


def _element_tag(body: str) -> str:
    """Das ``<boerdi-chat …>``-Start-Tag der Seite, ohne den Rest."""
    treffer = _ELEMENT_TAG.search(body)
    assert treffer, "kein <boerdi-chat>-Element auf der Seite"
    return treffer.group(0)


@pytest.mark.parametrize("path", LIVE_DEMOS)
def test_a_hostile_query_value_cannot_break_out_of_the_element_attribute(client, path):
    """Die zweite Verteidigungslinie, geprüft dort, wo sie liegt.

    Die Erlaubnisliste in ``widget_demo_context`` ist die erste — aber `search`
    lässt bewusst 2–200 BELIEBIGE Zeichen durch (ein Suchbegriff der Gastseite
    ist Fliesstext), also ist dies der Wert, der wirklich mit Anführungszeichen
    im Attribut landet. Maskiert wird seit 2026-08-13 in
    ``widget_demo_html._element``, für JEDEN Wert; deshalb steht die Zusicherung
    hier an der gerenderten Seite und nicht mehr am Modul, das den Kontext baut.

    Geprüft wird beides: dass nichts ausbricht UND dass der Wert unverändert
    ankommt — eine Maskierung, die den Suchbegriff verstümmelt, wäre sicher und
    trotzdem falsch.

    Nicht geprüft wird „die Zeichenkette ``onerror`` kommt nirgends vor": sie
    steht sehr wohl im Tag, als Teil des Suchbegriffs zwischen zwei ``&quot;``,
    und dort ist sie Text. Diese erste Fassung war rot bei richtigem Code.
    """
    boese = '" onerror="alert(1)'
    body = client.get(path, params={"kontext": "search", "wert": boese}).text
    tag = _element_tag(body)
    treffer = re.search(r'page-context="([^"]*)"', tag)
    assert treffer, tag
    # Der Angriff muss VOLLSTÄNDIG in dem einen Attribut stecken. Bleibt draussen
    # etwas von ihm übrig, hat sein Anführungszeichen das Attribut vorzeitig
    # beendet — und ab da liest der Browser Markup statt Daten.
    assert "onerror" not in tag.replace(treffer.group(0), "")
    assert json.loads(unescape(treffer.group(1)))["search_query"] == boese


def test_the_three_live_demos_differ_in_their_embed_situation(client):
    """Der Befund des Nutzers, als Test: „sehen alle gleich aus".

    Er hatte recht — vor dem 2026-08-13 setzten `/widget/`, `/inline` und
    `/classic` alle `position="bottom-right"` OHNE `embed-mode`, also dreimal
    denselben schwebenden Knopf; getrennt hat sie nur, was ohnehin im
    Bedienpult jeder Seite steht. Diese Zusicherung ist deshalb keine Kosmetik,
    sondern die einzige Stelle, an der „drei Seiten, drei Einbau-Lagen"
    überhaupt geprüft wird.

    Verglichen wird das Attribut-Paar, das die Lage AUSMACHT (`embed-mode` +
    `initial-state`), nicht der ganze Seitentext: der unterschiede sich schon
    durch die Überschrift, und der Test wäre grün ohne etwas zu wissen.
    """
    lagen = {}
    for path in LIVE_DEMOS:
        tag = _element_tag(client.get(path).text)
        lagen[path] = (
            "frameless" if 'embed-mode="frameless"' in tag else "panel",
            "expanded" if 'initial-state="expanded"' in tag else "collapsed",
        )
    assert len(set(lagen.values())) == len(LIVE_DEMOS), lagen


def test_classic_is_the_floating_bubble_that_opens_on_click(client):
    # Die Vorgabe-Einbettung: Eulen-Knopf unten rechts, geschlossen. Kein
    # `embed-mode` (dann gilt `panel`) und kein `initial-state` (dann gilt
    # `collapsed`) — beides negativ geprüft, weil die vier Seiten EINE
    # Schablone teilen und ein verirrter Vorgabewert dort alle zugleich träfe.
    tag = _element_tag(client.get("/widget/classic").text)
    assert 'position="bottom-right"' in tag
    assert "embed-mode" not in tag
    assert "initial-state" not in tag


def test_inline_starts_as_an_embedded_open_chat(client):
    # Der Befund „die inline Demo sollte auch mit einem eingebetteten Chatbot
    # starten": eingebettet heisst `embed-mode="frameless"` IM Container der
    # Seite, und „startet" heisst offen — sonst stünde dort ein leerer Kasten.
    body = client.get("/widget/inline").text
    tag = _element_tag(body)
    assert 'embed-mode="frameless"' in tag
    assert 'initial-state="expanded"' in tag
    assert "<boerdi-chat" in body.split('<div class="frame">')[1].split("</div>")[0]


@pytest.mark.parametrize("path", ["/widget/inline", "/widget/frameless"])
def test_a_frameless_embed_gets_a_sized_container(client, path):
    # Frameless means the element fills its container instead of floating at a
    # size of its own. Embedded bare into the page flow it would therefore
    # render at zero height — visible as nothing at all, with no error. The
    # container and its height are the page, not decoration.
    body = client.get(path).text
    frame = body.split('<div class="frame">')[1].split("</div>")[0]
    assert "<boerdi-chat" in frame
    rule = re.search(r"\.frame\s*\{([^}]*)\}", body)
    assert rule and "block-size" in rule.group(1), rule


def test_no_live_demo_hides_the_grouping_boxes_by_default(client):
    # `/classic` trug bis 2026-08-13 `inline-result-grouping="false"` und war
    # damit ein A/B über ein ANZEIGE-Attribut — während der Nutzer unter
    # „klassisch" die schwebende Blase verstand. Der A/B ist nicht verloren: er
    # ist ein Schalter im Bedienpult JEDER Seite. Genau deshalb kostete das
    # Umwidmen nichts, und genau das prüft diese Zeile.
    for path in LIVE_DEMOS:
        assert 'inline-result-grouping="false"' not in _element_tag(client.get(path).text)
    assert any(
        c.attr == "inline-result-grouping" for c in widget_demo_controls.CONTROLS
    )


@pytest.mark.parametrize("path", DEMOS)
def test_every_demo_page_links_to_every_variant(client, path):
    # The nav is shared, so a new page is only reachable if it is listed there —
    # otherwise it exists but nobody finds it.
    body = client.get(path).text
    for target in DEMOS:
        assert f'href="{target}"' in body, f"{target} fehlt in der Navigation von {path}"


@pytest.mark.parametrize("path", LIVE_DEMOS)
def test_the_event_inspector_listens_to_exactly_what_the_widget_emits(client, path):
    body = client.get(path).text
    for event in WIDGET_EVENTS:
        assert event in body, f"{event} fehlt auf {path}"
    # Nothing else: a panel for an event that is never dispatched reads as a
    # broken widget, not as an unused feature.
    import re as _re

    # The lookbehind keeps a leftover `badboerdi:` OUT of the match — without
    # it a stale legacy listener would pass as if it were one of the new names.
    listed = set(_re.findall(r"(?<!bad)boerdi:[a-z-]+", body))
    assert listed == set(WIDGET_EVENTS), listed


def test_a_demo_route_wins_over_a_file_of_the_same_name(client, dist):
    # ALT's documented trap: declared after the catch-all, `/widget/inline`
    # would look for a file called `inline` in the dist directory.
    (dist / "inline").write_text("not the page", encoding="utf-8")
    r = client.get("/widget/inline")
    assert r.headers["content-type"].startswith("text/html")
    assert "not the page" not in r.text


# ── U8: das Bedienpult der Demo-Seiten ───────────────────────────────────


@pytest.mark.parametrize("path", LIVE_DEMOS)
def test_every_demo_page_carries_the_control_panel(client, path):
    # Vor U8 zeigte jede Seite EINE feste Attribut-Kombination — zusammen acht
    # der 23 Host-Attribute. Wer `show-cards="never"` sehen wollte, musste sich
    # eine eigene HTML-Datei schreiben; „geht nicht" las sich dann wie ein
    # Defekt, wo nur kein Weg da war, es zu sehen.
    body = client.get(path).text
    assert 'id="pult-gitter"' in body
    erwartet = {c.attr for c in widget_demo_controls.CONTROLS}
    # Beide rahmenlosen Seiten haben keinen Eulen-Knopf — ein Schalter für
    # dessen Ecke wäre dort eine Lüge.
    if path in ("/widget/frameless", "/widget/inline"):
        erwartet -= {"position"}
    assert set(re.findall(r'data-attr="([a-z-]+)"', body)) == erwartet


def test_the_panel_preselects_what_the_page_itself_set(client):
    # Sonst zeigte das Pult auf der eingebetteten Seite „Debug-Knopf: Standard",
    # obwohl er dort aus ist — und der erste Klick wäre eine Korrektur einer
    # Anzeige, die nie stimmte. Deshalb speist EINE Quelle Element und Pult.
    body = client.get("/widget/inline").text
    feld = body.split('data-attr="show-debug-button"')[1].split("</select>")[0]
    assert '<option value="false" selected>' in feld


def test_only_the_two_start_only_attributes_are_marked_for_a_restart(client):
    # `size` und `initial-state` sind laut Vertrag Startwerte; ein `setAttribute`
    # darauf tut nichts. Das Pult baut dafür das Element neu auf. Die Markierung
    # ist die einzige Stelle, an der diese Vertragszusage im Backend steht —
    # gerät sie an ein Attribut, das live wirkt, verliert der Nutzer bei jedem
    # Umschalten grundlos das Panel.
    body = client.get("/widget/classic").text
    mit_neustart = re.findall(r'data-attr="([a-z-]+)" data-restart="true"', body)
    assert set(mit_neustart) == {"size", "initial-state"}


@pytest.mark.parametrize("path", LIVE_DEMOS)
def test_page_scheme_and_widget_theme_are_two_separate_switches(client, path):
    # Der Kern von U4a: bei `theme="auto"` folgt das Widget dem `color-scheme`
    # der Gastseite, bei `light`/`dark` nicht mehr. Mit nur einem Schalter liesse
    # sich dieser Unterschied auf keiner Demo-Seite zeigen.
    body = client.get(path).text
    assert 'id="pult-seite"' in body
    assert 'data-attr="theme"' in body


def test_no_control_promises_an_attribute_the_element_does_not_have():
    # Der lebende Vertrag steht im Studio (`widget-contract-data.ts`) und wird
    # dort von einem Frontend-Test gegen das Element festgenagelt. Diese kleine
    # Liste hier ist die zweite Kopie — genau die Sorte, von der dieses Projekt
    # schon zweimal eine driften sah. Also gegenlesen statt hoffen.
    from pathlib import Path

    vertrag = (
        Path(__file__).resolve().parents[2]
        / "frontend/projects/studio/src/app/views/widget-contract-data.ts"
    )
    if not vertrag.exists():  # Backend-Image ohne Frontend-Quellen
        pytest.skip(f"Vertragsdatei nicht da: {vertrag}")
    bekannt = set(re.findall(r"attr: '([a-z-]+)'", vertrag.read_text(encoding="utf-8")))
    unbekannt = {c.attr for c in widget_demo_controls.CONTROLS} - bekannt
    assert not unbekannt, f"kein Host-Attribut: {sorted(unbekannt)}"
