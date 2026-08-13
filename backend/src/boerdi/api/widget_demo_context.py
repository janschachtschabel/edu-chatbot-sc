"""Seitenkontext simulieren — der Trigger der Demo-Seiten (2026-08-13).

**Warum es das gibt.** Auf einer echten Gastseite erkennt das Widget selbst, wo
es steht (``page-context-detector.ts``): Sammlung, Themenseite, Einzelinhalt,
Suche. Das Backend reagiert darauf — Kontext-Begrüssung, Kontext-Aktionen,
Themenseiten-Auflösung. Auf einer Demo-Seite gibt es dieses „wo" nicht, und
damit war die halbe Wirkung des Chatbots dort nicht vorführbar. Der Nutzer hat
genau das verlangt: „damit ich die Reaktion testen kann".

**Serverseitig aus dem Query-String**, nicht per JavaScript nach dem Aufbau.
Drei Gründe, und der dritte ist der wichtige:

1. Die Simulation ist neuladefest und teilbar — ein Link genügt.
2. Es ist das Prinzip, das ``widget_demo_controls`` schon trägt (dort steht die
   lange Begründung).
3. Der Kontext steht **beim Aufbau** am Element. Damit greift im Backend der
   Pfad ``context_open_initial`` — der Fall „ich lande auf einer Sammlungsseite".
   Nachträglich gesetzt wäre es der Fall „die Seite hat unter mir gewechselt",
   also eine andere Zusicherung als die, die man sehen will.

**``auto-context="false"``**, wie in der Studio-Vorschau und aus demselben Grund:
sonst trüge der Detektor ``page_url``/``page_host`` der DEMO-Seite bei, und das
Backend entschiede „eigene Seite oder fremde" gegen eine Adresse, die mit dem
simulierten Typ nichts zu tun hat.

**Der Wert wird geprüft, nicht nur maskiert.** Er kommt aus dem Query-String
eines öffentlichen Endpunkts und landet in einem HTML-Attribut. Maskierung ist
die zweite Verteidigungslinie; die erste ist eine Erlaubnisliste je Typ — UUID,
Slug, Längendeckel, ``http(s)``. Was sie nicht besteht, wird verworfen und
**benannt**: stumm zu schlucken hiesse, den Fehler beim Chatbot suchen zu lassen.
"""

from __future__ import annotations

import json
import re
from html import escape
from typing import NamedTuple
from urllib.parse import urlsplit

#: Woher der Kontext stammt. Macht Demo-Sitzungen in den Auswertungen
#: unterscheidbar — der Detektor schreibt hier z.B. ``url:/themenseite``, die
#: Studio-Vorschau ``studio:vorschau``.
DETECTION_SOURCE = "demo:bedienpult"

#: Query-Parameter, unter denen die Wahl reist.
PARAM_KIND = "kontext"
PARAM_VALUE = "wert"

_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
#: Wie ``SLUG_RE`` im Detektor.
_SLUG = re.compile(r"^[a-z0-9-]{2,80}$", re.I)
#: Wie der Deckel, den der Detektor an ``?q=`` anlegt.
_SEARCH_MIN, _SEARCH_MAX = 2, 200
_URL_MAX = 2000


class ContextKind(NamedTuple):
    """Ein simulierbarer Seitentyp."""

    #: Wert im Query-String.
    id: str
    #: ``page_kind``, wie das Backend ihn einordnet.
    page_kind: str
    #: Schlüssel im Seitenkontext.
    field: str
    label: str
    #: Beschriftung des Wertfeldes.
    feld_label: str
    #: Beispiel — Form, nicht Inhalt (kein echter Datensatz).
    beispiel: str


#: ``subject`` (Fachportal) fehlt bewusst: der Prompt-Block kennt es, aber es
#: löst weder Begrüssung noch Kontext-Aktionen aus. Dieselbe Begründung wie in
#: ``studio/views/preview-embed.ts`` — einen Typ anzubieten, dessen Wirkung
#: ausbleibt, ist ein Versprechen, das die Seite nicht hält.
KINDS: tuple[ContextKind, ...] = (
    ContextKind("topic", "topic", "topic_page_slug", "Themenseite",
                "Slug der Themenseite", "eiszeit"),
    ContextKind("collection", "collection", "collection_id", "Sammlung",
                "Sammlungs-ID (UUID)", "00000000-0000-0000-0000-000000000000"),
    ContextKind("content", "content", "node_id", "Einzelinhalt",
                "Knoten-ID (UUID)", "00000000-0000-0000-0000-000000000000"),
    ContextKind("search", "search", "search_query", "Suche",
                "Suchbegriff der Gastseite", "Dreiecke berechnen"),
    ContextKind("url", "other", "page_url", "Andere Adresse",
                "Vollständige Adresse (http/https)", "https://beispiel.de/artikel"),
)

_BY_ID = {k.id: k for k in KINDS}


def _valid(kind: ContextKind, wert: str) -> bool:
    if kind.field in ("collection_id", "node_id"):
        return bool(_UUID.match(wert))
    if kind.field == "topic_page_slug":
        return bool(_SLUG.match(wert))
    if kind.field == "search_query":
        return _SEARCH_MIN <= len(wert) <= _SEARCH_MAX
    # page_url — nur http(s), und der Hostname muss da sein: ``https:///x``
    # parst durch, hat aber keinen, und „fremde Seite" ohne Host ist sinnlos.
    if len(wert) > _URL_MAX:
        return False
    teile = urlsplit(wert)
    return teile.scheme in ("http", "https") and bool(teile.hostname)


def build_context(kind_id: str, wert: str) -> dict[str, str] | None:
    """Der geprüfte Seitenkontext, oder ``None``.

    ``None`` heisst „nichts mitschicken" — nie ein halber Kontext. Ein
    ``page_kind`` ohne auflösbare ID liesse das Backend nichts finden, die
    Begrüssung bliebe aus, und die Seite sähe aus, als sei die Konfiguration
    kaputt.
    """
    kind = _BY_ID.get(kind_id)
    wert = (wert or "").strip()
    if kind is None or not wert or not _valid(kind, wert):
        return None
    gebaut = {"page_kind": kind.page_kind, kind.field: wert}
    if kind.field == "page_url":
        # Das Backend entscheidet „eigene Seite oder fremde" am Hostnamen.
        gebaut["page_host"] = urlsplit(wert).hostname or ""
    gebaut["detection_source"] = DETECTION_SOURCE
    return gebaut


def element_attributes(kind_id: str, wert: str) -> dict[str, str]:
    """Die Attribute für das ``<boerdi-chat>``-Element — oder nichts.

    **Roh, nicht maskiert.** Maskiert wird dort, wo das Attribut entsteht
    (``widget_demo_html._element``), und nur dort: eine hier vormaskierte
    Zeichenkette zwänge den Bauer, für dieses eine Attribut eine Ausnahme zu
    machen — und Ausnahmen von der Maskierung sind genau die Stellen, an denen
    sie eines Tages ausbleibt. Der Preis wäre sonst doppelte Maskierung.

    Das Widget nimmt ``page-context`` ausdrücklich auch als Zeichenkette
    entgegen (``input<string | Record<string, unknown>>``) und parst selbst.
    """
    gebaut = build_context(kind_id, wert)
    if gebaut is None:
        return {}
    return {
        "page-context": json.dumps(gebaut, ensure_ascii=False),
        "auto-context": "false",
    }


_STYLE = """
  .kontext { margin-block: 1.5rem; border: 1px solid #d1d5db; border-radius: .75rem;
             padding: 1rem 1.25rem; }
  .kontext > h2 { margin-block-start: 0; }
  .kontext-zeile { display: flex; flex-wrap: wrap; gap: .75rem 1.25rem; align-items: end; }
  .kontext label { display: flex; flex-direction: column; gap: .2rem; font-size: .85rem; }
  .kontext select, .kontext input { font: inherit; font-size: .85rem; padding: .3rem;
                                    border: 1px solid #9aa0a6; border-radius: .35rem;
                                    background: Field; color: FieldText; }
  .kontext input { min-inline-size: 22rem; max-inline-size: 100%; }
  .kontext button { font: inherit; font-size: .85rem; padding: .35rem .8rem;
                    border: 1px solid #9aa0a6; border-radius: .35rem;
                    background: Field; color: FieldText; cursor: pointer; }
  .kontext-hinweis { margin-block-end: 0; font-size: .8rem; color: #545a63; }
  .kontext-fehler { margin-block: .75rem 0; font-size: .85rem; color: #8a1c1c;
                    border-inline-start: .25rem solid #8a1c1c; padding-inline-start: .6rem; }
  @media (prefers-color-scheme: dark) {
    .kontext { border-color: #33373b; }
    .kontext-hinweis { color: #9aa0a6; }
    .kontext-fehler { color: #f0a3a3; border-inline-start-color: #f0a3a3; }
  }
"""

_PANEL = """
<section class="kontext" aria-labelledby="kontext-titel">
  <h2 id="kontext-titel">Seitenkontext simulieren</h2>
  <form method="get" class="kontext-zeile">
    <label>
      <span>Ich stehe auf …</span>
      <select name="%(param_kind)s">
        <option value="">nichts Bestimmtem</option>
%(optionen)s
      </select>
    </label>
    <label>
      <span>%(feld_label)s</span>
      <input type="text" name="%(param_value)s" value="%(wert)s"
             placeholder="%(beispiel)s" maxlength="%(max)d">
    </label>
    <button type="submit">Anwenden</button>
  </form>
%(fehler)s
  <p class="kontext-hinweis">
    Die Wahl steht in der Adresse dieser Seite — sie überlebt also das Neuladen
    und lässt sich verschicken. Das Widget bekommt sie beim Aufbau als
    <code>page-context</code>, mit abgeschaltetem <code>auto-context</code>:
    sonst trüge der Detektor die Adresse DIESER Seite bei.
    „Anwenden" lädt die Seite neu — die Schalter im Bedienpult darüber beginnen
    danach wieder bei den Vorgaben dieser Seite.
    Zum Zurücksetzen „nichts Bestimmtem" wählen.
  </p>
</section>
"""

_FEHLER = (
    '  <p class="kontext-fehler" role="alert">'
    "Der Wert passt nicht zu diesem Seitentyp (%(erwartet)s) — es wurde kein "
    "Kontext gesetzt.</p>\n"
)

#: Was je Typ erwartet wird, in einem Halbsatz. Aus derselben Tabelle wie die
#: Prüfung zu bauen wäre eine Ableitung mehr, als der Satz trägt.
_ERWARTUNG = {
    "topic": "2–80 Zeichen, nur Buchstaben, Ziffern und Bindestriche",
    "collection": "eine UUID",
    "content": "eine UUID",
    "search": f"{_SEARCH_MIN}–{_SEARCH_MAX} Zeichen",
    "url": "eine vollständige http(s)-Adresse",
}


def panel(kind_id: str, wert: str) -> str:
    """Das Bedienfeld als HTML-Schnipsel.

    Ein gewöhnliches ``<form method="get">`` — der Browser schickt es selbst an
    dieselbe Adresse. Kein Skript, also auch keines, das etwas ausführen könnte;
    dieselbe Linie wie im Attribut-Pult.
    """
    kind = _BY_ID.get(kind_id)
    abgelehnt = bool(kind and wert.strip() and build_context(kind_id, wert) is None)
    optionen = "\n".join(
        f'        <option value="{k.id}"'
        f'{" selected" if k.id == kind_id else ""}>{escape(k.label)}</option>'
        for k in KINDS
    )
    return _PANEL % {
        "param_kind": PARAM_KIND,
        "param_value": PARAM_VALUE,
        "optionen": optionen,
        "feld_label": escape(kind.feld_label if kind else "Wert"),
        "beispiel": escape(kind.beispiel if kind else "erst einen Seitentyp wählen",
                           quote=True),
        # Der abgelehnte Wert bleibt stehen, damit man ihn korrigieren statt neu
        # tippen kann — und geht deshalb durch die Maskierung.
        "wert": escape(wert or "", quote=True),
        "max": _URL_MAX,
        "fehler": _FEHLER % {"erwartet": _ERWARTUNG[kind_id]} if abgelehnt else "",
    }


def style() -> str:
    """Die Stile des Bedienfeldes — mit ihm zusammen, nicht im Seitenblatt."""
    return _STYLE
