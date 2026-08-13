"""Welche Demo-Seite was zeigt — ``/widget/``, ``/inline``, ``/classic``,
``/frameless`` (C4b; vierte Seite in U1, Umwidmung 2026-08-13).

**Diese Seiten sind Demos, nicht ALTs Integrationsanleitung.** ALT lieferte hier
942 Zeilen handgeschriebenes HTML, das meiste davon eine Attributliste — und die
listete 17 der 18 Host-Attribute. Das fehlende war ``inline-result-grouping``,
genau jenes, das 8-7 tot in der Shell fand. Der volle Vertrag steht im Studio an
einer Stelle, die ein Test im Widget-Projekt festnagelt. Eine dritte Kopie in
einer Python-Zeichenkette wäre die, die niemand prüft — dieses Projekt hat eine
solche Kopie schon zweimal driften sehen.

Die Seiten tun also, was nur sie können: das echte Element gegen das echte
Backend laufen lassen, jede in der Einbau-Lage, um die es ihr geht.

**Warum sie 2026-08-13 neu verteilt wurden.** Vorher setzten ``/widget/``,
``/inline`` und ``/classic`` alle ``position="bottom-right"`` ohne ``embed-mode``
— dreimal derselbe schwebende Knopf. Getrennt hat sie nur, was ohnehin auf jeder
Seite im Bedienpult steht. Der Nutzer las das als „sehen alle gleich aus und
machen alle dasselbe", und er hatte recht. Jetzt trägt jede Live-Seite eine
eigene Lage, und ``/widget/`` ist die Übersicht, die keine mehr doppelt.

Alle vier Pfade bleiben: sie stehen im eingefrorenen OpenAPI-Dokument
(``docs/api/openapi-v1.json``). Eine Seite umzuwidmen ist billig, eine zu
löschen wäre Vertragsdrift.
"""

from __future__ import annotations

from html import escape

from boerdi.api import widget_demo_context, widget_demo_controls, widget_demo_layout

#: Beide Melde-Attribute sind auf den Live-Seiten an: sonst bliebe der
#: Ereignis-Spiegel leer, und die Seite sähe kaputt aus statt still.
_EMIT = {"emit-guide-suggestion": "true", "emit-routing-debug": "true"}

#: Der Host-Container der rahmenlosen Einbauten. Er ist die Seite, nicht Zierrat:
#: rahmenlos legt mit dem Rahmen auch die eigene Grösse ab, ein Element also, das
#: blank im Textfluss steht, hat keine Höhe und zeigt — still — nichts.
#: `overflow: hidden` beschneidet den Chat auf die runde Ecke, die der GASTGEBER
#: gewählt hat; das Widget bringt keine mehr mit.
_FRAME_STYLE = """
  .frame { block-size: min(32rem, 70vh); border: 1px solid #d1d5db;
           border-radius: .75rem; overflow: hidden; }
  @media (prefers-color-scheme: dark) { .frame { border-color: #33373b; } }
"""


def _element(**attrs: str) -> str:
    """Das ``<boerdi-chat>``-Tag, ein Attribut je Zeile — damit die Seite lesbar
    bleibt, wenn jemand den Quelltext zum Kopieren ansieht.

    **Jeder Wert wird hier maskiert, ausnahmslos.** Die meisten sind Literale
    aus den Seitenfunktionen unten, einer (``page-context``) stammt aus dem
    Query-String. Die Maskierung an der EINEN Stelle zu tun, an der das Attribut
    entsteht, statt sie dem jeweiligen Lieferanten zu überlassen, ist der
    Unterschied zwischen einer Regel und einer Verabredung über eine
    Modulgrenze hinweg. ``quote=True`` ist dabei der Punkt: JSON besteht aus
    doppelten Anführungszeichen, und das erste unmaskierte beendete das Attribut.
    """
    lines = "\n".join(
        f'  {name}="{escape(value, quote=True)}"' for name, value in attrs.items()
    )
    return f"<boerdi-chat\n{lines}>\n</boerdi-chat>"


def _live_page(
    *,
    title: str,
    lead: str,
    pfad: str,
    attrs: dict[str, str],
    kontext: tuple[str, str] = ("", ""),
    extra_style: str = "",
    ohne_schalter: tuple[str, ...] = (),
    wrap: str = "%s",
) -> str:
    """Eine Seite mit laufendem Widget.

    ``attrs`` baut das Element UND speist das Bedienpult (U8) — dieselbe Quelle
    für beide, sonst zeigte das Pult einen Anfangszustand, den die Seite gar
    nicht hat. ``kontext`` ist die Wahl des Kontext-Simulators; sie kann
    ``attrs`` um ``page-context``/``auto-context`` ergänzen.
    """
    kontext_attrs = widget_demo_context.element_attributes(*kontext)
    body = (
        widget_demo_controls.panel(attrs, exclude=ohne_schalter)
        + widget_demo_context.panel(*kontext)
    )
    tail = (
        widget_demo_layout.inspector()
        + '\n<script src="/widget/boerdi-widget.js" defer></script>\n'
        + wrap % _element(**attrs, **kontext_attrs)
    )
    return widget_demo_layout.page(
        title=title,
        lead=lead,
        aktuell=pfad,
        body=body,
        tail=tail,
        extra_style=widget_demo_controls.style()
        + widget_demo_context.style()
        + extra_style,
    )


_UEBERSICHT = """
<h2>Was die drei Seiten zeigen</h2>
<table class="varianten">
  <thead>
    <tr><th>Seite</th><th>Einbau-Lage</th><th>Attribute</th></tr>
  </thead>
  <tbody>
    <tr>
      <td><a href="/widget/classic">Schwebender Knopf</a></td>
      <td>Die Eule sitzt unten rechts auf der Seite und öffnet den Chat bei
          Klick. Der Vorgabe-Einbau — zwei Zeilen, sonst nichts.</td>
      <td><code>position</code></td>
    </tr>
    <tr>
      <td><a href="/widget/inline">Eingebettet</a></td>
      <td>Der Chat steht offen <em>in</em> der Seite, in einem Kasten, den die
          Seite selbst stellt. Kein Knopf, keine eigene Kopfzeile — so tritt das
          Widget auf einer Themenseite oder in einem fremden CMS auf.</td>
      <td><code>embed-mode</code>, <code>initial-state</code></td>
    </tr>
    <tr>
      <td><a href="/widget/frameless">Rahmenlos</a></td>
      <td>Dieselbe Lage, aber geschlossen gestartet und mit dem Hinweis, was
          passiert, wenn der Gastgeber keine Höhe vorgibt: dann ist das Widget
          null Pixel hoch und man sieht gar nichts.</td>
      <td><code>embed-mode</code></td>
    </tr>
  </tbody>
</table>

<h2>Und was auf jeder von ihnen geht</h2>
<ul>
  <li><strong>Bedienpult</strong> — jedes Anzeige-Attribut live umstellen
      (Farbschema, Grösse, Kacheln, Ergebnis-Boxen, Sprache …). Der frühere
      A/B <code>inline-result-grouping</code>, für den es einmal eine eigene
      Seite gab, ist einer dieser Schalter.</li>
  <li><strong>Seitenkontext simulieren</strong> — dem Widget vorgeben, es stünde
      auf einer Sammlung, einer Themenseite, einem Einzelinhalt, einer Suche
      oder einer fremden Adresse, und die Reaktion beobachten.</li>
  <li><strong>Ereignis-Spiegel</strong> — was das Widget nach aussen meldet,
      mitlesen.</li>
</ul>
"""


def index_page() -> str:
    """Die Übersicht: kein Widget, sondern der Wegweiser zu den dreien.

    Bewusst ohne Element und ohne Bundle. Vorher war dies die dritte Seite mit
    demselben schwebenden Knopf — sie kostete 400 kB und zeigte nichts, was
    ``/classic`` nicht auch zeigt.
    """
    return widget_demo_layout.page(
        title="Widget-Demo",
        lead="Drei Seiten, drei Einbau-Lagen — dazu auf jeder ein Bedienpult für "
             "die Attribute und ein Simulator für den Seitenkontext. Diese Seite "
             "selbst trägt kein Widget; sie sagt nur, wo welches steht.",
        aktuell="/widget/",
        body=_UEBERSICHT,
    )


def classic_page(kontext: tuple[str, str] = ("", "")) -> str:
    """Der Vorgabe-Einbau: schwebender Eulen-Knopf, geschlossen.

    Weder ``embed-mode`` noch ``initial-state`` stehen am Element — die Vorgaben
    ``panel``/``collapsed`` sind genau das, was diese Seite zeigen will, und ein
    hingeschriebener Vorgabewert liesse offen, ob er nötig ist.
    """
    return _live_page(
        title="Schwebender Knopf",
        lead="Unten rechts öffnet die Eule den Chat. So sieht der Einbau aus, den "
             "eine Gastseite mit zwei Zeilen bekommt: das Widget erkennt Adresse "
             "und Titel dieser Seite selbst (<code>auto-context</code>) und meldet, "
             "was es nach aussen gibt.",
        pfad="/widget/classic",
        attrs={"position": "bottom-right", **_EMIT},
        kontext=kontext,
    )


def inline_page(kontext: tuple[str, str] = ("", "")) -> str:
    """Eingebettet: rahmenlos im Container der Seite, offen von Anfang an."""
    return _live_page(
        title="Eingebettet",
        lead="Mit <code>embed-mode=\"frameless\"</code> füllt das Widget den Kasten, "
             "in dem es steht, und mit <code>initial-state=\"expanded\"</code> steht "
             "es offen da — kein Eulen-Knopf, keine eigene Kopfzeile, kein Rahmen. "
             "Kopfzeile und Navigation stellt die Gastanwendung. Zusätzlich sind "
             "Mikrofon, Vorlesen und der Debug-Knopf aus, wie in einem fremden CMS.",
        pfad="/widget/inline",
        attrs={
            "embed-mode": "frameless",
            "initial-state": "expanded",
            "show-language-buttons": "false",
            "show-debug-button": "false",
            **_EMIT,
        },
        kontext=kontext,
        extra_style=_FRAME_STYLE,
        # Kein Eulen-Knopf, also auch kein Schalter für dessen Ecke.
        ohne_schalter=("position",),
        wrap='<div class="frame">\n%s\n</div>',
    )


def frameless_page(kontext: tuple[str, str] = ("", "")) -> str:
    """Rahmenlos pur — dieselbe Lage wie ``/inline``, aber geschlossen gestartet.

    Der Unterschied ist die Lektion: rahmenlos legt mit dem Rahmen auch die
    eigene Grösse ab. Wer den Container vergisst, sieht nichts — ohne Fehler.
    """
    return _live_page(
        title="Rahmenlos",
        lead="Wie <a href='/widget/inline'>Eingebettet</a>, aber ohne "
             "<code>initial-state</code>: das Widget startet geschlossen und der "
             "Kasten bleibt zunächst leer. Genau daran hängt die Regel — der Kasten "
             "unten ist ein gewöhnliches <code>&lt;div&gt;</code> dieser Seite, und "
             "seine Höhe kommt von hier, nicht vom Widget. Ohne ihn wäre das "
             "Element null Pixel hoch, und man sähe gar nichts.",
        pfad="/widget/frameless",
        attrs={"embed-mode": "frameless", **_EMIT},
        kontext=kontext,
        extra_style=_FRAME_STYLE,
        ohne_schalter=("position",),
        wrap='<div class="frame">\n%s\n</div>',
    )
