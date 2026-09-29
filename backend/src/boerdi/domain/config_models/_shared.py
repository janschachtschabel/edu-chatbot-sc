"""Shared bases for area models (P2-1). extra='allow' everywhere — the ALT
loaders tolerate unknown keys, and editors must not 422 on additive fields.

Dazu (S2) die zwei Auszeichnungen, mit denen ein Feld dem Studio sagt, dass es
eine Auswahl verdient statt eines leeren Textfeldes. Sie reisen als
Zusatzschlüssel im JSON-Schema mit, das ``GET /api/config/schema/{area}`` ohnehin
ausliefert — das Studio braucht dafür keine eigene Tabelle. Eine solche Tabelle
wäre auch falsch: ``pattern`` heißt in ``01-base/classify-overrides`` eine
Muster-ID und in ``02-domain/guide-rules`` ein Regex. Was ein Feld bedeutet,
weiß nur das Feld.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AreaModel(BaseModel):
    model_config = ConfigDict(extra="allow")


def Choices(*values: str) -> Any:  # noqa: N802 — wie ``Field``: an der Typangabe gelesen
    """Geschlossener Wertevorrat; das Studio zeigt ein Auswahlfeld.

    Bewusst KEIN ``Literal``: ``PUT /api/config/data/{area}`` validiert gegen das
    Modell, ein ``Literal`` würde also jeden Bestandswert außerhalb der Liste ab
    sofort mit 422 abweisen — womöglich denselben, den ein Redakteur gerade
    korrigieren will. Dies ist eine Bedienhilfe, keine Verschärfung. Damit die
    Liste trotzdem nicht lügt, prüft ein Wächter jeden ausgelieferten Seed-Wert
    gegen sie (``tests/test_config_choices_annotations.py``).

    Verwendung::

        mode: Annotated[str, Choices("off", "smart", "always")] = ""
    """
    return Field(json_schema_extra={"x-choices": list(values)})


def Catalog(name: str) -> Any:  # noqa: N802 — s.o.
    """Verweis auf anderswo Angelegtes; das Studio zeigt eine Vorschlagsliste.

    ``name`` ist einer der Kataloge aus ``api/config_choices.CATALOG_NAMES``.
    Offen und nicht geschlossen: ein RAG-Bereich entsteht durch Einlesen, ein
    Muster durch Anlegen — wer den neuen Namen schon kennt, soll ihn tippen
    dürfen, bevor er im Katalog steht.

    An einer Liste gehört die Auszeichnung an den EINTRAG, nicht an die Liste::

        rag_areas: list[Annotated[str, Catalog("rag_areas")]] | None = None
    """
    return Field(json_schema_extra={"x-catalog": name})


def Textarea() -> Any:  # noqa: N802 — s.o.
    """Fließtext: das Studio zeigt eine Textfläche statt einer Zeile (ST-2f).

    Bis ST-2f entschied eine Namensliste im Studio (``MULTILINE_KEYS``) — per
    Hand gemessen, und wo die Messung fehlte, plättete ein einzeiliges Feld
    mehrzeilige Kernregeln (SF-2). Jetzt sagt es das Modell; der Wächter
    ``tests/test_config_textarea_hints.py`` misst jeden langen Seed-Text und
    jede lange Vorgabe dagegen. An einer Liste oder Map gehört der Hinweis an
    den EINTRAG::

        core_rule: Annotated[str, Textarea()] = ""
        when_to_use: list[Annotated[str, Textarea()]] = []
    """
    return Field(json_schema_extra={"x-widget": "textarea"})


def Primary() -> Any:  # noqa: N802 — s.o.
    """Der Inhalt des Bereichs — das Studio stellt ihn vor die übrigen Felder (ST-4).

    Bis ST-4 stand „Grundwerte" bzw. „Kopfangaben" zuerst und offen, der
    Begrüßungstext und die Regeltexte dahinter und zugeklappt. Neben anderen
    Hinweisen zu schreiben, pydantic behält beide::

        greeting: Annotated[str, Textarea(), Primary()] = ""

    Bewusst sparsam: der Wächter ``tests/test_config_primary_hint.py`` führt
    die Liste — ein Hinweis an jedem Feld ordnete nichts mehr.
    """
    return Field(json_schema_extra={"x-primary": True})


def Marker(target: str) -> Any:  # noqa: N802 — s.o.
    """Eine Liste, die EINEN ihrer Einträge hervorhebt; der Wert steht im
    Nachbarfeld ``target`` (ST-2i, Plan 2026-09-26 §9.3).

    ``tour_reply`` muss wörtlich einem Start-Chip gleichen — als Freitext eine
    Stolperfalle, die beim Speichern niemand prüft. Das Studio zeigt deshalb je
    Eintrag ein Radio und schreibt den gewählten Text ins Nachbarfeld. Die
    Auszeichnung gehört an die LISTE (anders als ``Catalog``); der Wächter
    ``tests/test_config_markers.py`` hält fest, dass das Nachbarfeld existiert::

        quick_replies: Annotated[list[str], Marker("tour_reply")] = []
    """
    return Field(json_schema_extra={"x-marker": target})
