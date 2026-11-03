"""Namen der UI-Module, die das Backend gesondert behandelt (Paket U1-c, U1-d1).

Die abgeleiteten Module entstehen ohne Werkzeugaufruf aus der fertigen Antwort; der Inhaltsrahmen
hat sein eigenes Dokument-Werkzeug. Beide nehmen die allgemeinen Modul-Werkzeuge aus
(``ui_module/werkzeuge``). Eigene Datei ohne Importe, damit das Muster-Modell
(``config_models/patterns``) sie prüfen kann, ohne das API-Schema und den Katalog mitzuladen.
Reihenfolge der abgeleiteten = Anzeige-Reihenfolge.
"""

from __future__ import annotations

import re
from typing import Final

INHALTSRAHMEN: Final = "ui_inhaltsrahmen"
TREFFERLISTE: Final = "ui_trefferliste"
LINKBOX: Final = "ui_linkbox"
#: Paket U1-e: Modul-Werkzeug mit Datenquelle; die Direktaktion show_collection_tree baut ihn auch.
THEMENBAUM: Final = "ui_themenbaum"
ENTSCHEIDUNG: Final = "ui_entscheidung"

#: Anzeige-Reihenfolge: erst die WLO-Treffer, dann die Webseiten (wie bisher die Boxen).
ABGELEITETE: Final = (TREFFERLISTE, LINKBOX)


def pruefe_abgeleitete(namen: list[str] | None) -> list[str] | None:
    """Für Validatoren (Muster-Frontmatter, Studio-Eintrag): nur abgeleitete Module."""
    if fremd := [n for n in namen or [] if n not in ABGELEITETE]:
        raise ValueError(f"ui_module: {', '.join(fremd)} ist kein abgeleitetes UI-Modul "
                         f"(erlaubt: {', '.join(ABGELEITETE)})")
    return namen

#: Module, die in ``tools:`` eines Musters nichts bewirken (Review U1-d2, Befund 4): der
#: Inhaltsrahmen hat sein eigenes Dokument-Werkzeug, die abgeleiteten entstehen ohne Aufruf.
OHNE_WIRKUNG_IN_TOOLS: Final = (INHALTSRAHMEN, *ABGELEITETE)


def pruefe_werkzeug_namen(namen: list[str] | None) -> list[str] | None:
    """Für den Muster-Validator: ``tools:`` darf kein Modul nennen, das dort nichts bewirkt.
    Andere unbekannte Namen bleiben erlaubt (fremde Server, spätere Werkzeuge)."""
    if wirkungslos := [n for n in namen or [] if n in OHNE_WIRKUNG_IN_TOOLS]:
        raise ValueError(
            f"tools: {', '.join(wirkungslos)} wirkt hier nicht — der Inhaltsrahmen ist immer "
            f"angeboten, abgeleitete Module wählt ui_module (erlaubt als Modul-Werkzeug sind nur "
            f"Module mit agent: true, z. B. {ENTSCHEIDUNG})")
    return namen


#: Paket U1-d2 (U-F4): Unter diesem Schlüssel stehen in der Muster-Ausgabe (``phase3_modulate``)
#: die UI-Module, die ein Muster in ``tools:`` nennt — getrennt von den MCP-Werkzeugen, weil
#: Pflicht-Prüfung (A1), Kuratier-Absicht und Medientyp-Strip ``tools`` als MCP-Liste lesen.
UI_WERKZEUGE_KEY: Final = "ui_werkzeuge"


#: Paket U1-f (Plan §16, F-4): Module, die das Studio nicht abschalten kann. Der Inhaltsrahmen
#: trägt Systemarten (``x-nur-system``: Volltext, Schreib-Vorschau vor einer Freigabe), sein
#: Dokument-Werkzeug ist bewusst nicht sperrbar, und seine Anzeige steuert
#: ``display_rules.inline_documents.enabled``.
FEST: Final = (INHALTSRAHMEN,)

#: Form eines Modulnamens wie im Manifest-Schema (``name``).
_NAME_FORM: Final = r"^ui_[a-z0-9_]{2,40}$"


def pruefe_schalter_namen(namen: list[str]) -> list[str]:
    """Für den Validator der Studio-Schalter (``display_rules.ui_module``): Form, keine Doppelten,
    kein festes Modul. Unbekannte, aber gültig geformte Namen bleiben erlaubt — ein später
    entferntes Modul soll einen gespeicherten Stand nicht unspeicherbar machen."""
    if falsch := [n for n in namen if not re.fullmatch(_NAME_FORM, n)]:
        raise ValueError(f"ui_module: {', '.join(repr(n) for n in falsch)} ist kein Modulname "
                         f"(Form {_NAME_FORM})")
    if doppelt := sorted({n for n in namen if namen.count(n) > 1}):
        raise ValueError(f"ui_module: {', '.join(doppelt)} steht doppelt")
    if fest := [n for n in namen if n in FEST]:
        raise ValueError(f"ui_module: {', '.join(fest)} ist fest und lässt sich nicht abschalten "
                         f"(die Anzeige steuert display_rules.inline_documents.enabled)")
    return namen
