"""Die Hülle einer Demo-Seite: Stile, Ereignis-Spiegel, Seitenschablone.

Herausgelöst aus ``widget_demo_html`` (2026-08-13), weil dort zwei Dinge lagen,
die sich aus verschiedenen Gründen ändern: **wie eine Demo-Seite aussieht** (hier)
und **welche Seite was zeigt** (dort). Als der Nutzer eine Übersichtsseite und
einen Kontext-Simulator dazubestellte, wäre die Datei sonst weit über die 300
Zeilen gewachsen.

Der Ereignis-Spiegel ist das eine Stück ALT, das eine Demo zur Integrationshilfe
macht. Klein neu geschrieben: eine IIFE, keine Globalen, keine Bibliothek — und
seine Ereignisliste kommt aus ``EVENTS``, kann also nicht vom Widget wegdriften.
"""

from __future__ import annotations

#: Die vier Ereignisse, die das Widget auslöst — `ui/src/host-events/host-events.ts`
#: (guide-suggestion, routing-debug) und `ui/src/shell/chat-shell.component.ts`
#: (query-meta, page-action). Hier aufgezählt, weil der Spiegel unten genau diese
#: und nur diese zeigen darf: eine Anzeige für ein Ereignis, das niemand feuert,
#: liest sich als kaputtes Widget statt als ungenutzte Möglichkeit.
#:
#: Nur die neuen `boerdi:`-Namen (U5a, 2026-08-09). Das Widget feuert jedes
#: zusätzlich unter seinem alten `badboerdi:`-Namen, solange der ALTE Chatbot
#: daneben läuft — auf beide zu hören zeigte jedes Ereignis doppelt und liesse
#: die Demo aussehen, als feuere sie zweimal.
EVENTS = (
    "boerdi:guide-suggestion",
    "boerdi:routing-debug",
    "boerdi:query-meta",
    "boerdi:page-action",
)

#: Die vier Demo-Pfade in ihrer Lesereihenfolge: erst die Übersicht, dann die
#: drei Einbau-Lagen vom vertrautesten zum ungewöhnlichsten.
NAV = (
    ("/widget/", "Übersicht"),
    ("/widget/classic", "Schwebender Knopf"),
    ("/widget/inline", "Eingebettet"),
    ("/widget/frameless", "Rahmenlos"),
)

STYLE = """
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
  nav a[aria-current] { font-weight: 600; text-decoration: none; }
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
  .varianten { border-collapse: collapse; inline-size: 100%; font-size: .9rem; }
  .varianten th, .varianten td { text-align: start; padding: .5rem .75rem;
                                 border-block-end: 1px solid #e5e7eb; vertical-align: top; }
  @media (prefers-color-scheme: dark) {
    body { background: #131517; color: #e5e7eb; }
    .lead { background: #1b1e21; border-color: #33373b; }
    code { background: #23272b; }
    .varianten th, .varianten td { border-block-end-color: #33373b; }
  }
"""

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

#: Die Seiten-Schablone. ``body`` trägt alles zwischen Vorspann und Element —
#: bei den Live-Seiten das Bedienpult, bei der Übersicht die Variantentabelle.
_PAGE = """<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(title)s — BOERDi</title>
<style>%(style)s</style>
</head>
<body>
<h1>%(title)s</h1>
<div class="lead">%(lead)s</div>

%(body)s

<nav aria-label="Demo-Varianten">
  <h2>Die vier Seiten</h2>
%(nav)s
</nav>

<h2>So bindet eine Host-Seite das Widget ein</h2>
<pre><code>%(snippet)s</code></pre>
<p>
  <code>/widget/boerdi-widget.js</code> ist der stabile Pfad und bleibt es. Er
  leitet auf eine Datei mit Inhalts-Hash weiter, die ein Jahr lang
  <code>immutable</code> gecacht werden darf — ein neuer Build erzeugt von
  selbst eine neue URL.
</p>

<h2>Alle Attribute</h2>
<p>
  Die vollständige Liste der Host-Attribute samt Standardwerten steht im
  Studio unter <strong>Übersicht → Architektur &amp; Referenz</strong>. Sie wird
  dort aus einer Quelle gepflegt, die ein Test gegen das Element festnagelt —
  eine zweite, abgetippte Liste hier wäre die, die als Erstes veraltet.
</p>
%(tail)s
</body>
</html>
"""

SNIPPET = (
    '&lt;script src="https://api.example.org/widget/boerdi-widget.js"'
    " defer&gt;&lt;/script&gt;\n"
    '&lt;boerdi-chat api-url="https://api.example.org"&gt;&lt;/boerdi-chat&gt;'
)


def inspector() -> str:
    """Der Ereignis-Spiegel, samt seinem Skript."""
    return _INSPECTOR % {"events": list(EVENTS)}


def _nav(aktuell: str) -> str:
    """Die Navigation. Die eigene Seite trägt ``aria-current`` und keinen Link —
    sonst führt auf jeder Seite ein Verweis im Kreis, und ein Screenreader
    kündigt vier gleichwertige Ziele an, von denen eines das Hier ist."""
    zeilen = []
    for pfad, text in NAV:
        if pfad == aktuell:
            zeilen.append(f'  <a href="{pfad}" aria-current="page">{text}</a>')
        else:
            zeilen.append(f'  <a href="{pfad}">{text}</a>')
    return "\n".join(zeilen)


def page(
    *,
    title: str,
    lead: str,
    aktuell: str,
    body: str = "",
    tail: str = "",
    extra_style: str = "",
) -> str:
    """Eine fertige Demo-Seite.

    ``extra_style`` wird an das gemeinsame Blatt ANGEHÄNGT statt hineingeschrieben:
    nur die rahmenlosen Seiten brauchen einen Host-Container, und eine
    ``.frame``-Regel, die die anderen nie treffen, wäre auf jeder Seite ausser
    einer toter Stil.

    ``tail`` steht nach dem Fliesstext — dort hängen Ereignis-Spiegel, Bundle
    und Element. Die Übersicht lässt ihn leer und lädt damit auch das Bundle
    nicht: 400 kB für eine Seite ohne Widget wären reine Kosten.
    """
    return _PAGE % {
        "title": title,
        "style": STYLE + extra_style,
        "lead": lead,
        "body": body,
        "nav": _nav(aktuell),
        "snippet": SNIPPET,
        "tail": tail,
    }
