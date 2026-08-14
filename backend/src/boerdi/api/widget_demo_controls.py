"""Das Bedienpult der Demo-Seiten (U8, 2026-08-09).

**Warum es das gibt.** Die vier Demo-Seiten zeigten je EINE feste
Attribut-Kombination — zusammen acht der damals 23 Host-Attribute. Alles andere
(`theme`, `size`, `show-cards`, `language`, `primary-color`, …) liess sich auf
keiner Seite ausprobieren; wer wissen wollte, wie das Widget mit
`show-cards="never"` aussieht, musste sich eine eigene HTML-Datei schreiben.
Genau deshalb liest sich „geht nicht" schnell wie ein Defekt, wo in Wahrheit nur
kein Weg da war, es zu sehen.

Das Pult setzt die Attribute am **laufenden** Element. Damit ist es zugleich der
Beweis, dass sie zur Laufzeit greifen — und macht sichtbar, welche es nicht tun:

* Die meisten Attribute wirken sofort (Signal-Eingang am Custom Element).
* `size` und `initial-state` sind laut Vertrag **Startwerte** — danach gehört die
  Grösse dem Panel, weil der Nutzer sie über die Eingabezeile selbst umstellt.
  Ein `setAttribute` darauf tut also nichts. Statt das zu verschweigen, baut das
  Pult das Element neu auf und sagt im Etikett „(Neustart)". Der Verlauf
  überlebt, weil die Sitzungs-ID im `localStorage` liegt.

**Zwei Farbschema-Schalter, nicht einer.** Der eine stellt die **Gastseite**
(`color-scheme` am `<html>`), der andere das **Widget** (`theme`). Erst
zusammen zeigen sie die Regel aus U4a: bei `theme="auto"` folgt das Widget der
Seite; bei `light`/`dark` nicht mehr. Ein einzelner Schalter könnte das nicht
auseinanderhalten.

**Serverseitig gebaut, nicht per JavaScript.** Die naheliegende Fassung erzeugt
die Auswahlfelder im Browser aus einer JSON-Liste. Dann müsste das Skript aber
den Anfangswert aus dem Element zurücklesen — und genau der ist hier schon
bekannt: die Seite hat die Attribute selbst gesetzt. Serverseitig markiert
`selected` ihn direkt, ein Test kann ihn lesen, und übrig bleibt ein Skript, das
nur noch zuhört.

Alle Werte stammen aus der Konstante unten — die Seite baut keine Zeichenkette
aus Nutzereingaben. Der Farbwähler ist die einzige freie Eingabe; sein Wert geht
durch die Attribut-Validierung des Elements (`primary-color`).
"""

from __future__ import annotations

from html import escape
from typing import NamedTuple


class Control(NamedTuple):
    """Ein Schalter des Pults."""

    #: Host-Attribut, exakt wie im Vertrag.
    attr: str
    #: Beschriftung.
    label: str
    #: `(wert, beschriftung)`; der leere Wert entfernt das Attribut wieder.
    options: tuple[tuple[str, str], ...]
    #: True = wirkt nur beim Start, das Pult baut das Element neu auf.
    restart: bool = False


_AN_AUS = (("", "Standard"), ("true", "an"), ("false", "aus"))

#: Die Attribute, die man auf einer Demo-Seite ANSEHEN kann. Bewusst nicht
#: dabei: `api-url`, `page-context`, `auto-context`, `trusted-domains`,
#: `session-*`, `intercept-edu-sharing-links`, `emit-*`, `greeting`. Sie ändern
#: nichts Sichtbares oder würden die Seite ihrer eigenen Aufgabe berauben (die
#: `emit-*` speisen den Ereignis-Spiegel, `api-url` die Verbindung).
CONTROLS: tuple[Control, ...] = (
    Control("theme", "Widget-Farbschema", (
        ("", "auto (folgt der Seite)"), ("light", "hell"), ("dark", "dunkel"))),
    Control("size", "Grösse", (("", "klein"), ("large", "gross")), restart=True),
    Control("initial-state", "Beim Laden", (
        ("", "geschlossen"), ("expanded", "offen")), restart=True),
    Control("position", "Ecke des Eulen-Knopfs", (
        ("bottom-right", "unten rechts"), ("bottom-left", "unten links"),
        ("top-right", "oben rechts"), ("top-left", "oben links"))),
    Control("show-cards", "Kacheln", (
        ("", "auto (klein Links, gross Kacheln)"),
        ("always", "immer"), ("never", "nie"))),
    Control("inline-result-grouping", "Ergebnis-Boxen", _AN_AUS),
    Control("show-debug-button", "Debug-Knopf", _AN_AUS),
    # Der Attributname ist ALT-Erbe und meint die SPRACH-AUSGABE (Mikrofon +
    # Vorlesen), nicht den EN/DE-Umschalter. Das Etikett sagt es, weil der Name
    # es nicht kann — und weil genau diese Verwechslung schon einmal für einen
    # vermeintlichen Defekt gehalten wurde.
    Control("show-language-buttons", "Mikro + Vorlesen", _AN_AUS),
    Control("language", "Oberflächensprache", (
        ("", "auto (Browser)"), ("de", "Deutsch"), ("en", "Englisch"))),
    # Der einzige Schalter, der nichts am AUSSEHEN ändert. Er steht trotzdem
    # hier, weil er die Frage beantwortet, die man auf einer Demo-Seite stellt:
    # „was tut die Agent-Schleife eigentlich anders?" Sichtbar wird das an den
    # Antworten, nicht am Rahmen. Leer = die Vorgabe aus `01-base/engine`.
    Control("engine", "Maschine", (
        ("", "Vorgabe (01-base/engine)"), ("pattern", "Muster-Engine"),
        ("agent", "Agent-Schleife"))),
)

_STYLE = """
  .pult { margin-block: 1.5rem; border: 1px solid #d1d5db; border-radius: .75rem;
          padding: 1rem 1.25rem; }
  .pult > h2 { margin-block-start: 0; }
  .pult-gitter { display: grid; gap: .75rem 1.25rem;
                 grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr)); }
  .pult label { display: flex; flex-direction: column; gap: .2rem; font-size: .85rem; }
  .pult select, .pult input { font: inherit; font-size: .85rem; padding: .3rem;
                              border: 1px solid #9aa0a6; border-radius: .35rem;
                              background: Field; color: FieldText; }
  .pult-farbe { display: flex; gap: .5rem; align-items: center; }
  .pult-farbe input[type=color] { inline-size: 3rem; block-size: 2rem; padding: 0; }
  .pult button { font: inherit; font-size: .8rem; padding: .3rem .6rem;
                 border: 1px solid #9aa0a6; border-radius: .35rem;
                 background: Field; color: FieldText; cursor: pointer; }
  .pult-hinweis { margin-block-end: 0; font-size: .8rem; color: #545a63; }
  @media (prefers-color-scheme: dark) {
    .pult { border-color: #33373b; }
    .pult-hinweis { color: #9aa0a6; }
  }
"""

# Ein einziger Zuhörer für alle Auswahlfelder: das `data-attr` am Feld sagt,
# welches Attribut es stellt, `data-restart` ob dafür neu aufgebaut werden muss.
# Damit kostet ein neuer Schalter genau eine Zeile in CONTROLS und keine im JS.
_SCRIPT = """
<script>
(function () {
  /** Das Element wird bei JEDEM Zugriff neu gesucht, nie in einer Variablen
      gehalten. Zwei Gründe, beide gemessen:
      1. Das Pult steht im Dokument ÜBER dem `<boerdi-chat>` (es ist eine
         Bedienleiste, die gehört nach oben). Ein `querySelector` beim Laden
         träfe daher `null` — die erste Fassung tat genau das, und jeder
         Schalter warf still eine TypeError in die Konsole.
      2. `neuAufbauen()` tauscht das Element aus. Eine gehaltene Referenz zeigte
         danach auf ein Element, das nicht mehr im Dokument hängt. */
  function widget() { return document.querySelector('boerdi-chat'); }

  /** `size` und `initial-state` wirken nur beim Aufbau. Ein frisches Element mit
      denselben Attributen ist der einzige ehrliche Weg, sie vorzuführen. */
  function neuAufbauen() {
    var alt = widget();
    var frisch = document.createElement('boerdi-chat');
    for (var i = 0; i < alt.attributes.length; i++) {
      var a = alt.attributes[i];
      // `class` und `style` setzt das Element selbst (Host-Bindings), `ng-version`
      // Angular. Sie mitzunehmen hiesse, abgeleiteten Zustand als Vorgabe auszugeben.
      // Dieselben drei stehen als `_ELEMENT_OWN_ATTRS` in `widget_demo_snippet`
      // (dort für die ANZEIGE, hier fürs Kopieren) — kommt eines dazu, gehört es
      // an beide Stellen.
      if (a.name === 'class' || a.name === 'style' || a.name === 'ng-version') continue;
      frisch.setAttribute(a.name, a.value);
    }
    alt.replaceWith(frisch);
  }

  document.querySelectorAll('#pult-gitter select[data-attr]').forEach(function (feld) {
    feld.addEventListener('change', function () {
      if (feld.value === '') { widget().removeAttribute(feld.dataset.attr); }
      else { widget().setAttribute(feld.dataset.attr, feld.value); }
      if (feld.dataset.restart === 'true') { neuAufbauen(); }
    });
  });

  // Markenfarbe: der einzige freie Wert. Das Element validiert ihn selbst.
  var farbe = document.getElementById('pult-farbe');
  farbe.addEventListener('input', function () {
    widget().setAttribute('primary-color', farbe.value);
  });
  document.getElementById('pult-farbe-reset').addEventListener('click', function () {
    widget().removeAttribute('primary-color');
  });

  // Die GASTSEITE umschalten — nicht das Widget. Bei `theme="auto"` zieht das
  // Widget mit, sonst nicht; genau das soll man hier sehen können.
  document.getElementById('pult-seite').addEventListener('change', function () {
    document.documentElement.style.colorScheme = this.value;
  });
})();
</script>
"""

_PANEL = """
<section class="pult" aria-labelledby="pult-titel">
  <h2 id="pult-titel">Bedienpult — Attribute live ausprobieren</h2>
  <div class="pult-gitter" id="pult-gitter">
    <label>
      <span>Farbschema der Gastseite</span>
      <select id="pult-seite">
        <option value="">auto (Betriebssystem)</option>
        <option value="light">hell</option>
        <option value="dark">dunkel</option>
      </select>
    </label>
%(felder)s
    <label>
      <span>Markenfarbe (<code>primary-color</code>)</span>
      <span class="pult-farbe">
        <input type="color" id="pult-farbe" value="#1c4587">
        <button type="button" id="pult-farbe-reset">Standard</button>
      </span>
    </label>
  </div>
  <p class="pult-hinweis">
    Die Schalter setzen die Attribute am laufenden Element — das ist zugleich
    der Nachweis, dass sie zur Laufzeit wirken. Zwei tun das nicht: Grösse und
    Anfangszustand sind Startwerte, dafür wird das Element neu aufgebaut. Der
    Gesprächsverlauf überlebt das, er hängt an der Sitzungs-ID.
  </p>
</section>
"""


def _feld(control: Control, aktuell: str) -> str:
    """Ein Auswahlfeld mit vorgewähltem Ist-Wert."""
    optionen = "\n".join(
        f'        <option value="{escape(wert, quote=True)}"'
        f'{" selected" if wert == aktuell else ""}>{escape(text)}</option>'
        for wert, text in control.options
    )
    etikett = escape(control.label) + (" (Neustart)" if control.restart else "")
    neustart = ' data-restart="true"' if control.restart else ""
    return (
        "    <label>\n"
        f"      <span>{etikett} — <code>{escape(control.attr)}</code></span>\n"
        f'      <select data-attr="{escape(control.attr, quote=True)}"{neustart}>\n'
        f"{optionen}\n"
        "      </select>\n"
        "    </label>"
    )


def panel(current: dict[str, str], exclude: tuple[str, ...] = ()) -> str:
    """Das Pult als HTML-Schnipsel.

    ``current`` sind die Attribute, die die Seite am Element gesetzt hat — sie
    entscheiden, welche Option vorgewählt ist. Ohne sie zeigte das Pult für die
    eingebettete Seite „Debug-Knopf: Standard", obwohl er dort ausgeschaltet ist.

    ``exclude`` nimmt Attributnamen: die rahmenlose Seite hat keinen
    Eulen-Knopf, ein Schalter für dessen Ecke wäre dort eine Lüge.
    """
    felder = "\n".join(
        _feld(c, current.get(c.attr, "")) for c in CONTROLS if c.attr not in exclude
    )
    return _PANEL % {"felder": felder} + _SCRIPT


def style() -> str:
    """Die Stile des Pults — vom Seiten-Stylesheet getrennt, weil sie mit dem
    Pult kommen und gehen."""
    return _STYLE
