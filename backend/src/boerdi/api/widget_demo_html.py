"""The four demo pages behind ``/widget/``, ``/widget/inline``,
``/widget/classic`` and ``/widget/frameless`` (C4b, fourth added in U1).

**These are demo pages, not ALT's integration guide.** ALT served 942 lines of
hand-written HTML here, most of it an attribute reference — and that reference
lists 17 of the 18 host attributes. The missing one is ``inline-result-grouping``
(measured against ``widget-contract-data.ts``), which is exactly the attribute
8-7 found dead in the shell. The studio already documents the full contract in
one place, from a source a test in the widget project pins. A third copy in a
Python string would be the one nobody checks, and this project has now found
that copy drifted twice.

So the pages do what only they can do: run the real element against the real
backend, with the attributes each variant is about, and show what it emits.

One template, four variants — ALT kept two near-identical copies plus a
``str.replace`` for the third, which is why its ``/classic`` page ended up
describing a mode it no longer had.
"""

from __future__ import annotations

from boerdi.api import widget_demo_controls

#: The four events the widget dispatches — `ui/src/host-events/host-events.ts`
#: (guide-suggestion, routing-debug) and `ui/src/shell/chat-shell.component.ts`
#: (query-meta, page-action). Listed here because the inspector below must show
#: these and only these: a panel for an event nobody fires reads as a broken
#: widget rather than an unused feature.
#:
#: Only the new `boerdi:` names (U5a, 2026-08-09). The widget also fires each
#: one under its old `badboerdi:` name while the OLD chatbot runs alongside —
#: listening to both would show every event twice and make the demo look like
#: it double-fires.
EVENTS = (
    "boerdi:guide-suggestion",
    "boerdi:routing-debug",
    "boerdi:query-meta",
    "boerdi:page-action",
)

_STYLE = """
  :root { color-scheme: light dark; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
         max-width: 60rem; margin: 2.5rem auto; padding: 0 1.25rem; line-height: 1.6; }
  h1 { color: #1c4587; font-size: 1.6rem; }
  h2 { color: #1c4587; font-size: 1.1rem; margin-block-start: 2rem; }
  code { background: #f3f4f6; padding: .1rem .35rem; border-radius: .25rem; font-size: .85em; }
  pre { background: #1f2937; color: #e5e7eb; padding: 1rem; border-radius: .5rem;
        overflow-x: auto; font-size: .8rem; }
  pre code { background: none; color: inherit; padding: 0; }
  .lead { background: #f9fafb; border: 1px solid #e5e7eb; border-radius: .75rem; padding: 1.25rem; }
  nav a { margin-inline-end: 1rem; }
  /* Width capped against the viewport: the widget's own button sits bottom-right
     and the two would overlap on a phone (seen at 460 px). */
  #ev { position: fixed; inset-block-end: 1.25rem; inset-inline-start: 1.25rem;
        inline-size: min(22rem, calc(100vw - 8rem));
        max-block-size: 60vh; overflow: auto; background: #fff; color: #1f2937;
        border: 1px solid #d1d5db; border-radius: .75rem; font-size: .8rem; }
  #ev h2 { margin: 0; padding: .5rem .875rem; background: #1c4587; color: #fff; font-size: .85rem; }
  #ev ol { margin: 0; padding: .5rem .875rem .875rem 1.75rem; }
  #ev li { margin-block-end: .35rem; word-break: break-word; }
  #ev .none { padding: .75rem .875rem; color: #545a63; }
  @media (prefers-color-scheme: dark) {
    body { background: #131517; color: #e5e7eb; }
    .lead { background: #1b1e21; border-color: #33373b; }
    code { background: #23272b; }
  }
"""

# The inspector is the one piece of ALT worth keeping: it is what turns a demo
# into an integration aid. Rewritten small — an IIFE, no globals, no library,
# and its event list comes from EVENTS so it cannot drift from the widget.
_INSPECTOR = """
<aside id="ev" aria-live="polite">
  <h2>Events dieser Seite</h2>
  <p class="none" id="ev-none">Noch nichts empfangen — stell dem Widget eine Frage.</p>
  <ol id="ev-list"></ol>
</aside>
<script>
(function () {
  var names = %(events)s;
  var list = document.getElementById('ev-list');
  var none = document.getElementById('ev-none');
  names.forEach(function (name) {
    window.addEventListener(name, function (event) {
      none.hidden = true;
      var li = document.createElement('li');
      var strong = document.createElement('strong');
      strong.textContent = name.replace('boerdi:', '') + ' ';
      li.appendChild(strong);
      // textContent, never innerHTML: the payload carries backend text.
      li.appendChild(document.createTextNode(JSON.stringify(event.detail).slice(0, 220)));
      list.insertBefore(li, list.firstChild);
      while (list.children.length > 12) { list.removeChild(list.lastChild); }
    });
  });
})();
</script>
"""

_PAGE = """<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(title)s — BOERDi</title>
<style>%(style)s%(extra_style)s</style>
</head>
<body>
<h1>%(title)s</h1>
<div class="lead">%(lead)s</div>

%(controls)s

<nav aria-label="Demo-Varianten">
  <h2>Die vier Varianten</h2>
  <a href="/widget/">Standard</a>
  <a href="/widget/inline">Eingebettet</a>
  <a href="/widget/classic">Ohne Gruppen-Boxen</a>
  <a href="/widget/frameless">Rahmenlos</a>
</nav>

<h2>So bindet eine Host-Seite das Widget ein</h2>
<pre><code>%(snippet)s</code></pre>
<p>
  <code>/widget/boerdi-widget.js</code> ist der stabile Pfad und bleibt es. Er
  leitet auf eine Datei mit Inhalts-Hash weiter, die ein Jahr lang
  <code>immutable</code> gecacht werden darf — ein neuer Build erzeugt von
  selbst eine neue URL. Diese Seite lädt das Widget genauso.
</p>

<h2>Alle Attribute</h2>
<p>
  Die vollständige Liste der Host-Attribute samt Standardwerten steht im
  Studio unter <strong>Übersicht → Architektur &amp; Referenz</strong>. Sie wird
  dort aus einer Quelle gepflegt, die ein Test gegen das Element festnagelt —
  eine zweite, abgetippte Liste hier wäre die, die als Erstes veraltet.
</p>

%(inspector)s
<script src="/widget/boerdi-widget.js" defer></script>
%(element)s
</body>
</html>
"""

_SNIPPET = (
    '&lt;script src="https://api.example.org/widget/boerdi-widget.js"'
    " defer&gt;&lt;/script&gt;\n"
    '&lt;boerdi-chat api-url="https://api.example.org"&gt;&lt;/boerdi-chat&gt;'
)


def _element(**attrs: str) -> str:
    """The ``<boerdi-chat>`` tag, one attribute per line so the page is readable
    when someone views the source to copy it."""
    lines = "\n".join(f'  {name}="{value}"' for name, value in attrs.items())
    return f"<boerdi-chat\n{lines}>\n</boerdi-chat>"


def _render(
    title: str,
    lead: str,
    attrs: dict[str, str],
    extra_style: str = "",
    ohne_schalter: tuple[str, ...] = (),
    wrap: str = "%s",
) -> str:
    """``extra_style`` is appended to the shared sheet rather than added to it:
    only the frameless page needs a host container, and a ``.frame`` rule the
    other three never match would be dead CSS on every page but one.

    ``attrs`` baut das Element UND speist das Bedienpult (U8) — dieselbe Quelle
    für beide, sonst zeigte das Pult einen Anfangszustand, den die Seite gar
    nicht hat. ``wrap`` umschliesst das Element (nur die rahmenlose Seite
    braucht einen Container), ``ohne_schalter`` blendet Schalter aus.
    """
    inspector = _INSPECTOR % {"events": list(EVENTS)}
    return _PAGE % {
        "title": title,
        "style": _STYLE + widget_demo_controls.style(),
        "extra_style": extra_style,
        "lead": lead,
        "controls": widget_demo_controls.panel(attrs, exclude=ohne_schalter),
        "snippet": _SNIPPET,
        "inspector": inspector,
        "element": wrap % _element(**attrs),
    }


#: Both emit flags are on here on purpose — otherwise the inspector below stays
#: empty and the page would look broken rather than quiet.
_EMIT = {"emit-guide-suggestion": "true", "emit-routing-debug": "true"}


def standard_page() -> str:
    """The default embed: floating button, page context detected automatically."""
    return _render(
        "Widget-Demo",
        "Unten rechts öffnet die Eule den Chat. Das Widget läuft hier mit den "
        "Standardwerten — es erkennt Adresse und Titel dieser Seite selbst "
        "(<code>auto-context</code>) und meldet, was es nach außen gibt.",
        {"position": "bottom-right", **_EMIT},
    )


def inline_page() -> str:
    """The embedded look: the two operator buttons off (ALT's actual delta)."""
    return _render(
        "Eingebettet",
        # U8: hier stand „die beiden Bedien-Knöpfe für Sprache und Debug". Seit
        # C1 gibt es einen EN/DE-Umschalter in der Kopfzeile, und „Sprache"
        # meinte damit plötzlich zwei verschiedene Dinge — der Satz las sich wie
        # ein Versprechen, das die Seite nicht hält.
        "Dieselbe Integration mit <code>show-language-buttons=\"false\"</code> und "
        "<code>show-debug-button=\"false\"</code>: ohne Mikrofon, ohne Vorlesen, "
        "ohne Debug-Knopf — so tritt das Widget auf einer Themenseite oder in "
        "einem fremden CMS auf. Der EN/DE-Umschalter bleibt; für ihn gibt es "
        "(noch) kein Host-Attribut. Quick-Replies und Ergebnis-Boxen bleiben "
        "ebenfalls.",
        {
            "position": "bottom-right",
            "show-language-buttons": "false",
            "show-debug-button": "false",
            **_EMIT,
        },
    )


def classic_page() -> str:
    """Like the embedded page, but with the grouping boxes switched off.

    ALT could not show this any more: it had forced ``inline-result-grouping``
    to true, so its ``/classic`` page was the inline page plus a banner saying
    the mode was gone. Here the attribute is live again (8-7), which makes this
    an A/B against ``/widget/inline`` instead of a note about one.
    """
    return _render(
        "Ohne Gruppen-Boxen",
        "Wie <a href='/widget/inline'>Eingebettet</a>, aber mit "
        "<code>inline-result-grouping=\"false\"</code>: Treffer erscheinen als "
        "Links im Antworttext statt in den strukturierten Boxen. Zum direkten "
        "Vergleich beide Seiten nebeneinander öffnen.",
        {
            "position": "bottom-right",
            "show-language-buttons": "false",
            "show-debug-button": "false",
            "inline-result-grouping": "false",
            **_EMIT,
        },
    )


#: The host container the frameless element fills. It is the page, not styling:
#: frameless drops the widget's own size along with its frame, so an element
#: dropped bare into the document flow has no height and renders as nothing —
#: silently. `overflow: hidden` clips the chat to the rounded corner the *host*
#: chose; the widget itself no longer brings one.
_FRAME_STYLE = """
  .frame { block-size: min(32rem, 70vh); border: 1px solid #d1d5db;
           border-radius: .75rem; overflow: hidden; }
  @media (prefers-color-scheme: dark) { .frame { border-color: #33373b; } }
"""


def frameless_page() -> str:
    """The frameless embed (U1): no floating button, no widget header.

    ``position`` is deliberately absent — it steers the floating button, and
    there is none here. Passing it anyway would suggest it did something.
    """
    return _render(
        "Rahmenlos",
        "Mit <code>embed-mode=\"frameless\"</code> füllt das Widget den "
        "Container, in dem es steht: kein Eulen-Knopf, keine eigene Kopfzeile, "
        "kein Rahmen. Übrig bleiben Verlauf und Eingabezeile — Kopfzeile und "
        "Navigation stellt die Gastanwendung. Der Kasten unten ist ein "
        "gewöhnliches <code>&lt;div&gt;</code> dieser Seite; seine Höhe und "
        "seine runden Ecken kommen von hier, nicht vom Widget.",
        {"embed-mode": "frameless", **_EMIT},
        extra_style=_FRAME_STYLE,
        # Kein Eulen-Knopf, also auch kein Schalter für dessen Ecke — aus dem
        # gleichen Grund, aus dem `position` oben schon fehlt.
        ohne_schalter=("position",),
        wrap='<div class="frame">\n%s\n</div>',
    )
