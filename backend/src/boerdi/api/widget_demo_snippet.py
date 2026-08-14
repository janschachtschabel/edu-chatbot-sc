"""Der Einbindungscode einer Demo-Seite — der Block zum Kopieren.

Eigenes Modul seit P8 (2026-08-13). In ``widget_demo_layout`` stand vorher ein
statischer Zweizeiler; jetzt zeigt der Block die Attribute der jeweiligen Seite
und wird im Browser nachgeführt. Damit hat er einen eigenen Grund, sich zu
ändern — *was ein Gastgeber wirklich braucht* —, der mit Stilen,
Ereignis-Spiegel und Seitenschablone nichts zu tun hat. Die Hülle war mit ihm
über 300 Zeilen; sie ist aus demselben Grund einmal aus ``widget_demo_html``
entstanden.
"""

from __future__ import annotations

import json
from html import escape

#: Beispiel-Ursprung im Einbindungscode. Bewusst KEIN echter: der Code soll auf
#: einer fremden Domain laufen, und dort steht ein anderer Ursprung als hier.
API_URL = "https://api.example.org"

#: Was ein Gastgeber NICHT einbaut, obwohl es am Demo-Element steht.
#: ``page-context``/``auto-context`` simulieren hier eine Gastseite — auf einer
#: echten erkennt das Widget sie selbst; die ``emit-*`` speisen den
#: Ereignis-Spiegel dieser Demo. Mitkopiert redete der Chatbot auf einer
#: beliebigen Seite von der Optik-Sammlung.
DEMO_ONLY_ATTRS = (
    "page-context",
    "auto-context",
    "emit-guide-suggestion",
    "emit-routing-debug",
)

#: Was das Element selbst setzt (Host-Bindings bzw. Angular). Dieselbe Liste wie
#: in ``widget_demo_controls.neuAufbauen()`` und aus demselben Grund: abgeleiteter
#: Zustand ist keine Vorgabe, die man abschreibt.
_ELEMENT_OWN_ATTRS = ("class", "style", "ng-version")

#: Zeile 1 des Schnipsels. Von hier bezieht sie AUCH das Skript unten — sonst
#: stünde die Beispiel-Adresse zweimal und driftete beim ersten Umzug.
_SCRIPT_LINE = f'<script src="{API_URL}/widget/boerdi-widget.js" defer></script>'


def embed_snippet(attrs: dict[str, str] | None = None) -> str:
    """Die Zeilen, die eine Gastseite braucht — maskiert für den ``<pre>``-Block.

    ``attrs`` sind die Attribute, die die Demo-Seite an ihr Element geschrieben
    hat; ohne sie (Übersicht) bleibt es beim allgemeinen Beispiel.

    ``api-url`` steht hier und **nicht** am Demo-Element: die Demo lädt vom
    selben Ursprung und braucht es nicht, eine fremde Domain schon — ohne die
    Zeile bliebe der kopierte Code stumm.

    Einzeilig, solange nur ``api-url`` dasteht: das ist der Zwei-Zeilen-Einbau,
    den die Dokumentation verspricht. Erst weitere Attribute rechtfertigen den
    Umbruch.
    """
    paare = [("api-url", API_URL)]
    paare += [(n, w) for n, w in (attrs or {}).items() if n not in DEMO_ONLY_ATTRS]
    if len(paare) == 1:
        element = f'<boerdi-chat api-url="{API_URL}"></boerdi-chat>'
    else:
        zeilen = "\n".join(f'  {n}="{w}"' for n, w in paare)
        element = f"<boerdi-chat\n{zeilen}></boerdi-chat>"
    return escape(f"{_SCRIPT_LINE}\n{element}")


#: Hält den Einbindungscode am Element — nicht am Bedienpult.
#:
#: Ein ``MutationObserver`` statt eines Aufrufs aus ``widget_demo_controls``:
#: die Skripte dieser Seiten sind IIFEs ohne Globale, ein Aufruf über die
#: Modulgrenze bräuchte eine. Der Beobachter kommt zudem an Stellen mit, an die
#: ein Aufruf nicht gedacht hätte — Farbwähler, Zurücksetzen, der Neuaufbau, der
#: das Element AUSTAUSCHT (deshalb ``childList`` am ``body``, nicht ``attributes``
#: am Element), und jede Änderung aus der Konsole.
#:
#: Der Preis dieser Wahl: der Block, den er schreibt, liegt IM beobachteten
#: Teilbaum. Ohne Vergleich vor dem Schreiben weckt der Rückruf sich selbst —
#: gemessen an diesem Skript (jsdom, EINE fremde Mutation): 500+ Rückrufe ohne
#: Abbruch, die Seite friert ein. Deshalb die eine `return`-Zeile unten; sie ist
#: keine Optimierung, sondern die Abbruchbedingung. Wächter:
#: ``test_the_live_updater_writes_only_when_something_changed``.
#:
#: Ausschlussliste und Kopfzeile kommen aus dem Python-Code oben. Was hier
#: bleibt, ist die Formatierung — driftet die, sagt der Schnipsel dasselbe in
#: anderer Einrückung; eine zweite Ausschlussliste wäre dagegen ein zweiter Ort,
#: an dem man `emit-*` vergisst.
_WATCHER = """
<script>
(function () {
  var demoOnly = %(demo_only)s, eigene = %(eigene)s;
  var kopf = %(kopf)s, apiUrl = %(api_url)s;
  var block = document.querySelector('#einbindung code');
  function schreiben() {
    var el = document.querySelector('boerdi-chat');
    if (!el || !block) return;
    var paare = ['api-url="' + apiUrl + '"'];
    for (var i = 0; i < el.attributes.length; i++) {
      var a = el.attributes[i];
      if (eigene.indexOf(a.name) !== -1 || demoOnly.indexOf(a.name) !== -1) continue;
      paare.push(a.name + '="' + a.value + '"');
    }
    var element = paare.length === 1
      ? '<boerdi-chat ' + paare[0] + '></boerdi-chat>'
      : '<boerdi-chat\\n  ' + paare.join('\\n  ') + '></boerdi-chat>';
    var neu = kopf + '\\n' + element;
    // Erst vergleichen, dann schreiben: der Block liegt IM beobachteten
    // Teilbaum, eine Zuweisung ist also selbst eine Mutation und weckt den
    // Beobachter wieder — ohne diese Zeile endlos.
    if (block.textContent === neu) return;
    // textContent, nie innerHTML: der Block ist Text zum Kopieren. Damit ist
    // auch ein Attributwert, der wie Markup aussieht, hier nur Text.
    block.textContent = neu;
  }
  new MutationObserver(schreiben).observe(
    document.body, { subtree: true, attributes: true, childList: true });
})();
</script>
"""


def _js_literal(wert: object) -> str:
    """JSON-Literal, sicher innerhalb eines Inline-``<script>``.

    **Der Fehler, gegen den das steht (live gemessen 2026-08-14).** Der
    HTML-Parser beendet ein ``<script>``-Element am ERSTEN ``</script`` in
    seinem Text — die Anführungszeichen von JavaScript sieht er nicht.
    :data:`_SCRIPT_LINE` trägt genau das, es IST eine Skript-Zeile. Ohne
    Maskierung endete das Element also mitten im Beobachter, und der Rest
    wurde als MARKUP geparst: aus ``'<boerdi-chat ' + paare[0] + '>'`` wurde
    ein zweites, leeres ``<boerdi-chat>``. Das Widget nahm dieses erste und
    versteckte das echte als Dublette — der Seitenkontext war weg, und der
    Chatbot redete über die Adresse statt über die Sammlung.

    In einem JS-String ist ``<\\/`` dasselbe wie ``</``; für den HTML-Parser ist
    es kein Ende-Tag mehr. ``<!--`` kommt mit, weil es denselben Sonderzustand
    auslöst — eine Zeile für die ganze Klasse, statt auf den einen bekannten
    Wert zu zielen.

    Dieselbe Zeichenkette hat damit ZWEI korrekte Kodierungen: hier für das
    Skript, in :func:`embed_snippet` HTML-maskiert für den ``<pre>``-Block.
    """
    return json.dumps(wert).replace("</", "<\\/").replace("<!--", "<\\!--")


def snippet_watcher() -> str:
    """Das Skript, das den Einbindungscode dem Element nachführt.

    Nur für die Live-Seiten: die Übersicht hat kein Element, dort beobachtete er
    nichts und schriebe nie.

    Jeder eingesetzte Wert geht durch :func:`_js_literal` — auch die, die heute
    harmlos aussehen. Eine Ausnahme wäre die Stelle, an der die Maskierung beim
    nächsten neuen Wert ausbleibt.
    """
    return _WATCHER % {
        "demo_only": _js_literal(list(DEMO_ONLY_ATTRS)),
        "eigene": _js_literal(list(_ELEMENT_OWN_ATTRS)),
        "kopf": _js_literal(_SCRIPT_LINE),
        "api_url": _js_literal(API_URL),
    }
