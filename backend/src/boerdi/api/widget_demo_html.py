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

from boerdi.api import (
    widget_demo_context,
    widget_demo_controls,
    widget_demo_layout,
    widget_demo_snippet,
)

#: Beide Melde-Attribute sind auf den Live-Seiten an: sonst bliebe der
#: Ereignis-Spiegel leer, und die Seite sähe kaputt aus statt still.
_EMIT = {"emit-guide-suggestion": "true", "emit-routing-debug": "true"}

#: Der Kasten der eingebetteten Seite. Er ist die Seite, nicht Zierrat:
#: rahmenlos legt mit dem Rahmen auch die eigene Grösse ab, ein Element also, das
#: blank im Textfluss steht, hat keine Höhe und zeigt — still — nichts.
#: `overflow: hidden` beschneidet den Chat auf die runde Ecke, die der GASTGEBER
#: gewählt hat; das Widget bringt keine mehr mit.
_FRAME_STYLE = """
  .frame { block-size: min(32rem, 70vh); border: 1px solid #d1d5db;
           border-radius: .75rem; overflow: hidden; }
  @media (prefers-color-scheme: dark) { .frame { border-color: #33373b; } }
"""

#: Ab dieser Fensterbreite steht die Spalte fest neben dem Text. EINE Quelle für
#: Stilblatt und Fliesstext: die Zahl stand zweimal da und lief auseinander
#: (Blatt 88, Vorspann noch 84 aus der ersten Fassung).
#:
#: 90 statt 88 seit der Browser-Probe (2026-08-14): bei 88rem blieben gemessen
#: 0.45rem zwischen Text und Spalte statt der gerechneten 1.5rem — der
#: Scrollbalken. Er zählt bei der Media Query mit und bei ``position: fixed``
#: nicht, die Spalte stand also 17 px weiter links als das Blatt vermuten lässt.
_SPALTE_UMBRUCH = "90rem"

#: Die Spalte der rahmenlosen Seite (P9). Dieselbe Regel wie beim Kasten —
#: Grösse kommt vom Gastgeber —, nur sichtbar anders: der Chat steht NEBEN dem
#: Inhalt statt in ihm. Das ist der Fall, den ein CMS wirklich baut, und der
#: Unterschied, den der Nutzer zwischen den beiden rahmenlosen Seiten vermisste.
#:
#: **Nachgerechnet, nicht geschätzt** — und beim zweiten Anlauf richtig. Der
#: Textkörper ist ``max-width: 60rem`` mit ``margin: auto``, der freie Rand
#: rechts also ``(W-60)/2``; die Spalte belegt 22rem plus 1.5rem Abstand.
#: Zentriert bliebe sie erst ab 107rem überlappungsfrei — bis dahin läge sie
#: ÜBER dem Text. Deshalb rückt der Textkörper in derselben Media Query nach
#: links. Die Rechnung MIT seinem Innenabstand (``padding: 0 1.25rem``, und das
#: Blatt setzt kein ``box-sizing``, der Kasten ist also 62.5rem breit):
#:
#: * Text endet bei 1.75 + 1.25 + 60 = **63rem**, sein Kasten bei 64.25rem.
#: * Spalte beginnt bei 90 - 1.25 - 1.5 - 22 = **65.25rem** — die 1.25rem sind
#:   der Scrollbalken, den ``position: fixed`` abzieht und die Media Query
#:   mitzählt.
#: * Dazwischen 2.25rem Luft, und der Kasten stösst nicht an.
#:
#: Zwei Anläufe lagen daneben, beide zu optimistisch: der erste rechnete ohne
#: den Innenabstand des Textkörpers (3rem Rand → 0.25rem Luft), der zweite ohne
#: den Scrollbalken (88rem → im Browser gemessene 0.45rem). Nachgerechnet hält
#: das jetzt ``test_the_frameless_column_leaves_the_text_its_room``.
#:
#: Unterhalb des Umbruchs ist sie ein gewöhnlicher Kasten im Fluss — kein
#: Querscrollen, nichts verdeckt. Der Ereignis-Spiegel sitzt unten LINKS und
#: kommt ihr deshalb nicht in die Quere.
_SPALTE_STYLE = """
  .spalte { block-size: min(32rem, 70vh); border: 1px solid #d1d5db;
            border-radius: .75rem; overflow: hidden; }
  @media (min-width: %(umbruch)s) {
    body { margin-inline: 1.75rem auto; }
    .spalte { position: fixed; inset-block: 1.5rem; inset-inline-end: 1.5rem;
              inline-size: 22rem; block-size: auto; }
  }
  @media (prefers-color-scheme: dark) { .spalte { border-color: #33373b; } }
"""

#: Die Wahl des Kontext-Simulators, so wie sie aus dem Query-String kommt.
#: ``None`` = der Parameter fehlt (dann greift die Voreinstellung), ``""`` =
#: ausdrücklich abgewählt. Aufgelöst wird beides an EINER Stelle, in
#: ``_live_page`` — siehe ``widget_demo_context.resolve_choice``.
_Wahl = tuple[str | None, str | None]


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
    kontext: _Wahl = (None, None),
    extra_style: str = "",
    ohne_schalter: tuple[str, ...] = (),
    wrap: str = "%s",
) -> str:
    """Eine Seite mit laufendem Widget.

    ``attrs`` baut das Element UND speist das Bedienpult (U8) — dieselbe Quelle
    für beide, sonst zeigte das Pult einen Anfangszustand, den die Seite gar
    nicht hat. ``kontext`` ist die Wahl des Kontext-Simulators; sie kann
    ``attrs`` um ``page-context``/``auto-context`` ergänzen.

    Die Voreinstellung wird hier aufgelöst, an der einen Stelle, an der Element
    und Bedienfeld dieselbe Wahl bekommen — sonst zeigte das Feld etwas anderes,
    als am Element steht.

    **Der Startzustand bleibt der der Seite (P6).** Naheliegend wäre gewesen,
    bei gesetztem Kontext überall ``initial-state="expanded"`` zu ergänzen —
    geschlossen ist die Chat-Shell nämlich gar nicht gemountet
    (``PanelState.everExpanded`` ist der Lazy-Mount-Latch), also läuft
    ``_greetOnFirstLoad`` nicht und es gibt keine Bestätigung zu sehen (B-5).
    Gebaut, gemessen, zurückgenommen: die Lage einer Seite ist das Paar
    (``embed-mode``, ``initial-state``), und drei Seiten belegen bereits alle
    drei Kombinationen. Ein erzwungenes ``expanded`` macht ``/inline`` und
    ``/frameless`` identisch — der Nutzer-Befund „sehen alle gleich aus", gegen
    den ``test_the_three_live_demos_differ_in_their_embed_situation`` steht, und
    das Gegenteil dessen, was P9 aus den beiden machen soll.

    Sichtbar wird die Bestätigung deshalb dort, wo sie hingehört: auf
    ``/inline`` sofort (die Seite startet ohnehin offen und trägt seit P5 einen
    Kontext), auf den beiden anderen beim Öffnen — und der Hinweis im
    Kontext-Feld sagt es, statt ihnen ihre Einbau-Lage zu nehmen.
    """
    kontext = widget_demo_context.resolve_choice(*kontext)
    kontext_attrs = widget_demo_context.element_attributes(*kontext)
    body = (
        widget_demo_controls.panel(attrs, exclude=ohne_schalter)
        + widget_demo_context.panel(*kontext)
    )
    tail = (
        widget_demo_layout.inspector()
        + widget_demo_snippet.snippet_watcher()
        + '\n<script src="/widget/boerdi-widget.js" defer></script>\n'
        + wrap % _element(**attrs, **kontext_attrs)
    )
    return widget_demo_layout.page(
        title=title,
        lead=lead,
        aktuell=pfad,
        body=body,
        tail=tail,
        # Dieselbe Quelle wie Element und Bedienpult (U8). Der Schnipsel zeigt
        # damit die Lage DIESER Seite; das Skript im Schwanz zieht ihn nach,
        # sobald jemand am Pult dreht.
        snippet=widget_demo_snippet.embed_snippet(attrs),
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
      <td>Der Chat steht offen <em>im Textfluss</em> der Seite, in einem Kasten
          zwischen zwei Absätzen. Kein Knopf, keine eigene Kopfzeile — so tritt
          das Widget auf einer Themenseite auf.</td>
      <td><code>embed-mode</code>, <code>initial-state</code></td>
    </tr>
    <tr>
      <td><a href="/widget/frameless">Rahmenlos</a></td>
      <td>Dieselbe Betriebsart, andere Lage: als Spalte <em>neben</em> dem
          Inhalt, über dessen ganze Höhe — der Fall, den ein CMS als Seitenpanel
          baut. Beide zeigen dabei dieselbe Regel: Grösse und Platz kommen vom
          Gastgeber, sonst ist das Widget null Pixel hoch.</td>
      <td><code>embed-mode</code>, <code>initial-state</code></td>
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


def classic_page(kontext: _Wahl = (None, None)) -> str:
    """Der Vorgabe-Einbau: schwebender Eulen-Knopf, geschlossen.

    Weder ``embed-mode`` noch ``initial-state`` stehen am Element — die Vorgaben
    ``panel``/``collapsed`` sind genau das, was diese Seite zeigen will, und ein
    hingeschriebener Vorgabewert liesse offen, ob er nötig ist.
    """
    return _live_page(
        title="Schwebender Knopf",
        lead="Unten rechts öffnet die Eule den Chat. So sieht der Einbau aus, den "
             "eine Gastseite mit zwei Zeilen bekommt; der Ereignis-Spiegel zeigt, "
             "was das Widget dabei nach aussen meldet. Woher es weiss, wo es "
             "steht, entscheidet der Simulator: mit „nichts Bestimmtem“ erkennt es "
             "Adresse und Titel dieser Seite selbst (<code>auto-context</code>), "
             "sonst gilt die dort gewählte Seite. Die Bestätigung dazu kommt, "
             "sobald du den Chat öffnest — vorher ist er nicht aufgebaut.",
        pfad="/widget/classic",
        attrs={"position": "bottom-right", **_EMIT},
        kontext=kontext,
    )


def inline_page(kontext: _Wahl = (None, None)) -> str:
    """Eingebettet: der Kasten IM Textfluss, offen von Anfang an.

    Der Kasten steht seit P9 zwischen zwei Absätzen und nicht mehr unter allen
    Abschnitten am Seitenende. Vorher unterschied sich diese Seite von der
    rahmenlosen nur in ``initial-state`` — für den Nutzer „kein echter
    Unterschied", und er hatte recht: was eine rahmenlose Einbettung ausmacht,
    ist die Lage, die der GASTGEBER ihr gibt.
    """
    return _live_page(
        title="Eingebettet",
        lead="Mit <code>embed-mode=\"frameless\"</code> füllt das Widget den Kasten, "
             "in dem es steht, und mit <code>initial-state=\"expanded\"</code> steht "
             "es offen da — kein Eulen-Knopf, keine eigene Kopfzeile, kein Rahmen. "
             "Kopfzeile und Navigation stellt die Gastanwendung. Zusätzlich sind "
             "Mikrofon, Vorlesen und der Debug-Knopf aus, wie in einem fremden CMS. "
             "Ganz unten steht der Kasten mitten im Text — so, wie er auf einer "
             "Themenseite zwischen zwei Abschnitten stünde.",
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
        # Text davor und danach: erst dadurch ist „eingebettet" zu SEHEN und
        # nicht nur behauptet. Der Kasten selbst bleibt ein gewöhnliches
        # ``<div>`` dieser Seite.
        wrap=(
            "<p>Hier läuft der Fliesstext der Gastseite — und mitten darin steht "
            "der Chat:</p>\n"
            '<div class="frame">\n%s\n</div>\n'
            "<p>… und danach geht der Text weiter. Der Kasten oben ist ein "
            "gewöhnliches <code>&lt;div&gt;</code> dieser Seite; das Widget füllt "
            "ihn aus, mehr nicht.</p>"
        ),
    )


def frameless_page(kontext: _Wahl = (None, None)) -> str:
    """Rahmenlos als **Spalte neben dem Inhalt** — der CMS-Fall (P9).

    Bis P9 war diese Seite ``/inline`` mit ``initial-state`` weniger: derselbe
    Kasten, dieselbe Lage. Jetzt trägt sie die zweite Art, rahmenlos einzubauen —
    eine Spalte, die neben dem Seiteninhalt steht und dessen ganze Höhe nutzt.

    **Offen gestartet, anders als vorher.** Eine leere Spalte sähe schlicht
    kaputt aus, während ein leerer Kasten im Text noch als Lektion durchging.
    Die Lektion selbst bleibt und ist hier sogar deutlicher: rahmenlos legt mit
    dem Rahmen auch die eigene Grösse ab — Breite und Höhe der Spalte kommen aus
    dem Stilblatt DIESER Seite.
    """
    return _live_page(
        title="Rahmenlos",
        lead="Dieselbe Betriebsart wie <a href='/widget/inline'>Eingebettet</a>, "
             "aber eine andere Einbau-Lage: der Chat steht als Spalte <em>neben</em> "
             "dem Inhalt statt in ihm — so baut ein CMS ein Seitenpanel. Ab "
             f"{_SPALTE_UMBRUCH} Fensterbreite steht sie rechts und nutzt die volle Höhe, "
             "darunter rückt sie als gewöhnlicher Kasten unter den Text; sonst läge "
             "sie darüber. Beides kommt aus dem Stilblatt dieser Seite: rahmenlos "
             "legt mit dem Rahmen auch die eigene Grösse ab, und ohne Container "
             "wäre das Element null Pixel hoch — man sähe gar nichts, ohne Fehler.",
        pfad="/widget/frameless",
        # Offen: eine leere Spalte wäre kein Lehrstück, sondern ein Defekt.
        attrs={"embed-mode": "frameless", "initial-state": "expanded", **_EMIT},
        kontext=kontext,
        # Umbruchbreite am Gebrauchsort eingesetzt, wie bei den anderen
        # Vorlagen dieses Pakets — dieselbe Zahl steht oben im Vorspann.
        extra_style=_SPALTE_STYLE % {"umbruch": _SPALTE_UMBRUCH},
        ohne_schalter=("position",),
        wrap='<div class="spalte">\n%s\n</div>',
    )
